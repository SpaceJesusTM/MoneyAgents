import pytest


def test_aggregate_is_convex_combination():
    # TODO: two hand-made messages with known c, H -> w_bar equals the formula
    #       sum c_i H_i w_i / sum c_i H_i, and lies on the simplex.
    pytest.skip("TODO")


def test_coordination_terminates_within_max_rounds(synthetic_data):
    # TODO: Manager(...).coordinate(...) -> result.rounds <= cfg.max_rounds.
    pytest.skip("TODO")


def test_force_single_round(synthetic_data):
    # TODO: force_single_round=True -> result.rounds == 1.
    pytest.skip("TODO")


def test_override_bypasses_convergence(synthetic_data):
    # TODO: stub agent returning override=True -> result.cb_active and the
    #       weights equal the override weights.
    pytest.skip("TODO")


def test_optimizer_returns_w_bar_when_constraints_loose():
    # TODO: with generous caps, optimize(w_bar, cov, grs=0) ~= w_bar (atol 1e-4).
    pytest.skip("TODO")


def test_optimizer_respects_geo_constraint():
    # TODO: grs > 0.52 -> g @ w <= 0.45 + tol; all group caps respected.
    pytest.skip("TODO")


def test_transaction_cost_zero_when_no_trade():
    # TODO: transaction_cost(w, w, ...) == 0.
    pytest.skip("TODO")
