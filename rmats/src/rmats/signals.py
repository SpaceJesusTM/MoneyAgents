"""Reusable signal / risk-model helpers shared by agents and baselines.

All functions take data that is ALREADY truncated at the decision date and
return the value "as of" the last row. None of them may peek forward.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from rmats.config import CYCLICAL_EQUITY, DEFENSIVE_EQUITY, Config


# --------------------------------------------------------------------------- #
# Generic helpers
# --------------------------------------------------------------------------- #
def normalize_simplex(w: pd.Series) -> pd.Series:
    # Clip negatives, NaN -> 0, rescale to sum 1; equal weight if nothing survives.
    # Every agent output must pass through this.
    w = w.astype(float).fillna(0.0).clip(lower=0.0)
    total = w.sum()
    if total <= 0 or not np.isfinite(total):
        return pd.Series(1.0 / len(w), index=w.index)
    return w / total


def rolling_percentile_rank(x: pd.Series, window: int) -> pd.Series:
    # Percentile of each value within its trailing `window` observations, in (0, 1].
    # NaN until a full window is available. Puts every GRS component on one scale.
    return x.rolling(window, min_periods=window).rank(pct=True)


def realized_vol(returns: pd.DataFrame, window: int, annualize: int | None = 252) -> pd.Series:
    # Per-asset std of the last `window` daily returns. Assets without a full
    # window of history (e.g. XLRE early on) get NaN.
    r = returns.iloc[-window:]
    vol = r.std(ddof=1)
    vol[r.count() < window] = np.nan
    if annualize:
        vol = vol * np.sqrt(annualize)
    return vol


def inverse_vol_weights(returns: pd.DataFrame, window: int) -> pd.Series:
    # w_i ∝ 1/sigma_i; NaN or zero vol (insufficient history / dead series) -> 0.
    vol = realized_vol(returns, window, annualize=None)
    inv = 1.0 / vol.where(vol > 0)
    return normalize_simplex(inv.fillna(0.0))


def ewma_covariance(returns: pd.DataFrame, lam: float) -> pd.DataFrame:
    # RiskMetrics EWMA covariance as of the last row (zero-mean):
    #   Sigma_t = lam * Sigma_{t-1} + (1 - lam) * r_t r_t^T
    # Unrolled: Sigma_t = sum_k w_k r_{t-k} r_{t-k}^T with w_k ∝ lam^k, normalized
    # to sum 1 so a short history is not biased toward 0. Missing returns count
    # as 0. A 1e-8 ridge keeps it strictly PD for cvxpy.
    r = returns.fillna(0.0).to_numpy()
    k = np.arange(len(r))[::-1]  # 0 for the most recent row
    w = lam**k
    w /= w.sum()
    sigma = (r * w[:, None]).T @ r
    sigma = 0.5 * (sigma + sigma.T) + 1e-8 * np.eye(r.shape[1])
    return pd.DataFrame(sigma, index=returns.columns, columns=returns.columns)


# --------------------------------------------------------------------------- #
# Sentiment: Geopolitical Risk Score (GRS) composite
# --------------------------------------------------------------------------- #
def grs_components(prices: pd.DataFrame, vix: pd.Series, cfg: Config) -> pd.DataFrame:
    # Each column is a rolling percentile rank in [0, 1]; higher = MORE stress.
    k = cfg.grs_return_window
    ret_k = prices.pct_change(k, fill_method=None)
    vix = vix.reindex(prices.index).ffill()

    raw = {
        "vix": vix,
        "defensive_rotation": ret_k[DEFENSIVE_EQUITY].mean(axis=1) - ret_k[CYCLICAL_EQUITY].mean(axis=1),
        "gold_premium": ret_k["GLD"] - ret_k["SPY"],
        "em_stress": -(ret_k["EEM"] - ret_k["SPY"]),  # EM underperformance = stress
        "bond_flight": ret_k["TLT"] - ret_k["SPY"],
    }
    return pd.DataFrame(
        {name: rolling_percentile_rank(raw[name], cfg.grs_rank_window) for name in cfg.grs_weights}
    )


def grs_composite(components: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    # GRS(t) = sum_k weights[k] * components[k](t). Divided by sum(weights) so the
    # ±20% weight ablations still land in [0, 1]. NaN while any component warms up.
    w = pd.Series(weights, dtype=float)
    grs = (components[w.index] * w).sum(axis=1, min_count=len(w)) / w.sum()
    return grs.rename("grs")


def gpr_percentile(gpr_daily: pd.Series, window: int) -> pd.Series:
    # The lagged GPR on the same [0, 1] scale as the proxy GRS.
    return rolling_percentile_rank(gpr_daily, window).rename("grs")


def compute_grs(prices: pd.DataFrame, vix: pd.Series, gpr_daily: pd.Series, cfg: Config) -> pd.Series:
    if cfg.grs_source == "proxy":
        return grs_composite(grs_components(prices, vix, cfg), cfg.grs_weights)
    gpr = gpr_percentile(gpr_daily.reindex(prices.index).ffill(), cfg.grs_rank_window)
    if cfg.grs_source == "gpr":
        return gpr
    if cfg.grs_source == "blend":  # ASSUMPTION: equal blend
        proxy = grs_composite(grs_components(prices, vix, cfg), cfg.grs_weights)
        return (0.5 * proxy + 0.5 * gpr).rename("grs")
    raise ValueError(f"unknown grs_source {cfg.grs_source!r}")


# --------------------------------------------------------------------------- #
# Report: momentum + earnings-surprise proxy
# --------------------------------------------------------------------------- #
def momentum(returns: pd.DataFrame, lookback: int, periods_per_year: int = 252) -> pd.Series:
    # Annualized mean daily return over the last `lookback` days; NaN without full history.
    r = returns.iloc[-lookback:]
    m = r.mean() * periods_per_year
    m[r.count() < lookback] = np.nan
    return m


def earnings_surprise_proxy(returns: pd.DataFrame, short: int, long: int) -> pd.Series:
    # ES_i = (mean_r_short - mean_r_long) / std_r_long: a short-term price reaction
    # standing in for EPS surprises (no proprietary earnings data).
    r_long = returns.iloc[-long:]
    std = r_long.std(ddof=1)
    es = (returns.iloc[-short:].mean() - r_long.mean()) / std.where(std > 0)
    es[r_long.count() < long] = np.nan
    return es


def zscore(x: pd.Series) -> pd.Series:
    # Cross-sectional z-score. NaN inputs (no history) map to 0 = neutral; all
    # zeros if the cross-section has no dispersion.
    std = x.std(ddof=1)
    if not np.isfinite(std) or std < 1e-12:
        return pd.Series(0.0, index=x.index)
    return ((x - x.mean()) / std).fillna(0.0)
