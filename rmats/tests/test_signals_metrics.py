import pytest


def test_normalize_simplex_sums_to_one_and_nonnegative():
    # TODO: random Series with negatives/NaNs -> output >= 0, sums to 1;
    #       all-negative input -> equal weight.
    pytest.skip("TODO")


def test_grs_in_unit_interval(synthetic_data):
    # TODO: compute_grs(...) after warm-up is within [0, 1] and has no NaNs.
    pytest.skip("TODO")


def test_grs_has_no_lookahead(synthetic_data):
    # TODO: GRS at date t computed on data.until(t) == GRS at t computed on full data.
    pytest.skip("TODO")


def test_ewma_cov_is_psd(synthetic_data):
    # TODO: min eigenvalue of ewma_covariance(...) >= 0.
    pytest.skip("TODO")


def test_max_drawdown_known_series():
    # TODO: returns [+0.1, -0.5, +0.2] -> MDD = 0.5 (positive fraction).
    pytest.skip("TODO")


def test_sharpe_constant_returns_is_nan_or_inf_safe():
    # TODO: zero-vol series must not raise.
    pytest.skip("TODO")
