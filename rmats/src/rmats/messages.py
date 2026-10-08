"""Message schemas exchanged between agents and the Manager.

Paper: m_i^r = {w_i^r, c_i^r, g_i^r, s_i^r, tau_i^r, delta_i^r}
  w     weight vector on the simplex (long-only, sums to 1)
  c     confidence in [0, 1]
  g     geopolitical risk assessment in [0, 1]
  s     regime: 0 = bull, 1 = bear, 2 = stress
  tau   timestamp (the rebalance date)
  delta L2 update magnitude ||w^r - w^{r-1}||_2
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum

import pandas as pd


class Regime(IntEnum):
    BULL = 0
    BEAR = 1
    STRESS = 2


@dataclass
class AgentMessage:
    agent: str
    weights: pd.Series  # indexed by ticker, >= 0, sums to 1
    confidence: float
    geo_risk: float
    regime: Regime
    timestamp: pd.Timestamp
    delta: float = 0.0
    override: bool = False  # True when the Risk agent's circuit breaker fires
    info: dict = field(default_factory=dict)  # free-form diagnostics


@dataclass
class BroadcastMessage:
    round: int
    weights: pd.Series  # w_bar^r
    geo_risk: float
    regime: Regime
    health: dict[str, float]
    cb_active: bool
    timestamp: pd.Timestamp


@dataclass
class CoordinationResult:
    """What the Manager returns for one rebalance date."""

    weights: pd.Series
    rounds: int
    converged: bool
    cb_active: bool
    messages: list[list[AgentMessage]]  # messages[r] = all agent messages in round r
    broadcasts: list[BroadcastMessage]
