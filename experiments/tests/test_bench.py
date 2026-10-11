"""Tests for the grader and the benchmark definitions (no model, no network)."""
import json
from pathlib import Path

from experiments.bench.grade import grade
from experiments.bench.run_bench import arm_config, load_arms, load_tasks
from webswarm_baseline.config import SwarmConfig

TASK = {"key_facts": [{"fact": "DC revenue 115.2", "patterns": ["115\\.2"]}, {"fact": "up 142%", "patterns": ["142\\s?%"]}],
        "coverage": [{"point": "supply", "patterns": ["supply", "tsmc"]}, {"point": "demand", "patterns": ["demand"]}],
        "authoritative": ["nvidia.com"]}
AUDIT_OK = {"citations": 2, "unknown_citations": [], "numbers_ungrounded": 0, "cited_domains": ["nvidianews.nvidia.com"]}


def test_grade_full_marks():
    g = grade(TASK, "Data Center revenue was $115.2 billion [S1], up 142% [S1]; TSMC supply and demand matter [S2].", AUDIT_OK)
    assert g["fact_recall"] == 1.0 and g["coverage"] == 1.0 and g["grounding"] == 1.0 and g["quality"] == 1.0
    assert g["cites_authoritative_source"] is True and g["facts_missed"] == []


def test_grade_partial_and_ungrounded():
    audit = {**AUDIT_OK, "numbers_ungrounded": 1, "cited_domains": ["someblog.example"]}
    g = grade(TASK, "Revenue was $115.2 billion [S1]. Demand is strong [S1].", audit)
    assert g["fact_recall"] == 0.5 and g["facts_missed"] == ["up 142%"]
    assert g["coverage"] == 0.5 and g["coverage_missed"] == ["supply"]
    assert g["grounding"] == 0.5 and g["quality"] == round((0.5 + 0.5 + 0.5) / 3, 3)
    assert g["cites_authoritative_source"] is False


def test_grade_uncited_or_empty_answer_gets_no_grounding_credit():
    assert grade(TASK, "Revenue was $115.2 billion, up 142%.", {"citations": 0})["grounding"] == 0.0
    g = grade(TASK, "", {})
    assert g["answered"] is False and g["quality"] == 0.0


def test_grade_reports_facts_that_were_retrieved_but_dropped_from_the_answer():
    ev = {"findings": [{"claim": "Data Center revenue was $115.2 billion, up 142%", "quote": "x"}]}
    g = grade(TASK, "NVIDIA grew strongly [S1].", AUDIT_OK, ev)
    assert g["fact_recall"] == 0.0 and g["fact_recall_in_evidence"] == 1.0


def test_task_and_arm_definitions_are_consistent():
    tasks, arms = load_tasks(), load_arms()
    assert len(tasks) >= 8 and {"ATOM", "WIDE", "DEEP", "MIXED", "ENTITY_COLLECT"} <= {t["type"] for t in tasks.values()}
    assert "baseline" in arms and arms["baseline"]["overrides"] == []
    for name, spec in arms.items():
        cfg = arm_config(name, spec, "A1", use_cassette=True)       # every override must be a valid config key
        assert cfg.name == name and cfg.web_mode == "replay_or_record" and cfg.cassette.endswith("cassettes/A1")
        assert set(spec.get("subset", [])) <= set(tasks)
    base = arm_config("baseline", arms["baseline"], "A1", use_cassette=False).to_dict()
    frozen = SwarmConfig.load(Path("webswarm_baseline/configs/baseline.json")).to_dict()
    assert {k: v for k, v in base.items() if k != "name"} == {k: v for k, v in frozen.items() if k != "name"}
