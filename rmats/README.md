# RMATS — Recursive Multi-Agent Trading System

A from-scratch reproduction of [arXiv 2605.25311](https://arxiv.org/abs/2605.25311). This is a **learning skeleton**: every function has its signature and a `# TODO` comment that explains what to implement. Each TODO gives the paper equation, the shapes involved and the pitfalls. `config.py` and `messages.py` are already complete.

## What the paper does
Every month-end, four specialist agents each propose a long-only portfolio over 24 ETFs:

| Agent | Signal | Confidence |
|---|---|---|
| Sentiment | GRS = .30 VIX + .20 defensive rotation + .20 gold premium + .15 EM stress + .15 bond flight | 0.52 |
| Report | inverse-vol + 12% momentum tilt, earnings-surprise proxy | 0.52 |
| Analysis | 3-state HMM regimes + Kalman fusion → regime-weighted portfolio | max P(regime) |
| Risk | min-CVaR, plus a circuit breaker (20d DD < −6% ∨ GRS > .52 ∨ vol > 1.8σ₂₅₂) | — |

The **Manager** weights each proposal by confidence × health and combines them: `w̄ = Σ cᵢHᵢwᵢ / Σ cᵢHᵢ`. It broadcasts the result, the agents revise, and this repeats until `‖Δw̄‖₂ < 0.005` or 3 rounds have run. A firing circuit breaker skips all of this and goes straight to a defensive allocation. Otherwise a constrained mean-variance layer enforces leverage, group caps and geo-exposure caps (`γ_geo` = 0.65, or 0.45 when GRS > 0.52).

Paper targets for the test period (2023-01 → 2026-03): **Sharpe 0.953, MDD 8.48%, ann. return 13.0%.**

## Setup
```bash
# install uv: https://docs.astral.sh/uv/  (or: pip install uv)
cd rmats
uv sync
uv run pytest                                  # all tests are skipped until you implement them
uv run python -m rmats.experiments --help
```

## Learning path (suggested order)
1. **`data.py`**: `download_prices`, `download_gpr`, `align_gpr_daily`, `load_market_data`, `MarketData.until`, `rebalance_dates`. Cache the data once, then work offline.
2. **`signals.py` + `metrics.py`**: small pure functions. Fill in `tests/test_signals_metrics.py` as you go.
3. **Agents**, one at a time: `base.revise`, then `sentiment.py`, `report.py`, `analysis.py` (HMM + Kalman) and `risk.py` (CVaR LP + circuit breaker). Tests: `tests/test_agents.py`.
4. **`manager.py`**, then **`optimizer.py`**, then **`costs.py`**. Tests: `tests/test_manager_optimizer.py`.
5. **`strategy.py` + `backtest.py`**: get `Static6040` running first because it's the easiest to check by hand, then RMATS.
6. **`baselines.py`, `events.py`, `experiments.py`**: reproduce Tables 2–3.
7. **Ablations**: r = 1 forced, no circuit breaker, GRS source, GRS weights ±20%.

Rule: calibrate anything on **2021–2022 (validation)** only. Never tune on the test period.

## Assumptions (where the paper is underspecified)
| Area | Assumption | Where |
|---|---|---|
| GRS components | each one is a 252-day rolling percentile rank of a 20-day relative return (VIX: level) | `signals.grs_components` |
| Sentiment weights | inverse-vol, tilted toward bonds/GLD/XLP/XLU/XLV in proportion to GRS | `SentimentAgent.defensive_tilt` |
| Momentum `m̃` | cross-sectional z-score; ES proxy is a small additive tilt (3%) | `ReportAgent` |
| HMM features | SPY return + 20d realized vol, fit on 2016–2020 | `AnalysisAgent.fit` |
| Kalman | scalar random walk fusing (1−2·GRS, momentum breadth, P(bull)−P(stress)) | `ScalarKalman` |
| Regime templates | bull 70/20/10, bear 40/45/15, stress 15/60/25 (equity/bond/commodity) | `AnalysisAgent.regime_portfolio` |
| CVaR | α = 95%, historical 252-day scenarios; EWMA λ = 0.94 | `RiskAgent`, `config` |
| Health A/S/R/L | built from each agent's own paper-portfolio return, stability, vol and drawdown over 63 days | `Manager.health_components` |
| Revision rule | `w ← w + (1−c)·η·(w̄ − w)`, η = 0.5 | `Agent.revise` |
| Optimizer μ | implied from consensus, `μ = 2λΣw̄`, so the solve is a projection of w̄ | `optimizer.optimize` |
| Geo exposure `g` and group caps | static tables | `config.GEO_EXPOSURE`, `GROUP_CAPS` |
| Costs | NAV = $10M; slippage interpretation documented in the TODO | `costs.transaction_cost` |
| 60/40 | SPY / IEF | `baselines.Static6040` |
| Event day bounds | the full calendar months listed in the paper | `config.EVENTS` |

Out of scope by choice: DQN RL, MAPS-lite and the FinBERT baselines.
