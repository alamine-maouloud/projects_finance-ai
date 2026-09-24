"""The investable universe: one row per commune with everything the simulation needs."""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import data, prices
from .config import Assumptions

CURRENT_YEARS = (2023, 2024, 2025)


def vacancy_months(vac: pd.DataFrame, dep: pd.Series, tight: float = 1.0, slack: float = 3.0) -> pd.Series:
    """Expected months empty between two tenants, from the slackness of the local market.

    The share of private homes vacant for more than two years (LOVAC) measures
    how weak local demand is. Communes are ranked on it nationally and the
    expected re-letting time runs linearly from `tight` months (tightest
    market) to `slack` months (slackest). The short-term vacancy rate is not
    used: it is highest in big cities, where tenants move often but flats let
    fast. Masked values take the department median.
    """
    long_rate = vac["vacant_long"] / vac["stock"]
    rank = long_rate.rank(pct=True)
    rank = rank.fillna(rank.groupby(dep).transform("median")).fillna(0.5)
    return tight + (slack - tight) * rank


def energy_mix(table: pd.DataFrame, prior_weight: float = 30.0) -> pd.DataFrame:
    """Share of E, F and G ratings among the flats diagnosed in each commune.

    Communes with few diagnoses are pulled towards their department's mix with
    the weight of `prior_weight` diagnoses (a beta-binomial posterior mean).
    """
    dpe = data.load_dpe(table["dep"].unique()).set_index("commune")
    d = table[["commune", "dep"]].join(dpe, on="commune")
    d["dpe_count"] = d["dpe_count"].fillna(0)
    out = pd.DataFrame(index=table.index)
    out["dpe_count"] = d["dpe_count"]
    for label in ("E", "F", "G"):
        k = d[f"share_{label}"].fillna(0) * d["dpe_count"]
        dep_share = k.groupby(d["dep"]).transform("sum") / d["dpe_count"].groupby(d["dep"]).transform("sum").replace(0, np.nan)
        dep_share = dep_share.fillna((k.sum() / d["dpe_count"].sum()))
        out[f"share_{label}"] = (k + prior_weight * dep_share) / (d["dpe_count"] + prior_weight)
    return out


def build(assumptions: Assumptions | None = None, min_sales: int = 30, sales: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    """Join prices (DVF), rents (rent map) and vacancy (LOVAC) by INSEE code."""
    sales = data.load_sales(CURRENT_YEARS) if sales is None else sales
    rents = data.load_rents(2025, "app12")
    table, fit, fh = prices.commune_prices(sales, rents)
    table = table.merge(rents, on=["commune"], how="inner", suffixes=("", "_rent"))
    table["dep"] = table["dep"].astype(str)
    table = table[~table["dep"].isin(data.EXCLUDED_DEPARTMENTS)]

    vac = data.load_vacancy()
    table = table.merge(vac[["commune", "vacant", "vacant_long", "stock", "vacancy_short"]], on="commune", how="left")
    a = assumptions or Assumptions()
    table["vacancy_months"] = vacancy_months(table, table["dep"], a.operating.vacancy_months_tight, a.operating.vacancy_months_slack).to_numpy()
    table["long_vacancy"] = table["vacant_long"] / table["stock"]

    table = table.join(energy_mix(table), how="left")

    geo = sales.groupby("commune").agg(lon=("lon", "median"), lat=("lat", "median"))
    table = table.merge(geo, on="commune", how="left")
    table["zone"] = table["dep"].map(data.zone_of)
    table["sales_per_year"] = table["n_sales"] / len(CURRENT_YEARS)
    table["rent_sd_log"] = np.log(table["rent_hi"] / table["rent_lo"]) / (2 * 1.96)

    universe = table[table["n_sales"] >= min_sales].reset_index(drop=True)
    info = {
        "sales_used": int(len(sales)),
        "communes_with_sales": int(len(fit.level)),
        "communes_priced": int(len(table)),
        "communes_investable": int(len(universe)),
        "min_sales": min_sales,
        "hedonic_beta": fit.beta.round(4).to_dict(),
        "residual_sd": float(np.round(fit.residuals.std(), 4)),
        "fay_herriot": {"tau": round(float(np.sqrt(fh.tau2)), 4), "gamma_rent": round(fh.gamma, 4)},
    }
    return universe, info
