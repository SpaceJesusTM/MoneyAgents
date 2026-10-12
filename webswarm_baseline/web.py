"""Web access: keyless search, guarded page fetching, text extraction, and record/replay.

Retrieved content is untrusted data. This module only returns text; it never executes anything
from a page, and it refuses non-public network destinations (SSRF guard) on every redirect hop.

Record/replay ("cassettes") exists so experiment arms can be compared on the same web responses:
each search and fetch is stored with the latency it originally took, and a replay sleeps for that
latency, so wall-clock comparisons stay fair whichever arm happened to record the entry.
"""
from __future__ import annotations

import hashlib
import io
import ipaddress
import json
import re
import select
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlsplit

import requests

from .config import SwarmConfig
from .runtime import Budget, Tracer
from .textutil import domain_of, norm

USER_AGENT = "MoneyAgents-WebSwarm-Research/0.1 (local research prototype; python-requests)"
ALLOWED_TYPES = ("text/html", "application/xhtml+xml", "text/plain", "application/pdf",
                 "application/json", "application/xml", "text/xml")
MAX_TEXT_CHARS = 80_000
MAX_REDIRECTS = 5
PDF_PARSE_SECONDS = 15.0      # oversize_policy="fail": stop parsing a PDF after this long (checked between pages)
LEGACY_PAGE_CAP = 3_000_000   # recordings made before truncation was marked were all cut at this size


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    date: str = ""


class SearchResults(list):
    """Search results that can also say the search itself failed. An empty list with `error` set
    means "we could not ask", which is not the same as "we asked and nothing came back"."""
    error: str = ""
    kind: str = ""      # timeout | network | rate_limited | provider | internal | unavailable | replay_miss


class SearchFailure(Exception):
    """A search that got no valid answer. Always transient from the point of view of a recording:
    nothing about it says what the web contains, so it must never be stored and replayed."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}"[:300])
        self.kind, self.detail = kind, detail


# ---- local network profile ------------------------------------------------------------------------

_NET: dict = {}


def ipv6_route() -> bool:
    """Does this machine have a route to the IPv6 internet? Checked once, without sending anything:
    connecting a UDP socket only consults the routing table."""
    if "v6" not in _NET:
        try:
            with socket.socket(socket.AF_INET6, socket.SOCK_DGRAM) as s:
                s.connect(("2001:4860:4860::8888", 53))
            _NET["v6"] = True
        except OSError:
            _NET["v6"] = False
    return _NET["v6"]


def gai_family() -> int:
    """Address family for name lookups. Without an IPv6 route an AAAA answer cannot be used, and on a
    network whose resolver drops AAAA queries every dual-stack lookup waits out a timeout (measured
    here: 2-5 s per connection). So: no IPv6 route, IPv4-only lookups."""
    return socket.AF_UNSPEC if ipv6_route() else socket.AF_INET


def prefer_usable_addresses() -> str:
    """Apply `gai_family()` to this process's `requests` connections. Returns what was chosen."""
    if gai_family() == socket.AF_INET:
        import urllib3.util.connection as conn
        conn.allowed_gai_family = lambda: socket.AF_INET
        return "ipv4 only (no IPv6 route)"
    return "system default"


class Ipv4Tunnel:
    """A CONNECT proxy on 127.0.0.1 that resolves names over IPv4 only.

    The `ddgs` search client does its own name resolution and has no address-family switch, so on a
    network with broken AAAA lookups each of its requests burns its whole timeout. It does accept a
    proxy. This one only opens TLS tunnels (port 443) to hosts the SSRF guard accepts, and relays
    bytes; it never sees request contents."""

    def __init__(self):
        self._sock = socket.socket()
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(32)
        self.url = f"http://127.0.0.1:{self._sock.getsockname()[1]}"
        threading.Thread(target=self._serve, name="ipv4-tunnel", daemon=True).start()

    def close(self) -> None:
        try:
            self._sock.close()
        except OSError:
            pass

    def _serve(self) -> None:
        while True:
            try:
                client, _ = self._sock.accept()
            except OSError:
                return
            threading.Thread(target=self._handle, args=(client,), daemon=True).start()

    def _handle(self, client: socket.socket) -> None:
        up = None
        try:
            client.settimeout(10)
            head = b""
            while b"\r\n\r\n" not in head and len(head) < 8192:
                chunk = client.recv(4096)
                if not chunk:
                    return
                head += chunk
            parts = head.split(b"\r\n", 1)[0].decode("latin-1").split(" ")
            host, _, port = (parts[1] if len(parts) > 1 else "").rpartition(":")
            if parts[0] != "CONNECT" or port != "443" or validate_url(f"https://{host}/"):
                client.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                return
            addr = socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)[0][4]
            up = socket.create_connection(addr, timeout=8)
            client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            client.settimeout(None)
            up.settimeout(None)
            while True:
                ready, _, _ = select.select([client, up], [], [], 30)
                if not ready:
                    return
                for sock in ready:
                    data = sock.recv(65536)
                    if not data:
                        return
                    (up if sock is client else client).sendall(data)
        except (OSError, ValueError, IndexError):
            return
        finally:
            for sock in (client, up):
                try:
                    if sock is not None:
                        sock.close()
                except OSError:
                    pass


@dataclass
class Page:
    url: str
    final_url: str = ""
    status: int = 0
    content_type: str = ""
    title: str = ""
    text: str = ""
    error: str = ""
    nbytes: int = 0
    truncated: bool = False   # the body was cut off by the size or time limit, or the connection dropped
    partial: str = ""         # e.g. "read 15 of 212 PDF pages": the text is the front of a longer document

    @property
    def ok(self) -> bool:
        return not self.error and len(self.text) >= 200


# ---- SSRF guard ---------------------------------------------------------------------------------

def validate_url(url: str) -> str | None:
    """Return a reason string if the URL must not be fetched, else None."""
    try:
        p = urlsplit(url)
    except ValueError:
        return "malformed URL"
    if p.scheme not in ("http", "https"):
        return f"scheme {p.scheme!r} not allowed"
    if p.username or p.password:
        return "credentials in URL"
    host = p.hostname
    if not host:
        return "no host"
    try:
        port = p.port
    except ValueError:
        return "bad port"
    if port not in (None, 80, 443):
        return f"port {port} not allowed"
    try:
        infos = socket.getaddrinfo(host, port or (443 if p.scheme == "https" else 80),
                                   family=gai_family(), proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return "DNS resolution failed"
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0].split("%")[0])
        except ValueError:
            return "unparseable address"
        mapped = getattr(ip, "ipv4_mapped", None)
        if mapped is not None:
            ip = mapped
        if not ip.is_global:
            return f"non-public address {ip}"
    return None


# ---- content extraction -------------------------------------------------------------------------

_TAG = re.compile(r"<[^>]+>")
_DROP = re.compile(r"<(script|style|noscript|svg|nav|footer|header|form)\b.*?</\1>", re.S | re.I)


def html_to_text(html: str, url: str = "") -> tuple[str, str]:
    """(title, main text). trafilatura first; crude tag stripping as the fallback."""
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if m:
        title = re.sub(r"\s+", " ", _TAG.sub("", m.group(1))).strip()[:200]
    text = ""
    try:
        import trafilatura  # imported lazily: it is slow to import and tests do not need it
        text = trafilatura.extract(html, url=url or None, include_comments=False,
                                   include_tables=True, favor_recall=True) or ""
    except Exception:  # noqa: BLE001
        text = ""
    if len(text) < 200:
        import html as htmllib
        stripped = _TAG.sub(" ", _DROP.sub(" ", html))
        stripped = re.sub(r"[ \t\r\f\v]+", " ", htmllib.unescape(stripped))
        stripped = re.sub(r"\s*\n\s*", "\n", stripped).strip()
        if len(stripped) > len(text):
            text = stripped
    return title, text[:MAX_TEXT_CHARS]


def pdf_extract(data: bytes, max_pages: int = 15, seconds: float | None = None) -> dict:
    """Text of the first `max_pages` pages, plus how much of the document that was.

    Bounded three ways: pages, characters (MAX_TEXT_CHARS) and, when `seconds` is given, parse time
    (checked between pages; one pathological page cannot be interrupted). pypdf applies its own
    limits to decompressed stream sizes. A file that cannot be parsed yields no text and an error."""
    out = {"text": "", "pages": 0, "pages_read": 0, "error": ""}
    try:
        import logging
        from pypdf import PdfReader
        logging.getLogger("pypdf").setLevel(logging.ERROR)   # font-table warnings are noise here
        reader = PdfReader(io.BytesIO(data))
        out["pages"] = len(reader.pages)
        parts, t0 = [], time.perf_counter()
        for page in reader.pages[:max_pages]:
            parts.append(page.extract_text() or "")
            out["pages_read"] += 1
            if sum(len(x) for x in parts) > MAX_TEXT_CHARS:
                break
            if seconds is not None and time.perf_counter() - t0 > seconds:
                out["error"] = "parse time limit reached"
                break
        out["text"] = "\n".join(parts)[:MAX_TEXT_CHARS]
    except Exception as e:  # noqa: BLE001
        out.update(text="", error=f"unreadable PDF ({type(e).__name__})")
    return out


def pdf_to_text(data: bytes, max_pages: int = 15) -> str:
    return pdf_extract(data, max_pages)["text"]


@dataclass
class _Got:
    """Result of one guarded GET."""
    status: int = 0
    url: str = ""
    ctype: str = ""
    body: bytes = b""
    err: str = ""
    truncated: str = ""          # "" | "size" | "time" | "connection": why the body is incomplete
    declared: int | None = None  # Content-Length, when the server sent one
    cap: int = 0                 # the byte limit that applied to this response


# ---- search providers ---------------------------------------------------------------------------

class DDGSProvider:
    """Keyless metasearch via the `ddgs` package. Swappable: anything with `.search(q, n)` works.

    `search` returns a list (possibly empty: the engines answered and had nothing) or raises
    `SearchFailure` (no valid answer: timeout, network, rate limit, provider or internal error)."""
    name = "ddgs"

    def __init__(self, timeout: int = 10, deadline: float = 25.0):
        self.timeout, self.deadline = timeout, deadline
        self._tunnel: Ipv4Tunnel | None = None
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ddgs")

    def _proxy(self) -> str | None:
        if ipv6_route():
            return None
        if self._tunnel is None:
            self._tunnel = Ipv4Tunnel()
        return self._tunnel.url

    def _ask(self, query: str, n: int) -> list[dict]:
        from ddgs import DDGS
        return DDGS(timeout=self.timeout, proxy=self._proxy()).text(query, max_results=n, region="us-en")

    def search(self, query: str, n: int) -> list[dict]:
        t0 = time.perf_counter()
        future = self._pool.submit(self._ask, query, n)
        try:
            rows = future.result(timeout=self.deadline)       # the library has no overall time limit of its own
        except FutureTimeout:
            raise SearchFailure("timeout", f"no answer within {self.deadline:.0f} s") from None
        except Exception as e:  # noqa: BLE001 - classified below; the caller decides what to do with it
            outcome = classify_ddgs_error(e, time.perf_counter() - t0, self.timeout)
            if isinstance(outcome, _Empty):
                return []                                     # the engines answered and had nothing
            raise outcome from None
        return [{"title": r.get("title") or "", "url": r.get("href") or "",
                 "snippet": r.get("body") or "", "date": r.get("date") or ""}
                for r in rows if r.get("href")]


def classify_ddgs_error(e: Exception, elapsed: float, timeout: float):
    """Turn a `ddgs` exception into an empty result (returned) or a `SearchFailure` (returned, to be
    raised). The library reports "No results found" both when the engines had nothing and when every
    engine timed out or served a rate-limit page; only the first is an answer."""
    name, text = type(e).__name__, str(e)
    if name == "RatelimitException" or re.search(r"\b(?:202|429)\b|ratelimit|rate limit|too many requests", text, re.I):
        return SearchFailure("rate_limited", text)
    if name == "TimeoutException" or re.search(r"timed? ?out", text, re.I):
        return SearchFailure("timeout", text)
    if "no results" in text.lower():
        if elapsed >= 0.8 * timeout:
            return SearchFailure("timeout", f"'no results' after {elapsed:.0f} s: the engines did not answer in time")
        return _Empty()
    if re.search(r"dns|resolve|connect|network|unreachable|ssl|certificate", text, re.I):
        return SearchFailure("network", text)
    return SearchFailure("provider" if name == "DDGSException" else "internal", f"{name}: {text}")


class _Empty(Exception):
    """Marker: the provider answered and had no results."""


PROVIDERS = {"ddgs": DDGSProvider}
CANARY_QUERY = "Apple Inc investor relations"   # a query that always has results, used to test the provider
CANARY_TTL = 120.0                              # seconds a canary verdict is trusted
TRANSIENT_FETCH = ("Timeout", "ConnectionError", "ConnectTimeout", "ReadTimeout", "SSLError", "ChunkedEncodingError",
                   "ProxyError", "download did not finish", "connection dropped")


# ---- record / replay ----------------------------------------------------------------------------

class Cassette:
    def __init__(self, directory: str):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, kind: str, key: str) -> Path:
        return self.dir / f"{kind}_{hashlib.sha1(key.encode()).hexdigest()[:20]}.json"

    def get(self, kind: str, key: str) -> dict | None:
        p = self._path(kind, key)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def put(self, kind: str, key: str, response: dict, latency: float) -> None:
        entry = {"kind": kind, "key": key, "latency": round(latency, 3),
                 "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "response": response}
        with self._lock:
            self._path(kind, key).write_text(json.dumps(entry, ensure_ascii=False))


# ---- client -------------------------------------------------------------------------------------

class WebClient:
    def __init__(self, cfg: SwarmConfig, tracer: Tracer, budget: Budget, provider=None, fetcher=None):
        if cfg.web_mode not in ("live", "record", "replay", "replay_or_record"):
            raise ValueError(f"unknown web_mode {cfg.web_mode!r}")
        if cfg.web_mode != "live" and not cfg.cassette:
            raise ValueError(f"web_mode={cfg.web_mode} needs a cassette directory")
        self.cfg, self.tracer, self.budget = cfg, tracer, budget
        if provider is None:
            provider = PROVIDERS[cfg.search_provider]()
            if hasattr(provider, "deadline"):
                provider.deadline = cfg.search_deadline
        self.provider = provider
        self._fetcher = fetcher  # test hook: fn(url) -> response dict
        self._fail_streak = 0            # searches in a row that got no valid answer
        self._open_until = 0.0           # monotonic time until which search is treated as unavailable
        self._canary: tuple[float, bool] | None = None
        if cfg.web_mode != "replay":
            tracer.event("net_profile", None, ipv6_route=ipv6_route(), name_lookups=prefer_usable_addresses())
        self.cassette = Cassette(cfg.cassette) if cfg.cassette else None
        self._sem = threading.Semaphore(max(1, cfg.web_concurrency))
        self._lock = threading.Lock()
        self._memo: dict[tuple[str, str], dict] = {}
        self._inflight: dict[tuple[str, str], threading.Event] = {}
        self._search_lock = threading.Lock()
        self._last_search = 0.0
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT,
                                     "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.5",
                                     "Accept-Language": "en-US,en;q=0.8"})

    # ---- public ----

    def search(self, query: str, node=None) -> SearchResults:
        """Results for `query`. If the search could not be answered at all, the list is empty and its
        `error` / `kind` say so; callers must not read that as "nothing exists"."""
        query = re.sub(r"\s+", " ", query or "").strip()[:300]
        out = SearchResults()
        if not query:
            return out
        resp = self._call("search", norm(query), lambda: self._live_search(query), node, label=query)
        out.extend(SearchResult(**r) for r in resp.get("results", []))
        if resp.get("error"):
            out.error = str(resp["error"])
            out.kind = resp.get("error_kind") or ("replay_miss" if "not in cassette" in out.error else "recorded_failure")
        return out

    def fetch(self, url: str, node=None) -> Page:
        url = (url or "").strip()
        key, on_replay = url, None
        if self.cfg.oversize_policy == "fail" and self.cassette and self.cfg.web_mode in ("replay", "replay_or_record"):
            key, on_replay = self._truncated_recording(url)
        resp = self._call("fetch", key, lambda: self._live_fetch(url), node, label=url, on_replay=on_replay)
        return Page(**{k: resp.get(k, v) for k, v in asdict(Page(url=url)).items()})

    def _cap_for(self, ctype: str, url: str) -> int:
        """Byte limit for a response: PDFs may have their own, larger one (config max_pdf_bytes)."""
        is_pdf = "application/pdf" in (ctype or "").lower() or urlsplit(url).path.lower().endswith(".pdf")
        return max(self.cfg.max_page_bytes, self.cfg.max_pdf_bytes) if is_pdf else self.cfg.max_page_bytes

    def _truncated_recording(self, url: str):
        """oversize_policy="fail" meeting a recording that holds a cut-off body.

        Recordings are keyed by URL, so replaying one would hand back the truncated body whatever
        the limit is now. If a larger limit applies today, the page is looked up (and, when
        recording is allowed, fetched again) under a second key that names the limit; the original
        recording is never overwritten. Otherwise the replay is turned into the explicit failure
        a live fetch would produce."""
        entry = self.cassette.get("fetch", url)
        r = (entry or {}).get("response") or {}
        cut = r.get("truncated") or ("truncated" not in r and (r.get("nbytes") or 0) == LEGACY_PAGE_CAP)
        if not entry or not cut:
            return url, None
        cap, had = self._cap_for(r.get("content_type", ""), url), r.get("nbytes") or 0
        if cap > had:
            return f"{url}#cap={cap}", None

        def explicit(resp: dict) -> dict:
            return {**resp, "truncated": True, "text": "", "title": "",
                    "error": f"too large: the recorded copy was cut off at {had:,} bytes (limit {cap:,}); nothing parsed"}
        return url, explicit

    # ---- shared call path: run memo -> budget -> cassette -> live ----

    def _call(self, kind: str, key: str, live, node, label: str, budgeted: bool = True, on_replay=None) -> dict:
        """`budgeted=False` is for robots.txt lookups: they run inside a page fetch, so they must not
        count against the page budget or wait for a second concurrency slot (that would deadlock)."""
        nid = getattr(node, "id", None)
        mkey = (kind, key)
        while True:
            with self._lock:
                if mkey in self._memo:
                    self.tracer.event("web_call", nid, kind=kind, target=label[:200], source="run_cache",
                                      secs=0.0, ok=not self._memo[mkey].get("error"))
                    return self._memo[mkey]
                waiter = self._inflight.get(mkey)
                if waiter is None:
                    self._inflight[mkey] = threading.Event()
                    break
            waiter.wait(timeout=60)  # another agent is already retrieving the same thing

        resp, source, secs = {"error": "internal error"}, "live", 0.0
        try:
            if budgeted:
                self.budget.take_web()
            mode = self.cfg.web_mode
            entry = self.cassette.get(kind, key) if (self.cassette and mode in ("replay", "replay_or_record")) else None
            if entry is not None and kind == "search" and entry["response"].get("error") and mode == "replay_or_record":
                entry = None      # a failure recorded by an older version is not an answer: ask again
            t0 = time.perf_counter()
            if entry is not None:
                resp, source = entry["response"], "cassette"
                if on_replay is not None:
                    resp = on_replay(resp)
                if self.cfg.replay_latency:
                    time.sleep(min(float(entry.get("latency", 0.0)), 30.0))
            elif mode == "replay":
                resp, source = {"error": "not in cassette (replay mode)"}, "cassette_miss"
            else:
                if budgeted:
                    self._sem.acquire()
                try:
                    t0 = time.perf_counter()
                    try:
                        resp = live()
                    except Exception as e:  # noqa: BLE001 - network errors become data, not crashes
                        resp = {"error": f"{type(e).__name__}: {e}"[:300]}
                finally:
                    if budgeted:
                        self._sem.release()
                # A request that got no valid answer (timeout, dropped connection, rate limit) says nothing
                # about the web, so it is never recorded: a recorded timeout would be replayed to every
                # later run as if it were the page or the result list. An empty result list, an HTTP 403
                # or a page that is too large ARE answers, and are recorded.
                unanswered = bool(resp.get("transient")) or (kind == "search" and bool(resp.get("error")))
                if self.cassette and mode in ("record", "replay_or_record") and not unanswered:
                    self.cassette.put(kind, key, {k: v for k, v in resp.items() if k != "attempts"},
                                      time.perf_counter() - t0)
            secs = time.perf_counter() - t0
            if not (source == "live" and resp.get("transient")):     # a transient failure may be retried later
                with self._lock:
                    self._memo[mkey] = resp
            return resp
        except Exception as e:
            resp, source = {"error": f"{type(e).__name__}: {e}"[:200]}, "refused"
            raise
        finally:
            extra = {"n": len(resp.get("results", []))} if kind == "search" else \
                    {"status": resp.get("status"), "chars": len(resp.get("text") or "")} if kind == "fetch" else {}
            if kind == "fetch":      # only present when true, so ordinary fetch events look as they always did
                extra.update({k: resp[k] for k in ("truncated", "partial") if resp.get(k)})
            extra.update({k: resp[k] for k in ("error_kind", "transient", "attempts", "provider") if resp.get(k)})
            self.tracer.event("web_call", nid, kind=kind, target=label[:200], source=source,
                              secs=round(secs, 3), ok=not resp.get("error"),
                              error=(resp.get("error") or None), **extra)
            with self._lock:
                ev = self._inflight.pop(mkey, None)
            if ev:
                ev.set()

    # ---- live implementations ----

    def _live_search(self, query: str) -> dict:
        """Ask the provider, with bounded retries. Returns {"results": [...]} when the provider answered
        (an empty list is an answer) or {"error", "error_kind", "transient": True} when it did not."""
        if time.monotonic() < self._open_until:
            return {"error": f"search unavailable: {self.cfg.search_breaker} searches in a row got no answer; "
                             f"not asking again for up to {self.cfg.search_cooldown:.0f} s",
                    "error_kind": "unavailable", "transient": True}
        failure, attempts = SearchFailure("internal", "no attempt made"), 0
        for attempts in range(1, max(1, self.cfg.search_attempts) + 1):
            with self._search_lock:  # be polite to the provider: space searches out
                wait = self.cfg.min_search_interval - (time.perf_counter() - self._last_search)
                if wait > 0:
                    time.sleep(wait)
                self._last_search = time.perf_counter()
            try:
                rows = self.provider.search(query, self.cfg.search_results)
            except SearchFailure as f:
                failure = f
                if f.kind == "rate_limited":
                    time.sleep(min(2.0 * attempts, 5.0))      # asking again at once only makes this worse
                continue
            except Exception as e:  # noqa: BLE001 - a provider bug is a failed search, not a crashed run
                failure = SearchFailure("internal", f"{type(e).__name__}: {e}")
                break
            if not rows and not self._provider_answers():
                failure = SearchFailure("rate_limited", "empty result, and a control query that always has results "
                                                        "also came back empty: the provider is not answering")
                break
            self._fail_streak = 0
            seen, out = set(), []
            for r in rows:
                if r["url"] in seen or validate_scheme(r["url"]):
                    continue
                seen.add(r["url"])
                out.append({"title": r["title"][:200], "url": r["url"], "snippet": r["snippet"][:400],
                            "date": str(r.get("date") or "")[:32]})
            return {"results": out, "attempts": attempts}
        self._fail_streak += 1
        if self._fail_streak >= self.cfg.search_breaker:
            self._open_until = time.monotonic() + self.cfg.search_cooldown
            self._fail_streak = 0
            self.tracer.event("search_unavailable", None, after=self.cfg.search_breaker,
                              cooldown=self.cfg.search_cooldown, last_kind=failure.kind)
        return {"error": f"search failed ({failure.kind}): {failure.detail}"[:300], "error_kind": failure.kind,
                "transient": True, "attempts": attempts}

    def _provider_answers(self) -> bool:
        """An empty result is only an answer if the provider is answering. `ddgs` reports "no results"
        when its engines serve rate-limit pages, so on an empty result a query that always has results
        is tried (at most once every CANARY_TTL seconds)."""
        now = time.monotonic()
        if self._canary is None or now - self._canary[0] > CANARY_TTL:
            try:
                ok = bool(self.provider.search(CANARY_QUERY, 3))
            except Exception:  # noqa: BLE001
                ok = False
            self._canary = (now, ok)
            self.tracer.event("search_canary", None, ok=ok)
        return self._canary[1]

    def _live_fetch(self, url: str) -> dict:
        if self._fetcher is not None:
            return self._fetcher(url)
        if self.cfg.respect_robots and not self._robots_allow(url):
            return {"url": url, "error": "disallowed by robots.txt"}
        strict = self.cfg.oversize_policy == "fail"
        got = self._guarded_get(url, self.cfg.fetch_timeout, self.cfg.max_page_bytes, self.cfg.max_pdf_bytes, strict)
        status, final, ctype, body, err = got.status, got.url, got.ctype, got.body, got.err
        base = {"url": url, "final_url": final, "status": status, "content_type": ctype, "nbytes": len(body)}
        if got.truncated:
            base["truncated"] = True
        if err:
            if any(t in err for t in TRANSIENT_FETCH):
                return {**base, "error": err, "error_kind": "network", "transient": True}
            return {**base, "error": err}
        if status >= 400:
            return {**base, "error": f"HTTP {status}"}
        main = ctype.split(";")[0].strip().lower()
        if main and not any(main == t for t in ALLOWED_TYPES):
            return {**base, "error": f"content type {main!r} not supported"}
        if strict and got.truncated:
            cut = {"transient": True, "error_kind": "network"} if got.truncated in ("time", "connection") else {}
            return {**base, "error": _incomplete(got), **cut}
        if main == "application/pdf" or body[:5] == b"%PDF-":
            pdf = pdf_extract(body, self.cfg.pdf_max_pages, PDF_PARSE_SECONDS if strict else None)
            text, title = pdf["text"], ""
            if pdf["pages"]:
                base.update(pdf_pages=pdf["pages"], pdf_pages_read=pdf["pages_read"])
                if pdf["pages_read"] < pdf["pages"]:
                    base["partial"] = f"read {pdf['pages_read']} of {pdf['pages']} PDF pages"
            if strict and pdf["error"] and len(text) < 200:
                return {**base, "error": pdf["error"]}
        else:
            enc = "utf-8"
            m = re.search(r"charset=([\w\-]+)", ctype, re.I)
            if m:
                enc = m.group(1)
            title, text = html_to_text(body.decode(enc, errors="replace"), final or url)
        if len(text) < 200:
            return {**base, "title": title, "text": text, "error": "no extractable text (script-rendered or empty page)"}
        return {**base, "title": title, "text": text}

    def _guarded_get(self, url: str, timeout: float, max_bytes: int, pdf_bytes: int = 0,
                     strict: bool = False) -> _Got:
        """GET with the SSRF guard applied to every hop and a hard cap on body size and time.

        The body is never read past the cap. Whether it was cut short is reported in `truncated`;
        with `strict`, a response whose declared length already exceeds the cap is refused before
        any of its body is downloaded."""
        deadline = time.perf_counter() + timeout * 2
        for _ in range(MAX_REDIRECTS + 1):
            reason = validate_url(url)
            if reason:
                return _Got(url=url, err=f"blocked: {reason}")
            try:
                r = self.session.get(url, timeout=(5, timeout), stream=True, allow_redirects=False)
            except requests.RequestException as e:
                return _Got(url=url, err=f"{type(e).__name__}")
            try:
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
                    url = urljoin(url, r.headers["Location"])
                    continue
                ctype = r.headers.get("Content-Type", "")
                is_pdf = "application/pdf" in ctype.lower() or urlsplit(url).path.lower().endswith(".pdf")
                cap = max(max_bytes, pdf_bytes) if (is_pdf and pdf_bytes) else max_bytes
                length = r.headers.get("Content-Length", "")
                got = _Got(r.status_code, url, ctype, cap=cap, declared=int(length) if length.isdigit() else None)
                if strict and got.declared is not None and got.declared > cap and r.status_code < 400:
                    got.truncated = "size"
                    return got
                chunks, total = [], 0
                try:
                    stream = r.iter_content(65536)
                    for chunk in stream:
                        chunks.append(chunk)
                        total += len(chunk)
                        if total >= cap:
                            # more to come? known from the declared length, from having overshot the cap,
                            # or (exactly at the cap, length unknown) by looking for one more chunk
                            more = got.declared > cap if got.declared is not None else \
                                (total > cap or bool(next(stream, b"")))
                            got.truncated = "size" if more else ""
                            break
                        if time.perf_counter() > deadline:
                            if got.declared is None or total < got.declared:
                                got.truncated = "time"
                            break
                except requests.RequestException as e:
                    if not chunks:
                        got.err = f"{type(e).__name__}"
                        return got
                    got.truncated = got.truncated or "connection"
                got.body = b"".join(chunks)[:cap]
                return got
            finally:
                r.close()
        return _Got(url=url, err="too many redirects")

    def _robots_allow(self, url: str) -> bool:
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        with self._lock:
            known = origin in self._robots
            rp = self._robots.get(origin)
        if not known:
            def live():
                got = self._guarded_get(origin + "/robots.txt", 4.0, 200_000)
                ok = not got.err and got.status == 200
                return {"status": got.status, "text": got.body.decode("utf-8", "replace") if ok else "",
                        "error": got.err}
            try:
                resp = self._call("robots", origin, live, None, label=origin + "/robots.txt", budgeted=False)
            except Exception:  # noqa: BLE001
                resp = {"text": ""}
            rp = None
            if resp.get("text"):
                rp = robotparser.RobotFileParser()
                rp.parse(resp["text"].splitlines())
            with self._lock:
                self._robots[origin] = rp
        if rp is None:
            return True  # no readable robots.txt: allowed
        return rp.can_fetch(USER_AGENT, url)


def _incomplete(got: _Got) -> str:
    """The explicit error for a body that did not arrive whole (oversize_policy="fail")."""
    if got.truncated == "size":
        size = f"{got.declared:,} bytes declared" if got.declared is not None else f"more than {got.cap:,} bytes"
        return f"too large: {size}, limit {got.cap:,}; nothing parsed"
    if got.truncated == "time":
        return "download did not finish within the time limit; the partial content was discarded"
    return "connection dropped during download; the partial content was discarded"


def validate_scheme(url: str) -> str | None:
    """Cheap pre-filter for search results (no DNS): only http(s) links are kept."""
    try:
        return None if urlsplit(url).scheme in ("http", "https") else "scheme"
    except ValueError:
        return "malformed"


__all__ = ["WebClient", "SearchResult", "SearchResults", "SearchFailure", "Page", "Cassette", "validate_url",
           "html_to_text", "pdf_to_text", "pdf_extract", "domain_of", "USER_AGENT", "ipv6_route", "Ipv4Tunnel"]
