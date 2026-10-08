"""Experiment runner: reproduces the paper's tables, ablations and plots.

    python -m rmats.experiments --download          # fetch + cache data
    python -m rmats.experiments --main              # Table 2 + event tables
    python -m rmats.experiments --ablations
    python -m rmats.experiments --all
    python -m rmats.experiments --all --period validation
"""

from __future__ import annotations

import argparse

from rmats.backtest import BacktestResult
from rmats.config import DEFAULT, Config
from rmats.data import MarketData


def period_bounds(cfg: Config, period: str) -> tuple[str, str]:
    return {"train": cfg.train, "validation": cfg.validation, "test": cfg.test}[period]


def run_main(data: MarketData, cfg: Config, period: str) -> dict[str, BacktestResult]:
    # TODO: strategies = [RMATSStrategy(cfg)] + all_baselines(cfg)
    #       results = run_many(strategies, data, *period_bounds(cfg, period), cfg)
    #       write results/table_full.csv       (metrics.summary + cost_bps_per_cycle)
    #             results/table_events.csv     (metrics.event_split_summary)
    #             results/table_event_returns.csv (events.per_event_returns)
    #             results/convergence.csv      (rounds per date from RMATSStrategy.log)
    #       print the tables next to the paper's numbers for a quick comparison.
    raise NotImplementedError


def run_ablations(data: MarketData, cfg: Config, period: str) -> None:
    # TODO: variants (name -> strategy):
    #         "RMATS"              RMATSStrategy(cfg)
    #         "r=1 forced"         RMATSStrategy(cfg, force_single_round=True)   paper dSharpe ~ -0.002
    #         "no circuit breaker" RMATSStrategy(cfg.with_(use_circuit_breaker=False))
    #         "GRS=gpr"            RMATSStrategy(cfg.with_(grs_source="gpr"))
    #         "GRS weights +/-20%" perturb each grs_weights entry, renormalize
    #       Write results/table_ablation.csv with full + event-period Sharpe/MDD.
    raise NotImplementedError


def plot_equity_curves(results: dict[str, BacktestResult], cfg: Config) -> None:
    # TODO: matplotlib: top panel cumulative NAV per strategy, bottom panel
    #       drawdowns; shade config.EVENTS windows. Save results/equity_curves.png.
    raise NotImplementedError


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="rmats.experiments", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--download", action="store_true", help="download/refresh the data cache")
    p.add_argument("--main", action="store_true", help="run RMATS + baselines, write tables")
    p.add_argument("--ablations", action="store_true", help="run ablation variants")
    p.add_argument("--plots", action="store_true", help="plot equity curves (implies --main)")
    p.add_argument("--all", action="store_true", help="everything")
    p.add_argument("--period", choices=["train", "validation", "test"], default="test")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    cfg = DEFAULT
    # TODO: wire it up:
    #   data = load_market_data(cfg, refresh=args.download)
    #   cfg.results_dir.mkdir(parents=True, exist_ok=True)
    #   if args.main or args.plots or args.all: results = run_main(data, cfg, args.period)
    #   if args.plots or args.all: plot_equity_curves(results, cfg)
    #   if args.ablations or args.all: run_ablations(data, cfg, args.period)
    raise NotImplementedError("experiments.main: see TODO")


if __name__ == "__main__":
    main()
