"""Side-by-side table for runs that differ only in the research model, with the two things a model
comparison cannot be read without: where each run's evidence came from, and what memory did.

    .venv/bin/python -m experiments.bench.model_table model_compare_v1

Evidence columns per run: searches replayed from the shared recording / answered live / not answered.
Two runs whose searches were all replayed saw the same search results; a run with live searches saw
results the other model never did, and a run with unanswered searches was simply short of evidence.
The table says which, so that a difference in answers is not blamed on the model when it is retrieval.
"""
from __future__ import annotations

import csv
import json
import sys

from .run_bench import RESULTS


def memory(path) -> dict:
    try:
        rows = list(csv.DictReader(open(path)))
    except OSError:
        return {}
    if not rows:
        return {}
    f = lambda k: [float(r[k]) for r in rows if r.get(k) not in (None, "", "None")]   # noqa: E731
    swap, po, so, rss, free = f("swap_used_mb"), f("pageouts"), f("swapouts"), f("runner_rss_mb"), f("free_pct")
    return {"samples": len(rows), "runner_peak_mb": int(max(rss)) if rss else None,
            "swap_start_mb": int(swap[0]), "swap_peak_mb": int(max(swap)), "swap_end_mb": int(swap[-1]),
            "pageouts": int(po[-1] - po[0]) if po else None, "swapouts": int(so[-1] - so[0]) if so else None,
            "free_pct_min": int(min(free)) if free else None, "minutes": round(len(rows) * 5 / 60, 1)}


def main() -> None:
    name = sys.argv[1]
    rows = [json.loads(line) for line in (RESULTS / name / "results.jsonl").read_text().splitlines() if line.strip()]
    arms = list(dict.fromkeys(r["arm"] for r in rows))
    tasks = list(dict.fromkeys(r["task"] for r in rows))
    by = {(r["task"], r["arm"]): r for r in rows}
    print(f"# {name}\n")
    print("| Task | Arm | Model | v1 / v2 | Status, confidence | Model calls | Prompt / output tokens | Time to answer | "
          "Model work | Searches: replayed / live / unanswered | Pages: replayed / live / unanswered | Limits hit |")
    print("|---|---|---|---|---|---:|---|---:|---:|---|---|---|")
    for t in tasks:
        for a in arms:
            r = by.get((t, a))
            if not r:
                continue
            p = r.get("web_provenance") or {}
            s, f = p.get("search", {}), p.get("fetch", {})
            model = json.loads(open(r["run_dir"] + "/run.json").read())["config"]["model"] if r.get("run_dir") else "?"
            work = (r.get("llm_generation_seconds") or 0) + (r.get("llm_prompt_eval_seconds") or 0)
            print(f"| {t} | `{a}` | {model.split(':')[1].split('-')[0]} | {r.get('quality')} / {(r.get('v2') or {}).get('quality')} | "
                  f"{r.get('status')}, {r.get('confidence')} | {r.get('llm_calls')} | {r.get('prompt_tokens')} / {r.get('output_tokens')} | "
                  f"{r.get('answer_seconds')} s | {work:.0f} s | {s.get('replayed')} / {s.get('live')} / {s.get('no_answer')} | "
                  f"{f.get('replayed')} / {f.get('live')} / {f.get('no_answer')} | {', '.join(r.get('budget_hits') or []) or '-'} |")
    print("\n## Memory (sampled every 5 s; swap is system-wide)\n")
    print("| Arm | Minutes sampled | Runner peak | Swap start / peak / end (MB) | Pageouts | Swapouts | Lowest free memory |")
    print("|---|---:|---:|---|---:|---:|---:|")
    for label in ("4b", "9b"):
        m = memory(RESULTS / name / f"memory_{label}.csv")
        if m:
            print(f"| {label} | {m['minutes']} | {m['runner_peak_mb']} MB | {m['swap_start_mb']} / {m['swap_peak_mb']} / "
                  f"{m['swap_end_mb']} | {m['pageouts']} | {m['swapouts']} | {m['free_pct_min']}% |")


if __name__ == "__main__":
    main()
