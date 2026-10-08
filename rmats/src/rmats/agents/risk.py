"""Risk Agent — CVaR control + multi-level circuit breaker.

Paper:
  CVaR_a(t) = -E[R_p(t) | R_p(t) <= VaR_a(t)]      (Rockafellar-Uryasev)
  EWMA dynamic covariance.
  CB(t) = 1[DD_p(t) > theta_dd] OR 1[GRS(t) > theta_geo] OR 1[sigma_p(t) > theta_vol]
    theta_dd  = -6% (20-day cumulative return)
    theta_geo = 0.52
    theta_vol = 1.8 * sigma_hat_252
  When CB fires: hard shift to defensive assets (bonds, gold) and BYPASS the
  Manager's convergence check.
"""

from __future__ import annotations

import pandas as pd

from rmats.agents.base import Agent
from rmats.config import DEFENSIVE
from rmats.data import MarketData
from rmats.messages import AgentMessage, BroadcastMessage


class RiskAgent(Agent):
    name = "risk"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Realized portfolio returns are needed for the drawdown / vol triggers.
        # The backtester sets this before each rebalance (returns up to t).
        self.portfolio_returns: pd.Series | None = None

    def min_cvar_weights(self, returns: pd.DataFrame) -> pd.Series:
        # TODO: Rockafellar-Uryasev LP with cvxpy over the last cfg.cvar_window days:
        #         S scenarios r_s (rows), variables w (N), zeta (VaR), u (S) >= 0
        #         minimize  zeta + 1/((1-alpha) S) * sum(u)
        #         s.t.      u_s >= -r_s @ w - zeta,  sum(w) = 1, w >= 0,
        #                   w <= cfg-level single-asset cap
        #       Drop assets with NaN history. Return normalize_simplex(w.value).
        raise NotImplementedError

    def defensive_portfolio(self, returns: pd.DataFrame) -> pd.Series:
        # TODO: inverse-vol weights restricted to DEFENSIVE (bonds + GLD), 0 elsewhere.
        raise NotImplementedError

    def circuit_breaker(self, data: MarketData, w: pd.Series, grs: float) -> tuple[bool, dict]:
        # TODO: evaluate the three triggers, return (fired, {trigger_name: bool, values...}).
        #   dd:  20-day cumulative return of the LIVE portfolio
        #        (self.portfolio_returns) < cfg.cb_dd_threshold. If no history yet,
        #        use the return of `w` applied to the last 20 days of asset returns.
        #   geo: grs > cfg.cb_geo_threshold
        #   vol: current portfolio vol (EWMA cov, sqrt(w' S w) annualized) >
        #        cfg.cb_vol_multiplier * 252d realized portfolio vol
        #   If not cfg.use_circuit_breaker -> always (False, ...)   [ablation]
        #   NOTE: with theta_geo = 0.52 and GRS as a percentile, the geo trigger may
        #   fire very often — log the firing rate and compare to the paper.
        raise NotImplementedError

    def initial_proposal(self, data: MarketData, t: pd.Timestamp) -> AgentMessage:
        # TODO: w = min_cvar_weights(data.returns)
        #       grs = signals.compute_grs(...) last value
        #       fired, info = circuit_breaker(data, w, grs)
        #       if fired: w = defensive_portfolio(...), override=True, regime=STRESS
        #       confidence: ASSUMPTION 0.6 normally, 1.0 when fired.
        #       info: cvar of w, trigger flags.
        raise NotImplementedError

    def revise(
        self,
        data: MarketData,
        t: pd.Timestamp,
        previous: AgentMessage,
        broadcast: BroadcastMessage,
    ) -> AgentMessage:
        # TODO: re-run circuit_breaker on the CONSENSUS weights broadcast.weights
        #       (the question is "is the team's portfolio too risky?").
        #       If it fires -> return override message with defensive weights.
        #       Otherwise fall back to super().revise(...).
        raise NotImplementedError
