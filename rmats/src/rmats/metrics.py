"""Performance metrics (paper Tables 2-3).

All functions take a daily simple-return Series of a strategy.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from rmats.config import Config


def annualized_return(r: pd.Series, periods: int = 252) -> float:
    # Geometric: prod(1 + r) ** (periods / n) - 1
    if len(r) == 0:
        return float("nan")
    return float((1 + r).prod() ** (periods / len(r)) - 1)


def annualized_vol(r: pd.Series, periods: int = 252) -> float:
    return float(r.std(ddof=1) * np.sqrt(periods))


def sharpe_ratio(r: pd.Series, rf: float = 0.0, periods: int = 252) -> float:
    # Paper target for RMATS on the test period: ~0.953. NaN for zero/undefined vol.
    std = r.std(ddof=1)
    if not np.isfinite(std) or std < 1e-12:  # constant series -> float noise, not exactly 0
        return float("nan")
    return float((r - rf / periods).mean() / std * np.sqrt(periods))


def drawdown_series(r: pd.Series) -> pd.Series:
    equity = (1 + r).cumprod()
    # Include the starting equity of 1 so a loss on day 1 counts as a drawdown.
    peak = equity.cummax().clip(lower=1.0)
    return equity / peak - 1


def max_drawdown(r: pd.Series) -> float:
    # Positive fraction, e.g. 0.0848 for the paper's 8.48%.
    if len(r) == 0:
        return float("nan")
    return float(-drawdown_series(r).min())


def cvar(r: pd.Series, alpha: float = 0.95) -> float:
    # Historical CVaR_a = -E[R | R <= VaR_a], as a positive loss.
    if len(r) == 0:
        return float("nan")
    var = r.quantile(1 - alpha)
    return float(-r[r <= var].mean())


def cumulative_return(r: pd.Series) -> float:
    # Per-event returns (Table 3).
    return float((1 + r).prod() - 1)


def risk_aware_reward(r: pd.Series, cfg: Config) -> float:
    # R = r_ann - lambda1 * sigma_ann - lambda2 * max(0, MDD - theta).
    # Used to compare settings on the VALIDATION window.
    p = cfg.periods_per_year
    return (
        annualized_return(r, p)
        - cfg.reward_lambda_vol * annualized_vol(r, p)
        - cfg.reward_lambda_dd * max(0.0, max_drawdown(r) - cfg.reward_dd_theta)
    )


def summary(r: pd.Series, cfg: Config) -> dict[str, float]:
    # One row of table_full.csv.
    p = cfg.periods_per_year
    return {
        "ann_return": annualized_return(r, p),
        "ann_vol": annualized_vol(r, p),
        "sharpe": sharpe_ratio(r, cfg.risk_free_rate, p),
        "mdd": max_drawdown(r),
        "cvar": cvar(r, cfg.cvar_alpha),
        "reward": risk_aware_reward(r, cfg),
    }


def event_split_summary(
    r: pd.Series, event_mask: pd.Series, cfg: Config
) -> dict[str, dict[str, float]]:
    # Sharpe on concatenated non-contiguous days is what the paper reports. MDD on
    # the stitched series is approximate: gaps between events are skipped, so a
    # drawdown can span two separate events.
    mask = event_mask.reindex(r.index, fill_value=False).astype(bool)
    return {"event": summary(r[mask], cfg), "non_event": summary(r[~mask], cfg)}
