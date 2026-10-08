"""All hyperparameters, the asset universe, sample periods and stress events.

Everything tunable lives here so experiments/ablations only swap a Config.
Values marked "ASSUMPTION" are not specified in the paper; see README.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

# --------------------------------------------------------------------------- #
# Universe (paper: 24 ETFs)
# --------------------------------------------------------------------------- #
US_SECTORS = ["XLK", "XLE", "XLF", "XLV", "XLI", "XLP", "XLY", "XLU", "XLB", "XLRE"]
INTL_EQUITY = ["EWJ", "EWG", "EWU", "FXI", "EEM"]
FIXED_INCOME = ["TLT", "IEF", "LQD", "EMB"]
COMMODITIES = ["GLD", "SLV", "USO", "DBC"]
BENCHMARK = ["SPY"]

UNIVERSE: list[str] = US_SECTORS + INTL_EQUITY + FIXED_INCOME + COMMODITIES + BENCHMARK
VIX_TICKER = "^VIX"

ASSET_CLASS: dict[str, str] = {
    **{t: "us_sector" for t in US_SECTORS},
    **{t: "intl_equity" for t in INTL_EQUITY},
    **{t: "fixed_income" for t in FIXED_INCOME},
    **{t: "commodity" for t in COMMODITIES},
    "SPY": "us_broad",
}

# Circuit-breaker / GPR-rule safe haven: bonds + gold.
DEFENSIVE: list[str] = FIXED_INCOME + ["GLD"]
# ASSUMPTION: the Sentiment agent also tilts toward defensive equity sectors.
DEFENSIVE_EQUITY: list[str] = ["XLP", "XLU", "XLV"]
CYCLICAL_EQUITY: list[str] = ["XLK", "XLY"]

# ASSUMPTION: static geopolitical exposure g_i in [0, 1] per asset, used in the
# optimizer constraint w^T g <= gamma_geo. Paper: "sector-average normalized GPR
# exposure". Replace with an estimated beta-to-GPR if you want to be fancier.
GEO_EXPOSURE: dict[str, float] = {
    "XLK": 0.55, "XLE": 0.80, "XLF": 0.60, "XLV": 0.30, "XLI": 0.60,
    "XLP": 0.25, "XLY": 0.55, "XLU": 0.25, "XLB": 0.65, "XLRE": 0.45,
    "EWJ": 0.60, "EWG": 0.70, "EWU": 0.60, "FXI": 0.95, "EEM": 0.85,
    "TLT": 0.10, "IEF": 0.10, "LQD": 0.25, "EMB": 0.70,
    "GLD": 0.15, "SLV": 0.40, "USO": 0.90, "DBC": 0.75,
    "SPY": 0.55,
}

# ASSUMPTION: group caps for the per-sector constraint w_s <= c_s.
GROUP_CAPS: dict[str, float] = {
    "us_sector": 0.60,
    "intl_equity": 0.35,
    "fixed_income": 0.70,
    "commodity": 0.35,
    "us_broad": 0.40,
}
MAX_SINGLE_WEIGHT = 0.25  # ASSUMPTION

# --------------------------------------------------------------------------- #
# Stress events (paper Table 3). Day bounds are ASSUMPTIONS within the stated months.
# --------------------------------------------------------------------------- #
EVENTS: dict[str, tuple[str, str]] = {
    "SVB": ("2023-03-01", "2023-03-31"),
    "Israel-Hamas": ("2023-10-01", "2023-11-30"),
    "US-China Tech": ("2024-01-01", "2024-02-29"),
    "Mid-East": ("2024-04-01", "2024-05-31"),
    "Rate Pivot": ("2024-08-01", "2024-09-30"),
}

GRSSource = Literal["proxy", "gpr", "blend"]


@dataclass(frozen=True)
class Config:
    # --- paths ------------------------------------------------------------- #
    root: Path = Path(__file__).resolve().parents[2]
    data_dir: Path = field(default=Path(__file__).resolve().parents[2] / "data")
    results_dir: Path = field(default=Path(__file__).resolve().parents[2] / "results")
    gpr_url: str = "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls"

    # --- sample periods ---------------------------------------------------- #
    data_start: str = "2015-01-01"  # one year of warm-up before training
    train: tuple[str, str] = ("2016-01-01", "2020-12-31")
    validation: tuple[str, str] = ("2021-01-01", "2022-12-31")
    test: tuple[str, str] = ("2023-01-01", "2026-03-31")
    rebalance_freq: str = "ME"  # pandas month-end alias
    gpr_lag_months: int = 1  # month t-1 GPR used for month t decisions

    # --- Sentiment agent: GRS composite ------------------------------------ #
    grs_weights: dict[str, float] = field(default_factory=lambda: {
        "vix": 0.30,
        "defensive_rotation": 0.20,
        "gold_premium": 0.20,
        "em_stress": 0.15,
        "bond_flight": 0.15,
    })
    grs_rank_window: int = 252  # ASSUMPTION: rolling percentile-rank window
    grs_return_window: int = 20  # ASSUMPTION: relative-return lookback
    grs_source: GRSSource = "proxy"
    sentiment_confidence: float = 0.52

    # --- Report agent ------------------------------------------------------ #
    momentum_lookback: int = 252
    invvol_window: int = 60
    momentum_tilt: float = 0.12
    es_short: int = 5
    es_long: int = 60
    es_tilt: float = 0.03  # ASSUMPTION
    report_confidence: float = 0.52

    # --- Analysis agent ---------------------------------------------------- #
    hmm_states: int = 3
    hmm_seed: int = 42
    hmm_vol_window: int = 20
    kalman_process_var: float = 1e-3  # ASSUMPTION (Q)
    kalman_obs_var: float = 1e-2  # ASSUMPTION (R)

    # --- Risk agent -------------------------------------------------------- #
    ewma_lambda: float = 0.94  # ASSUMPTION (RiskMetrics)
    cvar_alpha: float = 0.95  # ASSUMPTION
    cvar_window: int = 252
    cb_dd_threshold: float = -0.06  # 20-day cumulative return
    cb_dd_window: int = 20
    cb_geo_threshold: float = 0.52
    cb_vol_multiplier: float = 1.8
    cb_vol_window: int = 252
    use_circuit_breaker: bool = True

    # --- Manager ----------------------------------------------------------- #
    health_weights: tuple[float, float, float, float] = (0.25, 0.25, 0.25, 0.25)
    health_window: int = 63  # ASSUMPTION: ~3 months of each agent's paper P&L
    health_floor: float = 0.05  # ASSUMPTION
    consensus_step: float = 0.5  # ASSUMPTION: eta in w_i <- w_i + (1-c_i)*eta*(w_bar-w_i)
    convergence_eps: float = 0.005
    max_rounds: int = 3

    # --- Optimizer --------------------------------------------------------- #
    lambda_mv: float = 2.0
    leverage_max: float = 1.0
    gamma_geo_normal: float = 0.65
    gamma_geo_stress: float = 0.45
    grs_stress_threshold: float = 0.52

    # --- Reward (reported metric) ------------------------------------------ #
    reward_lambda_vol: float = 0.8
    reward_lambda_dd: float = 1.5
    reward_dd_theta: float = 0.05  # ASSUMPTION

    # --- Costs ------------------------------------------------------------- #
    fixed_cost_bps: float = 10.0
    slippage_kappa: float = 0.1
    nav: float = 10_000_000.0  # ASSUMPTION
    adv_window: int = 30

    # --- Metrics ----------------------------------------------------------- #
    periods_per_year: int = 252
    risk_free_rate: float = 0.0  # ASSUMPTION

    def with_(self, **kwargs) -> "Config":
        """Return a copy with some fields overridden (handy for ablations)."""
        return replace(self, **kwargs)


DEFAULT = Config()
