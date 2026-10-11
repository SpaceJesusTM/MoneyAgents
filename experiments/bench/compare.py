"""Turn benchmark results into comparison tables (markdown).

    .venv/bin/python -m experiments.bench.compare compare_v1
    .venv/bin/python -m experiments.bench.compare baseline_v1 compare_v1 --baseline baseline

Comparisons against the baseline are PAIRED: an arm is compared only on the tasks both ran, and the
time ratio is the median of per-task ratios, so one slow task cannot dominate. When a result set
contains several baseline rows for a task (repeats), their mean is the reference and their spread
is reported as the noise floor.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

from .grade import QUALITY_TOLERANCE

RESULTS = Path(__file__).resolve().parent.parent / "results"


def load(names: list[str]) -> list[dict]:
    rows = []
    for n in names:
        p = RESULTS / n / "results.jsonl"
        rows += [dict(json.loads(line), result_set=n) for line in p.read_text().splitlines() if line.strip()]
    return rows


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(st.mean(xs), 3) if xs else None


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 1) if xs else None


def fmt(x, nd=1):
    return "-" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def summary_table(rows: list[dict]) -> str:
    by = defaultdict(list)
    for r in rows:
        by[r["arm"]].append(r)
    out = ["| Arm | Runs | Quality | Fact recall | Coverage | Grounding | Median time (s) | Median first evidence (s) | "
           "Model calls | Decision calls | Web calls | Agents | Ref. model time (s) |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for arm, rs in by.items():
        out.append("| " + " | ".join([
            arm, str(len(rs)), fmt(mean(r.get("quality") for r in rs), 2), fmt(mean(r.get("fact_recall") for r in rs), 2),
            fmt(mean(r.get("coverage") for r in rs), 2), fmt(mean(r.get("grounding") for r in rs), 2),
            fmt(med(r.get("answer_seconds") for r in rs)), fmt(med(r.get("time_to_first_evidence") for r in rs)),
            fmt(mean(r.get("llm_calls") for r in rs)), fmt(mean(r.get("decision_calls") for r in rs)),
            fmt(mean(r.get("web_calls") for r in rs)), fmt(mean(r.get("nodes") for r in rs)),
            fmt(mean(r.get("ref_model_seconds") for r in rs))]) + " |")
    return "\n".join(out)


def paired_table(rows: list[dict], baseline: str) -> str:
    per = defaultdict(lambda: defaultdict(list))
    for r in rows:
        per[r["arm"]][r["task"]].append(r)
    if baseline not in per:
        return f"(no rows for baseline arm {baseline!r})"

    def avg(arm, task, key):
        return mean(r.get(key) for r in per[arm][task])

    out = [f"Paired against `{baseline}` on shared tasks. Time and model-time ratios below 1.00 mean faster.",
           "",
           "| Arm | Shared tasks | Time ratio (median) | Ref. model-time ratio | First-evidence ratio | Model calls | "
           "Web calls | Quality (arm / base) | Gold facts lost | Preserves quality? |",
           "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    for arm in per:
        if arm == baseline:
            continue
        shared = [t for t in per[arm] if t in per[baseline]]
        if not shared:
            continue

        def ratio(key):
            rs = [avg(arm, t, key) / avg(baseline, t, key) for t in shared
                  if avg(arm, t, key) is not None and avg(baseline, t, key)]
            return round(st.median(rs), 2) if rs else None

        qa, qb = mean(avg(arm, t, "quality") for t in shared), mean(avg(baseline, t, "quality") for t in shared)
        lost = 0
        for t in shared:
            base_found = set().union(*[set(r.get("facts_found") or []) for r in per[baseline][t]])
            arm_found = set().union(*[set(r.get("facts_found") or []) for r in per[arm][t]])
            lost += len(base_found - arm_found)
        keeps = (qa is not None and qb is not None and qa >= qb - QUALITY_TOLERANCE and lost == 0)
        out.append("| " + " | ".join([
            arm, str(len(shared)), fmt(ratio("answer_seconds"), 2), fmt(ratio("ref_model_seconds"), 2),
            fmt(ratio("time_to_first_evidence"), 2),
            f"{fmt(mean(avg(arm, t, 'llm_calls') for t in shared))} / {fmt(mean(avg(baseline, t, 'llm_calls') for t in shared))}",
            f"{fmt(mean(avg(arm, t, 'web_calls') for t in shared))} / {fmt(mean(avg(baseline, t, 'web_calls') for t in shared))}",
            f"{fmt(qa, 2)} / {fmt(qb, 2)}", str(lost), "yes" if keeps else "NO"]) + " |")
    return "\n".join(out)


def per_task_table(rows: list[dict]) -> str:
    arms = list(dict.fromkeys(r["arm"] for r in rows))
    tasks = list(dict.fromkeys(r["task"] for r in rows))
    cell = defaultdict(list)
    for r in rows:
        cell[(r["task"], r["arm"])].append(r)
    out = ["Each cell: time to answer (s) / quality / agents. `!` marks a budget limit hit.", "",
           "| Task | " + " | ".join(arms) + " |", "|---|" + "---|" * len(arms)]
    for t in tasks:
        cells = []
        for a in arms:
            rs = cell.get((t, a))
            if not rs:
                cells.append("")
                continue
            hit = "!" if any(set(r.get("budget_hits") or []) - {"wrap_up"} for r in rs) else ""
            cells.append(f"{fmt(mean(r.get('answer_seconds') for r in rs), 0)} / "
                         f"{fmt(mean(r.get('quality') for r in rs), 2)} / {fmt(mean(r.get('nodes') for r in rs), 0)}{hit}")
        out.append(f"| {t} | " + " | ".join(cells) + " |")
    return "\n".join(out)


def noise_floor(rows: list[dict], baseline: str) -> str:
    per = defaultdict(list)
    for r in rows:
        if r["arm"] == baseline and r.get("answer_seconds"):
            per[r["task"]].append(r)
    lines = []
    for t, rs in per.items():
        if len(rs) > 1:
            ts = [r["answer_seconds"] for r in rs]
            ms = [r.get("ref_model_seconds") for r in rs]
            lines.append(f"- {t}: {len(rs)} baseline runs, time {min(ts):.0f}-{max(ts):.0f} s "
                         f"(spread {100 * (max(ts) - min(ts)) / st.mean(ts):.0f}%), "
                         f"ref. model time {min(ms):.0f}-{max(ms):.0f} s, "
                         f"quality {min(r['quality'] for r in rs)}-{max(r['quality'] for r in rs)}")
    return "\n".join(lines) or "(only one baseline run per task: no run-to-run spread available)"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="+")
    ap.add_argument("--baseline", default="baseline")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    rows = load(args.names)
    text = "\n\n".join(["### Per-arm summary (each arm on the tasks it ran)", summary_table(rows),
                        "### Paired comparison with the baseline", paired_table(rows, args.baseline),
                        "### Baseline run-to-run spread", noise_floor(rows, args.baseline),
                        "### Per task", per_task_table(rows)])
    print(text)
    if args.out:
        Path(args.out).write_text(text + "\n")


if __name__ == "__main__":
    main()
