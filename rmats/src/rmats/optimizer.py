"""Portfolio optimization layer (applied after the Manager's consensus).

Paper:
  max_w  mu^T w - lambda_MV w^T Sigma w        (lambda_MV = 2)
  s.t.   ||w||_1 <= L_max                      (gross leverage)
         w_s <= c_s  for each sector/group s
         w^T g(t) <= gamma_geo                 (geopolitical exposure)
  gamma_geo tightens 0.65 -> 0.45 when aggregate GRS > 0.52.

ASSUMPTION: mu is the return implied by the consensus, mu = 2 * lambda_MV * Sigma * w_bar,
so the unconstrained optimum is exactly w_bar and the solve becomes a
Sigma-metric projection of w_bar onto the constraint set. The agents decide
"what", the optimizer only enforces "within limits".
"""

from __future__ import annotations

import pandas as pd

from rmats.config import ASSET_CLASS, DEFAULT, GEO_EXPOSURE, GROUP_CAPS, MAX_SINGLE_WEIGHT, Config


def implied_returns(w_bar: pd.Series, cov: pd.DataFrame, lambda_mv: float) -> pd.Series:
    # TODO: first-order condition of mu^T w - lambda w^T S w  ->  mu = 2 * lambda * S @ w.
    #       Return as a Series aligned with w_bar.
    raise NotImplementedError


def gamma_geo(grs: float, cfg: Config = DEFAULT) -> float:
    # TODO: cfg.gamma_geo_stress if grs > cfg.grs_stress_threshold else cfg.gamma_geo_normal
    raise NotImplementedError


def optimize(
    w_bar: pd.Series,
    cov: pd.DataFrame,
    grs: float,
    cfg: Config = DEFAULT,
    mu: pd.Series | None = None,
) -> pd.Series:
    # TODO: with cvxpy:
    #   w = cp.Variable(n)
    #   mu = mu if given else implied_returns(w_bar, cov, cfg.lambda_mv)
    #   objective = cp.Maximize(mu @ w - cfg.lambda_mv * cp.quad_form(w, cp.psd_wrap(S)))
    #   constraints:
    #       cp.sum(w) == 1, w >= 0, cp.norm1(w) <= cfg.leverage_max,
    #       w <= MAX_SINGLE_WEIGHT,
    #       for each group in GROUP_CAPS: sum of w over tickers with ASSET_CLASS==group <= cap,
    #       g @ w <= gamma_geo(grs, cfg)  with g from GEO_EXPOSURE
    #   Solve (CLARABEL/ECOS/OSQP). If infeasible (e.g. gamma_geo too tight for
    #   the group caps), relax gamma_geo step by step, and log it.
    #   Return normalize_simplex(pd.Series(w.value, index=w_bar.index)).
    #   Test: with loose constraints the output must equal w_bar (up to solver tol).
    raise NotImplementedError


def _group_masks(tickers: list[str]) -> dict[str, list[int]]:
    # TODO: {group: [positions of tickers in that group]} from ASSET_CLASS.
    raise NotImplementedError
