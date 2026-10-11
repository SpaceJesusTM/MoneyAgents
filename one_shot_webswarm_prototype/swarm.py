"""LangGraph orchestration for the recursive ATOM / DEEP / WIDE delegation tree.

Graph:

    START -> route --(frontier not empty)--> route   (one tree node per step, breadth-first)
                   \\-(frontier empty)-----> synthesize -> END   (bottom-up answers; optional)

`route` pops one node from the frontier, asks the model for {reasoning, mode, children},
applies the safety limits, and appends any accepted children to the frontier. Every node
in the tree is routed exactly once, so the number of routing calls equals the node count
and is bounded by Limits.max_nodes.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

import prompts
from config import Limits


class RoutingDecision(BaseModel):
    reasoning: str = Field(description="1-3 sentence justification for the chosen mode.")
    mode: Literal["ATOM", "DEEP", "WIDE"]
    children: list[str] = Field(default_factory=list, description="Child objectives. Empty for ATOM.")


class SwarmState(TypedDict):
    root_objective: str
    nodes: dict[int, dict]
    frontier: list[int]


def new_node(nid: int, objective: str, parent: int | None, depth: int) -> dict:
    return {
        "id": nid, "parent": parent, "depth": depth, "objective": objective,
        "model_mode": None,      # what the model chose
        "mode": None,            # what was actually executed after limits/validation
        "reasoning": "", "proposed_children": [], "children": [],
        "notes": [],             # every intervention by the harness, so overrides are visible
        "answer": None,
    }


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def build_graph(llm, limits: Limits, synthesize: bool = True, log=print):
    today = date.today().isoformat()

    def route(state: SwarmState) -> dict:
        nodes = dict(state["nodes"])
        frontier = list(state["frontier"])
        nid = frontier.pop(0)
        node = nodes[nid] = {**nodes[nid], "notes": [], "children": []}

        ancestors = []
        p = node["parent"]
        while p is not None:
            ancestors.insert(0, nodes[p])
            p = nodes[p]["parent"]
        siblings = [nodes[s] for s in (nodes[node["parent"]]["children"] if node["parent"] is not None else [])
                    if s != nid]

        user = prompts.ROUTER_USER.format(
            today=today, root=state["root_objective"],
            path="\n".join(f"  depth {a['depth']} [{a['mode']}]: {a['objective']}" for a in ancestors) or "  (this is the root)",
            siblings="\n".join(f"  - {s['objective']}" for s in siblings) or "  (none)",
            depth=node["depth"], max_depth=limits.max_depth, objective=node["objective"],
        )
        system = prompts.ROUTER_SYSTEM.format(max_children=limits.max_children)

        decision, last_err = None, None
        for attempt in range(2):  # one retry on malformed output
            try:
                decision = llm.structured(RoutingDecision, system, user, node=node, kind="route")
                if attempt:
                    node["notes"].append(f"routing retried after failure: {type(last_err).__name__}")
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
        if decision is None:
            node["notes"].append(f"routing failed twice ({type(last_err).__name__}); defaulted to ATOM")
            decision = RoutingDecision(reasoning="", mode="ATOM", children=[])
            node["model_mode"] = "ERROR"
        else:
            node["model_mode"] = decision.mode

        node["reasoning"] = decision.reasoning.strip()
        node["proposed_children"] = [c.strip() for c in decision.children if c.strip()]
        mode, kids = decision.mode, list(node["proposed_children"])
        notes = node["notes"]

        # --- safety limits and validation; each override is recorded in notes ---
        if mode == "ATOM" and kids:
            notes.append(f"ATOM returned {len(kids)} children; ignored")
            kids = []
        if mode != "ATOM" and node["depth"] >= limits.max_depth:
            notes.append(f"max depth {limits.max_depth} reached; {mode} forced to ATOM")
            kids = []
        seen = {_norm(a["objective"]) for a in ancestors} | {_norm(s["objective"]) for s in siblings} | {_norm(node["objective"])}
        unique = []
        for k in kids:
            if _norm(k) in seen:
                notes.append(f"dropped duplicate child: {k!r}")
            else:
                seen.add(_norm(k))
                unique.append(k)
        kids = unique
        if len(kids) > limits.max_children:
            notes.append(f"{len(kids)} children > max_children={limits.max_children}; kept first {limits.max_children}")
            kids = kids[:limits.max_children]
        room = limits.max_nodes - len(nodes)
        if len(kids) > room:
            notes.append(f"node budget max_nodes={limits.max_nodes}: kept {max(room, 0)} of {len(kids)} children")
            kids = kids[:max(room, 0)]
        if mode == "WIDE" and len(kids) == 1:
            notes.append("WIDE with a single child (looks more like DEEP)")
        if mode != "ATOM" and not kids:
            mode = "ATOM"
        node["mode"] = mode

        for k in kids:
            cid = len(nodes)
            nodes[cid] = new_node(cid, k, nid, node["depth"] + 1)
            node["children"].append(cid)
            frontier.append(cid)

        _log_decision(log, node, nodes)
        return {"nodes": nodes, "frontier": frontier}

    def synthesize_answers(state: SwarmState) -> dict:
        nodes = {k: dict(v) for k, v in state["nodes"].items()}
        log("\n=== bottom-up synthesis (no web access: answers come from model knowledge) ===")

        def answer(nid: int) -> str:
            n = nodes[nid]
            fmt = dict(today=today, root=state["root_objective"], objective=n["objective"])
            try:
                if not n["children"]:
                    n["answer"] = llm.text(prompts.ATOM_SYSTEM, prompts.ATOM_USER.format(**fmt), node=n, kind="atom_answer")
                else:
                    findings = "\n\n".join(f"### Sub-objective: {nodes[c]['objective']}\n{answer(c)}" for c in n["children"])
                    n["answer"] = llm.text(prompts.SYNTH_SYSTEM.format(mode=n["mode"]),
                                           prompts.SYNTH_USER.format(findings=findings, **fmt),
                                           node=n, kind="synthesize")
            except Exception as e:  # noqa: BLE001
                n["answer"] = f"(answer failed: {type(e).__name__}: {e})"
            log(f"  answered #{nid} ({'leaf' if not n['children'] else 'synthesis of ' + str(len(n['children']))})")
            return n["answer"]

        answer(0)
        return {"nodes": nodes}

    def next_step(state: SwarmState) -> str:
        if state["frontier"]:
            return "route"
        return "synthesize" if synthesize else END

    g = StateGraph(SwarmState)
    g.add_node("route", route)
    g.add_node("synthesize", synthesize_answers)
    g.add_edge(START, "route")
    g.add_conditional_edges("route", next_step, ["route", "synthesize", END])
    g.add_edge("synthesize", END)
    return g.compile()


def _log_decision(log, node: dict, nodes: dict) -> None:
    parent = f"parent #{node['parent']}" if node["parent"] is not None else "root"
    changed = f" (model said {node['model_mode']})" if node["model_mode"] != node["mode"] else ""
    log(f"\n[#{node['id']} depth={node['depth']} {parent}] {node['mode']}{changed}")
    log(f"  objective: {node['objective']}")
    if node["reasoning"]:
        log(f"  why: {node['reasoning']}")
    for c in node["children"]:
        log(f"  + #{c}: {nodes[c]['objective']}")
    for note in node["notes"]:
        log(f"  ! {note}")


def run_swarm(objective: str, llm, limits: Limits, synthesize: bool = True, log=print) -> dict[int, dict]:
    graph = build_graph(llm, limits, synthesize, log)
    init: SwarmState = {"root_objective": objective, "nodes": {0: new_node(0, objective, None, 0)}, "frontier": [0]}
    final = graph.invoke(init, {"recursion_limit": limits.max_nodes + 10})
    return final["nodes"]
