import pytest


def test_drift_weights_stay_on_simplex():
    # TODO: drift_weights(w, r) sums to 1.
    pytest.skip("TODO")


def test_static_6040_backtest_matches_manual(synthetic_data):
    # TODO: run Static6040 on synthetic data; compare first month's returns to a
    #       hand computation (0.6 r_SPY + 0.4 r_IEF with drift), net of costs.
    pytest.skip("TODO")


def test_rmats_smoke_backtest(synthetic_data):
    # TODO: RMATSStrategy on synthetic data over 2022 runs end-to-end;
    #       returns are finite, weights rows sum to 1, len(log) == #rebalances.
    pytest.skip("TODO")


def test_event_mask_covers_configured_windows():
    # TODO: event_mask(pd.bdate_range("2023-01-01", "2024-12-31")) is True on
    #       2023-03-15 and False on 2023-06-15.
    pytest.skip("TODO")
