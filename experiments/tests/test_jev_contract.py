"""Contract tests for the Jev REST adapter, run against a LOCAL STUB of the documented API.

What these prove: the adapter builds the documented request, sends the documented auth header,
parses the documented response shapes, and handles the documented error codes.
What they do not prove: anything about the real service. No request leaves this machine.
"""
import json

import pytest

from experiments.deciders import build
from experiments.deciders.jev import JevBackend, JevError
from experiments.deciders.mock_jev import serve_stub, validate_request
from experiments.deciders.primitives import Answer, Choice, Noul, Score, peak_confidence
from webswarm_baseline.config import SwarmConfig
from webswarm_baseline.mock import mock_setup
from webswarm_baseline.run import execute
from webswarm_baseline.runtime import Tracer

# The example response from https://docs.typesafe.ai/introduction/quickstart, copied verbatim.
DOCUMENTED_RESPONSE = {
    "model": "jev-1.13.0",
    "answers": {
        "department": {"type": "choice", "choice": "technical", "confidence": 0.78,
                       "probabilities": {"technical": 0.85, "sales": 0.0, "billing": 0.15}},
        "frustration": {"type": "score", "score": 1.0, "confidence": 1.0,
                        "legend": {"0": "Calm, just stating facts", "1": "Frustrated but civil",
                                   "2": "Very angry, strong language"},
                        "probabilities": {"0": 0.0, "1": 1.0, "2": 0.0}},
        "is_urgent": {"type": "noul", "noul": 1.0}},
    "usage": {"input_tokens": 392, "output_tokens": 65}}

QUESTIONS = {
    "department": Choice("Which team should handle this",
                         {"billing": "Payment or subscription issues", "technical": "Bugs or integration problems",
                          "sales": "Pricing or account questions"}),
    "frustration": Score("How frustrated the customer appears",
                         ["Calm, just stating facts", "Frustrated but civil", "Very angry, strong language"]),
    "is_urgent": Noul("The message conveys urgency or time-sensitivity"),
}
STATE = "Hi, the Stripe integration keeps failing and I'm losing sales. Please help ASAP."


@pytest.fixture
def stub():
    server, url, log = serve_stub(api_key="test-key")
    yield url, log
    server.shutdown()


def backend(url, **kw):
    kw.setdefault("allow_external_calls", True)
    kw.setdefault("backoff", 0.01)
    return JevBackend(api_key=kw.pop("api_key", "test-key"), url=url, **kw)


def test_documented_response_parses_into_typed_answers():
    a = {k: Answer.from_wire(v) for k, v in DOCUMENTED_RESPONSE["answers"].items()}
    assert a["department"].choice == "technical" and a["department"].probabilities["billing"] == 0.15
    assert a["department"].confidence == 0.78
    assert a["frustration"].score == 1.0 and a["frustration"].probabilities == {"0": 0.0, "1": 1.0, "2": 0.0}
    assert a["is_urgent"].noul == 1.0 and a["is_urgent"].confidence is None   # a Noul has no confidence field


def test_local_confidence_formula_matches_the_documented_example():
    # the formula gives 0.775; the documentation shows 0.78 for this distribution
    assert abs(peak_confidence({"technical": 0.85, "sales": 0.0, "billing": 0.15}) - 0.775) < 1e-9
    assert peak_confidence({"0": 0.0, "1": 1.0, "2": 0.0}) == 1.0
    assert peak_confidence({"a": 0.5, "b": 0.5}) == 0.0


def test_request_matches_the_documented_wire_format(stub):
    url, log = stub
    out = backend(url).ask(STATE, QUESTIONS)
    sent = log[-1]
    assert sent["path"] == "/v1/systemone" and sent["auth"] == "Bearer test-key"
    body = sent["body"]
    assert set(body) == {"state", "model", "questions"} and body["model"] == "jev-latest" and body["state"] == STATE
    assert body["questions"]["department"] == {
        "type": "choice", "instructions": "Which team should handle this",
        "criteria": {"billing": "Payment or subscription issues", "technical": "Bugs or integration problems",
                     "sales": "Pricing or account questions"}}
    assert body["questions"]["frustration"]["type"] == "score" and len(body["questions"]["frustration"]["criteria"]) == 3
    assert body["questions"]["is_urgent"] == {"type": "noul",
                                             "instructions": "The message conveys urgency or time-sensitivity"}
    assert validate_request(body) is None
    assert set(out) == set(QUESTIONS) and out["department"].type == "choice" and 0 <= out["is_urgent"].noul <= 1
    assert abs(sum(out["department"].probabilities.values()) - 1) < 0.01


def test_structured_state_is_sent_as_an_object(stub):
    url, log = stub
    backend(url).ask({"objective": "x", "results": [1, 2]}, {"q": Noul("ok?")})
    assert log[-1]["body"]["state"] == {"objective": "x", "results": [1, 2]}


def test_usage_is_accumulated_and_traced_without_the_key(stub):
    url, _ = stub
    tr = Tracer()
    b = backend(url, tracer=tr)
    b.ask(STATE, QUESTIONS, kind="route")
    b.ask(STATE, {"q": Noul("ok?")}, kind="review")
    assert b.usage["requests"] == 2 and b.usage["input_tokens"] > 0
    calls = tr.of("decision_call")
    assert [c["kind"] for c in calls] == ["route", "review"] and all(c["provider"] == "jev" for c in calls)
    assert "test-key" not in json.dumps(tr.events)


def test_bad_key_is_a_clear_error_and_is_not_retried(stub):
    url, log = stub
    with pytest.raises(JevError) as e:
        backend(url, api_key="wrong").ask(STATE, QUESTIONS)
    assert e.value.status == 401 and "invalid API key" in str(e.value) and "wrong" not in str(e.value)
    assert len(log) == 1


def test_validation_error_is_not_retried(stub):
    url, log = stub
    with pytest.raises(JevError) as e:
        backend(url).ask(STATE, {"lvl": Score("rate", ["only one level"])})   # the API requires 2..10 levels
    assert e.value.status == 422 and len(log) == 1


def test_rate_limit_and_overload_are_retried_with_backoff():
    server, url, log = serve_stub(api_key="test-key", fail_first=[429, 529])
    try:
        b = backend(url)
        out = b.ask(STATE, {"q": Noul("ok?")})
        assert [e["status"] for e in log] == [429, 529, 200]
        assert b.usage["retries"] == 2 and "q" in out
    finally:
        server.shutdown()


def test_gives_up_after_max_retries():
    server, url, log = serve_stub(api_key="test-key", fail_first=[429] * 10)
    try:
        with pytest.raises(JevError) as e:
            backend(url, max_retries=2).ask(STATE, {"q": Noul("ok?")})
        assert e.value.status == 429 and len(log) == 3
    finally:
        server.shutdown()


def test_unreachable_endpoint_fails_cleanly():
    with pytest.raises(JevError):
        backend("http://127.0.0.1:9/v1/systemone", max_retries=1, timeout=0.5).ask(STATE, {"q": Noul("ok?")})


def test_refuses_to_start_without_a_key_or_without_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(JevError, match="TYPESAFE_API_KEY is not set"):
        JevBackend(allow_external_calls=True)
    with pytest.raises(JevError, match="allow_external_calls"):
        JevBackend(api_key="k")                       # key present, but nobody confirmed paid external calls


def test_full_swarm_run_with_the_jev_adapter_pointed_at_the_stub(stub, monkeypatch):
    """End to end: every typed decision in a (scripted) research run goes through the Jev HTTP
    adapter. Shows the integration is wired; the stub's answers are heuristics, not Jev's."""
    url, log = stub
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")
    cfg, extra = mock_setup(SwarmConfig())
    decider = build("jev", {"allow_external_calls": True, "url": url})
    art = execute("What could affect Acme Corp data center revenue growth?", cfg, echo=False, decider=decider, **extra)
    assert art.outcome["answer"]
    calls = art.tracer.of("decision_call")
    assert calls and all(c["provider"] == "jev" for c in calls)
    assert {c["kind"] for c in calls} >= {"route"}
    assert all(e["status"] == 200 for e in log) and len(log) == len(calls)
    routed = [e for e in art.tracer.of("decision") if e["point"] == "route"]
    assert routed and all(e["provider"] == "jev" for e in routed)
