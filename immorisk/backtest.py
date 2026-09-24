"""Out-of-sample checks on real data.

1. Small area estimation. Commune price levels are estimated from 2023-2024
   sales, directly and with the Fay-Herriot EBLUP, and compared with the level
   measured on 2025 sales that the estimators never saw.

2. Yield traps. Gross yields measured in 2022 (2022 rent map, 2021-2022 sales)
   are compared with the price change of each commune from 2022 to 2025. If
   high yields only compensate for falling prices, the total return is what
   matters, not the yield.

3. Commune volatility. The dispersion of commune price changes around their
   department over 2022-2025, net of estimation noise, calibrates the commune
   random walk of the simulation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import data, prices


def _levels(sales: pd.DataFrame, rents: pd.DataFrame) -> pd.DataFrame:
    tab, _, _ = prices.commune_prices(sales, rents)
    return tab.set_index("commune")


def shrinkage_validation(sales: pd.DataFrame, rents: pd.DataFrame, min_test: int = 10) -> pd.DataFrame:
    """Error of direct and EBLUP levels (2023-2024) against held-out 2025 sales.

    Both estimates and the target are expressed relative to the department's
    sales-weighted average, so the department trend between the two periods
    cancels out. The target is itself noisy; its known sampling variance is
    subtracted from both mean squared errors, which leaves the comparison fair.
    """
    year = sales["date"].dt.year
    train = _levels(sales[year.isin([2023, 2024])], rents)
    test_fit = prices.fit_hedonic(sales[year == 2025])
    test = test_fit.level.set_index("commune")
    test = test[test["n_sales"] >= min_test]
    df = train.join(test[["direct", "v", "n_sales"]], rsuffix="_test", how="inner")

    def rel(col, w):
        mean = df.groupby("dep")[col].transform(lambda s: np.average(s, weights=w.loc[s.index]))
        return df[col] - mean

    w = df["n_sales_test"].astype(float)
    target = rel("direct_test", w)
    direct = rel("direct", w)
    eblup = rel("eblup", w)
    df["err_direct"] = (direct - target) ** 2 - df["v_test"]
    df["err_eblup"] = (eblup - target) ** 2 - df["v_test"]
    bins = [0, 3, 6, 10, 20, 50, 1e9]
    labels = ["1-3", "4-6", "7-10", "11-20", "21-50", "51+"]
    df["train_sales"] = pd.cut(df["n_sales"], bins, labels=labels)
    out = df.groupby("train_sales", observed=True).agg(
        communes=("err_direct", "size"),
        rmse_direct=("err_direct", lambda s: np.sqrt(max(s.mean(), 0))),
        rmse_eblup=("err_eblup", lambda s: np.sqrt(max(s.mean(), 0))),
        mean_shrink=("shrink", "mean"),
    )
    out["error_cut"] = 1 - out["rmse_eblup"] / out["rmse_direct"]
    total = pd.DataFrame({
        "communes": [len(df)],
        "rmse_direct": [np.sqrt(max(df["err_direct"].mean(), 0))],
        "rmse_eblup": [np.sqrt(max(df["err_eblup"].mean(), 0))],
        "mean_shrink": [df["shrink"].mean()],
    }, index=pd.Index(["all"], name="train_sales"))
    total["error_cut"] = 1 - total["rmse_eblup"] / total["rmse_direct"]
    return pd.concat([out, total])


def yield_vs_growth(sales: pd.DataFrame, recoverable: float = 1.5, min_sales: int = 10) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """2022 gross yield against 2022-2025 price change, per commune.

    Returns the commune table, a decile summary and the commune volatility
    estimate.
    """
    year = sales["date"].dt.year
    r22 = data.load_rents(2022, "app12")
    r25 = data.load_rents(2025, "app12")
    then = _levels(sales[year.isin([2021, 2022])], r22)
    now = _levels(sales[year == 2025], r25)
    df = then[["dep", "n_sales", "eblup", "mse", "direct", "v"]].join(
        now[["n_sales", "eblup", "mse", "direct", "v"]], rsuffix="_25", how="inner")
    df = df[(df["n_sales"] >= min_sales) & (df["n_sales_25"] >= min_sales)]
    df = df.join(r22.set_index("commune")[["rent_m2"]])
    df["zone"] = df["dep"].map(data.zone_of)
    df["price22"] = np.exp(df["eblup"])
    df["gross_yield22"] = (df["rent_m2"] - recoverable) * 12 / df["price22"]
    df["growth"] = df["direct_25"] - df["direct"]  # log change, 2022 to 2025
    df["noise"] = df["v"] + df["v_25"]

    vac = data.load_vacancy().set_index("commune")
    df = df.join((vac["vacant_long"] / vac["stock"]).rename("long_vacancy"))

    # commune volatility: dispersion around the department, net of noise, per year
    w = df["n_sales"] + df["n_sales_25"]
    dep_mean = df.groupby("dep")["growth"].transform(lambda s: np.average(s, weights=w.loc[s.index]))
    rel = df["growth"] - dep_mean
    years = 3.0
    idio_var = float(np.average(rel**2 - df["noise"], weights=w))
    commune_sd = float(np.sqrt(max(idio_var, 0.0) / years))

    # does the 2022 yield predict the relative price change? (weighted, within department)
    y_rel = np.log(df["gross_yield22"]) - df.groupby("dep")["gross_yield22"].transform(lambda s: np.log(s).mean())
    wls_w = 1.0 / (df["noise"] + max(idio_var, 1e-4))
    slope = float(np.sum(wls_w * y_rel * rel) / np.sum(wls_w * y_rel**2))
    resid = rel - slope * y_rel
    se = float(np.sqrt(np.sum(wls_w**2 * y_rel**2 * resid**2)) / np.sum(wls_w * y_rel**2))

    df["decile"] = pd.qcut(df["gross_yield22"], 10, labels=[f"D{i}" for i in range(1, 11)])
    dec = df.groupby("decile", observed=True).agg(
        communes=("growth", "size"),
        yield_2022=("gross_yield22", "median"),
        price_m2_2022=("price22", "median"),
        price_change=("growth", lambda s: np.expm1(np.average(s, weights=w.loc[s.index]))),
        long_vacancy=("long_vacancy", "median"),
    )
    dec["total_return_3y"] = dec["price_change"] + years * dec["yield_2022"]
    stats = {
        "communes": int(len(df)),
        "commune_sd_annual": round(commune_sd, 4),
        "yield_slope_within_dep": round(slope, 4),
        "yield_slope_se": round(se, 4),
        "national_price_change": float(np.expm1(np.average(df["growth"], weights=w))),
    }
    return df.reset_index(), dec, stats
