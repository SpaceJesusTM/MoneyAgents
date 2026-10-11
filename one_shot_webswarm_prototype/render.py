"""Human-readable tree, run statistics, and JSON/TXT trace files."""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path


def render_tree(nodes: dict[int, dict], show_reasoning: bool = True) -> str:
    lines: list[str] = []

    def walk(nid: int, prefix: str, is_last: bool, is_root: bool) -> None:
        n = nodes[nid]
        connector = "" if is_root else ("└── " if is_last else "├── ")
        label = f"[{n['mode'] or 'UNROUTED'}] {n['objective']}  (#{nid}"
        if n["model_mode"] and n["model_mode"] != n["mode"]:
            label += f", model said {n['model_mode']}"
        lines.append(prefix + connector + label + ")")
        child_prefix = prefix + ("" if is_root else ("    " if is_last else "│   "))
        bar = "│   " if n["children"] else "    "
        if show_reasoning and n["reasoning"]:
            lines.append(child_prefix + bar + "why: " + n["reasoning"])
        for note in n["notes"]:
            lines.append(child_prefix + bar + "! " + note)
        for i, c in enumerate(n["children"]):
            walk(c, child_prefix, i == len(n["children"]) - 1, False)

    walk(0, "", True, True)
    return "\n".join(lines)


def compute_stats(nodes: dict[int, dict], calls: list[dict], seconds: float) -> dict:
    def tok(key):
        vals = [c.get(key) for c in calls if c.get(key) is not None]
        return sum(vals) if vals else None

    return {
        "nodes": len(nodes),
        "modes_executed": dict(Counter(n["mode"] for n in nodes.values())),
        "modes_chosen_by_model": dict(Counter(n["model_mode"] for n in nodes.values())),
        "max_depth_reached": max(n["depth"] for n in nodes.values()),
        "leaves": sum(1 for n in nodes.values() if not n["children"]),
        "nodes_with_interventions": sum(1 for n in nodes.values() if n["notes"]),
        "llm_calls": dict(Counter(c["kind"] for c in calls)),
        "failed_llm_calls": sum(1 for c in calls if not c.get("ok")),
        "llm_seconds": round(sum(c.get("seconds", 0) for c in calls), 1),
        "wall_seconds": round(seconds, 1),
        "input_tokens": tok("input_tokens"),
        "output_tokens": tok("output_tokens"),
    }


def format_stats(stats: dict) -> str:
    return "\n".join(f"  {k}: {v}" for k, v in stats.items())


def save_run(out_dir: Path, objective: str, nodes: dict, calls: list, stats: dict, meta: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", objective.lower())[:50].strip("-")
    base = out_dir / f"{datetime.now():%Y%m%d-%H%M%S}_{slug}"
    tree = render_tree(nodes)
    payload = {"objective": objective, **meta, "stats": stats, "tree_text": tree,
               "nodes": [nodes[k] for k in sorted(nodes)], "llm_calls": calls}
    base.with_suffix(".json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    txt = [f"OBJECTIVE: {objective}", "", "TREE:", tree, "", "STATS:", format_stats(stats)]
    if nodes[0].get("answer"):
        txt += ["", "ROOT ANSWER:", nodes[0]["answer"]]
    base.with_suffix(".txt").write_text("\n".join(txt) + "\n")
    return base
