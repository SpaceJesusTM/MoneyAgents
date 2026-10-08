"""Transaction cost model (paper Sec. "Transaction costs").

  fixed:     10 bps on traded notional, i.e. 0.0010 * sum_i |dw_i|
  slippage:  c_i = kappa * |dw_i| * P / ADV_i    (kappa = 0.1)
             P = portfolio NAV, ADV_i = 30-day average daily DOLLAR volume

Paper reference: RMATS ~1.03 bps per monthly cycle, MVO ~6.37 bps.
"""

from __future__ import annotations

import pandas as pd

from rmats.config import DEFAULT, Config


def average_dollar_volume(prices: pd.DataFrame, volume: pd.DataFrame, window: int) -> pd.Series:
    # TODO: (prices * volume).iloc[-window:].mean() per ticker, as of the last row.
    raise NotImplementedError


def transaction_cost(
    w_old: pd.Series,
    w_new: pd.Series,
    adv: pd.Series,
    nav: float,
    cfg: Config = DEFAULT,
) -> tuple[float, dict[str, float]]:
    # TODO: dw = |w_new - w_old| (aligned, fill 0)
    #       fixed    = cfg.fixed_cost_bps / 1e4 * dw.sum()
    #       slippage = see note below
    #   Careful: the paper's formula  kappa * |dw_i| * P / ADV_i  is a cost RATE
    #   (fraction of the traded notional). As a fraction of NAV that is
    #       sum_i dw_i * (kappa * dw_i * P / ADV_i)
    #   Decide, document, and sanity-check against ~1 bps/cycle.
    #   Return (total cost as a fraction of NAV, {"fixed": ..., "slippage": ..., "turnover": dw.sum()}).
    raise NotImplementedError
