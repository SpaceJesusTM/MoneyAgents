"""Shared fixtures: a small synthetic market so unit tests never hit the network."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from rmats.config import UNIVERSE
from rmats.data import MarketData


@pytest.fixture
def synthetic_data() -> MarketData:
    """~3 years of GBM prices for the full universe, plus fake VIX and GPR."""
    rng = np.random.default_rng(0)
    idx = pd.bdate_range("2020-01-01", "2022-12-31")
    n = len(UNIVERSE)
    rets = rng.normal(0.0003, 0.01, size=(len(idx), n))
    prices = pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=idx, columns=UNIVERSE)
    volume = pd.DataFrame(rng.integers(1_000_000, 5_000_000, size=(len(idx), n)), index=idx, columns=UNIVERSE)
    vix = pd.Series(20 + rng.normal(0, 3, len(idx)).cumsum() * 0.1, index=idx).clip(lower=9)
    gpr = pd.Series(100 + rng.normal(0, 10, len(idx)), index=idx)
    return MarketData(prices=prices, volume=volume, vix=vix, gpr=gpr)
