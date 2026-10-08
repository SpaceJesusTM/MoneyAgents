"""Data layer: download, cache and serve market data without look-ahead.

Sources (paper Sec. "Data"):
  * yfinance adjusted close + volume for the 24 ETFs, plus ^VIX
  * Caldara-Iacoviello monthly GPR index (published with a 3-4 week lag)

Everything is cached under Config.data_dir as parquet so backtests run offline
and are reproducible. Agents never see raw frames directly; they get a
MarketData view truncated at the decision date via `MarketData.until(t)`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from rmats.config import DEFAULT, UNIVERSE, VIX_TICKER, Config
from functools import cached_property


@dataclass
class MarketData:
    prices: pd.DataFrame  # (T, N) adjusted close, DatetimeIndex, columns = tickers
    volume: pd.DataFrame  # (T, N) share volume
    vix: pd.Series  # (T,) VIX close
    gpr: pd.Series  # (T,) GPR, already lagged + forward-filled to daily

    @cached_property
    def returns(self) -> pd.DataFrame:
        # Simple daily returns, first all-NaN row dropped. Cached: agents call this
        # repeatedly, and `until` builds a fresh object so the cache never leaks.
        return self.prices.pct_change(fill_method=None).iloc[1:]

    def until(self, t: pd.Timestamp) -> "MarketData":
        # THE look-ahead guard: every agent/baseline is only ever handed `data.until(t)`.
        # Inclusive slice: decisions at the close of t may use the close of t and
        # are applied from t+1.
        return MarketData(
            prices=self.prices.loc[:t],
            volume=self.volume.loc[:t],
            vix=self.vix.loc[:t],
            gpr=self.gpr.loc[:t],
        )


def download_prices(
    tickers: list[str], start: str, end: str | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Adjusted close + volume, columns ordered as `tickers`. Warm-up NaNs (e.g. XLRE
    # before 2015-10) are left in place; downstream code masks short histories.
    import yfinance as yf

    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)
    if isinstance(raw.columns, pd.MultiIndex):
        close, volume = raw["Close"], raw["Volume"]
    else:  # single ticker -> flat columns
        close, volume = raw[["Close"]], raw[["Volume"]]
        close.columns = volume.columns = tickers
    close = close.reindex(columns=tickers)
    volume = volume.reindex(columns=tickers)
    close.index = volume.index = pd.DatetimeIndex(close.index).tz_localize(None)
    return close, volume


def download_gpr(url: str) -> pd.Series:
    # Monthly headline GPR, indexed by month-END timestamps to line up with
    # month-end rebalancing.
    df = pd.read_excel(url)
    month = pd.DatetimeIndex(pd.to_datetime(df["month"]))
    idx = month.to_period("M").to_timestamp() + pd.offsets.MonthEnd(0)
    gpr = pd.Series(df["GPR"].to_numpy(dtype=float), index=idx, name="gpr")
    return gpr.dropna().sort_index()


def align_gpr_daily(gpr_monthly: pd.Series, daily_index: pd.DatetimeIndex, lag_months: int) -> pd.Series:
    # The value for month m becomes available on the LAST TRADING DAY of month
    # m + lag (not the calendar month-end, which can fall on a weekend and would
    # hide the value from that month's rebalance). With lag = 1:
    #   2023-03-15 -> Jan GPR (Feb not yet out),  2023-03-31 -> Feb GPR.
    # Caveat: if daily_index ends mid-month, that partial month's last day is
    # treated as its month-end.
    periods = daily_index.to_period("M")
    last_day = pd.Series(daily_index, index=daily_index).groupby(periods).max()
    avail_period = gpr_monthly.index.to_period("M") + lag_months
    avail = pd.Series(gpr_monthly.to_numpy(), index=avail_period)
    avail = avail[avail.index.isin(last_day.index)]
    avail.index = pd.DatetimeIndex(last_day.loc[avail.index].to_numpy())
    return avail.reindex(daily_index).ffill().rename("gpr")


def load_market_data(cfg: Config = DEFAULT, refresh: bool = False) -> MarketData:
    names = ["prices", "volume", "vix", "gpr_monthly"]
    paths = {n: _cache_path(cfg, n) for n in names}

    if not refresh and all(p.exists() for p in paths.values()):
        prices = pd.read_parquet(paths["prices"])
        volume = pd.read_parquet(paths["volume"])
        vix = pd.read_parquet(paths["vix"])["vix"]
        gpr_monthly = pd.read_parquet(paths["gpr_monthly"])["gpr"]
    else:
        end = (pd.Timestamp(cfg.test[1]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")  # yf end is exclusive
        close, vol = download_prices(UNIVERSE + [VIX_TICKER], cfg.data_start, end)
        prices, volume = close[UNIVERSE], vol[UNIVERSE]
        vix = close[VIX_TICKER].rename("vix")
        gpr_monthly = download_gpr(cfg.gpr_url)

        cfg.data_dir.mkdir(parents=True, exist_ok=True)
        prices.to_parquet(paths["prices"])
        volume.to_parquet(paths["volume"])
        vix.to_frame("vix").to_parquet(paths["vix"])
        gpr_monthly.to_frame("gpr").to_parquet(paths["gpr_monthly"])

    # Common index = ETF trading days (rows where at least one ETF printed).
    prices = prices.dropna(how="all")
    idx = prices.index
    volume = volume.reindex(idx)
    vix = vix.reindex(vix.index.union(idx)).ffill().reindex(idx)
    gpr = align_gpr_daily(gpr_monthly, idx, cfg.gpr_lag_months)
    return MarketData(prices=prices, volume=volume, vix=vix, gpr=gpr)


def rebalance_dates(index: pd.DatetimeIndex, start: str, end: str) -> pd.DatetimeIndex:
    # Last trading day of each month within [start, end].
    s = index.to_series().loc[start:end]
    return pd.DatetimeIndex(s.groupby(s.index.to_period("M")).last().to_numpy())


def _cache_path(cfg: Config, name: str) -> Path:
    return cfg.data_dir / f"{name}.parquet"
