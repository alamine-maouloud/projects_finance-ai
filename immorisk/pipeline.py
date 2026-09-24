"""End to end run: data, estimation, backtests, simulation, rankings, scenarios."""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from . import backtest, data, market, prices, rank, simulate, universe
from .config import OUT, Assumptions

# large cities shown in the comparison tables (INSEE codes; arrondissements for Paris, Lyon, Marseille)
REFERENCE = {
    "75111": "Paris 11e", "69383": "Lyon 3e", "13205": "Marseille 5e", "33063": "Bordeaux",
    "31555": "Toulouse", "59350": "Lille", "44109": "Nantes", "35238": "Rennes",
    "34172": "Montpellier", "06088": "Nice", "63113": "Clermont-Ferrand", "87085": "Limoges",
    "42218": "Saint-Etienne", "76351": "Le Havre",
}

SCENARIOS = {
    "base": {},
    "flat prices (0%)": {"market": {"price_growth": 0.0}},
    "strong prices (3%)": {"market": {"price_growth": 0.03}},
    "loan at 4.2%": {"financing": {"rate": 0.042}},
    "loan at 2.5%": {"financing": {"rate": 0.025}},
    "10-year horizon": {"market": {"horizon_years": 10}},
    "20-year horizon": {"market": {"horizon_years": 20}},
    "self-managed": {"operating": {"management_fee": 0.0}},
}

REGIMES = {"micro_foncier": "Unfurnished, flat allowance", "reel": "Unfurnished, actual expenses", "lmnp": "Furnished (LMNP), actual expenses"}


def _log(msg: str, t0: float) -> None:
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


def calibrate(sales_all: pd.DataFrame, t0: float):
    levels = data.load_insee()
    model = market.fit_market(levels)
    fit_all = prices.fit_hedonic(sales_all)
    model.dep_sd, per_dep = market.dep_idio_sd(fit_all.index, levels)
    _log(f"market model fitted ({model.sample}), department volatility {model.dep_sd:.4f}", t0)
    comm, deciles, bt_stats = backtest.yield_vs_growth(sales_all)
    model.commune_sd = bt_stats["commune_sd_annual"]
    _log(f"yield backtest on {bt_stats['communes']} communes, commune volatility {model.commune_sd:.4f}", t0)
    return levels, model, fit_all, deciles, bt_stats


def run(a: Assumptions | None = None, write: bool = True) -> dict:
    a = a or Assumptions()
    t0 = time.time()
    sales_all = data.load_sales()
    sales_cur = sales_all[sales_all["date"].dt.year.isin(universe.CURRENT_YEARS)]
    _log(f"{len(sales_all):,} flat sales loaded", t0)

    uni, info = universe.build(a, sales=sales_cur)
    _log(f"{info['communes_investable']} investable communes out of {info['communes_priced']} priced", t0)

    levels, model, fit_all, deciles, bt_stats = calibrate(sales_all, t0)
    validation = backtest.shrinkage_validation(sales_all, data.load_rents(2025, "app12"))
    _log("small area estimation validated out of sample", t0)

    res = simulate.run(uni, a, model)
    _log(f"simulated {len(res)} communes x {a.market.n_paths} paths", t0)
    by_commune = res.set_index("commune").loc[uni["commune"]]
    ranks = rank.rank_intervals(uni, a, model, regimes=by_commune["regime"].to_numpy(), centre=by_commune["irr_median"].to_numpy())
    _log("rank intervals done", t0)

    cols = ["commune", "name", "dep", "zone", "n_sales", "sales_per_year", "price_m2", "price_m2_direct",
            "price_sd_log", "shrink", "rent_m2", "rent_lo", "rent_hi", "rent_level", "vacancy_months",
            "long_vacancy", "qpv_share", "dpe_count", "share_E", "share_F", "share_G", "lon", "lat"]
    table = uni[cols].merge(res, on="commune").merge(ranks, on="commune")
    table["rank"] = table["irr_median"].rank(ascending=False, method="first").astype(int)
    table = table.sort_values("rank").reset_index(drop=True)

    ref = uni[uni["commune"].isin(REFERENCE)]
    regimes = regime_table(ref, a, model)
    scen = scenario_table(ref, a, model)
    _log("tax regimes and scenarios done", t0)

    results = summarize(table, info, model, a, deciles, bt_stats, validation, regimes, scen)
    if write:
        OUT.mkdir(parents=True, exist_ok=True)
        table.to_csv(OUT / "communes.csv", index=False, float_format="%.6g")
        (OUT / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False, default=float))
        _log(f"wrote {OUT / 'results.json'} and communes.csv", t0)
    return {"results": results, "table": table, "universe": uni, "model": model}


def regime_table(ref: pd.DataFrame, a: Assumptions, model: market.MarketModel) -> pd.DataFrame:
    rows = []
    for regime in REGIMES:
        r = simulate.run(ref, a.with_(tax={"regime": regime}), model)
        r["regime"] = regime
        rows.append(r[["commune", "regime", "irr_median", "irr_p05", "prob_loss", "effort_month"]])
    return pd.concat(rows, ignore_index=True)


def scenario_table(ref: pd.DataFrame, a: Assumptions, model: market.MarketModel) -> pd.DataFrame:
    rows = []
    for name, change in SCENARIOS.items():
        r = simulate.run(ref, a.with_(**change) if change else a, model)
        r["scenario"] = name
        rows.append(r[["commune", "scenario", "irr_median", "irr_p05", "prob_loss"]])
    return pd.concat(rows, ignore_index=True)


def _records(df: pd.DataFrame, cols: list[str], digits: int = 4) -> list[dict]:
    out = df[cols].copy()
    for c in out.select_dtypes("number"):
        out[c] = out[c].round(digits)
    return out.to_dict(orient="records")


def summarize(table, info, model, a, deciles, bt_stats, validation, regimes, scen) -> dict:
    show = ["rank", "commune", "name", "dep", "regime", "sales_per_year", "qpv_share", "price_m2", "rent_m2", "gross_yield", "net_yield",
            "irr_median", "irr_p05", "irr_p95", "prob_loss", "effort_month", "share_F", "share_G", "rank_p05", "rank_p95"]
    liquid = table[table["sales_per_year"] >= 100]
    ref = table[table["commune"].isin(REFERENCE)].copy()
    ref["city"] = ref["commune"].map(REFERENCE)
    reg = regimes.pivot(index="commune", columns="regime", values="irr_median")
    reg.index = reg.index.map(REFERENCE)
    sc = scen.pivot(index="commune", columns="scenario", values="irr_median")[list(SCENARIOS)]
    sc.index = sc.index.map(REFERENCE)
    sc_loss = scen.pivot(index="commune", columns="scenario", values="prob_loss")[list(SCENARIOS)]
    sc_loss.index = sc_loss.index.map(REFERENCE)
    q = table["irr_median"].quantile([0.1, 0.5, 0.9])
    return {
        "assumptions": a.to_dict(),
        "data": info,
        "market_model": model.to_dict(),
        "national": {
            "communes": int(len(table)),
            "irr_median_p10": q.loc[0.1], "irr_median_p50": q.loc[0.5], "irr_median_p90": q.loc[0.9],
            "share_positive_median": float((table["irr_median"] > 0).mean()),
            "regime_shares": table["regime"].value_counts(normalize=True).round(4).to_dict(),
            "share_prob_loss_below_10pct": float((table["prob_loss"] < 0.10).mean()),
            "corr_gross_yield_irr": float(table[["gross_yield", "irr_median"]].corr(method="spearman").iloc[0, 1]),
            "corr_base_median": float(table[["irr_base", "irr_median"]].corr().iloc[0, 1]),
        },
        "top": _records(table.head(20), show),
        "top_liquid": _records(liquid.head(15), show),
        "reference": _records(ref.sort_values("irr_median", ascending=False), ["city"] + show),
        "regimes": {k: {c: round(float(v), 4) for c, v in row.items()} for k, row in reg.iterrows()},
        "scenarios": {k: {c: round(float(v), 4) for c, v in row.items()} for k, row in sc.iterrows()},
        "scenarios_prob_loss": {k: {c: round(float(v), 4) for c, v in row.items()} for k, row in sc_loss.iterrows()},
        "backtest": {
            "stats": bt_stats,
            "deciles": _records(deciles.reset_index(), list(deciles.reset_index().columns)),
            "shrinkage_validation": _records(validation.reset_index(), list(validation.reset_index().columns)),
        },
    }
