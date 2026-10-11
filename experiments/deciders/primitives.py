"""Typed-decision primitives, shaped like TypeSafe's System One API (Jev).

Three question types, taken from https://docs.typesafe.ai/api (checked 2026-10-10):

    Choice  pick one option from `criteria` {option: description}        -> choice, probabilities, confidence
    Noul    a yes/no question                                              -> noul = P(yes)
    Score   a position on an ordered rubric `criteria` [level, level, ...] -> score, probabilities, confidence

`to_wire()` produces exactly the JSON the REST endpoint documents, so the real Jev backend sends
these objects unchanged, and the local backends answer the same questions. That is what makes the
backends swappable: the research engine asks typed questions and never knows who answered.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Choice:
    instructions: str
    criteria: dict            # option -> description (or None)

    def to_wire(self) -> dict:
        return {"type": "choice", "instructions": self.instructions, "criteria": dict(self.criteria)}


@dataclass
class Noul:
    instructions: str
    criteria: dict | None = None   # optional {"true": "...", "false": "..."}

    def to_wire(self) -> dict:
        d = {"type": "noul", "instructions": self.instructions}
        if self.criteria:
            d["criteria"] = dict(self.criteria)
        return d


@dataclass
class Score:
    instructions: str
    criteria: list            # ordered level descriptions, 2..10

    def to_wire(self) -> dict:
        return {"type": "score", "instructions": self.instructions, "criteria": list(self.criteria)}


Question = Choice | Noul | Score


@dataclass
class Answer:
    type: str
    choice: str | None = None
    noul: float | None = None
    score: float | None = None
    probabilities: dict = field(default_factory=dict)
    confidence: float | None = None

    @classmethod
    def from_wire(cls, d: dict) -> "Answer":
        """Parse one answer object from a System One response."""
        t = d.get("type")
        if t == "choice":
            return cls("choice", choice=d["choice"], probabilities=dict(d.get("probabilities") or {}),
                       confidence=d.get("confidence"))
        if t == "noul":
            return cls("noul", noul=float(d["noul"]))
        if t == "score":
            return cls("score", score=float(d["score"]), probabilities=dict(d.get("probabilities") or {}),
                       confidence=d.get("confidence"))
        raise ValueError(f"unknown answer type {t!r}")


def peak_confidence(probs: dict) -> float:
    """Confidence from how peaked a distribution is: 0 when flat, 1 when all mass is on one option.

    TypeSafe documents confidence only qualitatively ("a single peak gives high confidence; a flat
    spread gives low"). (p_max - 1/n) / (1 - 1/n) gives 0.775 for the one worked example in their
    quickstart (0.85/0.15/0.0, shown there as 0.78), so local backends use it. It is an inference
    from that single example, not a documented formula.
    """
    n = len(probs)
    if n <= 1:
        return 1.0
    return max(0.0, (max(probs.values()) - 1 / n) / (1 - 1 / n))


class Backend:
    """Answers a batch of typed questions about one `state`."""
    name = "backend"
    external = False     # True if `state` leaves this machine

    def ask(self, state, questions: dict, *, node=None, kind: str = "") -> dict:
        raise NotImplementedError
