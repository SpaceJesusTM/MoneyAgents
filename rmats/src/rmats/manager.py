"""Manager Agent — recursive coordination protocol.

Paper:
  Health:      H_i(t) = a A_i(t) + b S_i(t) + g R_i(t) - d L_i(t),  a=b=g=d=0.25
  Aggregate:   w_bar^r = sum_i c_i^r H_i w_i^r / sum_i c_i^r H_i
  Converged:   ||w_bar^{r+1} - w_bar^r||_2 < eps = 0.005
  Max rounds:  3 (paper: 69% of steps stop at r=1, 97% by r=2)
  A circuit-breaker override from the Risk agent bypasses convergence.
"""

from __future__ import annotations

import pandas as pd

from rmats.agents.base import Agent
from rmats.config import DEFAULT, Config
from rmats.data import MarketData
from rmats.messages import AgentMessage, BroadcastMessage, CoordinationResult


class Manager:
    def __init__(self, agents: list[Agent], cfg: Config = DEFAULT) -> None:
        self.agents = agents
        self.cfg = cfg
        # Each agent's own past proposals, used to score its health:
        # {agent_name: [(rebalance_date, weights), ...]}
        self.proposal_history: dict[str, list[tuple[pd.Timestamp, pd.Series]]] = {
            a.name: [] for a in agents
        }

    # ---- Health ---------------------------------------------------------- #
    def health_components(self, agent: str, data: MarketData) -> dict[str, float]:
        # TODO: score the agent's *paper portfolio* — i.e. what would have happened
        #       if we had followed ITS past proposals — over the last
        #       cfg.health_window days (ASSUMPTION, the paper doesn't define A/S/R/L):
        #         A  analytical: realized return, squashed to [0,1] (e.g. sigmoid of
        #            annualized return / 0.2)
        #         S  stability : 1 - mean delta of its recent proposals (clip [0,1])
        #         R  risk      : 1 - min(1, realized vol / 0.3)
        #         L  loss      : min(1, max drawdown / 0.2)
        #       Not enough history (early dates) -> return neutral {A:.5,S:.5,R:.5,L:.5}.
        raise NotImplementedError

    def health_score(self, agent: str, data: MarketData) -> float:
        # TODO: H = a*A + b*S + g*R - d*L with cfg.health_weights,
        #       floored at cfg.health_floor so no agent's vote becomes 0 or negative.
        raise NotImplementedError

    # ---- Aggregation ----------------------------------------------------- #
    def aggregate(self, messages: list[AgentMessage], health: dict[str, float]) -> pd.Series:
        # TODO: w_bar = sum_i c_i H_i w_i / sum_i c_i H_i
        #       Align all weight Series on the same index (fill 0). Result must be
        #       on the simplex (it's a convex combination — assert it in tests).
        raise NotImplementedError

    @staticmethod
    def has_converged(w_new: pd.Series, w_old: pd.Series, eps: float) -> bool:
        # TODO: ||w_new - w_old||_2 < eps
        raise NotImplementedError

    def make_broadcast(
        self,
        round_: int,
        w_bar: pd.Series,
        messages: list[AgentMessage],
        health: dict[str, float],
        t: pd.Timestamp,
    ) -> BroadcastMessage:
        # TODO: geo_risk = confidence-weighted mean of messages' geo_risk;
        #       regime = confidence-weighted vote over messages' regime;
        #       cb_active = any(m.override for m in messages).
        raise NotImplementedError

    # ---- Main loop ------------------------------------------------------- #
    def coordinate(self, data: MarketData, t: pd.Timestamp, force_single_round: bool = False) -> CoordinationResult:
        # TODO: the recursive protocol for one rebalance date:
        #
        #   health = {a.name: health_score(a.name, data) for a in agents}   # fixed for the date
        #   msgs_0 = [a.propose(data, t) for a in agents]
        #   if any override in msgs_0: return override weights immediately (CB bypass)
        #   w_bar  = aggregate(msgs_0, health)
        #   for r in 1 .. cfg.max_rounds - 1:
        #       if force_single_round: break                     # ablation "r=1 forced"
        #       b      = make_broadcast(r, w_bar, msgs, health, t)
        #       msgs   = [a.propose(data, t, prev_msg_of_a, b) for a in agents]
        #       if any override: return override weights (CB bypass)
        #       w_new  = aggregate(msgs, health)
        #       if has_converged(w_new, w_bar, eps): w_bar = w_new; break
        #       w_bar  = w_new
        #
        #   Record each agent's ROUND-0 proposal in self.proposal_history (used for
        #   health), and return CoordinationResult(weights=w_bar, rounds=..., ...).
        #
        #   "rounds" convention: count the number of aggregations performed, so a
        #   step that converges right after the first revision is rounds=2... check
        #   against the paper's "median 1 round" and pick a convention; document it.
        raise NotImplementedError
