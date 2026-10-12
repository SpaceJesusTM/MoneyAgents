"""Re-grade recorded benchmark answers with the v2 grader, without touching the recorded results.

    .venv/bin/python -m experiments.bench.regrade                 # every result set
    .venv/bin/python -m experiments.bench.regrade baseline_v1     # chosen sets

Reads experiments/results/<set>/results.jsonl (read-only) and writes two new files under
experiments/results/regrade_v2/: `regrade.jsonl` (one row per recorded run) and `summary.md`.
For every row it also recomputes the v1 score and checks that it equals the stored one, which is
the evidence that the v1 grader and the task definitions it reads have not changed.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from .grade import grade as grade_v1
from .grade_v2 import ORDERING_CAP, grade_v2
from .run_bench import RESULTS, load_tasks

OUT = RESULTS / "regrade_v2"
RULES = {"R1": "credit for something the answer says was not found",
         "R2": "right figure, wrong accounting basis",
         "R3": f"ordering statement contradicted by the figures (quality capped at {ORDERING_CAP})",
         "R4": "no gold fact found, yet v1 gave credit for citations (quality 0)"}


def main() -> None:
    wanted = sys.argv[1:]
    tasks = load_tasks()
    rows, drift = [], 0
    for path in sorted(RESULTS.glob("*/results.jsonl")):
        name = path.parent.name
        if name == OUT.name or name.startswith("smoke") or (wanted and name not in wanted):
            continue
        if name.startswith("reliability") and not wanted:
            continue          # runs made with the guards on are reported on their own, not mixed into the history
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            task = tasks[r["task"]]
            answer, audit = r.get("answer") or "", r.get("audit") or {}
            again = grade_v1(task, answer, audit)["quality"]
            if "error" not in r and abs(again - (r.get("quality") or 0.0)) > 1e-9:
                drift += 1
            v2 = grade_v2(task, answer, audit)
            rows.append({"set": name, "task": r["task"], "arm": r["arm"], "repeat": r.get("repeat", 0),
                         "confidence": r.get("confidence"), "quality_v1_recorded": r.get("quality"),
                         "quality_v1_recomputed": again, "quality_v2": v2["quality"], "rules": v2["rules"],
                         "fact_recall_v2": v2.get("fact_recall"), "coverage_v2": v2.get("coverage"),
                         "misattributed": v2.get("misattributed", []), "not_found_credit": v2.get("not_found_credit", []),
                         "ordering_errors": [e["detail"] for e in v2["ordering_errors"]]})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "regrade.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))

    def mean(xs):
        xs = [x for x in xs if x is not None]
        return sum(xs) / len(xs) if xs else float("nan")

    by_arm, by_task, by_rule = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in rows:
        by_arm[r["arm"]].append(r)
        if r["arm"] == "baseline":
            by_task[r["task"]].append(r)
        for rule in r["rules"]:
            by_rule[rule].append(r)
    md = ["# Recorded runs re-graded with the v2 grader", "",
          f"{len(rows)} recorded runs from {len({r['set'] for r in rows})} result sets. The recorded results are "
          "unchanged; this file and `regrade.jsonl` are the only outputs.",
          f"Stored v1 scores that differ from a fresh v1 computation: **{drift}** (0 means the v1 grader and the "
          "task fields it reads are as they were).", "",
          "## What v2 changes", ""]
    md += [f"- **{k}** ({v}): {len(by_rule[k])} runs" for k, v in RULES.items()]
    md += ["", "## Baseline, per task (mean over its recorded runs)", "",
           "| Task | Runs | v1 quality | v2 quality | Rules that fired |", "|---|---:|---:|---:|---|"]
    for t in tasks:
        rs = by_task.get(t, [])
        if rs:
            fired = sorted({x for r in rs for x in r["rules"]})
            md.append(f"| {t} | {len(rs)} | {mean([r['quality_v1_recorded'] for r in rs]):.2f} | "
                      f"{mean([r['quality_v2'] for r in rs]):.2f} | {', '.join(fired) or '-'} |")
    md += ["", "## Per arm (all recorded runs of that arm)", "",
           "| Arm | Runs | Mean v1 quality | Mean v2 quality | Runs changed by v2 |", "|---|---:|---:|---:|---:|"]
    for arm, rs in sorted(by_arm.items(), key=lambda kv: -len(kv[1])):
        changed = sum(1 for r in rs if abs((r["quality_v1_recorded"] or 0) - r["quality_v2"]) > 1e-9)
        md.append(f"| `{arm}` | {len(rs)} | {mean([r['quality_v1_recorded'] for r in rs]):.2f} | "
                  f"{mean([r['quality_v2'] for r in rs]):.2f} | {changed} |")
    md += ["", "Arms ran different numbers and subsets of tasks, so the per-arm means are not comparable with "
               "each other; compare each arm's v1 and v2 columns.", "",
           "## Every run whose score changed", "",
           "| Set | Task | Arm | v1 | v2 | Why |", "|---|---|---|---:|---:|---|"]
    for r in rows:
        if abs((r["quality_v1_recorded"] or 0) - r["quality_v2"]) > 1e-9:
            why = "; ".join(filter(None, [
                ("wrong basis: " + ", ".join(r["misattributed"])) if r["misattributed"] else "",
                ("not-found credit: " + ", ".join(r["not_found_credit"])) if r["not_found_credit"] else "",
                ("ordering: " + r["ordering_errors"][0]) if r["ordering_errors"] else "",
                "no gold fact found" if "R4" in r["rules"] else ""]))
            md.append(f"| {r['set']} | {r['task']} | `{r['arm']}` | {r['quality_v1_recorded']:.2f} | "
                      f"{r['quality_v2']:.2f} | {why} |")
    (OUT / "summary.md").write_text("\n".join(md) + "\n")
    print(f"{len(rows)} runs re-graded -> {OUT / 'summary.md'} (v1 drift: {drift})")


if __name__ == "__main__":
    main()
