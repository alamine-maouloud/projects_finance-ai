import numpy as np
import pandas as pd
import pytest

from immorisk import simulate
from immorisk.config import Assumptions
from immorisk.market import MarketModel


@pytest.fixture
def model():
    return MarketModel(phi=np.full(5, 0.8), sigma=np.array([0.012, 0.011, 0.011, 0.008, 0.003]),
                       corr=np.eye(5), start=np.full(5, 0.003), dep_sd=0.018, commune_sd=0.024)


def commune(code, **kw):
    row = dict(commune=code, dep="69", zone="province", eblup=np.log(3_000.0), price_sd_log=0.03,
               rent_m2=15.0, rent_sd_log=0.11, vacancy_months=1.5, share_E=0.15, share_F=0.05, share_G=0.03)
    row.update(kw)
    return row


def run(rows, a, model):
    return simulate.run(pd.DataFrame(rows), a, model).set_index("commune")


def test_more_rent_means_higher_return(model):
    a = Assumptions().with_(market={"n_paths": 400})
    r = run([commune("A", rent_m2=13.0), commune("B", rent_m2=17.0)], a, model)
    assert r.loc["B", "irr_median"] > r.loc["A", "irr_median"] + 0.01
    assert r.loc["B", "prob_loss"] < r.loc["A", "prob_loss"]
    assert r.loc["B", "gross_yield"] > r.loc["A", "gross_yield"]


def test_results_do_not_depend_on_batching(model):
    a = Assumptions().with_(market={"n_paths": 300})
    rows = [commune(c, rent_m2=12 + i) for i, c in enumerate("ABCDE")]
    together = simulate.run(pd.DataFrame(rows), a, model, batch=5).set_index("commune")
    split = simulate.run(pd.DataFrame(rows), a, model, batch=2).set_index("commune")
    pd.testing.assert_frame_equal(together, split)


def test_slack_market_and_poor_energy_rating_hurt(model):
    a = Assumptions().with_(market={"n_paths": 400})
    r = run([commune("A"), commune("B", vacancy_months=3.0),
             commune("C", share_E=0.3, share_F=0.3, share_G=0.3)], a, model)
    assert r.loc["B", "irr_median"] < r.loc["A", "irr_median"]
    assert r.loc["C", "irr_median"] < r.loc["A", "irr_median"]
    off = run([commune("C", share_E=0.3, share_F=0.3, share_G=0.3)], a.with_(transition={"enabled": False}), model)
    assert off.loc["C", "irr_median"] > r.loc["C", "irr_median"]


def test_expected_case_is_close_to_the_median(model):
    a = Assumptions().with_(market={"n_paths": 1_000})
    r = run([commune("A"), commune("B", rent_m2=18.0)], a, model)
    assert np.allclose(r["irr_base"], r["irr_median"], atol=0.01)


def test_cash_flow_identity(model):
    """Outlay, yearly flows and exit add up to what the components say."""
    a = Assumptions().with_(market={"n_paths": 50}, tax={"regime": "lmnp"})
    rows = pd.DataFrame([commune("A")])
    base, cf = simulate.base_case(rows, a, model)
    d = cf.detail
    H = a.market.horizon_years
    yearly = (d["rents"] - d["owner_charges"] - d["property_tax"] - d["insurance"] - d["management"]
              - d["upkeep"] - d["reletting"] - d["lmnp_costs"] - d["debt_service"] - d["income_tax"] - d["works"][:, :, 1:])
    assert np.allclose(cf.cash[:, :, 1:H], yearly[:, :, :H - 1])
    assert np.allclose(cf.cash[:, :, 0], -cf.equity0)
    assert 0 < base["net_yield"].iloc[0] < base["gross_yield"].iloc[0]


@pytest.mark.parametrize("regime", ["micro_foncier", "reel", "lmnp", "best"])
def test_every_tax_regime_runs(model, regime):
    a = Assumptions().with_(market={"n_paths": 200}, tax={"regime": regime})
    r = run([commune("A")], a, model)
    assert np.isfinite(r["irr_median"]).all()
    assert -0.2 < r.loc["A", "irr_median"] < 0.3


def test_best_regime_is_at_least_as_good_as_each(model):
    a = Assumptions().with_(market={"n_paths": 300})
    rows = [commune("cheap", eblup=np.log(1_200.0), rent_m2=11.0), commune("dear", eblup=np.log(6_000.0), rent_m2=24.0)]
    best = run(rows, a, model)
    for regime in ("micro_foncier", "reel", "lmnp"):
        other = run(rows, a.with_(tax={"regime": regime}), model)
        assert np.all(best["irr_base"] >= other["irr_base"] - 1e-12)
