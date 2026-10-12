"""Search failures versus search answers (no model, no network).

Background, 2026-10-11/12: on this machine every live search timed out for a day (the local resolver
dropped IPv6 lookups), and each failure was written into the benchmark recordings and replayed to
later runs as if "no results" were what the web had said. These tests pin the difference between a
search that was answered (possibly with nothing) and one that was not answered at all.
"""
import json
import socket
import time

import pytest
import requests

from webswarm_baseline import web as webmod
from webswarm_baseline.config import SwarmConfig
from webswarm_baseline.mock import default_handlers, mock_fetch, mock_setup
from webswarm_baseline.run import execute
from webswarm_baseline.runtime import Budget, Tracer
from webswarm_baseline.web import (CANARY_QUERY, Cassette, DDGSProvider, Ipv4Tunnel, SearchFailure, WebClient,
                                   classify_ddgs_error)

ROWS = [{"title": "Acme Corp fourth quarter results", "url": "https://example-ir.test/acme-q4",
         "snippet": "Acme Corp reported fourth quarter revenue of $4.2 billion.", "date": ""}]
Q = "acme fourth quarter revenue"


class Scripted:
    """A search provider that plays back a list of outcomes: rows, [] or an exception to raise."""
    name = "scripted"

    def __init__(self, *outcomes, canary=True):
        self.outcomes, self.calls, self.canary = list(outcomes), [], canary

    def search(self, query, n):
        self.calls.append(query)
        if query == CANARY_QUERY:
            return ROWS if self.canary else []
        out = self.outcomes.pop(0) if self.outcomes else ROWS
        if isinstance(out, Exception):
            raise out
        return out


class Forbidden:
    name = "none"

    def search(self, query, n):
        raise AssertionError("the provider was asked during a replay")


def client(provider, tmp_path=None, mode="replay_or_record", overrides=(), fetcher=None):
    extra = [f"cassette={tmp_path}", f"web_mode={mode}", "replay_latency=false"] if tmp_path else []
    cfg = SwarmConfig().override(["respect_robots=false", "min_search_interval=0", *extra, *overrides])
    tracer = Tracer(echo=None)
    return WebClient(cfg, tracer, Budget(cfg.budgets, tracer), provider=provider, fetcher=fetcher), tracer


def recorded(tmp_path):
    return sorted(p.name for p in tmp_path.glob("search_*.json"))


def calls(tracer):
    return [e for e in tracer.events if e["type"] == "web_call"]


# ---- what gets recorded ---------------------------------------------------------------------------

def test_a_search_that_got_no_answer_is_not_recorded_and_is_asked_again_next_time(tmp_path):
    down = Scripted(SearchFailure("timeout", "no answer within 25 s"), SearchFailure("timeout", "again"))
    c, tracer = client(down, tmp_path)
    got = c.search(Q)
    assert got == [] and got.kind == "timeout" and "search failed (timeout)" in got.error
    assert recorded(tmp_path) == []                                    # the bug: this used to be written
    assert calls(tracer)[0]["ok"] is False and calls(tracer)[0]["transient"] is True

    up = Scripted(ROWS)
    c2, _ = client(up, tmp_path)
    assert [r.url for r in c2.search(Q)] == ["https://example-ir.test/acme-q4"] and up.calls == [Q]
    assert len(recorded(tmp_path)) == 1

    c3, t3 = client(Forbidden(), tmp_path, mode="replay")              # and now it replays without the network
    assert [r.title for r in c3.search(Q)] == ["Acme Corp fourth quarter results"]
    assert calls(t3)[0]["source"] == "cassette"


def test_an_empty_result_is_an_answer_and_is_recorded_and_replayed(tmp_path):
    p = Scripted([])
    c, _ = client(p, tmp_path)
    got = c.search(Q)
    assert got == [] and got.error == "" and got.kind == ""
    assert p.calls == [Q, CANARY_QUERY]                                # the provider was checked to be answering
    entry = json.loads((tmp_path / recorded(tmp_path)[0]).read_text())
    assert entry["response"] == {"results": []}

    c2, t2 = client(Forbidden(), tmp_path, mode="replay")
    again = c2.search(Q)
    assert again == [] and again.error == "" and calls(t2)[0]["source"] == "cassette" and calls(t2)[0]["ok"]


def test_an_empty_result_from_a_provider_that_is_not_answering_is_a_failure_not_an_answer(tmp_path):
    """`ddgs` says "no results" when its engines serve rate-limit pages. A control query tells the two apart."""
    p = Scripted([], [], canary=False)
    c, tracer = client(p, tmp_path, overrides=["search_attempts=1"])
    first, second = c.search(Q), c.search("acme supply constraints")
    assert first.kind == second.kind == "rate_limited" and "control query" in first.error
    assert recorded(tmp_path) == []
    assert p.calls.count(CANARY_QUERY) == 1                            # the verdict is reused, not re-asked each time
    assert [e["ok"] for e in tracer.events if e["type"] == "search_canary"] == [False]


def test_a_failure_recorded_by_an_older_version_is_replayed_as_recorded_but_not_trusted_when_recording(tmp_path):
    key = webmod.norm(Q)
    Cassette(str(tmp_path)).put("search", key, {"error": "RuntimeError: search failed: TimeoutException"}, 30.0)
    c, _ = client(Forbidden(), tmp_path, mode="replay")                # strict replay stays deterministic
    old = c.search(Q)
    assert old == [] and old.kind == "recorded_failure"
    p = Scripted(ROWS)
    c2, _ = client(p, tmp_path)                                        # replay_or_record: ask again
    assert len(c2.search(Q)) == 1 and p.calls == [Q]
    c3, _ = client(Forbidden(), tmp_path, mode="replay")
    assert len(c3.search(Q)) == 1


def test_a_replay_miss_is_reported_as_a_miss():
    cfg, _ = mock_setup(SwarmConfig())
    c, _ = client(Forbidden(), mode="live")
    c.cfg.web_mode, c.cassette = "replay", Cassette("/tmp/does-not-matter-" + str(time.time_ns()))
    got = c.search(Q)
    assert got == [] and got.kind == "replay_miss"


# ---- retries and giving up -------------------------------------------------------------------------

def test_a_timeout_is_retried_once_and_the_second_answer_is_used(tmp_path):
    p = Scripted(SearchFailure("timeout", "slow"), ROWS)
    c, tracer = client(p, tmp_path)
    assert len(c.search(Q)) == 1 and p.calls == [Q, Q]
    assert calls(tracer)[0]["attempts"] == 2 and calls(tracer)[0]["ok"]
    assert "attempts" not in json.loads((tmp_path / recorded(tmp_path)[0]).read_text())["response"]


def test_retries_are_bounded():
    p = Scripted(*[SearchFailure("network", "down")] * 10)
    c, _ = client(p, overrides=["search_attempts=3", "search_breaker=99"])
    assert c.search(Q).kind == "network" and len(p.calls) == 3


def test_a_provider_bug_is_a_failed_search_not_a_crashed_run():
    c, _ = client(Scripted(KeyError("href")))
    got = c.search(Q)
    assert got.kind == "internal" and "KeyError" in got.error


def test_after_repeated_failures_search_is_switched_off_for_a_while_instead_of_waiting_each_time():
    p = Scripted(*[SearchFailure("timeout", "x")] * 10)
    c, tracer = client(p, overrides=["search_attempts=1", "search_breaker=2", "search_cooldown=0.2"])
    assert [c.search(f"query {i}").kind for i in range(4)] == ["timeout", "timeout", "unavailable", "unavailable"]
    assert len(p.calls) == 2                                           # the last two never reached the provider
    assert [e["after"] for e in tracer.events if e["type"] == "search_unavailable"] == [2]
    time.sleep(0.25)
    assert c.search("query after the pause").kind == "timeout" and len(p.calls) == 3


def test_a_success_resets_the_failure_count():
    p = Scripted(SearchFailure("timeout", "x"), ROWS, SearchFailure("timeout", "x"), ROWS)
    c, _ = client(p, overrides=["search_attempts=1", "search_breaker=2"])
    kinds = [c.search(f"query {i}").kind for i in range(4)]
    assert kinds == ["timeout", "", "timeout", ""] and len(p.calls) == 4


# ---- telling the library's errors apart ------------------------------------------------------------

def _named(name, message):
    return type(name, (Exception,), {})(message)


@pytest.mark.parametrize("error, elapsed, kind", [
    (_named("RatelimitException", "202 Ratelimit"), 0.3, "rate_limited"),
    (_named("TimeoutException", "error sending request for url (https://html.duckduckgo.com/html/) > operation timed out"), 10.0, "timeout"),
    (_named("DDGSException", "No results found."), 10.1, "timeout"),        # REAL: a timeout reported as "no results"
    (_named("DDGSException", "ConnectError: dns error: failed to lookup address"), 0.1, "network"),
    (_named("DDGSException", "HTTP 429 too many requests"), 0.2, "rate_limited"),
    (_named("DDGSException", "unexpected response structure"), 0.2, "provider"),
    (ValueError("bad argument"), 0.0, "internal"),
])
def test_library_errors_are_classified(error, elapsed, kind):
    outcome = classify_ddgs_error(error, elapsed, timeout=10)
    assert isinstance(outcome, SearchFailure) and outcome.kind == kind


def test_a_quick_no_results_from_the_library_is_an_empty_answer():
    assert not isinstance(classify_ddgs_error(_named("DDGSException", "No results found."), 0.6, timeout=10), SearchFailure)
    p = DDGSProvider()
    p._ask = lambda q, n: (_ for _ in ()).throw(_named("DDGSException", "No results found."))
    assert p.search(Q, 5) == []


def test_one_provider_call_cannot_run_past_its_deadline():
    p = DDGSProvider(deadline=0.15)
    p._ask = lambda q, n: time.sleep(1.0) or []
    t0 = time.perf_counter()
    with pytest.raises(SearchFailure) as e:
        p.search(Q, 5)
    assert e.value.kind == "timeout" and time.perf_counter() - t0 < 0.6


# ---- the local network ------------------------------------------------------------------------------

def test_without_an_ipv6_route_names_are_looked_up_over_ipv4_only(monkeypatch):
    monkeypatch.setattr(webmod, "_NET", {"v6": False})
    assert webmod.gai_family() == socket.AF_INET and webmod.prefer_usable_addresses().startswith("ipv4 only")
    monkeypatch.setattr(webmod, "_NET", {"v6": True})
    assert webmod.gai_family() == socket.AF_UNSPEC and webmod.prefer_usable_addresses() == "system default"


def _tunnel_says(request: bytes) -> bytes:
    t = Ipv4Tunnel()
    try:
        s = socket.create_connection(("127.0.0.1", int(t.url.rsplit(":", 1)[1])), timeout=3)
        s.sendall(request)
        return s.recv(200)
    finally:
        s.close()
        t.close()


def test_the_tunnel_only_opens_tls_connections_to_public_hosts():
    assert _tunnel_says(b"GET http://example.com/ HTTP/1.1\r\n\r\n").startswith(b"HTTP/1.1 403")      # not a tunnel request
    assert _tunnel_says(b"CONNECT example.com:25 HTTP/1.1\r\n\r\n").startswith(b"HTTP/1.1 403")        # not port 443
    assert _tunnel_says(b"CONNECT 127.0.0.1:443 HTTP/1.1\r\n\r\n").startswith(b"HTTP/1.1 403")         # loopback
    assert _tunnel_says(b"CONNECT 169.254.169.254:443 HTTP/1.1\r\n\r\n").startswith(b"HTTP/1.1 403")   # metadata address


# ---- page fetches -------------------------------------------------------------------------------------

class Refused:
    status_code, headers = 403, {"Content-Type": "text/html"}

    def iter_content(self, n):
        yield b"<html>Access denied</html>"

    def close(self):
        pass


def test_a_fetch_that_got_no_http_answer_is_not_recorded_but_a_refusal_is(tmp_path, monkeypatch):
    monkeypatch.setattr(webmod, "validate_url", lambda url: None)
    c, tracer = client(Scripted(), tmp_path)

    def dropped(*a, **k):
        raise requests.ConnectionError("connection reset")

    c.session.get = dropped
    page = c.fetch("https://example-ir.test/flaky")
    assert not page.ok and page.error == "ConnectionError"
    assert list(tmp_path.glob("fetch_*.json")) == [] and calls(tracer)[-1]["transient"] is True

    c.session.get = lambda *a, **k: Refused()
    assert c.fetch("https://example-ir.test/paywall").error == "HTTP 403"
    assert len(list(tmp_path.glob("fetch_*.json"))) == 1               # a refusal is what the site said: recorded
    c.session.get = lambda *a, **k: pytest.fail("fetched again")
    c2, _ = client(Scripted(), tmp_path, mode="replay")
    c2.session.get = c.session.get
    assert c2.fetch("https://example-ir.test/paywall").error == "HTTP 403"


# ---- what an agent does with it ------------------------------------------------------------------------

def test_an_agent_reports_a_retrieval_failure_and_does_not_reword_the_query():
    cfg, extra = mock_setup(SwarmConfig().override(["search_attempts=1"]), handlers=default_handlers("ATOM"))
    down = Scripted(*[SearchFailure("timeout", "no answer")] * 20)
    art = execute("Acme Corp fourth quarter revenue official confirmed report PDF transcript figures", cfg, echo=False,
                  llm_factory=extra["llm_factory"], web_kwargs={"provider": down, "fetcher": mock_fetch})
    root = art.swarm.nodes[0]
    assert art.outcome["status"] == "failed" and art.outcome["answer"] == ""
    assert "retrieval failure, not evidence that nothing exists" in art.outcome["gaps"]
    assert any("search got no answer (timeout)" in n for n in root.notes)
    assert not any("retried as" in n for n in root.notes)             # a simpler query cannot fix a dead provider
    prov = art.stats["web_provenance"]["search"]
    assert prov["no_answer"] >= 1 and prov["live"] == 0 and prov["replayed"] == 0
    assert set(art.stats["search_no_answer_by_kind"]) <= {"timeout", "unavailable"}


def test_an_agent_still_rewords_a_query_that_was_answered_with_nothing():
    cfg, extra = mock_setup(SwarmConfig(), handlers=default_handlers("ATOM"))
    p = Scripted([])                                                   # first search: answered, empty
    art = execute("Acme Corp fourth quarter revenue official confirmed report PDF transcript figures", cfg, echo=False,
                  llm_factory=extra["llm_factory"], web_kwargs={"provider": p, "fetcher": mock_fetch})
    assert any("retried as" in n for n in art.swarm.nodes[0].notes) and art.outcome["status"] == "ok"
    assert art.stats["web_provenance"]["search"]["no_answer"] == 0


# ---- replaying on another day --------------------------------------------------------------------------

def test_the_date_shown_to_the_model_can_be_pinned_so_a_recording_replays_on_another_day():
    """Found 2026-10-12: two baseline replays diverged from the previous day's because every prompt
    says "Today: <date>", and with the date changed the model wrote one search query differently."""
    seen = []
    h = default_handlers("ATOM")
    inner = h["act"]

    def act(system, user, schema):
        seen.append(user.splitlines()[0])
        return inner(system, user, schema)

    h["act"] = act
    cfg, extra = mock_setup(SwarmConfig().override(["as_of=2026-10-11"]), handlers=h)
    execute("Acme Corp fourth quarter revenue", cfg, echo=False, **extra)
    assert seen and set(seen) == {"Today: 2026-10-11"}
    seen.clear()
    cfg, extra = mock_setup(SwarmConfig(), handlers=h)
    execute("Acme Corp fourth quarter revenue", cfg, echo=False, **extra)
    assert seen and all(line.startswith("Today: 20") and line != "Today: 2026-10-11" for line in seen)
    assert SwarmConfig().as_of == ""

