"""Run statistics, the readable tree, the live console log, and saved run artifacts."""
from __future__ import annotations

import json
import platform
import re
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

from .config import REPO_ROOT
from .evidence import cited_ids
from .textutil import domain_of, norm, overlap


# ---- statistics ---------------------------------------------------------------------------------

def compute_stats(tracer, swarm, budget, wall: float) -> dict:
    ev = tracer.events
    llm = [e for e in ev if e["type"] == "llm_call"]
    dec = [e for e in ev if e["type"] == "decision_call"]
    web = [e for e in ev if e["type"] == "web_call"]
    real = [e for e in web if e["source"] in ("live", "cassette", "cassette_miss")]
    searches = [e for e in real if e["kind"] == "search"]
    fetches = [e for e in real if e["kind"] == "fetch"]
    findings = [e for e in ev if e["type"] == "finding"]
    reads = [e for e in ev if e["type"] == "page_read"]
    nodes = list(swarm.nodes.values())

    def total(rows, key):
        return round(sum((r.get(key) or 0) for r in rows), 2)

    def first_t(rows):
        return rows[0]["t"] if rows else None

    by_url: dict[str, set] = {}
    for r in reads:
        by_url.setdefault(r["url"], set()).add(r["node"])
    queries = [norm(e["query"]) for e in ev if e["type"] == "atom_action" and e["action"] == "search"]
    objs = [(n.id, n.parent, n.objective) for n in nodes if n.role == "research"]
    near_dupes = sum(1 for i, (ia, pa, a) in enumerate(objs) for (ib, pb, b) in objs[i + 1:]
                     if ia != pb and ib != pa and overlap(a, b) >= 0.6)
    decisions = Counter(f"{e['point']}:{e['provider']}" for e in ev if e["type"] == "decision")
    page_findings = [e for e in findings if e.get("kind") == "page"]

    root = swarm.nodes.get(0)
    return {
        # answer_seconds is the latency that matters: when the root's answer was ready.
        # wall_seconds also includes waiting for cancelled agents to wind down afterwards.
        "answer_seconds": round(root.finished, 1) if root and root.finished is not None else round(wall, 1),
        "wall_seconds": round(wall, 1),
        "time_to_first_search_result": first_t([e for e in searches if e["ok"]]),
        "time_to_first_evidence": first_t(findings),
        "time_to_first_page_evidence": first_t(page_findings),
        "llm_calls": len(llm),
        "llm_calls_by_kind": dict(Counter(e["kind"] for e in llm)),
        "llm_failed_calls": sum(1 for e in llm if not e["ok"]),
        "llm_seconds": total(llm, "secs"),
        "llm_queue_wait_seconds": total(llm, "queue_wait"),
        "prompt_tokens": int(total(llm, "prompt_tokens")) or None,
        "output_tokens": int(total(llm, "output_tokens")) or None,
        "llm_prompt_eval_seconds": total(llm, "prompt_secs"),
        "llm_generation_seconds": total(llm, "gen_secs"),
        "decision_calls": len(dec),
        "decision_seconds": total(dec, "secs"),
        "decision_prompt_tokens": int(total(dec, "prompt_tokens")) or None,
        "decisions": dict(decisions),
        "searches": len(searches),
        "fetches": len(fetches),
        "web_calls": len(searches) + len(fetches),
        "fetch_failures": sum(1 for e in fetches if not e["ok"]),
        "fetch_truncated": sum(1 for e in fetches if e.get("truncated")),   # body cut off by a size/time limit
        "search_failures": sum(1 for e in searches if not e["ok"]),
        "web_seconds": total(real, "secs"),
        "web_run_cache_hits": sum(1 for e in web if e["source"] == "run_cache" and e["kind"] != "robots"),
        "web_from_cassette": sum(1 for e in real if e["source"] == "cassette"),
        # where each run's evidence came from: needed before two runs can be compared at all
        "web_provenance": {kind: {"replayed": sum(1 for e in rows if e["source"] == "cassette" and e["ok"]),
                                  "live": sum(1 for e in rows if e["source"] == "live" and e["ok"]),
                                  "no_answer": sum(1 for e in rows if not e["ok"] and
                                                   (e.get("transient") or e["source"] == "cassette_miss")),
                                  "failed": sum(1 for e in rows if not e["ok"] and not
                                                (e.get("transient") or e["source"] == "cassette_miss"))}
                           for kind, rows in (("search", searches), ("fetch", fetches))},
        "search_no_answer_by_kind": dict(Counter(e.get("error_kind") or "unknown" for e in searches
                                                 if not e["ok"])),
        "nodes": len(nodes),
        "nodes_by_mode": dict(Counter(n.mode or "UNROUTED" for n in nodes)),
        "nodes_by_role": dict(Counter(n.role for n in nodes)),
        "nodes_by_status": dict(Counter(n.status for n in nodes)),
        "max_depth": max((n.depth for n in nodes), default=0),
        "findings": len(findings),
        "findings_from_pages": len(page_findings),
        "findings_rejected": sum(1 for e in ev if e["type"] == "finding_rejected"),
        "findings_adjusted": sum(1 for e in ev if e["type"] == "finding_adjusted"),
        "guard_events": dict(Counter(e["type"] for e in ev if e["type"] in (
            "verify_refused", "numeric_issue", "label_issue", "comparison", "finding_adjusted"))),
        "sources": len(swarm.evidence.sources),
        "source_domains": sorted({s.domain for s in swarm.evidence.sources.values()}),
        "redundancy": {
            "objectives_dropped_as_duplicate": sum(1 for e in ev if e["type"] == "redundant_dropped"),
            "near_duplicate_objective_pairs": near_dupes,
            "repeated_queries": len(queries) - len(set(queries)),
            "urls_read_by_more_than_one_agent": sum(1 for s in by_url.values() if len(s) > 1),
            "pages_read_with_no_accepted_finding": sum(1 for r in reads if not r["accepted"]),
            "nodes_with_no_evidence": sum(1 for n in nodes if n.status == "failed"),
            "nodes_cancelled": sum(1 for n in nodes if n.status == "cancelled"),
        },
        "interventions": sum(len(n.notes) for n in nodes),
        "budget_hits": budget.hits(),
    }


def format_stats(stats: dict) -> str:
    def row(k, v):
        return f"  {k}: {v}"
    lines = []
    for k, v in stats.items():
        if isinstance(v, dict) and k == "redundancy":
            lines.append("  redundancy:")
            lines += [f"    {a}: {b}" for a, b in v.items()]
        else:
            lines.append(row(k, v))
    return "\n".join(lines)


# ---- tree ---------------------------------------------------------------------------------------

def render_tree(nodes: dict, show_reasoning: bool = True) -> str:
    lines: list[str] = []

    def walk(nid: int, prefix: str, last: bool, root: bool) -> None:
        n = nodes[nid]
        conn = "" if root else ("└── " if last else "├── ")
        secs = f"{(n.finished or 0) - (n.started or 0):.0f}s" if n.started is not None and n.finished is not None else "-"
        tag = n.mode or "UNROUTED"
        if n.role != "research":
            tag += f"/{n.role}"
        extra = f"#{nid}, {n.status}, {secs}"
        if n.result and n.result.verdict:
            extra += f", verdict {n.result.verdict}"
        elif n.result and n.result.answer:
            extra += f", confidence {n.result.confidence}"
        if n.model_mode and n.model_mode != n.mode:
            extra += f", decider said {n.model_mode}"
        lines.append(f"{prefix}{conn}[{tag}] {n.objective}  ({extra})")
        child_prefix = prefix + ("" if root else ("    " if last else "│   "))
        bar = "│   " if n.children else "    "
        if show_reasoning and n.reason and n.reason != "assigned by parent":
            lines.append(f"{child_prefix}{bar}why: {n.reason}")
        for note in n.notes:
            lines.append(f"{child_prefix}{bar}! {note}")
        for i, c in enumerate(n.children):
            walk(c, child_prefix, i == len(n.children) - 1, False)

    walk(0, "", True, True)
    return "\n".join(lines)


# ---- live console log ---------------------------------------------------------------------------

def make_echo(swarm_ref: dict, verbose: bool = False):
    """Console logger for trace events. `swarm_ref['swarm']` is filled in once the swarm exists."""

    def depth(nid):
        sw = swarm_ref.get("swarm")
        n = sw.nodes.get(nid) if (sw and nid is not None) else None
        return n.depth if n else 0

    def echo(e: dict) -> None:
        t, nid, ty = e["t"], e["node"], e["type"]
        head = f"[{t:7.1f}s] {'  ' * depth(nid)}#{nid if nid is not None else '-'}"
        msg = None
        if ty == "node_created":
            msg = f"+ created ({e['role']}) {e['objective'][:110]}"
        elif ty == "node_mode":
            msg = f"mode {e['mode']}" + (f" (decider said {e['model_mode']})" if e["model_mode"] != e["mode"] else "")
        elif ty == "decision":
            msg = f"decide {e['point']} -> {e['value']} [{e['provider']}] {e.get('reason', '')[:90]}"
        elif ty == "atom_action":
            if e["action"] == "search":
                msg = f'search "{e["query"][:90]}"'
            elif e["action"] == "read":
                msg = f"read result {e['result']}"
            else:
                msg = "finish"
        elif ty == "web_call" and e["kind"] != "robots":
            if e["kind"] == "search":
                msg = f"  search -> {e.get('n', 0)} results ({e['secs']}s, {e['source']})" + \
                      (f" ERROR {e['error']}" if e.get("error") else "")
            else:
                msg = f"  fetch {domain_of(e['target'])} -> " + \
                      (f"{e.get('chars', 0)} chars" if e["ok"] else f"FAILED {e.get('error')}") + \
                      f" ({e['secs']}s, {e['source']})"
        elif ty == "page_read":
            msg = f"  extracted {e['accepted']}/{e['proposed']} findings from {e['domain']}"
        elif ty == "finding" and verbose:
            msg = f"  finding {e['id']} [{e['source']}] {e['claim'][:100]}"
        elif ty == "plan":
            msg = f"plan: {len(e['proposed'])} sub-objectives" + (f" (probe: {e['probing']})" if e.get("probing") else "")
        elif ty == "probe":
            msg = f"probe: {e['topology']} axis={e['axis']!r} hubs={len(e['hubs'])}"
        elif ty == "child_result":
            msg = f"<- result from #{e['child']} ({e['status']}); {e['pending']} pending"
        elif ty == "child_cancelled":
            msg = f"x cancelled #{e['child']} ({e['reason']})"
        elif ty == "experience":
            msg = f"experience: {e['tips'][:120]}"
        elif ty == "entity_merge":
            msg = f"merged entities: {len(e['entities'])} from {e['paths_with_hits']}/{e['paths']} paths"
        elif ty == "note":
            msg = f"! {e['text'][:140]}"
        elif ty == "node_end":
            msg = f"done {e['mode']} {e['status']} ({e['secs']}s)" + (f" verdict={e['verdict']}" if e.get("verdict") else "")
        elif ty == "budget_hit":
            msg = f"!! BUDGET LIMIT HIT: {e['limit']}"
        elif ty == "llm_call" and verbose:
            msg = f"  llm {e['kind']} {e['secs']}s (+{e['queue_wait']}s queued) in={e.get('prompt_tokens')} out={e.get('output_tokens')}"
        if msg:
            print(f"{head} {msg}", flush=True)

    return echo


# ---- final report -------------------------------------------------------------------------------

def render_sources(answer: str, evidence) -> str:
    rows = []
    for sid in cited_ids(answer):
        s = evidence.sources.get(sid)
        if s:
            kind = "" if s.kind == "page" else " (search snippet only; page not read)"
            rows.append(f"[{sid}] {s.title or s.domain} - {s.url} (retrieved {s.retrieved_at[:10]}){kind}")
    return "\n".join(rows)


def render_report(question: str, outcome: dict, swarm, stats: dict, cfg) -> str:
    a = outcome.get("audit") or {}
    parts = [f"# {question}", "",
             f"_config: {cfg.name} | model: {cfg.model} | decider: {cfg.decider} | web: {cfg.web_mode} | "
             f"status: {outcome['status']} | confidence: {outcome['confidence']}_", "",
             "## Answer", "", outcome["answer"] or "(no answer could be grounded in retrieved evidence)", ""]
    if outcome.get("gaps"):
        parts += ["**Gaps reported by the system:** " + outcome["gaps"], ""]
    src = render_sources(outcome["answer"], swarm.evidence)
    parts += ["## Sources cited", "", src or "(none)", ""]
    if a:
        parts += ["## Grounding audit (programmatic, no model involved)", "",
                  f"- citations: {a['citations']} ({a['cited_pages']} read pages, {a['cited_snippets']} snippet-only); "
                  f"unknown ids removed: {len(outcome.get('removed_citations') or [])}",
                  f"- figures in the answer: {a['numbers']}; found in the cited source: {a['numbers_in_cited_source']}; "
                  f"found elsewhere in retrieved evidence: {a['numbers_elsewhere_in_evidence']}; "
                  f"not found in any retrieved text: {a['numbers_ungrounded']}",
                  f"- sentences with figures but no citation: {a['sentences_with_figures_but_no_citation']}"]
        for u in a.get("ungrounded_examples", [])[:5]:
            parts.append(f"  - ungrounded figure `{u['number']}` in: {u['sentence']}")
        parts.append("")
        c = a.get("consistency")
        if c is not None:
            parts += ["## Consistency checks (programmatic, no model involved)", "",
                      f"- ordering statements that contradict the figures: {len(c['ordering_issues'])}"]
            parts += [f"  - {i['detail']} — in: {i['sentence']}" for i in c["ordering_issues"][:5]]
            parts.append(f"- GAAP / non-GAAP labels that contradict the cited passage: {len(c['basis_conflicts'])}")
            parts += [f"  - {b['figure']} is called {b['said']}, the passage shows {b['passage_shows']} — in: "
                      f"{b['sentence']}" for b in c["basis_conflicts"][:5]]
            parts.append(f"- quarter / full-year labels that contradict the finding: {len(c.get('period_conflicts', []))}")
            parts += [f"  - {b['figure']} is given as {b['said']}, the finding says {b['finding_says']} — in: "
                      f"{b['sentence']}" for b in c.get("period_conflicts", [])[:5]]
            parts += [f"- comparison caveat: {w}" for w in c["mixed_basis_or_period"]]
            parts.append("")
    parts += ["## Agent tree", "", "```", render_tree(swarm.nodes), "```", "",
              "## Statistics", "", "```", format_stats(stats), "```", ""]
    return "\n".join(parts)


def manifest(cfg) -> dict:
    def sh(*cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=5, cwd=REPO_ROOT).stdout.strip()
        except Exception:  # noqa: BLE001
            return ""
    info = {"created": datetime.now().astimezone().isoformat(timespec="seconds"),
            "git_commit": sh("git", "rev-parse", "HEAD"), "git_dirty": bool(sh("git", "status", "--porcelain")),
            "python": platform.python_version(), "platform": platform.platform(),
            "machine": platform.machine(), "ollama_version": "", "model_digest": ""}
    try:
        import requests
        base = cfg.ollama_url.rstrip("/")
        info["ollama_version"] = requests.get(base + "/api/version", timeout=3).json().get("version", "")
        for m in requests.get(base + "/api/tags", timeout=3).json().get("models", []):
            if m.get("name") == cfg.model:
                info["model_digest"] = m.get("digest", "")[:16]
                info["model_details"] = m.get("details", {})
    except Exception:  # noqa: BLE001
        pass
    return info


def save_run(out_dir: Path, question: str, outcome: dict, swarm, tracer, stats: dict, cfg, meta: dict) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower())[:48].strip("-")
    base = Path(out_dir) / f"{datetime.now():%Y%m%d-%H%M%S}_{cfg.name}_{slug}"
    base.mkdir(parents=True, exist_ok=True)
    payload = {"question": question, "config": cfg.to_dict(), "manifest": meta, "outcome": outcome,
               "stats": stats, "tree": render_tree(swarm.nodes),
               "nodes": [swarm.nodes[k].public() for k in sorted(swarm.nodes)],
               "evidence": swarm.evidence.snapshot()}
    (base / "run.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    with (base / "trace.jsonl").open("w") as fh:
        for e in tracer.events:
            fh.write(json.dumps(e, ensure_ascii=False, default=str) + "\n")
    (base / "report.md").write_text(render_report(question, outcome, swarm, stats, cfg))
    return base
