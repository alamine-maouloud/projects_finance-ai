import numpy as np
import pandas as pd
import pytest

from immorisk import prices


def synthetic_sales(seed=0, n_dep=3, communes_per_dep=40, noise=0.25):
    """Sales with known commune levels, department trends and a size effect."""
    rng = np.random.default_rng(seed)
    rows, truth = [], {}
    for d in range(n_dep):
        dep = f"{10 + d}"
        trend = rng.normal(0, 0.01, 8).cumsum()
        for c in range(communes_per_dep):
            commune = f"{dep}{c:03d}"
            level = 8.0 + 0.3 * d + rng.normal(0, 0.25)
            truth[commune] = level
            n = int(rng.integers(1, 120))
            q = rng.integers(0, 8, n)
            surface = rng.uniform(15, 110, n)
            rooms = np.clip(np.round(surface / 22), 1, 5).astype(int)
            logp = level + trend[q] - 0.14 * np.log(surface / 37) + noise * rng.standard_normal(n)
            quarter = np.array([20231 + 10 * (k // 4) + k % 4 for k in q])
            rows.append(pd.DataFrame({
                "commune": commune, "dep": dep, "quarter": quarter, "surface": surface,
                "rooms": rooms, "price_m2": np.exp(logp),
            }))
    return pd.concat(rows, ignore_index=True), pd.Series(truth)


def test_hedonic_recovers_size_effect_and_commune_ranking():
    sales, truth = synthetic_sales()
    fit = prices.fit_hedonic(sales)
    assert fit.beta["log_size"] == pytest.approx(-0.14, abs=0.03)
    lvl = fit.level.set_index("commune")
    big = lvl[lvl["n_sales"] >= 40]
    corr = np.corrcoef(big["direct"], truth.reindex(big.index))[0, 1]
    assert corr > 0.95
    # sampling variance shrinks with the number of sales
    assert lvl["v"].corr(1 / lvl["n_sales"]) > 0.9


def test_fay_herriot_shrinks_small_areas_and_beats_direct_estimates():
    rng = np.random.default_rng(1)
    m = 2_000
    dep = np.repeat(np.arange(20), m // 20).astype(str)
    x = rng.normal(0, 0.3, m)
    tau = 0.15
    theta = 0.5 + 1.5 * x + rng.normal(0, tau, m)
    n = rng.integers(1, 200, m)
    v = 0.3**2 / n
    direct = theta + rng.normal(0, np.sqrt(v))
    fh = prices.fay_herriot(direct, v, dep, x)
    assert np.sqrt(fh.tau2) == pytest.approx(tau, rel=0.15)
    assert fh.gamma == pytest.approx(1.5, abs=0.1)
    t = fh.table
    assert np.all(np.diff(t.sort_values("v")["shrink"].to_numpy()) >= -1e-12)
    mse_direct = np.mean((direct - theta) ** 2)
    mse_eblup = np.mean((t["eblup"] - theta) ** 2)
    assert mse_eblup < 0.9 * mse_direct
    small = n < 5
    assert np.mean((t["eblup"][small] - theta[small]) ** 2) < 0.5 * np.mean((direct[small] - theta[small]) ** 2)
