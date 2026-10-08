"""Agent interface.

Each specialist agent:
  * `fit(data)`   — optional one-off calibration on the TRAINING window
                    (only the Analysis agent's HMM needs it).
  * `propose(...)`— round 0: build an independent proposal from data alone.
                    round r>0: receive the Manager's BroadcastMessage and revise.

Agents are deterministic numeric modules (paper's reported configuration),
not LLM calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import replace

import numpy as np
import pandas as pd

from rmats.config import DEFAULT, Config
from rmats.data import MarketData
from rmats.messages import AgentMessage, BroadcastMessage
from rmats.signals import normalize_simplex


class Agent(ABC):
    name: str = "agent"

    def __init__(self, cfg: Config = DEFAULT) -> None:
        self.cfg = cfg

    def fit(self, data: MarketData) -> None:
        """Calibrate on training data. Default: nothing to fit."""

    @abstractmethod
    def initial_proposal(self, data: MarketData, t: pd.Timestamp) -> AgentMessage:
        """Round-0 proposal using only `data` (already truncated at t)."""

    def revise(
        self,
        data: MarketData,
        t: pd.Timestamp,
        previous: AgentMessage,
        broadcast: BroadcastMessage,
    ) -> AgentMessage:
        # Default revision for rounds r >= 1 (ASSUMPTION, the paper gives no exact rule):
        #   w_new = w_prev + (1 - c_i) * eta * (w_bar - w_prev)
        # Low-confidence agents move further toward consensus. Subclasses
        # (RiskAgent) override this to add their own checks.
        w_prev = previous.weights
        idx = w_prev.index.union(broadcast.weights.index)
        w_prev = w_prev.reindex(idx, fill_value=0.0)
        w_bar = broadcast.weights.reindex(idx, fill_value=0.0)

        step = (1.0 - previous.confidence) * self.cfg.consensus_step
        w_new = normalize_simplex(w_prev + step * (w_bar - w_prev))
        delta = float(np.linalg.norm(w_new - w_prev))
        return replace(
            previous,
            weights=w_new,
            delta=delta,
            timestamp=t,
            info={**previous.info, "round": broadcast.round},
        )

    def propose(
        self,
        data: MarketData,
        t: pd.Timestamp,
        previous: AgentMessage | None = None,
        broadcast: BroadcastMessage | None = None,
    ) -> AgentMessage:
        """Dispatch: initial proposal at round 0, revision afterwards."""
        if broadcast is None or previous is None:
            return self.initial_proposal(data, t)
        return self.revise(data, t, previous, broadcast)
