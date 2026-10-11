"""Automatic grading of one run against its task definition. No model involved.

Three components, each in [0, 1]:

    fact_recall   share of the task's gold facts found in the final answer        (stable tasks)
    coverage      share of the task's expected dimensions the answer touches      (tasks that list them)
    grounding     1.0  answer cites sources and every figure is found in retrieved text
                  0.5  answer cites sources but some figure is not in any retrieved text
                  0.0  answer has no valid citation (or there is no answer)

`quality` is the mean of the components the task defines. These are proxies: pattern matching can
miss a correct paraphrase and cannot see a wrong claim that happens to sit next to a right one.
They are consistent across arms, which is what the comparison needs; they are not a substitute for
reading the answers (see the manual notes in the results files).

QUALITY TOLERANCE, fixed before any arm was compared: an arm "preserves quality" if its mean
quality is within 0.05 of the baseline's on the same tasks AND it loses no gold fact that the
baseline found on a stable task.
"""
from __future__ import annotations

import re

QUALITY_TOLERANCE = 0.05


def _hits(items: list[dict], text: str) -> list[bool]:
    return [any(re.search(p, text, re.I) for p in it["patterns"]) for it in items]


def grade(task: dict, answer: str, audit: dict, evidence: dict | None = None) -> dict:
    answer = answer or ""
    out: dict = {"answered": bool(answer.strip())}
    parts = []
    if task.get("key_facts"):
        hits = _hits(task["key_facts"], answer)
        out["facts_found"] = [f["fact"] for f, h in zip(task["key_facts"], hits) if h]
        out["facts_missed"] = [f["fact"] for f, h in zip(task["key_facts"], hits) if not h]
        out["fact_recall"] = round(sum(hits) / len(hits), 3)
        parts.append(out["fact_recall"])
        if evidence is not None:   # was the fact retrieved even if the answer dropped it?
            pool = " ".join(f"{f['claim']} {f['quote']}" for f in evidence.get("findings", []))
            ev = _hits(task["key_facts"], pool)
            out["fact_recall_in_evidence"] = round(sum(ev) / len(ev), 3)
    if task.get("coverage"):
        hits = _hits(task["coverage"], answer)
        out["coverage_missed"] = [c["point"] for c, h in zip(task["coverage"], hits) if not h]
        out["coverage"] = round(sum(hits) / len(hits), 3)
        parts.append(out["coverage"])
    cites = (audit or {}).get("citations", 0) - len((audit or {}).get("unknown_citations", []))
    ungrounded = (audit or {}).get("numbers_ungrounded", 0)
    out["grounding"] = 0.0 if (cites <= 0 or not out["answered"]) else (1.0 if ungrounded == 0 else 0.5)
    parts.append(out["grounding"])
    out["quality"] = round(sum(parts) / len(parts), 3)
    domains = set((audit or {}).get("cited_domains", []))
    auth = task.get("authoritative", [])
    out["cites_authoritative_source"] = any(d == a or d.endswith("." + a) or a in d for d in domains for a in auth)
    return out
