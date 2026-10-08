"""Baseline strategies (paper Table 2), sharing the Strategy interface.

Implemented here: Static 60/40, MVO, Multi-Factor, GPR Rule-Based.
Out of scope (by choice): DQN RL, MAPS-lite, FinBERT proxy.
"""

from __future__ import annotations

import pandas as pd

from rmats.config import DEFAULT, DEFENSIVE, Config
from rmats.data import MarketData


class _Base:
    name = "base"

    def __init__(self, cfg: Config = DEFAULT) -> None:
        self.cfg = cfg

    def fit(self, data: MarketData) -> None:
        pass

    def on_portfolio_return(self, portfolio_returns: pd.Series) -> None:
        pass

    def target_weights(self, data: MarketData, t: pd.Timestamp) -> pd.Series:
        raise NotImplementedError


class Static6040(_Base):
    name = "Static 60/40"

    def target_weights(self, data: MarketData, t: pd.Timestamp) -> pd.Series:
        # TODO: 60% SPY / 40% IEF (ASSUMPTION — the paper doesn't say which bond ETF),
        #       0 on all other tickers. Paper: Sharpe 0.381, MDD 11.23%.
        raise NotImplementedError


class MVO(_Base):
    name = "MVO"

    def target_weights(self, data: MarketData, t: pd.Timestamp) -> pd.Series:
        # TODO: Markowitz with 252-day SAMPLE mean (annualized) and covariance:
        #         max mu^T w - lambda_MV w^T S w,  sum w = 1, w >= 0
        #       (no group/geo constraints — it's the naive baseline).
        #       Paper: Sharpe 0.755, MDD 15.84%, highest turnover/costs.
        raise NotImplementedError


class MultiFactor(_Base):
    name = "Multi-Factor"

    def target_weights(self, data: MarketData, t: pd.Timestamp) -> pd.Series:
        # TODO: equal-weight average of cross-sectional z-scores:
        #         12-month momentum, 60-day inverse vol, 1-month reversal (-21d return),
        #         rolling 252-day Sharpe
        #       Then: pick the top-k (ASSUMPTION k = 8) equal-weighted, or softmax.
        #       Paper: Sharpe 0.703, MDD 10.12%.
        raise NotImplementedError


class GPRRuleBased(_Base):
    name = "GPR Rule-Based"

    def target_weights(self, data: MarketData, t: pd.Timestamp) -> pd.Series:
        # TODO: grs = compute_grs(...) at t
        #       grs > 0.52 -> 100% DEFENSIVE (inverse-vol within DEFENSIVE)
        #       else       -> risk parity across the full universe (inverse-vol proxy)
        #       Paper: Sharpe 0.500, MDD 10.38%.
        raise NotImplementedError


def all_baselines(cfg: Config = DEFAULT) -> list[_Base]:
    return [Static6040(cfg), MVO(cfg), MultiFactor(cfg), GPRRuleBased(cfg)]


__all__ = ["Static6040", "MVO", "MultiFactor", "GPRRuleBased", "all_baselines"]
