"""Strategy interface consumed by the backtester, plus the RMATS strategy.

A Strategy maps (data truncated at t, t) -> target weights. Baselines and
RMATS share this interface so the backtester treats them identically.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from rmats.agents import AnalysisAgent, ReportAgent, RiskAgent, SentimentAgent
from rmats.config import DEFAULT, Config
from rmats.data import MarketData
from rmats.manager import Manager
from rmats.messages import CoordinationResult


class Strategy(Protocol):
    name: str

    def fit(self, data: MarketData) -> None: ...

    def target_weights(self, data: MarketData, t: pd.Timestamp) -> pd.Series: ...

    def on_portfolio_return(self, portfolio_returns: pd.Series) -> None:
        """Hook: backtester passes the realized strategy returns up to t."""
        ...


class RMATSStrategy:
    name = "RMATS"

    def __init__(self, cfg: Config = DEFAULT, force_single_round: bool = False) -> None:
        self.cfg = cfg
        self.force_single_round = force_single_round
        self.risk = RiskAgent(cfg)
        self.agents = [SentimentAgent(cfg), ReportAgent(cfg), AnalysisAgent(cfg), self.risk]
        self.manager = Manager(self.agents, cfg)
        self.log: list[tuple[pd.Timestamp, CoordinationResult]] = []

    def fit(self, data: MarketData) -> None:
        # TODO: call agent.fit(data) for each agent (only the HMM actually trains).
        #       Pass data restricted to cfg.train so nothing beyond 2020 is used.
        raise NotImplementedError

    def on_portfolio_return(self, portfolio_returns: pd.Series) -> None:
        # TODO: forward to self.risk.portfolio_returns (circuit-breaker DD/vol triggers).
        raise NotImplementedError

    def target_weights(self, data: MarketData, t: pd.Timestamp) -> pd.Series:
        # TODO: 1. result = self.manager.coordinate(data, t, self.force_single_round)
        #       2. if result.cb_active: return result.weights (skip the optimizer —
        #          the defensive allocation is final)
        #       3. cov = signals.ewma_covariance(data.returns, cfg.ewma_lambda)
        #          grs = signals.compute_grs(...) at t
        #          w = optimizer.optimize(result.weights, cov, grs, cfg)
        #       4. self.log.append((t, result)); return w
        raise NotImplementedError
