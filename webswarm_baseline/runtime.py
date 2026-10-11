"""Shared run-time plumbing: event trace, hard budgets, and the model-slot gate.

All three are thread-safe because every agent node runs in its own thread.
"""
from __future__ import annotations

import heapq
import itertools
import threading
import time
from contextlib import contextmanager

from .config import Budgets


class BudgetExceeded(RuntimeError):
    """A hard limit was hit; the caller should stop and return what it has."""


class Cancelled(RuntimeError):
    """The node (or an ancestor) was cancelled, e.g. its manager finished early."""


class Tracer:
    """Append-only event log with timestamps relative to the start of the run."""

    def __init__(self, echo=None):
        self.t0 = time.perf_counter()
        self.events: list[dict] = []
        self._lock = threading.Lock()
        self._echo = echo  # callable(event) or None

    def now(self) -> float:
        return time.perf_counter() - self.t0

    def event(self, type_: str, node: int | None = None, **data) -> dict:
        ev = {"t": round(self.now(), 3), "type": type_, "node": node, **data}
        with self._lock:
            self.events.append(ev)
        if self._echo:
            try:
                self._echo(ev)
            except Exception:  # noqa: BLE001 - logging must never break a run
                pass
        return ev

    def of(self, type_: str) -> list[dict]:
        with self._lock:
            return [e for e in self.events if e["type"] == type_]


class Budget:
    """Run-wide counters for the hard limits in `Budgets`."""

    def __init__(self, limits: Budgets, tracer: Tracer):
        self.limits = limits
        self.tracer = tracer
        self.llm_calls = 0
        self.web_calls = 0
        self.nodes = 0
        self._lock = threading.Lock()
        self._deadline = time.perf_counter() + limits.max_seconds
        self._wrap_up = time.perf_counter() + limits.max_seconds * limits.wrap_up_fraction
        self._hit: set[str] = set()

    def time_left(self) -> float:
        return self._deadline - time.perf_counter()

    def wrapping_up(self) -> bool:
        """Soft deadline: time to stop gathering evidence and answer with what is in hand, so the
        run ends with a synthesis of everything found instead of being cut off mid-research."""
        if time.perf_counter() >= self._wrap_up:
            self._note("wrap_up")
            return True
        return False

    def expired(self) -> bool:
        if self.time_left() <= 0:
            self._note("max_seconds")
            return True
        return False

    def _note(self, which: str) -> None:
        with self._lock:
            first = which not in self._hit
            self._hit.add(which)
        if first:
            self.tracer.event("budget_hit", limit=which)

    def take_llm(self, reserved: bool = False) -> None:
        """Count one generative call. `reserved` calls (final synthesis) may dip into the reserve."""
        with self._lock:
            cap = self.limits.max_llm_calls - (0 if reserved else self.limits.reserve_llm_calls)
            ok = self.llm_calls < cap
            if ok:
                self.llm_calls += 1
        if not ok:
            self._note("max_llm_calls")
            raise BudgetExceeded("max_llm_calls")
        if not reserved and self.expired():
            raise BudgetExceeded("max_seconds")

    def take_web(self) -> None:
        with self._lock:
            ok = self.web_calls < self.limits.max_web_calls
            if ok:
                self.web_calls += 1
        if not ok:
            self._note("max_web_calls")
            raise BudgetExceeded("max_web_calls")
        if self.expired():
            raise BudgetExceeded("max_seconds")

    def take_node(self) -> bool:
        with self._lock:
            ok = self.nodes < self.limits.max_nodes
            if ok:
                self.nodes += 1
        if not ok:
            self._note("max_nodes")
        return ok

    def hits(self) -> list[str]:
        with self._lock:
            return sorted(self._hit)


# Lower rank = served first by the "finish_first" scheduler: calls that complete a node and send
# evidence upward go ahead of calls that start new work.
_FINISH_FIRST_RANK = {
    "synthesize": 0, "answer": 0,
    "extract": 1, "snippet_extract": 1,
    "review": 2, "deep_step": 2, "decision": 2, "followups": 2,
    "act": 3,
    "plan": 4, "route": 4, "probe": 4, "entity_plan": 4, "experience": 4,
}


class LLMGate:
    """Bounded number of concurrent model calls, with a pluggable queue order.

    `fifo` serves callers in arrival order. `finish_first` serves by call kind (see ranks above),
    then by depth (deeper first), then arrival. With one model slot this decides which agent
    thinks next, so it changes when evidence becomes available but not how much work is done.
    """

    def __init__(self, slots: int = 1, policy: str = "fifo"):
        if policy not in ("fifo", "finish_first"):
            raise ValueError(f"unknown scheduler {policy!r}")
        self.policy = policy
        self._free = max(1, slots)
        self._heap: list[tuple] = []
        self._seq = itertools.count()
        self._cond = threading.Condition()

    def _priority(self, kind: str, depth: int) -> tuple:
        if self.policy == "fifo":
            return (0, 0)
        return (_FINISH_FIRST_RANK.get(kind, 3), -depth)

    @contextmanager
    def slot(self, kind: str = "", depth: int = 0):
        """Block until a model slot is free; yields the seconds spent queued."""
        t0 = time.perf_counter()
        ticket = (*self._priority(kind, depth), next(self._seq))
        with self._cond:
            heapq.heappush(self._heap, ticket)
            while not (self._free > 0 and self._heap[0] == ticket):
                self._cond.wait(timeout=0.5)
            heapq.heappop(self._heap)
            self._free -= 1
        try:
            yield time.perf_counter() - t0
        finally:
            with self._cond:
                self._free += 1
                self._cond.notify_all()
