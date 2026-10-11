"""Decision-accuracy check for routers: who picks the intended mode, how often, and how fast.

    .venv/bin/python -m experiments.bench.eval_routing            # all local routers
    .venv/bin/python -m experiments.bench.eval_routing rules      # one of them

Runs each router over experiments/bench/routing_cases.json with the real local model (rules need
none). The labels are the author's judgement, so read the numbers as agreement with an intended
policy, not as accuracy against ground truth. Jev is not included: it needs credentials.
"""
from __future__ import annotations

import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

from webswarm_baseline.config import SwarmConfig
from webswarm_baseline.decisions import load_decider
from webswarm_baseline.evidence import EvidenceStore
from webswarm_baseline.llm import OllamaLLM
from webswarm_baseline.runtime import Budget, LLMGate, Tracer
from webswarm_baseline.swarm import Swarm
from webswarm_baseline.web import WebClient

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
MODES = ["ATOM", "WIDE", "DEEP", "ENTITY_COLLECT"]

ROUTERS = {
    "generative_4b": ("generative", {}),
    "local_s1_4b": ("local_s1", {}),
    "local_s1_2b": ("local_s1", {"model": "qwen3.5:2b-q4_K_M"}),
    "rules": ("rules", {}),
}


def evaluate(label: str, decider_name: str, options: dict, cases: list[dict]) -> dict:
    cfg = SwarmConfig()
    cfg.budgets.max_llm_calls = 10_000
    cfg.budgets.max_nodes = 10_000
    cfg.budgets.max_seconds = 3600
    tracer = Tracer()
    budget = Budget(cfg.budgets, tracer)
    llm = OllamaLLM(cfg, tracer, budget, LLMGate(1))
    if decider_name != "rules":
        llm.check()
    decider = load_decider(decider_name, options)
    swarm = Swarm(cfg, llm, WebClient(cfg, tracer, budget), tracer, budget, EvidenceStore(tracer), decider)
    rows = []
    for case in cases:
        parent = swarm._new_node(case["parent"], None) if case.get("parent") else None
        node = swarm._new_node(case["objective"], parent)
        swarm.root_question = case.get("parent") or case["objective"]
        t0 = time.perf_counter()
        try:
            d = decider.route(node, MODES)
            got, conf, reason = d.value, d.confidence, d.reason
        except Exception as e:  # noqa: BLE001
            got, conf, reason = "ERROR", None, f"{type(e).__name__}: {e}"
        rows.append({"objective": case["objective"], "depth": node.depth, "expected": case["expected"],
                     "got": got, "ok": got == case["expected"], "confidence": conf,
                     "secs": round(time.perf_counter() - t0, 3), "reason": str(reason)[:200]})
    secs = [r["secs"] for r in rows]
    sub = [r for r in rows if r["depth"] >= 1 and r["expected"] == "ATOM"]
    return {
        "router": label, "decider": decider_name, "options": options, "cases": len(rows),
        "agreement": round(sum(r["ok"] for r in rows) / len(rows), 3),
        "agreement_by_expected": {m: f"{sum(r['ok'] for r in rows if r['expected'] == m)}/"
                                     f"{sum(1 for r in rows if r['expected'] == m)}" for m in MODES},
        "over_delegation_below_root": f"{sum(1 for r in sub if r['got'] != 'ATOM')}/{len(sub)}",
        "median_secs": round(statistics.median(secs), 3), "mean_secs": round(statistics.mean(secs), 3),
        "total_secs": round(sum(secs), 1), "predicted": dict(Counter(r["got"] for r in rows)), "rows": rows,
    }


def main() -> None:
    cases = json.loads((HERE / "routing_cases.json").read_text())["cases"]
    names = sys.argv[1:] or list(ROUTERS)
    out = []
    for name in names:
        decider, options = ROUTERS[name]
        res = evaluate(name, decider, options, cases)
        out.append(res)
        print(f"{name:15} agreement {res['agreement']:.0%}  by mode {res['agreement_by_expected']}  "
              f"over-delegation below root {res['over_delegation_below_root']}  "
              f"median {res['median_secs']}s  total {res['total_secs']}s", flush=True)
        for r in res["rows"]:
            if not r["ok"]:
                print(f"    x d{r['depth']} expected {r['expected']:14} got {r['got']:14} | {r['objective'][:80]}")
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / "routing_eval.json"
    prev = json.loads(path.read_text()) if path.exists() else []
    keep = [p for p in prev if p["router"] not in {o["router"] for o in out}]
    path.write_text(json.dumps(keep + out, indent=2))
    print(f"saved {path}")


if __name__ == "__main__":
    main()
