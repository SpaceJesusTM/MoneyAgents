"""Tests for the experimental deciders. Scripted model and canned pages only (no real model, no network)."""
import math

import pytest

from experiments.deciders import build
from experiments.deciders.local_s1 import LocalLogprobBackend, _label_probs
from experiments.deciders.mock_jev import MockJevBackend
from experiments.deciders.primitives import Choice, Noul, Score
from experiments.deciders.rules import RulesDecider
from webswarm_baseline.config import SwarmConfig
from webswarm_baseline.mock import mock_setup
from webswarm_baseline.run import execute

Q = "What are the main factors that could affect Acme Corp data center revenue growth?"


def run(decider_name, options=None, overrides=()):
    cfg, extra = mock_setup(SwarmConfig().override(list(overrides)))
    return execute(Q, cfg, echo=False, decider=build(decider_name, options or {}), **extra)


class N:  # minimal node stand-in for routing tests
    def __init__(self, objective, depth=0):
        self.objective, self.depth, self.id, self.parent = objective, depth, 0, None


MODES = ["ATOM", "WIDE", "DEEP", "ENTITY_COLLECT"]


# ---- rules --------------------------------------------------------------------------------------

@pytest.mark.parametrize("objective,depth,expected", [
    ("What was NVIDIA's data center revenue in fiscal 2025?", 0, "ATOM"),
    ("Compare the gross margins of NVIDIA, AMD and Intel over their most recent fiscal year.", 0, "WIDE"),
    ("What are the main factors that could affect NVIDIA's data-center revenue growth?", 0, "WIDE"),
    ("Which supplier's advanced-packaging capacity most constrains NVIDIA shipments, and how fast can it grow?", 0, "DEEP"),
    ("Which companies supply high-bandwidth memory for AI accelerators?", 0, "ENTITY_COLLECT"),
    ("Main drivers of hyperscaler demand for NVIDIA chips", 1, "ATOM"),          # below the root: not split again
    ("Compare AWS, Azure and Google Cloud capital expenditure in 2025", 1, "WIDE"),   # explicit comparison still splits
])
def test_rules_router(objective, depth, expected):
    assert RulesDecider().route(N(objective, depth), MODES).value == expected


def test_rules_arm_runs_with_no_generative_control_calls():
    art = run("rules")
    kinds = art.stats["llm_calls_by_kind"]
    assert art.outcome["answer"] and art.outcome["status"] == "ok"
    assert "route" not in kinds and "review" not in kinds and "act" not in kinds
    assert set(kinds) <= {"plan", "extract", "answer", "synthesize", "snippet_extract"}
    assert art.stats["decision_calls"] == 0
    assert all(k.endswith(":rules") for k in art.stats["decisions"])


def test_rules_verification_is_skipped_only_with_two_independent_sites():
    cfg, extra = mock_setup(SwarmConfig().override(["verify_policy=decider"]), root_mode="DEEP")
    d = build("rules", {})
    d.route = lambda node, modes: __import__("webswarm_baseline.decisions", fromlist=["Decision"]).Decision(
        "route", "DEEP" if node.depth == 0 else "ATOM", "rules")
    art = execute(Q, cfg, echo=False, decider=d, **extra)
    verify = [e for e in art.tracer.of("decision") if e["point"] == "verify"]
    assert len(verify) == 1
    n_sites = int(verify[0]["reason"].split("from ")[1].split(" ")[0])
    assert verify[0]["value"] is (n_sites < 2)
    has_verifier = any(n.role == "verifier" for n in art.swarm.nodes.values())
    assert has_verifier is verify[0]["value"]


# ---- typed decisions through the MOCK backend ---------------------------------------------------

def test_mock_jev_arm_is_labelled_as_mock_everywhere():
    art = run("mock_jev")
    assert art.outcome["answer"]
    calls = art.tracer.of("decision_call")
    assert calls and all(c["provider"] == "MOCK_jev" and c.get("mock") is True for c in calls)
    assert all(c["model"].startswith("MOCK") for c in calls)
    assert all("MOCK_jev" in k for k in art.stats["decisions"] if not k.startswith("review_gate"))


def test_mock_backend_returns_well_formed_answers():
    out = MockJevBackend().ask("NVIDIA and AMD margins compared", {
        "m": Choice("mode?", {"ATOM": "single lookup", "WIDE": "compare several named entities"}),
        "y": Noul("The text compares several named entities."), "s": Score("how broad", ["narrow", "medium", "broad"])})
    assert out["m"].choice in ("ATOM", "WIDE") and abs(sum(out["m"].probabilities.values()) - 1) < 0.01
    assert 0 <= out["y"].noul <= 1 and out["s"].score == 1.0


# ---- local logprob backend ----------------------------------------------------------------------

def lp(token, p):
    return {"token": token, "logprob": math.log(p)}


def test_label_probabilities_merge_token_variants_and_normalise():
    logprobs = [{"token": "Yes", "logprob": math.log(0.5),
                 "top_logprobs": [lp("Yes", 0.5), lp(" yes", 0.1), lp("No", 0.2), lp("Maybe", 0.2)]}]
    probs = _label_probs(logprobs, {"YES", "NO"})
    assert probs["YES"] == pytest.approx(0.75) and probs["NO"] == pytest.approx(0.25)


def test_label_probabilities_skip_a_leading_non_label_token():
    logprobs = [{"token": "\n", "logprob": 0.0, "top_logprobs": [lp("\n", 0.9), lp(" ", 0.1)]},
                {"token": "B", "logprob": math.log(0.6), "top_logprobs": [lp("B", 0.6), lp("A", 0.3), lp("C", 0.1)]}]
    probs = _label_probs(logprobs, {"A", "B", "C"})
    assert max(probs, key=probs.get) == "B" and sum(probs.values()) == pytest.approx(1.0)


class FakeLLM:
    """Returns canned logprobs; records the request so the prompt layout can be checked."""
    def __init__(self, top):
        self.top, self.bodies = top, []
        self.cfg = SwarmConfig()

    def raw(self, kind, node, body, model=None, provider=""):
        self.bodies.append((model, body))
        tok = max(self.top, key=lambda t: t[1])[0]
        return {"message": {"content": tok},
                "logprobs": [{"token": tok, "logprob": 0.0, "top_logprobs": [lp(t, p) for t, p in self.top]}]}


def test_local_backend_answers_a_choice_with_one_token_and_a_distribution():
    llm = FakeLLM([("B", 0.7), ("A", 0.2), ("C", 0.1)])
    b = LocalLogprobBackend(llm, model="tiny")
    a = b.ask("state text", {"mode": Choice("pick", {"ATOM": "one lookup", "WIDE": "many parts", "DEEP": None})})["mode"]
    assert a.choice == "WIDE" and a.probabilities == {"ATOM": 0.2, "WIDE": 0.7, "DEEP": 0.1}
    assert a.confidence == pytest.approx((0.7 - 1 / 3) / (1 - 1 / 3), abs=1e-3)
    model, body = llm.bodies[0]
    assert model == "tiny" and body["logprobs"] is True and body["options"]["num_predict"] <= 3
    user = body["messages"][1]["content"]
    assert user.startswith("STATE:\nstate text")          # state first, so questions share a cached prefix
    assert "A) ATOM: one lookup" in user and "C) DEEP" in user


def test_local_backend_noul_and_score():
    assert LocalLogprobBackend(FakeLLM([("Yes", 0.9), ("No", 0.1)])).ask("s", {"q": Noul("ok?")})["q"].noul == 0.9
    s = LocalLogprobBackend(FakeLLM([("2", 0.5), ("1", 0.5)])).ask("s", {"q": Score("lvl", ["a", "b", "c"])})["q"]
    assert s.score == 1.5 and s.probabilities == {"0": 0.0, "1": 0.5, "2": 0.5}


def test_unknown_decider_name_is_rejected():
    with pytest.raises(ValueError, match="unknown decider"):
        build("nope", {})


def test_rules_router_does_not_call_a_plain_two_part_lookup_deep():
    q = "What was NVIDIA's Data Center revenue for fiscal year 2025, and how much did it grow from the prior year?"
    assert RulesDecider().route(N(q), MODES).value == "ATOM"


def test_fuzzy_redundancy_applies_only_when_asked():
    d = RulesDecider()
    parent = "Which partner constrains Acme Corp advanced packaging supply, and how fast can it grow?"
    step = "Which partner constrains Acme Corp advanced packaging supply?"
    assert d.redundant(step, [parent], fuzzy=True) is True       # a WIDE child restating its parent is dropped
    assert d.redundant(step, [parent], fuzzy=False) is False     # a DEEP step narrowing its parent is kept
    assert d.redundant(parent, [parent], fuzzy=False) is True    # exact duplicates are always dropped


def test_rules_arm_completes_a_deep_run():
    cfg, extra = mock_setup(SwarmConfig().override(["verify_policy=decider"]), root_mode="DEEP")
    d = build("rules", {})
    art = execute("Which partner constrains Acme Corp advanced packaging supply, and how fast can it grow?",
                  cfg, echo=False, decider=d, **extra)
    assert art.swarm.nodes[0].mode == "DEEP" and len(art.swarm.nodes) >= 2
    assert art.outcome["answer"]
