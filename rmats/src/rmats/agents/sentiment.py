"""Sentiment Agent — geopolitical risk from market-implied signals.

Paper: GRS = 0.30 VIX + 0.20 defensive rotation + 0.20 gold premium
            + 0.15 EM stress + 0.15 bond flight-to-quality
(optionally the lagged Caldara-Iacoviello GPR index). It's a *coincident*
indicator built from prices, not LLM text inference. Confidence c_sent = 0.52.
"""

from __future__ import annotations

import pandas as pd

from rmats.agents.base import Agent
from rmats.config import DEFENSIVE, DEFENSIVE_EQUITY
from rmats.data import MarketData
from rmats.messages import AgentMessage, Regime


class SentimentAgent(Agent):
    name = "sentiment"

    def geo_risk(self, data: MarketData) -> float:
        # TODO: signals.compute_grs(data.prices, data.vix, data.gpr, self.cfg)
        #       and return the LAST value (as of t), as a float in [0, 1].
        #       Handle NaN during warm-up (return 0.5 = neutral).
        raise NotImplementedError

    def defensive_tilt(self, base: pd.Series, grs: float) -> pd.Series:
        # TODO: shift weight from risky assets to DEFENSIVE + DEFENSIVE_EQUITY in
        #       proportion to GRS (ASSUMPTION, paper only says it "tilts defensive"):
        #         safe = DEFENSIVE + DEFENSIVE_EQUITY
        #         w = (1 - grs) * base + grs * base_restricted_to(safe, renormalized)
        #       Return normalize_simplex(w).
        raise NotImplementedError

    def regime_from_grs(self, grs: float) -> Regime:
        # TODO: simple mapping (ASSUMPTION): grs > cfg.cb_geo_threshold -> STRESS,
        #       grs > ~0.40 -> BEAR, else BULL.
        raise NotImplementedError

    def initial_proposal(self, data: MarketData, t: pd.Timestamp) -> AgentMessage:
        # TODO: 1. grs = self.geo_risk(data)
        #       2. base = signals.inverse_vol_weights(data.returns, cfg.invvol_window)
        #       3. w = self.defensive_tilt(base, grs)
        #       4. AgentMessage(agent=self.name, weights=w,
        #                       confidence=cfg.sentiment_confidence, geo_risk=grs,
        #                       regime=self.regime_from_grs(grs), timestamp=t)
        #       Put the GRS components in `info` for later diagnostics.
        raise NotImplementedError
