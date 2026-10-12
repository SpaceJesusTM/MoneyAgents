"""Stricter automatic grading (v2). No model involved.

`grade.py` (v1) is unchanged, and every recorded result keeps the v1 scores it was given. v2 exists
because reading the baseline answers showed four ways v1 over-scores (BASELINE_RESULTS.md, "What
the automatic scores miss"):

    R1  not-found credit    a fact or coverage point "found" in a clause that says it was NOT found
                            (W1: "Intel's gross margin could not be established" covered Intel)
    R2  wrong attribution   the right figure under the wrong accounting basis
                            (W1: the non-GAAP 75.5% reported as GAAP)
    R3  wrong comparison    correct figures, then an ordering statement they contradict
                            (W2: $350 billion ranked above $638 billion)
    R4  cited but wrong     a task with gold facts where none is found still earned grounding credit
                            (A2 scored 0.25 for "not found" plus an invented figure; D1 0.67)

v2 starts from the v1 components and applies:

    R1, R2  the fact or coverage point is not credited
    R3      quality is capped at ORDERING_CAP
    R4      quality is 0

The checks are the deterministic ones in `webswarm_baseline/guards.py`, the same code the engine's
opt-in guards use. They are still pattern matching: v2 removes credit v1 should not have given; it
does not certify that what remains is correct.
"""
from __future__ import annotations

import re

from webswarm_baseline import guards

from .grade import grade as grade_v1

ORDERING_CAP = 0.5


def _match(patterns: list[str], clauses: list[str]) -> bool:
    return any(re.search(p, c, re.I) for p in patterns for c in clauses)


def _misattributed(fact: dict, clauses: list[str]) -> bool:
    """True when every statement of this fact that can be checked carries the wrong basis label."""
    rules = fact.get("attribution") or []
    right = wrong = 0
    for clause in clauses:
        labels = guards.basis_labels(clause)
        for rule in rules:
            if re.search(rule["pattern"], clause, re.I):
                if labels and rule["basis"] not in labels:
                    wrong += 1
                else:
                    right += 1
    return wrong > 0 and right == 0


def grade_v2(task: dict, answer: str, audit: dict, evidence: dict | None = None) -> dict:
    answer = answer or ""
    v1 = grade_v1(task, answer, audit, evidence)
    clauses = guards.positive_clauses(answer.split(guards.CORRECTION_MARK)[0])
    out: dict = {"quality_v1": v1["quality"], "grounding": v1["grounding"], "rules": []}
    parts = []
    credited: list[bool] = []
    if task.get("key_facts"):
        out["not_found_credit"], out["misattributed"] = [], []
        for fact in task["key_facts"]:
            anywhere = any(re.search(p, answer, re.I) for p in fact["patterns"])
            ok = _match(fact["patterns"], clauses)
            if anywhere and not ok:
                out["not_found_credit"].append(fact["fact"])
            if ok and _misattributed(fact, clauses):
                out["misattributed"].append(fact["fact"])
                ok = False
            credited.append(ok)
        out["facts_found"] = [f["fact"] for f, ok in zip(task["key_facts"], credited) if ok]
        out["fact_recall"] = round(sum(credited) / len(credited), 3)
        parts.append(out["fact_recall"])
    if task.get("coverage"):
        hits = [_match(c["patterns"], clauses) for c in task["coverage"]]
        lost = [c["point"] for c, h in zip(task["coverage"], hits)
                if not h and any(re.search(p, answer, re.I) for p in c["patterns"])]
        out.setdefault("not_found_credit", []).extend(lost)
        out["coverage"] = round(sum(hits) / len(hits), 3)
        parts.append(out["coverage"])
    parts.append(out["grounding"])
    quality = sum(parts) / len(parts)

    ranking, metric = None, None
    if task.get("ranking") and credited:
        # only entities whose figure the answer actually gives can be ranked against each other
        order = [e for e in task["ranking"]["order"] if credited[e["fact"]]]
        ranking = [(e["names"], float(len(order) - i)) for i, e in enumerate(order)]
        metric = task["ranking"].get("metric")
    out["ordering_errors"] = guards.ordering_issues(answer, ranking, metric)

    if out.get("not_found_credit"):
        out["rules"].append("R1")
    if out.get("misattributed"):
        out["rules"].append("R2")
    if out["ordering_errors"]:
        out["rules"].append("R3")
        quality = min(quality, ORDERING_CAP)
    if credited and not any(credited):
        if v1["quality"] > 0:
            out["rules"].append("R4")
        quality = 0.0
    out["quality"] = round(quality, 3)
    return out
