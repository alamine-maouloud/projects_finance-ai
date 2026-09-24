import numpy as np
import pytest

from mcrisk.models.gbm import gbm_paths, merton_terminal
from mcrisk.models.heston import Heston
from mcrisk.pricing.black_scholes import (
    bs_greeks, bs_price, crr_american, geometric_asian_call, implied_vol, merton_jump_call,
)
from mcrisk.pricing.montecarlo import american_put_lsm, asian_call_mc, european_mc, rqmc

S, K, T, R, V = 100.0, 100.0, 1.0, 0.03, 0.25


def test_put_call_parity_and_greeks():
    c, p = bs_price(S, K, T, R, V), bs_price(S, K, T, R, V, call=False)
    assert c - p == pytest.approx(S - K * np.exp(-R * T))
    g = bs_greeks(S, K, T, R, V)
    h = 1e-4
    assert g["delta"] == pytest.approx((bs_price(S + h, K, T, R, V) - bs_price(S - h, K, T, R, V)) / (2 * h), rel=1e-6)
    assert g["vega"] == pytest.approx((bs_price(S, K, T, R, V + h) - bs_price(S, K, T, R, V - h)) / (2 * h), rel=1e-6)
    assert implied_vol(c, S, K, T, R) == pytest.approx(V, abs=1e-10)


def test_european_mc_and_variance_reduction():
    exact = bs_price(S, K, T, R, V)
    plain = european_mc(S, K, T, R, V, 200_000, rng=np.random.default_rng(1))
    best = european_mc(S, K, T, R, V, 200_000, antithetic=True, control=True, rng=np.random.default_rng(1))
    for e in (plain, best):
        assert abs(e.value - exact) < 4 * e.stderr
    assert best.stderr < plain.stderr / 3


def test_gbm_paths_moments_and_correlation():
    corr = np.array([[1.0, 0.6], [0.6, 1.0]])
    p = gbm_paths([100, 50], [0.05, 0.02], [0.2, 0.3], corr, [0.5, 1.0], 400_000,
                  rng=np.random.default_rng(2))
    np.testing.assert_allclose(p[:, -1].mean(axis=0), [100 * np.exp(0.05), 50 * np.exp(0.02)], rtol=3e-3)
    lr = np.log(p[:, -1] / [100, 50])
    assert np.corrcoef(lr.T)[0, 1] == pytest.approx(0.6, abs=0.005)


def test_asian_control_variate_and_rqmc():
    plain = asian_call_mc(S, K, T, R, V, 12, 2**17, control=False, rng=np.random.default_rng(3))
    cv = asian_call_mc(S, K, T, R, V, 12, 2**17, control=True, rng=np.random.default_rng(3))
    q = rqmc(asian_call_mc, n_reps=16, s0=S, k=K, t=T, r=R, sigma=V, n_fix=12,
             n_paths=2**13, method="sobol", bridge=True, control=True)
    assert abs(cv.value - q.value) < 4 * np.hypot(cv.stderr, q.stderr)
    assert abs(plain.value - q.value) < 4 * plain.stderr
    assert (plain.stderr / cv.stderr) ** 2 > 200        # >200x variance reduction
    assert geometric_asian_call(S, K, T, R, V, 12) < q.value


def test_lsm_american_put_matches_binomial_tree():
    tree = crr_american(S, K, T, R, V, steps=3000)
    lsm = american_put_lsm(S, K, T, R, V, n_steps=50, n_paths=100_000, rng=np.random.default_rng(4))
    assert tree > bs_price(S, K, T, R, V, call=False)
    assert abs(lsm.value - tree) < 0.03 * tree


def test_merton_mc_matches_series():
    exact = merton_jump_call(S, K, T, R, 0.2, 0.5, -0.1, 0.15)
    st = merton_terminal(S, R, 0.2, 0.5, -0.1, 0.15, T, 800_000, rng=np.random.default_rng(5))
    pay = np.exp(-R * T) * np.maximum(st - K, 0)
    assert abs(pay.mean() - exact) < 4 * pay.std() / np.sqrt(pay.size)


def test_heston_reduces_to_black_scholes():
    # with rho != 0 the price moves at first order in rho * xi (skew), so the
    # Black-Scholes limit is checked with uncorrelated drivers
    h = Heston(v0=0.04, kappa=2.0, theta=0.04, xi=1e-3, rho=0.0)
    assert h.call(S, K, T, R) == pytest.approx(bs_price(S, K, T, R, 0.2), abs=1e-5)


@pytest.mark.parametrize("strike", [80.0, 100.0, 120.0])
def test_heston_qe_matches_semi_analytic(strike):
    h = Heston(v0=0.04, kappa=1.5, theta=0.04, xi=0.6, rho=-0.7)   # Feller violated
    x, _ = h.simulate(S, T, 40, 200_000, R, rng=np.random.default_rng(6))
    pay = np.exp(-R * T) * np.maximum(np.exp(x[:, -1]) - strike, 0)
    se = pay.std() / np.sqrt(pay.size)
    assert abs(pay.mean() - h.call(S, strike, T, R)) < 4 * se + 0.01
    assert h.put(S, strike, T, R) > 0


def test_heston_qe_is_martingale():
    h = Heston(v0=0.09, kappa=0.5, theta=0.09, xi=1.0, rho=-0.9)
    x, _ = h.simulate(S, 2.0, 20, 300_000, R, rng=np.random.default_rng(7))
    st = np.exp(x[:, -1]) * np.exp(-R * 2.0)
    assert abs(st.mean() - S) < 4 * st.std() / np.sqrt(st.size)
