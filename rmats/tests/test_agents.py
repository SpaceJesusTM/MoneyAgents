import pytest

AGENT_NAMES = ["sentiment", "report", "analysis", "risk"]


@pytest.mark.parametrize("agent_name", AGENT_NAMES)
def test_proposal_is_on_simplex(agent_name, synthetic_data):
    # TODO: build the agent (fit AnalysisAgent first), call initial_proposal on
    #       synthetic_data.until(t) for a late t; weights >= 0, sum to 1,
    #       0 <= confidence <= 1, 0 <= geo_risk <= 1.
    pytest.skip("TODO")


@pytest.mark.parametrize("agent_name", AGENT_NAMES)
def test_proposal_has_no_lookahead(agent_name, synthetic_data):
    # TODO: proposal on data.until(t) must equal proposal on data.until(t) even
    #       after the future is modified (e.g. multiply prices after t by 2).
    pytest.skip("TODO")


def test_revise_moves_toward_consensus(synthetic_data):
    # TODO: ||w_revised - w_bar|| < ||w_prev - w_bar|| and delta is set.
    pytest.skip("TODO")


def test_hmm_state_labels(synthetic_data):
    # TODO: after fit, state_map covers all three Regimes exactly once.
    pytest.skip("TODO")


def test_kalman_converges_to_constant_observation():
    # TODO: feeding [0.5, 0.5, 0.5] repeatedly -> x approaches 0.5.
    pytest.skip("TODO")


def test_circuit_breaker_fires_on_crash(synthetic_data):
    # TODO: inject a -10% 20-day portfolio return -> circuit_breaker returns True
    #       and the proposal is defensive-only with override=True.
    pytest.skip("TODO")


def test_circuit_breaker_disabled_by_config(synthetic_data):
    # TODO: cfg.with_(use_circuit_breaker=False) -> never fires.
    pytest.skip("TODO")
