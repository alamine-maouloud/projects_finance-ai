import numpy as np
import pandas as pd
import pytest

from immorisk import market


def ar1_levels(phi, sigma, n=400, seed=0):
    rng = np.random.default_rng(seed)
    cols = {}
    for k, name in enumerate(market.SERIES):
        r = np.zeros(n)
        for t in range(1, n):
            r[t] = 0.005 + phi[k] * (r[t - 1] - 0.005) + sigma[k] * rng.standard_normal()
        cols[name] = 100 * np.exp(np.cumsum(r))
    idx = pd.period_range("1920Q1", periods=n, freq="Q")
    return pd.DataFrame(cols, index=idx)


def test_fit_market_recovers_persistence_and_volatility():
    phi = [0.8, 0.75, 0.7, 0.85, 0.5]
    sigma = [0.012, 0.011, 0.010, 0.008, 0.003]
    m = market.fit_market(ar1_levels(phi, sigma))
    assert np.allclose(m.phi, phi, atol=0.07)
    assert np.allclose(m.sigma, sigma, rtol=0.1)
    assert m.corr.shape == (5, 5)


def test_simulated_growth_converges_to_the_scenario_drift():
    m = market.MarketModel(phi=np.full(5, 0.8), sigma=np.full(5, 0.01), corr=np.eye(5), start=np.full(5, 0.02))
    rng = np.random.default_rng(0)
    paths = market.simulate_market(m, 4_000, 30, price_growth=0.015, rent_growth=0.02, rng=rng)
    late = paths.zone_log_growth["province"][:, 10:].mean()
    assert late == pytest.approx(np.log1p(0.015), abs=0.003)
    # momentum: starting above trend, the first year grows faster than the drift
    assert paths.zone_log_growth["province"][:, 0].mean() > np.log1p(0.015) + 0.02
    assert paths.irl_log_growth[:, 10:].mean() == pytest.approx(np.log1p(0.02), abs=0.003)


def test_momentum_widens_long_horizon_risk():
    rng = np.random.default_rng(1)
    base = dict(sigma=np.full(5, 0.01), corr=np.eye(5), start=np.full(5, np.log1p(0.015) / 4))
    iid = market.simulate_market(market.MarketModel(phi=np.zeros(5), **base), 4_000, 15, 0.015, 0.02, rng)
    mom = market.simulate_market(market.MarketModel(phi=np.full(5, 0.8), **base), 4_000, 15, 0.015, 0.02, rng)
    sd_iid = iid.zone_log_growth["paris"].sum(axis=1).std()
    sd_mom = mom.zone_log_growth["paris"].sum(axis=1).std()
    assert sd_mom > 3 * sd_iid  # roughly 1 / (1 - phi) = 5 times for phi = 0.8
