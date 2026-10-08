"""Geopolitical stress-event windows and their evaluation.

Paper selection criteria (all three must hold):
  1. GPR >= 75th pct (2000-2023) for >= 10 consecutive trading days
  2. VIX rises >= 15% within a 5-day window
  3. cross-asset correlation rises >= 0.10 vs the 30-day pre-event baseline
Five qualifying events are hard-coded in config.EVENTS. `check_event_criteria`
lets you verify them against the data rather than trusting the dates blindly.
"""

from __future__ import annotations

import pandas as pd

from rmats.config import EVENTS
from rmats.data import MarketData


def event_mask(index: pd.DatetimeIndex, events: dict[str, tuple[str, str]] = EVENTS) -> pd.Series:
    # TODO: boolean Series on `index`, True on days inside ANY event window.
    raise NotImplementedError


def per_event_returns(returns: dict[str, pd.Series], events: dict[str, tuple[str, str]] = EVENTS) -> pd.DataFrame:
    # TODO: rows = strategy, cols = event, value = cumulative return over the window
    #       (metrics.cumulative_return). Reproduces paper Table 3.
    raise NotImplementedError


def check_event_criteria(data: MarketData, start: str, end: str) -> dict[str, bool | float]:
    # TODO: compute the three criteria above for a window and return the values
    #       and pass/fail flags. Cross-asset correlation = mean off-diagonal Pearson
    #       correlation of daily returns, event window vs the 30 days before it.
    raise NotImplementedError


def ks_test_grs(grs: pd.Series, mask: pd.Series) -> tuple[float, float]:
    # TODO: scipy.stats.ks_2samp(grs[mask], grs[~mask]) -> (statistic, p-value).
    #       Paper: KS = 0.1464, p = 0.0001 (event days mean GPR 0.588 vs 0.514).
    raise NotImplementedError
