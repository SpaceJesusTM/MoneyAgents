"""How much model time do bounded decisions take? An upper bound on what any fast decider can save.

    .venv/bin/python -m experiments.bench.decision_ceiling baseline_v1

Reads the traces of a result set and splits model time into:

    generative   work a typed decider cannot do: writing queries, sub-objectives, findings, answers
    bounded      choices among a few options: routing, review verdicts with no follow-up written,
                 DEEP step choices that end in "finish", and ATOM steps whose outcome was "read
                 result N" or "finish" (the model chose; it did not write anything that was used)

If every bounded decision were made instantly and identically, the run would be shorter by the
bounded share and no more. That is the ceiling for Jev, for a small local model, and for rules.
The projection for Jev multiplies the number of decisions by the latency range TypeSafe states
(70-500 ms). It is arithmetic on a vendor claim, NOT a measurement of Jev.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from webswarm_baseline.config import REPO_ROOT

RESULTS = Path(__file__).resolve().parent.parent / "results"
JEV_STATED_LATENCY = (0.07, 0.5)   # seconds per request, from the Jev announcement post


def split_trace(events: list[dict]) -> dict:
    secs, calls = Counter(), Counter()
    pending_act: dict = {}
    for e in events:
        t = e["type"]
        if t == "llm_call":
            kind = e["kind"]
            if kind == "act":
                pending_act[e["node"]] = e          # classified when we see what the step did
            elif kind == "route":
                secs["bounded:route"] += e["secs"]; calls["bounded:route"] += 1
            elif kind in ("review", "deep_step"):
                pending_act[(e["node"], kind)] = e
            else:
                secs["generative:" + kind] += e["secs"]; calls["generative:" + kind] += 1
        elif t == "atom_action" and e["node"] in pending_act:
            call = pending_act.pop(e["node"])
            if e.get("provider") == "guard":         # the model's output was discarded and repaired
                key = "wasted:act_repaired"
            elif e["action"] == "search":
                key = "generative:act_query"
            else:
                key = "bounded:act_" + e["action"]
            secs[key] += call["secs"]; calls[key] += 1
        elif t == "decision" and e["point"] in ("review", "deep_step") and (e["node"], e["point"]) in pending_act:
            call = pending_act.pop((e["node"], e["point"]))
            wrote_text = (e["point"] == "review" and e["value"] == "follow_up") or \
                         (e["point"] == "deep_step" and e["value"] in ("investigate", "verify"))
            key = ("generative:" if wrote_text else "bounded:") + e["point"]
            secs[key] += call["secs"]; calls[key] += 1
    for call in pending_act.values():                # failed or unpaired calls
        secs["wasted:failed_or_unused"] += call["secs"]; calls["wasted:failed_or_unused"] += 1
    return {"secs": secs, "calls": calls}


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "baseline_v1"
    arm = sys.argv[2] if len(sys.argv) > 2 else "baseline"
    rows = [json.loads(line) for line in (RESULTS / name / "results.jsonl").read_text().splitlines() if line.strip()]
    rows = [r for r in rows if r["arm"] == arm and r.get("run_dir")]
    total_secs, total_calls = Counter(), Counter()
    per_task = {}
    for r in rows:
        events = [json.loads(line) for line in (REPO_ROOT / r["run_dir"] / "trace.jsonl").read_text().splitlines()]
        s = split_trace(events)
        total_secs.update(s["secs"]); total_calls.update(s["calls"])
        model = sum(s["secs"].values())
        bounded = sum(v for k, v in s["secs"].items() if k.startswith("bounded:"))
        n_bounded = sum(v for k, v in s["calls"].items() if k.startswith("bounded:"))
        per_task[r["task"]] = (r["answer_seconds"], model, bounded, n_bounded)

    grand = sum(total_secs.values())
    by_class = defaultdict(float)
    for k, v in total_secs.items():
        by_class[k.split(":")[0]] += v
    print(f"Result set {name!r}, arm {arm!r}: {len(rows)} runs, {grand:.0f} s of model time\n")
    print("| Where model time went | Calls | Seconds | Share |\n|---|---:|---:|---:|")
    for k, v in sorted(total_secs.items(), key=lambda x: (x[0].split(':')[0], -x[1])):
        print(f"| {k} | {total_calls[k]} | {v:.0f} | {100 * v / grand:.1f}% |")
    print()
    for c in ("generative", "bounded", "wasted"):
        print(f"- {c}: {by_class[c]:.0f} s = {100 * by_class[c] / grand:.1f}% of model time")
    n_dec = sum(v for k, v in total_calls.items() if k.startswith("bounded:"))
    lo, hi = (n_dec * x for x in JEV_STATED_LATENCY)
    print(f"\nCeiling: a decider that made all {n_dec} bounded decisions instantly, with the same outcomes, "
          f"would remove at most {by_class['bounded']:.0f} s ({100 * by_class['bounded'] / grand:.1f}%) of model time.")
    print(f"Projection (vendor-stated latency, NOT measured): the same {n_dec} decisions at 70-500 ms each would "
          f"cost {lo:.0f}-{hi:.0f} s, a net saving of at most "
          f"{100 * (by_class['bounded'] - hi) / grand:.1f}%-{100 * (by_class['bounded'] - lo) / grand:.1f}% of model time, "
          "if its decisions were as good as the 4B model's.")
    print("\n| Task | Time to answer (s) | Model time (s) | Bounded-decision time (s) | Bounded share | Decisions |")
    print("|---|---:|---:|---:|---:|---:|")
    for t, (ans, model, bounded, n) in per_task.items():
        print(f"| {t} | {ans:.0f} | {model:.0f} | {bounded:.0f} | {100 * bounded / model if model else 0:.0f}% | {n} |")


if __name__ == "__main__":
    main()
