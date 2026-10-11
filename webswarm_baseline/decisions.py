"""Bounded control decisions, separated from generative work.

A research run mixes two kinds of model use:

  generative - writing search queries, sub-objectives, extracted findings and answers;
  bounded    - choosing among a few options: which mode, which result to read, stop or continue,
               verify or not, is this objective a duplicate.

The `Decider` owns the bounded ones, so experiment arms can swap who makes them (the main model,
a small local model, deterministic rules, or TypeSafe's Jev) without touching the research code.

A decider method may return None, meaning "no opinion": the engine then falls back to its
generative path. The baseline `GenerativeDecider` does this for everything except routing, so
in the baseline the main model controls the whole run.
"""
from __future__ import annotations

import importlib
import time
from dataclasses import dataclass, field

from . import prompts
from .textutil import objective_key


@dataclass
class Decision:
    point: str                    # route | atom_next | review | verify | redundant
    value: object
    provider: str
    confidence: float | None = None
    reason: str = ""
    secs: float = 0.0
    fallback: bool = False        # True when the provider deferred to another one


@dataclass
class AtomAction:
    kind: str                     # search | read | finish
    query: str = ""
    result: int = 0               # 1-based index into the agent's search results
    thought: str = ""
    provider: str = "generative"


@dataclass
class ReviewDecision:
    decision: str                 # wait | follow_up | finish
    follow_ups: list[str] = field(default_factory=list)
    reason: str = ""
    provider: str = "generative"


class Decider:
    """Base class: no opinion on anything except the cheap defaults below."""
    name = "base"

    def bind(self, swarm) -> None:
        self.swarm = swarm

    def route(self, node, modes: list[str]) -> Decision:
        raise NotImplementedError

    def atom_next(self, node, st, steps_left: int) -> AtomAction | None:
        return None

    def review(self, node, rt) -> ReviewDecision | None:
        return None

    def needs_verification(self, node, claim: str, steps: list[dict]) -> Decision:
        return Decision("verify", True, self.name, reason="policy: verify every candidate")

    def redundant(self, objective: str, existing: list[str]) -> bool:
        """Baseline check is lexical: only exact duplicates after normalisation are dropped."""
        key = objective_key(objective)
        return any(key == objective_key(e) for e in existing)


class GenerativeDecider(Decider):
    """Baseline: the main local model makes every decision with a short written reason."""
    name = "generative"

    def route(self, node, modes: list[str]) -> Decision:
        sw = self.swarm
        t0 = time.perf_counter()
        parent = sw.nodes.get(node.parent) if node.parent is not None else None
        lineage = (f"This objective is one part that a manager already split out of: {parent.objective}"
                   if parent else "This is the user's original question.")
        out = sw.llm.json(
            "route", node, prompts.ROUTE_SYSTEM,
            prompts.ROUTE_USER.format(today=sw.today, lineage=lineage, objective=node.objective),
            prompts.route_schema(modes), max_tokens=110)
        return Decision("route", out["mode"], self.name, reason=out.get("reason", "").strip(),
                        secs=time.perf_counter() - t0)


def load_decider(name: str, options: dict | None = None) -> Decider:
    """`generative` lives here; every other decider is an experiment and is imported lazily, so the
    baseline never depends on experiment code."""
    if name == "generative":
        return GenerativeDecider()
    mod = importlib.import_module("experiments.deciders")
    return mod.build(name, options or {})
