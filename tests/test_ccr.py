import numpy as np
import pytest

from mcrisk.ccr import (
    CSA, InterestRateSwap, cva, cva_wrong_way, netting_benefit, profile,
    sample_netting_set, simulate_exposures, trade_ee_contributions,
)
from mcrisk.ccr.exposure import exposure_paths
from mcrisk.curves import EUR_CURVE
from mcrisk.models.hull_white import HullWhite

HW = HullWhite()


def test_curve_forward_is_derivative_of_log_discount():
    t, h = 7.0, 1e-5
    num = -(np.log(EUR_CURVE.discount(t + h)) - np.log(EUR_CURVE.discount(t - h))) / (2 * h)
    assert EUR_CURVE.forward(t) == pytest.approx(num, abs=1e-9)


def test_hull_white_reprices_curve_and_bonds():
    p = HW.simulate(np.arange(1, 41) / 4, 200_000, np.random.default_rng(0), antithetic=True)
    for k in (4, 20, 40):
        d = p.discount[:, k]
        assert abs(d.mean() - EUR_CURVE.discount(k / 4)) < 4 * d.std() / np.sqrt(d.size)
    # E[D(0,t) P(t,T)] = P(0,T)
    T = np.array([8.0, 12.0, 20.0])
    v = p.discount[:, 20, None] * HW.zcb(5.0, T, p.x[:, 20])
    np.testing.assert_allclose(v.mean(axis=0), EUR_CURVE.discount(T), rtol=1e-3)


def test_zcb_consistency_at_time_zero():
    T = np.array([1.0, 5.0, 30.0])
    np.testing.assert_allclose(HW.zcb(0.0, T, np.zeros(1))[0], EUR_CURVE.discount(T), rtol=1e-12)


def test_swaption_mc_matches_jamshidian():
    t0, pay = 5.0, np.arange(6.0, 16.0)
    k = EUR_CURVE.par_swap_rate(5.0, 15.0)
    exact = HW.payer_swaption(t0, pay, k)
    p = HW.simulate([t0], 400_000, np.random.default_rng(1))
    z = HW.zcb(t0, np.concatenate([[t0], pay]), p.x[:, 1])
    swap = z[:, 0] - z[:, -1] - k * z[:, 1:].sum(axis=1)
    pay_off = p.discount[:, 1] * np.maximum(swap, 0)
    assert abs(pay_off.mean() - exact) < 4 * pay_off.std() / np.sqrt(pay_off.size)


@pytest.fixture(scope="module")
def cube():
    return simulate_exposures(sample_netting_set(), HW, n_paths=4000, seed=3)


def test_par_swaps_worth_zero_today(cube):
    v0 = cube.values[0, 0, :]
    for name, v in zip(cube.trade_names, v0):
        if "seasoned" not in name:
            assert abs(v) < 1.0            # EUR, on hundreds of millions notional


def test_discounted_swap_value_is_martingale_before_first_payment():
    # between cash flows, D(0,t) V(t) is a martingale: E[D(0,t) V(t)] = V(0)
    swap = InterestRateSwap("fwd", 1e8, 10.0, payer=True, start=2.0)
    c = simulate_exposures([swap], HW, n_paths=40_000, seed=4)
    k = np.searchsorted(c.times, 1.5)
    dv = c.discount[:, k] * c.values[:, k, 0]
    assert abs(dv.mean() - c.values[0, 0, 0]) < 4 * dv.std() / np.sqrt(dv.size)


def test_exposure_vanishes_after_maturity(cube):
    assert np.allclose(cube.net[:, -1], 0.0)


def test_netting_and_contributions(cube):
    nb = netting_benefit(cube.values, cube.times)
    assert nb["net_epe"] < nb["gross_epe"]
    contrib = trade_ee_contributions(cube.values)
    np.testing.assert_allclose(contrib.sum(axis=1), nb["net_ee"], rtol=1e-10, atol=1e-6)


def test_collateral_reduces_exposure_monotonically(cube):
    v = cube.net
    eepe = [profile(v, cube.times, csa).eepe for csa in (
        None, CSA(threshold_cpty=50e6, threshold_own=50e6), CSA(), CSA(initial_margin=5e6))]
    assert eepe == sorted(eepe, reverse=True)
    assert profile(v, cube.times, CSA()).ee[0] == 0.0


def test_eee_non_decreasing_and_eepe_bounds(cube):
    p = profile(cube.net, cube.times)
    assert np.all(np.diff(p.eee) >= 0)
    assert p.epe <= p.eepe <= p.eee[cube.times <= 1.0].max() + 1e-9


def test_cva_wrong_way_nests_independent_case(cube):
    v = cube.net
    e = exposure_paths(v, cube.times)
    base = cva(e, cube.discount, cube.times, spread=0.02)
    wwr0 = cva_wrong_way(v, e, cube.discount, cube.times, 0.02, b=0.0)
    assert wwr0["cva"] == pytest.approx(base, rel=1e-9)
    up = cva_wrong_way(v, e, cube.discount, cube.times, 0.02, b=0.8)["cva"]
    down = cva_wrong_way(v, e, cube.discount, cube.times, 0.02, b=-0.8)["cva"]
    assert down < base < up
