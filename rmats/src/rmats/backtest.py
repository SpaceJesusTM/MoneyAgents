"""Monthly-rebalance backtest engine.

Timeline convention (avoid look-ahead):
  * At the close of rebalance date t, the strategy sees data.until(t) and
    returns target weights.
  * Costs are charged at t; new weights earn returns from t+1 onward.
  * Between rebalances, weights DRIFT with asset returns (no daily rebalance).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from numpy import mean
import pandas as pd

from MoneyAgents.rmats.src.rmats import costs
from rmats.config import DEFAULT, Config
from rmats.data import MarketData
from rmats.strategy import Strategy


@dataclass
class BacktestResult:
    name: str
    returns: pd.Series  # daily net returns over the evaluation window
    weights: pd.DataFrame  # target weights at each rebalance date
    costs: pd.Series  # cost (fraction of NAV) at each rebalance date
    turnover: pd.Series
    extras: dict = field(default_factory=dict)

    @property
    def cost_bps_per_cycle(self) -> float:
        # TODO: mean(costs) * 1e4. Paper: RMATS ~1.03, MVO ~6.37.
        return mean(self.costs) * 1e4


def drift_weights(w: pd.Series, day_returns: pd.Series) -> pd.Series:
    # TODO: w_i * (1 + r_i) / sum_j w_j * (1 + r_j)  — weights after one day.
    return w * (1 + day_returns) / (w * (1 + day_returns)).sum()


def run_backtest(
    strategy: Strategy,
    data: MarketData,
    start: str,
    end: str,
    cfg: Config = DEFAULT,
) -> BacktestResult:
    # TODO:
    #   strategy.fit(data)                         # strategy restricts itself to cfg.train
    #   dates = rmats.data.rebalance_dates(data.prices.index, start, end)
    #   w = zeros (cash) ; nav = cfg.nav ; daily = []
    #   for each trading day d in [start, end]:
    #       if d is a rebalance date:
    #           strategy.on_portfolio_return(pd.Series(daily_so_far))
    #           target = strategy.target_weights(data.until(d), d)
    #           adv    = costs.average_dollar_volume(prices.until(d), volume.until(d), cfg.adv_window)
    #           c, info = costs.transaction_cost(w, target, adv, nav, cfg)
    #           record target/c/turnover ; w = target ; pending_cost = c
    #       else / and then from the NEXT day:
    #           r_p = (w * r_d).sum() - pending_cost ; pending_cost = 0
    #           w = drift_weights(w, r_d) ; nav *= 1 + r_p ; daily.append(r_p)
    #   Pitfall: the first rebalance must happen at/just before `start`, so the
    #   portfolio is invested on day one of the evaluation window. Simplest: also
    #   rebalance on the last trading day before `start`.
    #   Assets with NaN returns on a day contribute 0 (and should have 0 weight).
    strategy.fit(data)
    dates = data.rebalance_dates(start, end)
    w = pd.Series(0, index=data.prices.columns)
    nav = cfg.nav
    daily = []
    for d in range(start, end):
        if d in dates:
            strategy.on_portfolio_return(pd.Series(daily))
            target = strategy.target_weights(data.until(d), d)
            adv = costs.average_dollar_volume(data.prices.until(d), data.volume.until(d), cfg.adv_window)
            c, info = costs.transaction_cost(w, target, adv, nav, cfg)
            
            w = target
            pending_cost = c





def run_many(strategies: list[Strategy], data: MarketData, start: str, end: str, cfg: Config = DEFAULT) -> dict[str, BacktestResult]:
    # TODO: {s.name: run_backtest(s, data, start, end, cfg) for s in strategies}
    raise NotImplementedError
