"""Run benchmark tasks under one or more experiment arms and record graded results.

    .venv/bin/python -m experiments.bench.run_bench --name baseline_v1 --arms baseline
    .venv/bin/python -m experiments.bench.run_bench --name compare_v1 --arms baseline rules local_s1_4b --order task
    .venv/bin/python -m experiments.bench.run_bench --name smoke --arms baseline --tasks A1

Fairness measures:
  - every arm is the frozen baseline config plus that arm's overrides (arms.json);
  - web responses are shared through a per-task cassette: the first run to issue a search or fetch
    records it, later runs get the identical response AND sleep for the recorded latency;
  - `--order task` runs all arms on one task before moving on, rotating which arm goes first, so
    thermal slowdown on this fanless laptop is spread across arms instead of landing on the last;
  - each row stores token counts and `ref_model_seconds` (tokens at fixed reference speeds), a
    time measure that does not depend on how hot the machine was.

Results append to experiments/results/<name>/results.jsonl; finished (task, arm, repeat) rows are
skipped on re-run, so an interrupted benchmark resumes where it stopped.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from webswarm_baseline.config import REPO_ROOT, SwarmConfig
from webswarm_baseline.run import BASELINE_CONFIG, execute

from .grade import grade

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
CASSETTES = HERE / "cassettes"
REF_PROMPT_TPS, REF_GEN_TPS = 300.0, 25.0   # reference speeds for the hardware-independent time measure

KEEP = ["answer_seconds", "wall_seconds", "time_to_first_evidence", "time_to_first_page_evidence",
        "llm_calls", "llm_calls_by_kind", "llm_failed_calls", "llm_seconds", "llm_queue_wait_seconds",
        "prompt_tokens", "output_tokens", "llm_prompt_eval_seconds", "llm_generation_seconds",
        "decision_calls", "decision_seconds", "decision_prompt_tokens", "decisions",
        "searches", "fetches", "web_calls", "fetch_failures", "search_failures", "web_seconds",
        "web_from_cassette", "nodes", "nodes_by_mode", "nodes_by_status", "max_depth", "findings",
        "findings_from_pages", "findings_rejected", "sources", "redundancy", "interventions", "budget_hits"]


def load_tasks() -> dict:
    return {t["id"]: t for t in json.loads((HERE / "tasks.json").read_text())["tasks"]}


def load_arms() -> dict:
    return json.loads((HERE / "arms.json").read_text())["arms"]


def arm_config(arm: str, spec: dict, task_id: str, use_cassette: bool) -> SwarmConfig:
    cfg = SwarmConfig.load(BASELINE_CONFIG).override(spec.get("overrides", []))
    cfg.name = arm
    if use_cassette:
        cfg.web_mode = "replay_or_record"
        cfg.cassette = str(CASSETTES / task_id)
    return cfg


def run_one(task: dict, arm: str, spec: dict, repeat: int, out_dir: Path, use_cassette: bool) -> dict:
    cfg = arm_config(arm, spec, task["id"], use_cassette)
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    t0 = time.perf_counter()
    row = {"task": task["id"], "type": task["type"], "stability": task["stability"], "arm": arm,
           "repeat": repeat, "started": started}
    try:
        art = execute(task["question"], cfg, echo=False, out_dir=out_dir / "runs")
    except Exception as e:  # noqa: BLE001 - a crashed run is a result, not a reason to stop the benchmark
        row.update(error=f"{type(e).__name__}: {e}"[:300], answer="", quality=0.0,
                   answer_seconds=round(time.perf_counter() - t0, 1))
        return row
    s = art.stats
    row.update({k: s.get(k) for k in KEEP})
    row.update(status=art.outcome["status"], confidence=art.outcome["confidence"], answer=art.outcome["answer"],
               audit=art.outcome.get("audit") or {}, run_dir=str(art.path.relative_to(REPO_ROOT)) if art.path else "")
    row.update(grade(task, art.outcome["answer"], art.outcome.get("audit") or {}, art.swarm.evidence.snapshot()))
    row["ref_model_seconds"] = round(((s.get("prompt_tokens") or 0) + (s.get("decision_prompt_tokens") or 0))
                                     / REF_PROMPT_TPS + (s.get("output_tokens") or 0) / REF_GEN_TPS, 1)
    gen, gsec = s.get("output_tokens") or 0, s.get("llm_generation_seconds") or 0
    row["observed_gen_tps"] = round(gen / gsec, 1) if gsec else None
    return row


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", required=True, help="result set name (directory under experiments/results)")
    ap.add_argument("--arms", nargs="+", default=["baseline"])
    ap.add_argument("--tasks", nargs="*", default=None, help="task ids (default: all, limited by each arm's subset)")
    ap.add_argument("--order", choices=["task", "arm"], default="task")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--pause", type=float, default=15.0, help="seconds to idle between runs (lets the laptop cool)")
    ap.add_argument("--no-cassette", action="store_true", help="always hit the live web (no record/replay)")
    args = ap.parse_args()

    tasks, arms = load_tasks(), load_arms()
    for a in args.arms:
        if a not in arms:
            raise SystemExit(f"unknown arm {a!r}; available: {sorted(arms)}")
    ids = args.tasks or list(tasks)
    out_dir = RESULTS / args.name
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "results.jsonl"
    done = set()
    if path.exists():
        done = {(r["task"], r["arm"], r["repeat"]) for r in map(json.loads, path.read_text().splitlines()) if r}

    def wanted(arm: str, tid: str) -> bool:
        sub = arms[arm].get("subset")
        return sub is None or tid in sub

    jobs = []
    for rep in range(args.repeats):
        if args.order == "task":
            for i, tid in enumerate(ids):
                rot = args.arms[i % len(args.arms):] + args.arms[:i % len(args.arms)]
                jobs += [(tid, a, rep) for a in rot if wanted(a, tid)]
        else:
            jobs += [(tid, a, rep) for a in args.arms for tid in ids if wanted(a, tid)]
    jobs = [j for j in jobs if j not in done]
    print(f"{len(jobs)} runs to do ({len(done)} already recorded) -> {path}", flush=True)

    for n, (tid, arm, rep) in enumerate(jobs, 1):
        row = run_one(tasks[tid], arm, arms[arm], rep, out_dir, not args.no_cassette)
        with path.open("a") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
        print(f"[{n}/{len(jobs)}] {datetime.now():%H:%M:%S} {tid:3} {arm:14} "
              f"t={row.get('answer_seconds')}s q={row.get('quality')} facts={row.get('fact_recall')} "
              f"cov={row.get('coverage')} ground={row.get('grounding')} llm={row.get('llm_calls')} "
              f"dec={row.get('decision_calls')} web={row.get('web_calls')} nodes={row.get('nodes')} "
              f"tps={row.get('observed_gen_tps')} hits={row.get('budget_hits')} {row.get('error', '')}", flush=True)
        if n < len(jobs):
            time.sleep(args.pause)
    print("done", flush=True)


if __name__ == "__main__":
    main()
