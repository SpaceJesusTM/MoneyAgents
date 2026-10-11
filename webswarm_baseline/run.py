"""Command-line entry point and the `execute()` function used by tests and benchmarks.

    .venv/bin/python -m webswarm_baseline.run "your research question"
    .venv/bin/python -m webswarm_baseline.run --mock            # scripted plumbing check, no model/web
    .venv/bin/python -m webswarm_baseline.run "..." --set web_probing=true --set budgets.max_nodes=8
"""
from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

from .config import PACKAGE_DIR, SwarmConfig
from .decisions import load_decider
from .evidence import EvidenceStore
from .llm import OllamaLLM
from .report import compute_stats, format_stats, make_echo, manifest, render_report, save_run
from .runtime import Budget, LLMGate, Tracer
from .swarm import Swarm
from .web import WebClient

DEFAULT_QUESTION = ("What are the main factors that could affect NVIDIA's data-center revenue growth "
                    "over the next 12 months?")
BASELINE_CONFIG = PACKAGE_DIR / "configs" / "baseline.json"


@dataclass
class RunArtifacts:
    question: str
    outcome: dict
    stats: dict
    swarm: Swarm
    tracer: Tracer
    cfg: SwarmConfig
    path: Path | None = None


def execute(question: str, cfg: SwarmConfig, *, echo: bool = True, verbose: bool = False,
            out_dir: str | Path | None = None, llm_factory=None, web_kwargs: dict | None = None,
            decider=None) -> RunArtifacts:
    """Run one research question end to end. `llm_factory`/`web_kwargs` are test hooks."""
    ref: dict = {}
    tracer = Tracer(echo=make_echo(ref, verbose) if echo else None)
    budget = Budget(cfg.budgets, tracer)
    gate = LLMGate(cfg.llm_concurrency, cfg.scheduler)
    llm = llm_factory(cfg, tracer, budget, gate) if llm_factory else OllamaLLM(cfg, tracer, budget, gate)
    llm.check()
    web = WebClient(cfg, tracer, budget, **(web_kwargs or {}))
    evidence = EvidenceStore(tracer)
    swarm = Swarm(cfg, llm, web, tracer, budget, evidence, decider or load_decider(cfg.decider, cfg.decider_options))
    ref["swarm"] = swarm
    t0 = time.perf_counter()
    outcome = swarm.run(question)
    wall = time.perf_counter() - t0
    stats = compute_stats(tracer, swarm, budget, wall)
    art = RunArtifacts(question, outcome, stats, swarm, tracer, cfg)
    if out_dir:
        meta = manifest(cfg) if not llm_factory else {"scripted_llm": True}
        art.path = save_run(Path(out_dir), question, outcome, swarm, tracer, stats, cfg, meta)
    return art


def main() -> None:
    ap = argparse.ArgumentParser(description="WebSwarm-inspired recursive web research (local Ollama model)")
    ap.add_argument("question", nargs="?", default=DEFAULT_QUESTION)
    ap.add_argument("--config", default=str(BASELINE_CONFIG), help="JSON config (default: frozen baseline)")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="override a config value, e.g. --set web_probing=true --set budgets.max_nodes=8")
    ap.add_argument("--out", default=str(PACKAGE_DIR / "runs"), help="directory for run artifacts")
    ap.add_argument("--quiet", action="store_true", help="no live log")
    ap.add_argument("--verbose", action="store_true", help="also log every model call and finding")
    ap.add_argument("--mock", action="store_true",
                    help="SCRIPTED model and canned web pages: checks the plumbing only, proves nothing about quality")
    args = ap.parse_args()

    cfg = SwarmConfig.load(args.config) if Path(args.config).exists() else SwarmConfig()
    cfg = cfg.override(args.set)
    extra = {}
    if args.mock:
        from .mock import mock_setup
        cfg, extra = mock_setup(cfg)
        print("=" * 100 + "\nMOCK RUN: scripted model + canned web pages. Output is NOT research.\n" + "=" * 100)

    print(f"QUESTION: {args.question}")
    print(f"config={cfg.name} model={cfg.model} decider={cfg.decider} review={cfg.review_policy} "
          f"probing={cfg.web_probing} web={cfg.web_mode} budgets={cfg.budgets}\n")
    art = execute(args.question, cfg, echo=not args.quiet, verbose=args.verbose, out_dir=args.out, **extra)
    print("\n" + render_report(args.question, art.outcome, art.swarm, art.stats, cfg))
    print(f"saved: {art.path}")


if __name__ == "__main__":
    main()
