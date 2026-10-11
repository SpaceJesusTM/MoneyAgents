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
import socket
import threading
import time
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


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    date: str = ""


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
                                   proto=socket.IPPROTO_TCP)
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


def pdf_to_text(data: bytes, max_pages: int = 15) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        out = []
        for page in reader.pages[:max_pages]:
            out.append(page.extract_text() or "")
            if sum(len(x) for x in out) > MAX_TEXT_CHARS:
                break
        return "\n".join(out)[:MAX_TEXT_CHARS]
    except Exception:  # noqa: BLE001
        return ""


# ---- search providers ---------------------------------------------------------------------------

class DDGSProvider:
    """Keyless metasearch via the `ddgs` package. Swappable: anything with `.search(q, n)` works."""
    name = "ddgs"

    def search(self, query: str, n: int) -> list[dict]:
        from ddgs import DDGS
        last: Exception | None = None
        for attempt in range(2):
            try:
                rows = DDGS(timeout=10).text(query, max_results=n, region="us-en")
                return [{"title": r.get("title") or "", "url": r.get("href") or "",
                         "snippet": r.get("body") or "", "date": r.get("date") or ""}
                        for r in rows if r.get("href")]
            except Exception as e:  # noqa: BLE001
                last = e
                if "no results" in str(e).lower():
                    return []
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"search failed: {type(last).__name__}: {last}")


PROVIDERS = {"ddgs": DDGSProvider}


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
        self.provider = provider or PROVIDERS[cfg.search_provider]()
        self._fetcher = fetcher  # test hook: fn(url) -> response dict
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

    def search(self, query: str, node=None) -> list[SearchResult]:
        query = re.sub(r"\s+", " ", query or "").strip()[:300]
        if not query:
            return []
        resp = self._call("search", norm(query), lambda: self._live_search(query), node, label=query)
        return [SearchResult(**r) for r in resp.get("results", [])]

    def fetch(self, url: str, node=None) -> Page:
        url = (url or "").strip()
        resp = self._call("fetch", url, lambda: self._live_fetch(url), node, label=url)
        return Page(**{k: resp.get(k, v) for k, v in asdict(Page(url=url)).items()})

    # ---- shared call path: run memo -> budget -> cassette -> live ----

    def _call(self, kind: str, key: str, live, node, label: str, budgeted: bool = True) -> dict:
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
            t0 = time.perf_counter()
            if entry is not None:
                resp, source = entry["response"], "cassette"
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
                if self.cassette and mode in ("record", "replay_or_record"):
                    self.cassette.put(kind, key, resp, time.perf_counter() - t0)
            secs = time.perf_counter() - t0
            with self._lock:
                self._memo[mkey] = resp
            return resp
        except Exception as e:
            resp, source = {"error": f"{type(e).__name__}: {e}"[:200]}, "refused"
            raise
        finally:
            extra = {"n": len(resp.get("results", []))} if kind == "search" else \
                    {"status": resp.get("status"), "chars": len(resp.get("text") or "")} if kind == "fetch" else {}
            self.tracer.event("web_call", nid, kind=kind, target=label[:200], source=source,
                              secs=round(secs, 3), ok=not resp.get("error"),
                              error=(resp.get("error") or None), **extra)
            with self._lock:
                ev = self._inflight.pop(mkey, None)
            if ev:
                ev.set()

    # ---- live implementations ----

    def _live_search(self, query: str) -> dict:
        with self._search_lock:  # be polite to the provider: space searches out
            wait = self.cfg.min_search_interval - (time.perf_counter() - self._last_search)
            if wait > 0:
                time.sleep(wait)
            self._last_search = time.perf_counter()
        rows = self.provider.search(query, self.cfg.search_results)
        seen, out = set(), []
        for r in rows:
            if r["url"] in seen or validate_scheme(r["url"]):
                continue
            seen.add(r["url"])
            out.append({"title": r["title"][:200], "url": r["url"], "snippet": r["snippet"][:400],
                        "date": str(r.get("date") or "")[:32]})
        return {"results": out}

    def _live_fetch(self, url: str) -> dict:
        if self._fetcher is not None:
            return self._fetcher(url)
        if self.cfg.respect_robots and not self._robots_allow(url):
            return {"url": url, "error": "disallowed by robots.txt"}
        status, final, ctype, body, err = self._guarded_get(url, self.cfg.fetch_timeout, self.cfg.max_page_bytes)
        base = {"url": url, "final_url": final, "status": status, "content_type": ctype, "nbytes": len(body)}
        if err:
            return {**base, "error": err}
        if status >= 400:
            return {**base, "error": f"HTTP {status}"}
        main = ctype.split(";")[0].strip().lower()
        if main and not any(main == t for t in ALLOWED_TYPES):
            return {**base, "error": f"content type {main!r} not supported"}
        if main == "application/pdf" or body[:5] == b"%PDF-":
            text, title = pdf_to_text(body), ""
        else:
            enc = "utf-8"
            m = re.search(r"charset=([\w\-]+)", ctype, re.I)
            if m:
                enc = m.group(1)
            title, text = html_to_text(body.decode(enc, errors="replace"), final or url)
        if len(text) < 200:
            return {**base, "title": title, "text": text, "error": "no extractable text (script-rendered or empty page)"}
        return {**base, "title": title, "text": text}

    def _guarded_get(self, url: str, timeout: float, max_bytes: int) -> tuple[int, str, str, bytes, str]:
        """GET with the SSRF guard applied to every hop and a hard cap on body size and time."""
        deadline = time.perf_counter() + timeout * 2
        for _ in range(MAX_REDIRECTS + 1):
            reason = validate_url(url)
            if reason:
                return 0, url, "", b"", f"blocked: {reason}"
            try:
                r = self.session.get(url, timeout=(5, timeout), stream=True, allow_redirects=False)
            except requests.RequestException as e:
                return 0, url, "", b"", f"{type(e).__name__}"
            try:
                if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("Location"):
                    url = urljoin(url, r.headers["Location"])
                    continue
                ctype = r.headers.get("Content-Type", "")
                chunks, total = [], 0
                try:
                    for chunk in r.iter_content(65536):
                        chunks.append(chunk)
                        total += len(chunk)
                        if total >= max_bytes or time.perf_counter() > deadline:
                            break
                except requests.RequestException as e:
                    if not chunks:
                        return r.status_code, url, ctype, b"", f"{type(e).__name__}"
                return r.status_code, url, ctype, b"".join(chunks)[:max_bytes], ""
            finally:
                r.close()
        return 0, url, "", b"", "too many redirects"

    def _robots_allow(self, url: str) -> bool:
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        with self._lock:
            known = origin in self._robots
            rp = self._robots.get(origin)
        if not known:
            def live():
                status, _, _, body, err = self._guarded_get(origin + "/robots.txt", 4.0, 200_000)
                return {"status": status, "text": body.decode("utf-8", "replace") if (not err and status == 200) else "",
                        "error": err}
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


def validate_scheme(url: str) -> str | None:
    """Cheap pre-filter for search results (no DNS): only http(s) links are kept."""
    try:
        return None if urlsplit(url).scheme in ("http", "https") else "scheme"
    except ValueError:
        return "malformed"


__all__ = ["WebClient", "SearchResult", "Page", "Cassette", "validate_url", "html_to_text",
           "pdf_to_text", "domain_of", "USER_AGENT"]
