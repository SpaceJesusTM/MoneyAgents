"""Evidence checks for identification questions (SCRIPTED model, canned pages).

Why they exist: in the baseline runs D1 answered "Amkor" and D2 answered "Intel Foundry". The recorded
evidence shows the same pattern in both: one site, reporting a deal or a plan, and no quoted passage
that states the relationship the question asked about. Strings marked REAL are from those runs.

What these tests do not show: that a real model then reaches the right answer. See NEXT_PASS_RESULTS.md.
"""
import json
import re
from pathlib import Path

import pytest

from webswarm_baseline import guards as g
from webswarm_baseline.config import PACKAGE_DIR, SwarmConfig
from webswarm_baseline.mock import default_handlers, mock_setup
from webswarm_baseline.run import execute

ROUTING_CASES = json.loads((PACKAGE_DIR.parent / "experiments" / "bench" / "routing_cases.json").read_text())["cases"]

# REAL: D2, baseline. One page (aprenderhub.com); the question asked who manufactures iPhone processors.
D2_Q = ("Which company manufactures the processors Apple designs for the iPhone, and in which US state is that "
        "company building advanced chip factories?")
D2_ANSWER = "Intel Foundry manufactures the processors Apple designs for the iPhone [S1]."
D2_FINDINGS = [
    {"source_id": "S1", "claim": "Intel Foundry is the company manufacturing Apple-designed chips for the iPhone.",
     "quote": "Intel Foundry will manufacture Apple-designed chips at US facilities in Arizona and Ohio"},
    {"source_id": "S1", "claim": "The agreement between Apple and Intel was confirmed in May 2026.",
     "quote": "Talks lasted over one year; agreement confirmed May 2026"}]
# REAL: D1, first DEEP step, baseline. One page (en.sedaily.com) about a deal signed that week.
D1_STEP = "Who is the primary supplier of advanced packaging technology for NVIDIA's latest AI accelerator chips?"
D1_ANSWER = "Amkor is the primary supplier of advanced packaging technology for NVIDIA's latest AI accelerator chips [S1]."
D1_FINDINGS = [
    {"source_id": "S1", "claim": "Nvidia signed a packaging deal worth $1.5 billion with Amkor.",
     "quote": "According to Bloomberg on the 23rd, Nvidia signed a semiconductor packaging deal worth $1.5 billion "
              "(about 2.2 trillion won), including an advance payment, with Amkor to expand semiconductor production"},
    {"source_id": "S1", "claim": "Amkor previously specialized in relatively simple chip packaging.",
     "quote": "Amkor previously specialized in relatively simple chip packaging, but has been making efforts to enter "
              "more advanced technology stages through partnerships such as one with Taiwan's TSMC."}]


# ---- recognising the question ----------------------------------------------------------------------

def test_the_two_part_rule_fires_only_on_objectives_labelled_deep():
    """On the 32 labelled routing objectives. The labels and the rule have the same author; this shows the
    rule does not pull lookups, comparisons or collections into DEEP, not that it is right in general."""
    fired = [(c["expected"], c["objective"]) for c in ROUTING_CASES if g.two_part_identification(c["objective"])]
    assert fired and {mode for mode, _ in fired} == {"DEEP"}
    assert len(fired) == 3 and sum(c["expected"] == "DEEP" for c in ROUTING_CASES) == 6     # it finds half of them


@pytest.mark.parametrize("objective, two_part, identify", [
    (D2_Q, True, True),
    ("Which company acquired VMware, and in which month and year did that acquisition close?", True, True),
    ("Which company acquired VMware?", False, True),
    (D1_STEP, False, True),
    ("What was NVIDIA's Data Center revenue for fiscal year 2025, and how much did it grow from the prior year?", False, False),
    ("Which of Microsoft, Alphabet and Amazon had the highest revenue, and by how much?", False, False),
    ("Compare the gross margins of NVIDIA, AMD and Intel.", False, False),
    ("NVIDIA gross margin performance for fiscal year 2025", False, False),
])
def test_identification_questions_are_recognised(objective, two_part, identify):
    assert g.two_part_identification(objective) is two_part
    assert g.asks_to_identify(objective) is identify


# ---- support --------------------------------------------------------------------------------------

def test_d2_intel_foundry_rests_on_one_site_reporting_a_plan():
    sup = g.identification_support(D2_Q, D2_ANSWER, D2_FINDINGS, {"S1": "aprenderhub.com"})
    assert sup.entity == "Intel" and sup.domains == ["aprenderhub.com"]
    assert sup.flags == ["it rests on one source (aprenderhub.com)",
                         "the passages describe a deal or a plan, not the current situation"]


def test_d1_amkor_rests_on_one_site():
    sup = g.identification_support(D1_STEP, D1_ANSWER, D1_FINDINGS, {"S1": "en.sedaily.com"})
    assert sup.entity == "Amkor" and sup.flags[0] == "it rests on one source (en.sedaily.com)"


def test_an_identification_named_by_two_sites_in_the_present_tense_is_not_flagged():
    findings = [{"source_id": "S1", "claim": "", "quote": "TSMC manufactures the A-series processors Apple designs for the iPhone"},
                {"source_id": "S2", "claim": "", "quote": "Apple's iPhone chips are fabricated by TSMC, which is building fabs in Arizona"}]
    sup = g.identification_support(D2_Q, "TSMC manufactures the processors Apple designs for the iPhone [S1][S2].",
                                   findings, {"S1": "apple.com", "S2": "reuters.com"})
    assert sup.entity == "TSMC" and sup.flags == []


def test_an_entity_no_quoted_passage_names_is_flagged_and_other_questions_are_left_alone():
    sup = g.identification_support("Which company acquired VMware?", "Broadcom acquired VMware [S1].",
                                   [{"source_id": "S1", "claim": "Broadcom bought VMware.", "quote": "the deal closed in November 2023"}],
                                   {"S1": "reuters.com"})
    assert sup.flags == ["no quoted passage names it"]
    assert g.identification_support("What was Apple's Services revenue in fiscal year 2024?", "It was $96.2 billion [S1].",
                                    [], {}) is None
    assert g.identification_support("Which company acquired VMware?", "The findings do not say [S1].", [], {}) is None


# ---- in the engine ----------------------------------------------------------------------------------

def run(question, handlers, overrides=()):
    cfg, extra = mock_setup(SwarmConfig().override(list(overrides)), handlers=handlers)
    return execute(question, cfg, echo=False, **extra)


def cite(text, user):
    sid = re.search(r"\[(S\d+)\]", user).group(1)
    return re.sub(r"\[S\d+\]", f"[{sid}]", text)


ACME_Q = "Which partner constrains Acme Corp advanced packaging supply, and how fast will that partner expand capacity?"
STEP1 = "Which partner constrains Acme Corp advanced packaging supply?"
STEP2 = "How fast will Borealis Semiconductor expand its advanced packaging capacity?"
ANSWERS = {STEP1: "Borealis Semiconductor is the partner that constrains Acme Corp advanced packaging supply [S1].",
           STEP2: "Borealis Semiconductor plans to invest $3.1 billion in two new facilities [S1]."}


def deep_handlers(root_says):
    h = default_handlers("DEEP")
    h["route"] = lambda s, u, sc: {"reason": "scripted", "mode": root_says if "original question" in u else "ATOM"}

    def deep_step(system, user, schema):
        done = user.count("INVESTIGATE:")
        if done < 2:
            return {"reason": "", "action": "investigate", "text": [STEP1, STEP2][done]}
        return {"reason": "", "action": "finish", "text": ""}

    def answer(system, user, schema):
        if "verdict" in schema["properties"]:
            return {"verdict": "survived", "answer": cite("Borealis is named as the packaging partner [S1].", user), "gaps": ""}
        objective = re.search(r"OBJECTIVE: (.*)", user).group(1)
        return {"answer": cite(ANSWERS.get(objective, "Acme reported revenue of $4.2 billion [S1]."), user),
                "confidence": "high", "gaps": ""}

    h["deep_step"], h["answer"] = deep_step, answer
    return h


def test_a_two_part_identification_question_is_worked_as_deep_even_when_the_router_says_atom():
    """REAL: the 4B router sent D2 to a single lookup, which answered from one page with no verification."""
    art = run(ACME_Q, deep_handlers("ATOM"), overrides=["identify_guard=true"])
    root = art.swarm.nodes[0]
    assert root.model_mode == "ATOM" and root.mode == "DEEP" and len(root.children) >= 2
    assert any("two-part identification question" in n for n in root.notes)
    off = run(ACME_Q, deep_handlers("ATOM"))
    assert off.swarm.nodes[0].mode == "ATOM" and not off.swarm.nodes[0].children


def test_a_weakly_supported_identification_is_what_the_verifier_is_sent():
    art = run(ACME_Q, deep_handlers("DEEP"), overrides=["verify_guard=true", "support_check=true"])
    nodes = art.swarm.nodes
    kids = [nodes[c] for c in nodes[0].children]
    assert [k.role for k in kids] == ["research", "research", "verifier"]
    assert kids[0].result.support and "one source" in kids[0].result.support[0] and kids[0].result.confidence == "low"
    assert kids[1].result.support == []                                    # the second step names nobody new
    assert kids[2].objective.startswith("Borealis Semiconductor is the partner that constrains Acme Corp")
    assert any("verifying the weakly supported identification first" in n for n in nodes[0].notes)
    assert art.stats["guard_events"]["support_flag"] == 1

    off = run(ACME_Q, deep_handlers("DEEP"), overrides=["verify_guard=true"])     # without it: the latest claim
    last = off.swarm.nodes[off.swarm.nodes[0].children[-1]]
    assert last.role == "verifier" and last.objective.startswith("Borealis Semiconductor plans to invest")


def test_a_single_lookup_is_flagged_but_costs_no_extra_call_and_figure_questions_are_untouched():
    h = default_handlers("ATOM")
    h["answer"] = lambda s, u, sc: {"answer": cite(ANSWERS[STEP1], u), "confidence": "high", "gaps": ""}
    on, off = run(STEP1, h, overrides=["support_check=true"]), run(STEP1, h)
    assert on.outcome["confidence"] == "low" and "Weak support for Borealis" in on.outcome["gaps"]
    assert off.outcome["confidence"] == "high" and off.outcome["gaps"] == ""
    assert on.stats["llm_calls"] == off.stats["llm_calls"]

    figures = run("Acme Corp fourth quarter revenue and data center revenue figures", default_handlers("ATOM"),
                  overrides=["support_check=true", "identify_guard=true"])
    assert figures.swarm.nodes[0].mode == "ATOM" and "support_flag" not in figures.stats["guard_events"]


def test_the_new_switches_are_off_in_the_frozen_and_reliability_configs_and_on_in_evidence_v1():
    for name in ("baseline", "reliability_v1", "reliability_v1_9b"):
        cfg = SwarmConfig.load(PACKAGE_DIR / "configs" / f"{name}.json")
        assert not cfg.identify_guard and not cfg.support_check
    ev = SwarmConfig.load(PACKAGE_DIR / "configs" / "evidence_v1.json")
    rel = SwarmConfig.load(PACKAGE_DIR / "configs" / "reliability_v1.json")
    assert ev.identify_guard and ev.support_check
    assert {k for k, v in ev.to_dict().items() if rel.to_dict()[k] != v} == {"name", "identify_guard", "support_check"}
    nine = SwarmConfig.load(PACKAGE_DIR / "configs" / "reliability_v1_9b.json")
    assert {k for k, v in nine.to_dict().items() if rel.to_dict()[k] != v} == {"name", "model"}
