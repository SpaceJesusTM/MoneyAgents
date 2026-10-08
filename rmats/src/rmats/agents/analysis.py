"""Analysis Agent — HMM regime classification + Kalman signal fusion.

Paper:
  * 3-state HMM (bull / bear / stress), pi_k(t) = P(S_t = k | O_{1:t}, lambda)
    (Hamilton regime switching). FILTERED probabilities only — no smoothing,
    or you leak the future.
  * Kalman filter fuses Sentiment / Report / Analysis inputs into a composite
    signal Z(t) under partial observability.
  * Output: regime-weighted portfolio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from rmats.agents.base import Agent
from rmats.data import MarketData
from rmats.messages import AgentMessage, Regime


class ScalarKalman:
    """1-D random-walk Kalman filter: x_t = x_{t-1} + w,  y_t^j = x_t + v_j.

    Fuses several noisy observations of one latent 'risk-on' signal.
    """

    def __init__(self, q: float, r: float, x0: float = 0.0, p0: float = 1.0) -> None:
        self.q, self.r, self.x, self.p = q, r, x0, p0

    def step(self, observations: np.ndarray) -> float:
        # TODO: predict: p = p + q
        #       update with each observation y_j (sequentially, each with var r):
        #         k = p / (p + r);  x = x + k * (y_j - x);  p = (1 - k) * p
        #       skip NaN observations. Return x (the fused Z(t)).
        raise NotImplementedError


class AnalysisAgent(Agent):
    name = "analysis"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.hmm = None  # hmmlearn.hmm.GaussianHMM after fit()
        self.state_map: dict[int, Regime] = {}
        self.kalman = ScalarKalman(self.cfg.kalman_process_var, self.cfg.kalman_obs_var)

    # ---- HMM ------------------------------------------------------------- #
    def hmm_features(self, data: MarketData) -> pd.DataFrame:
        # TODO: observations O_t = [SPY daily return, SPY 20d realized vol]
        #       (cfg.hmm_vol_window). Drop NaNs. Shape (T, 2).
        raise NotImplementedError

    def fit(self, data: MarketData) -> None:
        # TODO: 1. features on the TRAINING window only (cfg.train).
        #       2. GaussianHMM(n_components=3, covariance_type="full",
        #                      random_state=cfg.hmm_seed, n_iter=200).fit(X)
        #       3. Label states: highest mean vol -> STRESS; of the remaining two,
        #          higher mean return -> BULL, other -> BEAR. Store in self.state_map.
        #       Pitfall: HMM state indices are arbitrary — always go through state_map.
        raise NotImplementedError

    def regime_probabilities(self, data: MarketData) -> pd.Series:
        # TODO: FILTERED P(S_t = k | O_1..t) for the last date, indexed by Regime.
        #       hmmlearn's predict_proba is SMOOTHED (uses the whole sequence),
        #       which is fine only if `data` is already truncated at t — it is,
        #       but the probs for t then still only use O_1..t. Double-check by
        #       comparing with a manual forward pass if unsure.
        raise NotImplementedError

    # ---- Fusion + allocation -------------------------------------------- #
    def fused_signal(self, data: MarketData, regime_probs: pd.Series) -> float:
        # TODO: observations of a "risk-on" latent (each roughly in [-1, 1]):
        #         y1 = 1 - 2 * GRS(t)                       (from sentiment signals)
        #         y2 = 2 * frac(assets with momentum > 0) - 1  (from report signals)
        #         y3 = P(BULL) - P(STRESS)                  (from the HMM)
        #       Z(t) = self.kalman.step([y1, y2, y3]).
        #       Pitfall: the Kalman state persists across rebalance dates, so the
        #       backtest must call this once per date in chronological order.
        raise NotImplementedError

    def regime_portfolio(self, data: MarketData, regime: Regime) -> pd.Series:
        # TODO: regime-conditional template (ASSUMPTION), each risk-parity within
        #       its sleeve:
        #         BULL   -> 70% equities / 20% bonds / 10% commodities
        #         BEAR   -> 40% / 45% / 15%
        #         STRESS -> 15% / 60% / 25% (commodities mostly GLD)
        raise NotImplementedError

    def initial_proposal(self, data: MarketData, t: pd.Timestamp) -> AgentMessage:
        # TODO: probs = regime_probabilities(data)
        #       w = sum_k probs[k] * regime_portfolio(data, k)  (regime-weighted)
        #       z = fused_signal(data, probs); optionally scale the equity sleeve by
        #       sigmoid(z) (ASSUMPTION).
        #       regime = argmax probs; confidence = max(probs) (ASSUMPTION);
        #       geo_risk = P(STRESS). info: probs, z.
        raise NotImplementedError
