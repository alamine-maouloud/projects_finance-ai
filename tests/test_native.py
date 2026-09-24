import numpy as np
import pytest

from mcrisk.credit import (
    CreditModel, homogeneous_exact, homogeneous_portfolio, simulate, synthetic_portfolio,
)
from mcrisk.credit import native

pytestmark = pytest.mark.skipif(not native.available(), reason="native kernel not built")


def test_native_matches_exact_pool_distribution():
    n, pd, rho = 300, 0.02, 0.2
    model = CreditModel(homogeneous_portfolio(n, pd, rho))
    pmf = homogeneous_exact(n, pd, rho)
    r = simulate(model, 600_000, seed=17, backend="native")
    for x in (6.5, 15.5, 40.5, 70.5):
        tp = r.tail_probability(x)
        assert abs(tp.value - pmf[int(x + 0.5):].sum()) < 4 * tp.stderr
    assert abs(r.expected_loss().value - n * pd) < 4 * r.expected_loss().stderr


@pytest.mark.parametrize("copula", ["gaussian", "t"])
def test_native_agrees_with_numpy_engine(copula):
    model = CreditModel(synthetic_portfolio(1500, seed=3), copula=copula)
    a = simulate(model, 300_000, seed=1)
    b = simulate(model, 300_000, seed=2, backend="native")
    for alpha in (0.99, 0.999):
        (va, ea), (vb, eb) = a.risk_estimates(alpha), b.risk_estimates(alpha)
        assert abs(ea.value - eb.value) < 4 * np.hypot(ea.stderr, eb.stderr)
    assert abs(a.expected_loss().value - b.expected_loss().value) < 4 * np.hypot(
        a.expected_loss().stderr, b.expected_loss().stderr)


def test_native_reproducible_and_thread_invariant():
    model = CreditModel(synthetic_portfolio(500, seed=5))
    x = simulate(model, 50_000, seed=9, backend="native", threads=1).losses
    y = simulate(model, 50_000, seed=9, backend="native", threads=8).losses
    np.testing.assert_array_equal(x, y)


def test_native_contributions_add_up():
    model = CreditModel(synthetic_portfolio(800, seed=6))
    r = simulate(model, 200_000, seed=4, backend="native", contributions=True, alphas=(0.999,))
    tail = r.losses[r.losses >= r.var(0.999)].mean()
    assert r.es_contrib.sum() == pytest.approx(tail, rel=1e-9)
    assert r.var_contrib.sum() == pytest.approx(r.var(0.999), rel=1e-9)
    ref = simulate(model, 200_000, seed=5, contributions=True, alphas=(0.999,))
    top = np.argsort(ref.es_contrib)[-5:]
    np.testing.assert_allclose(r.es_contrib[top], ref.es_contrib[top], rtol=0.25)


def test_thinning_bound_is_tight():
    model = CreditModel(synthetic_portfolio(5000, seed=1))
    k = native.kernel(model)
    assert k.candidates_per_scenario(5000) < 2.0 * model.portfolio.pd.sum()
