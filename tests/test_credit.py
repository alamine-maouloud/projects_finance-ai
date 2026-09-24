import numpy as np
import pytest

from mcrisk.credit import (
    CreditModel, capital_requirement, conditional_factor_sampler,
    homogeneous_exact, homogeneous_portfolio, pmf_var_es, portfolio_irb,
    simulate, synthetic_portfolio, vasicek_quantile,
)
from mcrisk.credit.engine import _twist

N, PD, RHO = 400, 0.01, 0.15


@pytest.fixture(scope="module")
def pool():
    pf = homogeneous_portfolio(N, PD, RHO)
    return CreditModel(pf), homogeneous_exact(N, PD, RHO)


def test_exact_pmf_sums_and_mean(pool):
    _, pmf = pool
    assert pmf.sum() == pytest.approx(1.0)
    assert np.dot(np.arange(N + 1), pmf) == pytest.approx(N * PD, rel=1e-8)


def test_plain_mc_matches_exact_distribution(pool):
    model, pmf = pool
    r = simulate(model, 300_000, seed=11, alphas=(0.99, 0.999))
    for x in (10.5, 30.5, 50.5):
        tp = r.tail_probability(x)
        exact = pmf[int(x + 0.5):].sum()
        assert abs(tp.value - exact) < 4 * tp.stderr
    assert r.expected_loss().value == pytest.approx(N * PD, rel=0.02)


def test_importance_sampling_unbiased_far_tail(pool):
    model, pmf = pool
    r = simulate(model, 100_000, method="is", seed=12, alphas=(0.9999,))
    assert r.weights.mean() == pytest.approx(1.0, abs=0.03)
    for x in (60.5, 80.5, 100.5):
        tp = r.tail_probability(x)
        exact = pmf[int(x + 0.5):].sum()
        assert abs(tp.value - exact) < 4 * tp.stderr
        assert tp.stderr < 0.02 * exact          # < 2% relative error at 1e-5
    v_exact, es_exact = pmf_var_es(pmf, 1.0, 0.9999)
    v, es = r.risk_estimates(0.9999)
    assert abs(v.value - v_exact) <= max(4 * v.stderr, 1.0)
    assert abs(es.value - es_exact) < 4 * es.stderr + 0.5


def test_twist_solves_saddlepoint_equation():
    rng = np.random.default_rng(0)
    p = rng.uniform(1e-4, 0.05, size=(50, 300))
    c = rng.uniform(0.5, 2.0, 300)
    c /= c.sum()
    x = 0.08
    theta, _ = _twist(p, c, x)
    from scipy.special import expit, logit
    q = expit(logit(p) + theta[:, None] * c)
    active = p @ c < x
    np.testing.assert_allclose(q[active] @ c, x, rtol=1e-7)
    assert np.all(theta[~active] == 0)


def test_large_pool_converges_to_vasicek_irb():
    # fine-grained single-factor pool: MC quantile -> ASRF / IRB quantile
    pf = homogeneous_portfolio(20_000, 0.005, 0.2, lgd=0.45)
    r = simulate(CreditModel(pf), 60_000, seed=3, alphas=(0.999,))
    target = vasicek_quantile(0.999, 0.005, 0.2, 0.45) * pf.total_exposure
    v = r.var_estimate(0.999)
    assert abs(v.value - target) / target < 0.03
    k = capital_requirement(0.005, 0.45, 0.2)
    assert k == pytest.approx(vasicek_quantile(0.999, 0.005, 0.2, 0.45) - 0.005 * 0.45)


def test_reproducible_across_thread_counts():
    model = CreditModel(synthetic_portfolio(300, seed=1))
    a = simulate(model, 20_000, seed=5, threads=1, chunk=1000)
    b = simulate(model, 20_000, seed=5, threads=8, chunk=1000)
    np.testing.assert_array_equal(a.losses, b.losses)


@pytest.fixture(scope="module")
def book():
    return CreditModel(synthetic_portfolio(800, seed=2))


def test_euler_contributions_add_up(book):
    r = simulate(book, 200_000, seed=8, contributions=True, alphas=(0.999,))
    tail_mean = np.mean(r.losses[r.losses >= r.var(0.999)])
    assert r.es_contrib.sum() == pytest.approx(tail_mean, rel=1e-9)
    assert r.var_contrib.sum() == pytest.approx(r.var(0.999), rel=1e-9)
    assert np.all(r.es_contrib >= 0)


def test_plain_and_is_agree_on_realistic_book(book):
    a = simulate(book, 400_000, seed=21, alphas=(0.999,))
    b = simulate(book, 100_000, seed=22, method="is", alphas=(0.999,))
    (va, ea), (vb, eb) = a.risk_estimates(0.999), b.risk_estimates(0.999)
    assert abs(ea.value - eb.value) < 4 * np.hypot(ea.stderr, eb.stderr)
    assert abs(va.value - vb.value) < 4 * np.hypot(va.stderr, vb.stderr) + 1e6
    assert eb.stderr < ea.stderr / 3


def test_expected_loss_preserved_by_copula_choice():
    pf = synthetic_portfolio(500, seed=4)
    for model in (CreditModel(pf), CreditModel(pf, copula="t", nu=5)):
        el = simulate(model, 200_000, seed=1).expected_loss()
        assert abs(el.value - pf.expected_loss) < 4 * el.stderr


def test_t_copula_fattens_tail():
    pf = synthetic_portfolio(500, seed=4)
    g = simulate(CreditModel(pf), 200_000, seed=1).var(0.999)
    t = simulate(CreditModel(pf, copula="t", nu=5), 200_000, seed=1).var(0.999)
    assert t > 1.3 * g


def test_downturn_lgd_raises_losses():
    pf = synthetic_portfolio(500, seed=4)
    base = simulate(CreditModel(pf, lgd_model="beta"), 200_000, seed=1)
    corr = simulate(CreditModel(pf, lgd_model="beta", pd_lgd_corr=0.6), 200_000, seed=1)
    assert abs(base.expected_loss().value - pf.expected_loss) < 4 * base.expected_loss().stderr
    assert corr.expected_loss().value > 1.1 * base.expected_loss().value


def test_stress_sampler_conditions_factors(book):
    samp = conditional_factor_sampler(book, {"Energy": -3.0})
    f = samp(np.random.default_rng(0), 100_000)
    i = book.portfolio.factor_names.index("Energy")
    j = book.portfolio.factor_names.index("Materials")
    assert np.all(f[:, i] == -3.0)
    rho = book.portfolio.factor_corr[i, j]
    assert f[:, j].mean() == pytest.approx(-3.0 * rho, abs=0.02)
    assert f[:, j].std() == pytest.approx(np.sqrt(1 - rho**2), abs=0.02)


def test_multifactor_diversification_below_asrf(book):
    r = simulate(book, 200_000, seed=2, alphas=(0.999,))
    assert r.var(0.999) < portfolio_irb(book.portfolio)["asrf_var"]
