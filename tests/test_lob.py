import numpy as np
import pytest
from scipy.stats import norm

from mcrisk.lob import ASK, BID, FlowModel, ReferenceBook, execution as E, hawkes as H
from mcrisk.lob import simulate, simulate_agent, stylized as S
from mcrisk.lob.flow import available

native = pytest.mark.skipif(not available(), reason="native kernel not built")


@pytest.fixture
def Book():
    from mcrisk._native import OrderBook
    return OrderBook


# ------------------------------------------------------------ matching engine

@native
def test_price_time_priority_and_partial_fills(Book):
    b = Book(100)
    a1 = b.limit(ASK, 50, 5)
    a2 = b.limit(ASK, 50, 3)          # same price, later: behind a1
    a3 = b.limit(ASK, 49, 2)          # better price: first
    assert b.best_ask == 49 and b.best_bid == -1
    assert b.market(BID, 6) == 6
    fills = b.take_fills()
    assert [(f[0], f[2], f[3]) for f in fills] == [(a3, 49, 2), (a1, 50, 4)]
    assert b.volume(ASK, 50) == 4 and b.count(ASK, 50) == 2 and b.best_ask == 50
    # a marketable limit order fills then rests the remainder
    oid = b.limit(BID, 50, 10)
    assert b.best_bid == 50 and b.volume(BID, 50) == 6 and b.best_ask == 100
    assert b.is_live(oid) and not b.is_live(a1) and not b.is_live(a2)
    assert b.cancel(oid) and not b.cancel(oid)
    assert b.best_bid == -1 and b.check_invariants()


@native
def test_market_order_on_empty_side_fills_nothing(Book):
    b = Book(50)
    assert b.market(ASK, 3) == 0
    b.limit(BID, 10, 2)
    assert b.market(ASK, 5) == 2 and b.best_bid == -1


@native
@pytest.mark.parametrize("seed", range(5))
def test_native_book_matches_reference_on_random_streams(Book, seed):
    rng = np.random.default_rng(seed)
    n = 60
    fast, ref = Book(n), ReferenceBook(n)
    ids = []
    for _ in range(4000):
        u = rng.random()
        if u < 0.55:
            side = int(rng.integers(2))
            mid = 30
            price = int(np.clip(mid + (rng.integers(-8, 3) if side == BID else rng.integers(-2, 9)), 0, n - 1))
            qty = int(rng.integers(1, 6))
            i1, i2 = fast.limit(side, price, qty), ref.limit(side, price, qty)
            assert i1 == i2
            ids.append(i1)
        elif u < 0.75:
            side, qty = int(rng.integers(2)), int(rng.integers(1, 8))
            assert fast.market(side, qty) == ref.market(side, qty)
        elif ids:
            oid = ids[int(rng.integers(len(ids)))]
            assert fast.cancel(oid) == ref.cancel(oid)
        assert fast.take_fills() == ref.take_fills()
        assert fast.best_bid == ref.best_bid and fast.best_ask == ref.best_ask
    for side in (BID, ASK):
        for p in range(n):
            assert fast.volume(side, p) == ref.volume(side, p)
            assert fast.count(side, p) == ref.count(side, p)
    assert fast.check_invariants()


# ------------------------------------------------------------------- Hawkes

def test_hawkes_excitation_matches_direct_sum():
    t = H.simulate(0.5, 0.6, 1.5, 3000.0, np.random.default_rng(1))
    direct = np.array([np.exp(-1.5 * (t[i] - t[:i])).sum() for i in range(t.size)])
    np.testing.assert_allclose(H.excitation(t, 1.5), direct, rtol=1e-10, atol=1e-12)


def test_hawkes_stationary_rate_and_mle():
    mu, al, be, T = 0.4, 0.9, 1.5, 40_000.0
    t = H.simulate(mu, al, be, T, np.random.default_rng(2))
    rate = mu / (1 - al / be)
    assert abs(t.size / T - rate) < 0.05 * rate
    f = H.fit(t, T)
    for est, se, true in zip((f.mu, f.alpha, f.beta), f.stderr, (mu, al, be)):
        assert abs(est - true) < 4 * se
    assert H.goodness_of_fit(t, f.mu, f.alpha, f.beta) > 0.01
    assert H.goodness_of_fit(t, t.size / T, 1e-9, 1.0) < 1e-6     # Poisson is rejected


# ---------------------------------------------------------------- order flow

@pytest.fixture(scope="module")
def day():
    if not available():
        pytest.skip("native kernel not built")
    return simulate(FlowModel.cst(), 23_400.0, seed=11)


@native
def test_mle_recovers_cst_parameters(day):
    est, true = day.calibrate(), day.model
    n_lo = day.n_limit
    np.testing.assert_allclose(est.lam, true.lam, rtol=5 / np.sqrt(n_lo.min()))
    np.testing.assert_allclose(est.theta, true.theta, rtol=5 / np.sqrt(day.n_cancel.min()))
    assert abs(est.mu - true.mu) < 5 * true.mu / np.sqrt(day.n_market)


@native
def test_stylised_facts(day):
    spread = S.spread_distribution(day.spread)
    assert spread[0] > 0.6                              # mostly one tick
    k = S.kurtosis_by_horizon(day.mid, [1, 60, 300])
    assert k[0] > 2 and abs(k[2]) < 1                    # fat tails fade with aggregation
    assert S.autocorrelation(S.increments(day.mid, 1), [1])[0] < -0.02   # bid-ask bounce
    sig = S.signature_plot(day.mid, [1, 60])
    assert sig[0] > sig[1]
    r = S.response_function(day.mo_t, day.mo_side, day.mo_mid_before, day.mid, [0, 60])
    assert np.all(r > 0)                                  # buys push the price up


@native
def test_hawkes_market_orders_cluster_and_are_recovered():
    m = FlowModel.cst(hawkes_branching=0.6, beta=1.0, cross_share=0.0)
    res = simulate(m, 40_000.0, seed=4)
    buys = res.mo_t[res.mo_side == BID]
    assert abs(buys.size / res.horizon - m.mu) < 0.12 * m.mu
    assert S.dispersion_index(buys, res.horizon, 60) > 3
    f = res.fit_hawkes(BID)
    assert abs(f.alpha - m.alpha_self) < 4 * f.stderr[1] + 0.02
    assert abs(f.beta - m.beta) < 4 * f.stderr[2] + 0.05
    poisson = simulate(FlowModel.cst(), 20_000.0, seed=5)
    assert abs(S.dispersion_index(poisson.mo_t[poisson.mo_side == BID], 20_000.0, 60) - 1) < 0.3


@native
def test_simulation_reproducible_and_thread_invariant():
    m = FlowModel.cst()
    a, b = simulate(m, 600.0, seed=7), simulate(m, 600.0, seed=7)
    np.testing.assert_array_equal(a.bid, b.bid)
    sched = [(0.0, ASK, 5), (30.0, ASK, 5)]
    x = simulate_agent(m, sched, 60.0, 16, seed=3, threads=1)
    y = simulate_agent(m, sched, 60.0, 16, seed=3, threads=8)
    np.testing.assert_array_equal(x["notional"], y["notional"])


# ---------------------------------------------------------------- execution

P = E.ImpactParams(sigma=0.8, eta=12.0, gamma=0.1, eps=0.5)


def test_almgren_chriss_closed_form_matches_monte_carlo():
    s = E.ac_schedule(200, 1200, 20, 5e-4, P)
    e, v = E.ac_moments(s, P)
    sh = E.ac_simulate(s, P, 400_000, np.random.default_rng(0))
    assert abs(sh.mean() - e) < 4 * sh.std() / np.sqrt(sh.size)
    assert sh.std() == pytest.approx(np.sqrt(v), rel=0.01)


def test_almgren_chriss_frontier_and_twap_limit():
    twap = E.ac_schedule(100, 600, 10, 0.0, P)
    np.testing.assert_allclose(twap.trades, 10.0)
    f = E.ac_frontier(100, 600, 10, P, [1e-6, 1e-4, 1e-3, 1e-2])
    assert np.all(np.diff(f[:, 1]) > 0) and np.all(np.diff(f[:, 2]) < 0)   # more cost, less risk
    t_small, _ = E.optimal_horizon(50, P, horizons=np.geomspace(10, 1e5, 300), n_per_unit=0.1)
    t_big, _ = E.optimal_horizon(800, P, horizons=np.geomspace(10, 1e5, 300), n_per_unit=0.1)
    assert t_big > t_small


def test_walk_cost():
    depth = np.array([2, 3, 1, 4])
    assert E.walk_cost(depth, 2) == 0
    assert E.walk_cost(depth, 5) == pytest.approx(3 / 5)
    assert E.walk_cost(depth, 7) == pytest.approx((3 + 2 + 3) / 7)


@native
def test_execution_in_book_costs_and_fill_rates():
    m = FlowModel.cst(levels=20)
    p = E.ImpactParams(sigma=1.0, eta=15.0, gamma=0.3, eps=0.7)
    fast = E.execute_in_book(m, E.ac_schedule(180, 120, 2, 0.0, p), 300, seed=1)
    slow = E.execute_in_book(m, E.ac_schedule(180, 1200, 20, 0.0, p), 300, seed=2)
    small = E.execute_in_book(m, E.ac_schedule(30, 1200, 20, 0.0, p), 300, seed=3)
    assert fast["fill_rate"] < slow["fill_rate"] == pytest.approx(1.0, abs=2e-3)
    per_lot = lambda r: r["spread_impact"].mean() / r["qty"]  # noqa: E731
    assert per_lot(small) < per_lot(slow)                  # bigger children walk further
    assert slow["shortfall"].std() > small["shortfall"].std()
