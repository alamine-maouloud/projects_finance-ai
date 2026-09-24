import numpy as np
import pytest

from mcrisk.market import (
    DeltaGamma, FilteredHS, component_es, fit_garch, frtb_es, imcc, loss_measures,
    sample_trading_book, synthetic_history,
)
from mcrisk.market import scenarios as sc
from mcrisk.market.backtest import christoffersen, kupiec_pof, traffic_light, rolling_backtest
from mcrisk.market.scenarios import Garch


@pytest.fixture(scope="module")
def book():
    return sample_trading_book()


@pytest.fixture(scope="module")
def history():
    return synthetic_history()


def test_garch_recovers_parameters():
    rng = np.random.default_rng(0)
    g = Garch(1e-6 * (1 - 0.08 - 0.9), 0.08, 0.9)
    h, r = 1e-6, np.empty(20_000)
    for t in range(r.size):
        r[t] = np.sqrt(h) * rng.standard_normal()
        h = g.omega + g.alpha * r[t] ** 2 + g.beta * h
    fit = fit_garch(r)
    assert fit.alpha == pytest.approx(0.08, abs=0.015)
    assert fit.beta == pytest.approx(0.90, abs=0.02)


def test_historical_scenarios_are_overlapping_sums():
    r = np.arange(12, dtype=float).reshape(6, 2)
    s = sc.historical(r, 3)
    np.testing.assert_allclose(s[0], r[:3].sum(axis=0))
    assert s.shape == (4, 2)


def test_zero_shock_zero_pnl_and_linearity(book):
    assert np.allclose(book.pnl(np.zeros((3, 16))), 0.0, atol=1e-4)
    bumped = np.zeros((1, 16)); bumped[0, 0] = 0.01
    pnl = book.pnl(bumped)[0]
    # the EU cash position moves by exactly (e^0.01 - 1) of its value
    assert pnl[0] == pytest.approx(180e6 * (np.exp(0.01) - 1))


def test_component_es_adds_up(book, history):
    s = FilteredHS.fit(history.returns[-500:]).simulate(50_000, 10, rng=np.random.default_rng(1))
    pnl = book.pnl(s)
    total = loss_measures(pnl.sum(axis=1))[0.975]["ES"]
    assert component_es(pnl).sum() == pytest.approx(total, rel=2e-3)


def test_frtb_liquidity_cascade_and_imcc(book, history):
    s = FilteredHS.fit(history.returns[-500:]).simulate(50_000, 10, rng=np.random.default_rng(2))
    f = frtb_es(book, s)
    assert f["es_liquidity_adjusted"] > f["es_10d"]
    im = imcc(book, s)
    assert im["es_total"] <= sum(im["es_by_class"].values())
    assert im["es_total"] <= im["imcc"] <= sum(im["es_by_class"].values())


def test_delta_gamma_improves_on_delta(book, history):
    s = sc.normal(history.returns[-500:], 20_000, 10, rng=np.random.default_rng(3))
    full = book.pnl(s).sum(axis=1)
    dg = DeltaGamma.from_book(book)
    err_d = np.abs(dg.pnl(s, gamma=False) - full).mean()
    err_g = np.abs(dg.pnl(s, gamma=True) - full).mean()
    assert err_g < err_d / 3


def test_backtest_statistics():
    rng = np.random.default_rng(4)
    hits = rng.random(5000) < 0.01
    assert kupiec_pof(hits, 0.01)["p_value"] > 0.01
    assert christoffersen(hits, 0.01)["p_ind"] > 0.01
    assert kupiec_pof(rng.random(5000) < 0.03, 0.01)["p_value"] < 1e-6
    assert [traffic_light(k) for k in (4, 5, 9, 10)] == ["green", "yellow", "yellow", "red"]


@pytest.mark.slow
def test_fhs_passes_where_historical_fails(book, history):
    res = rolling_backtest(book, history.returns, start=600, window=500, n_mc=2000)
    rep = {m: r.report() for m, r in res.items()}
    assert rep["historical"]["p_value"] < 0.01
    assert rep["fhs"]["p_value"] > 0.05
    assert rep["fhs"]["exceptions"] < rep["historical"]["exceptions"]
