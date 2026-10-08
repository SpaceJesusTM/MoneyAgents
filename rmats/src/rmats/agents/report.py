"""Report Agent — momentum + earnings-surprise proxy.

Deliberately decoupled from GRS so it can disagree with the Sentiment agent
(the disagreement is what the recursive coordination resolves).

Paper:
  w_i ∝ (1/sigma_i^{60d}) + 0.12 * m~_i        m_i = annualized 252d mean return
  ES_i = (rbar_i^{5d} - rbar_i^{60d}) / sigma_i^{60d}
Confidence c_rep = 0.52.
"""

from __future__ import annotations

import pandas as pd

from rmats.agents.base import Agent
from rmats.data import MarketData
from rmats.messages import AgentMessage, Regime


class ReportAgent(Agent):
    name = "report"

    def momentum_tilted_weights(self, returns: pd.DataFrame) -> pd.Series:
        # TODO: 1. inv = 1 / realized_vol(returns, cfg.invvol_window); normalize inv
        #          to sum to 1 so it's on the same scale as the tilt.
        #       2. m = momentum(returns, cfg.momentum_lookback); m_tilde = zscore(m)
        #          (ASSUMPTION: the paper's m~ is a normalized momentum).
        #       3. raw = inv + cfg.momentum_tilt * m_tilde  (scale the tilt by
        #          mean(inv) if it dominates — check magnitudes in a notebook!)
        #       4. return normalize_simplex(raw)
        raise NotImplementedError

    def earnings_tilt(self, returns: pd.DataFrame) -> pd.Series:
        # TODO: es = earnings_surprise_proxy(returns, cfg.es_short, cfg.es_long);
        #       return cfg.es_tilt * zscore(es)  (ASSUMPTION: a small additive tilt)
        raise NotImplementedError

    def initial_proposal(self, data: MarketData, t: pd.Timestamp) -> AgentMessage:
        # TODO: w = normalize_simplex(momentum_tilted_weights + earnings_tilt).
        #       geo_risk: the Report agent has no geo view -> report 0.5 (neutral)
        #       or the fraction of assets with negative momentum (ASSUMPTION).
        #       regime: BULL if cross-sectional median momentum > 0 else BEAR.
        #       confidence = cfg.report_confidence.
        raise NotImplementedError
