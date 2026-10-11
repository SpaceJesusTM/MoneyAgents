"""CLI entry point.

    .venv/bin/python one_shot_webswarm_prototype/run.py "your research objective"
    .venv/bin/python one_shot_webswarm_prototype/run.py --batch one_shot_webswarm_prototype/examples.txt
    .venv/bin/python one_shot_webswarm_prototype/run.py --mock          # no LM Studio needed
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from config import EXPERIMENT_DIR, Limits, load_settings
from llm import LMStudioLLM, MockLLM
from render import compute_stats, format_stats, render_tree, save_run
from swarm import run_swarm

DEFAULT_OBJECTIVE = ("What are the main factors that could affect NVIDIA's data-center revenue growth "
                     "over the next 12 months?")


def run_one(objective: str, args, settings) -> dict:
    llm = MockLLM() if args.mock else LMStudioLLM(settings)
    llm.check_connection()
    limits = Limits(args.max_depth, args.max_children, args.max_nodes)
    print("=" * 100)
    print(f"ROOT OBJECTIVE: {objective}")
    print(f"model={'MOCK' if args.mock else settings.model}  limits={limits}  synthesis={not args.no_synthesis}")
    print("=" * 100)

    t0 = time.perf_counter()
    nodes = run_swarm(objective, llm, limits, synthesize=not args.no_synthesis)
    stats = compute_stats(nodes, llm.calls, time.perf_counter() - t0)

    print("\n=== delegation tree ===")
    print(render_tree(nodes, show_reasoning=not args.hide_reasoning))
    print("\n=== stats ===")
    print(format_stats(stats))
    if nodes[0].get("answer"):
        print("\n=== root answer (unverified; model knowledge only) ===")
        print(nodes[0]["answer"])

    meta = {"model": "MOCK" if args.mock else settings.public(), "limits": vars(limits),
            "synthesis": not args.no_synthesis}
    base = save_run(Path(args.out), objective, nodes, llm.calls, stats, meta)
    print(f"\nsaved: {base}.json / .txt")
    return {"objective": objective, "root_mode": nodes[0]["mode"], **stats}


def main() -> None:
    ap = argparse.ArgumentParser(description="One-shot WebSwarm-inspired ATOM/DEEP/WIDE delegation prototype")
    ap.add_argument("objective", nargs="?", default=DEFAULT_OBJECTIVE)
    ap.add_argument("--batch", help="file with one objective per line (# comments allowed)")
    ap.add_argument("--max-depth", type=int, default=3)
    ap.add_argument("--max-children", type=int, default=4)
    ap.add_argument("--max-nodes", type=int, default=25)
    ap.add_argument("--no-synthesis", action="store_true", help="only build the tree; skip bottom-up answers")
    ap.add_argument("--hide-reasoning", action="store_true", help="omit 'why:' lines from the printed tree")
    ap.add_argument("--mock", action="store_true", help="scripted fake LLM to test plumbing (no LM Studio)")
    ap.add_argument("--out", default=str(EXPERIMENT_DIR / "runs"))
    args = ap.parse_args()

    settings = load_settings()
    if args.batch:
        lines = Path(args.batch).read_text().splitlines()
        objectives = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
    else:
        objectives = [args.objective]

    summaries = [run_one(o, args, settings) for o in objectives]
    if len(summaries) > 1:
        print("\n=== batch summary ===")
        print(f"{'root':5} {'nodes':>5} {'depth':>5} {'secs':>7}  objective")
        for s in summaries:
            print(f"{s['root_mode']:5} {s['nodes']:>5} {s['max_depth_reached']:>5} {s['wall_seconds']:>7}  {s['objective'][:70]}")


if __name__ == "__main__":
    main()
