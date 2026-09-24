import numpy as np
import pytest
from scipy.stats import norm

from mcrisk.rng import brownian_bridge, spawn_generators, standard_normals
from mcrisk.stats import quantile_ci, tail_probability, var_es


def test_streams_reproducible_and_independent():
    a = [g.standard_normal(5) for g in spawn_generators(42, 3)]
    b = [g.standard_normal(5) for g in spawn_generators(42, 3)]
    np.testing.assert_array_equal(a[1], b[1])
    assert not np.allclose(a[0], a[1])


@pytest.mark.parametrize("method", ["pseudo", "antithetic", "sobol"])
def test_normal_generators_moments(method):
    z = standard_normals(2**16, 3, method=method, rng=np.random.default_rng(1))
    assert abs(z.mean()) < 0.02
    assert abs(z.std() - 1) < 0.02


def test_brownian_bridge_covariance():
    t = np.linspace(0.25, 2.0, 8)
    z = np.random.default_rng(0).standard_normal((200_000, 8))
    w = brownian_bridge(z, t)
    cov = np.cov(w.T)
    np.testing.assert_allclose(cov, np.minimum.outer(t, t), atol=0.03)


def test_var_es_normal():
    x = np.random.default_rng(3).standard_normal(1_000_000)
    v, e = var_es(x, 0.99)
    assert v == pytest.approx(norm.ppf(0.99), abs=0.01)
    assert e == pytest.approx(norm.pdf(norm.ppf(0.99)) / 0.01, abs=0.01)


def test_var_es_discrete_exact():
    # L = 0 w.p. 0.95, 1 w.p. 0.04, 10 w.p. 0.01 -> VaR_97.5 = 1, ES_97.5 = (0.015*1+0.01*10)/0.025
    x = np.array([0.0] * 95 + [1.0] * 4 + [10.0])
    v, e = var_es(x, 0.975)
    assert v == 1.0
    assert e == pytest.approx((0.015 * 1 + 0.01 * 10) / 0.025)


def test_weighted_estimators_match_resampling():
    # a sample from N(0,1) reweighted to N(1,1) behaves like a N(1,1) sample
    rng = np.random.default_rng(5)
    x = rng.standard_normal(2_000_000)
    w = np.exp(x - 0.5)
    v, _ = var_es(x, 0.99, w)
    assert v == pytest.approx(1 + norm.ppf(0.99), abs=0.03)
    tp = tail_probability(x, 3.0, w)
    assert abs(tp.value - norm.sf(2.0)) < 4 * tp.stderr


def test_quantile_ci_covers():
    rng = np.random.default_rng(9)
    q = norm.ppf(0.99)
    hits = sum(lo <= q <= hi for lo, hi in
               (quantile_ci(rng.standard_normal(5000), 0.99) for _ in range(200)))
    assert 180 <= hits <= 200
