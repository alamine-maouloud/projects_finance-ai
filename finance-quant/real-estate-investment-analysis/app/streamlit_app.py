"""Buy-to-let risk explorer: ranking of every commune and a live simulation of one.

Run `immorisk run` once (downloads the open data and writes out/), then
`streamlit run app/streamlit_app.py`.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import streamlit as st

from immorisk import data, market, simulate, universe
from immorisk.config import OUT, Assumptions
from immorisk.finance import irr

st.set_page_config(page_title="immorisk", layout="wide")


@st.cache_data
def load_results():
    table = pd.read_csv(OUT / "communes.csv", dtype={"commune": str, "dep": str})
    results = json.loads((OUT / "results.json").read_text())
    return table, results


@st.cache_resource
def load_universe():
    sales = data.load_sales(universe.CURRENT_YEARS)
    uni, _ = universe.build(Assumptions(), sales=sales)
    return uni


def model_from(results) -> market.MarketModel:
    mm = results["market_model"]
    return market.MarketModel(np.array(mm["phi"]), np.array(mm["sigma_quarterly"]), np.array(mm["corr"]),
                              np.array(mm["start_quarterly"]), dep_sd=mm["dep_sd_annual"], commune_sd=mm["commune_sd_annual"])


if not (OUT / "communes.csv").exists():
    st.error("Run `immorisk run` first: it downloads the open data and simulates every commune.")
    st.stop()

table, results = load_results()
model = model_from(results)

st.title("Buy-to-let risk and return in every French commune")
st.caption("One 37 m2 flat bought with a 20-year loan and held 15 years. Prices from DVF sales, rents from the "
           "rent map (Estimations ANIL, a partir des donnees du Groupe SeLoger et de leboncoin), vacancy from LOVAC, "
           "energy ratings from ADEME, market risk calibrated on INSEE indices.")

ranking, one, method = st.tabs(["Ranking", "One commune", "Method"])

with ranking:
    c1, c2, c3, c4 = st.columns(4)
    zones = c1.multiselect("Zone", sorted(table["zone"].unique()), default=sorted(table["zone"].unique()))
    min_sales = c2.slider("Flat sales a year, at least", 10, 300, 10, help="liquidity: can you sell again?")
    max_qpv = c3.slider("Share of sales in priority neighbourhoods, at most", 0.0, 1.0, 1.0, 0.05)
    max_price = c4.slider("Price per m2, at most", 500, 15_000, 15_000, 250)
    t = table[table["zone"].isin(zones) & (table["sales_per_year"] >= min_sales)
              & (table["qpv_share"] <= max_qpv) & (table["price_m2"] <= max_price)]
    st.write(f"{len(t):,} communes. Default assumptions (best tax regime per commune, 30% tax bracket, loan at 3.2%, prices +1.5% a year).")
    show = t[["name", "dep", "regime", "sales_per_year", "qpv_share", "price_m2", "rent_m2", "gross_yield", "net_yield",
              "irr_median", "irr_p05", "prob_loss", "effort_month", "share_F", "share_G", "rank_p05", "rank_p95"]]
    st.dataframe(
        show.head(300), hide_index=True, use_container_width=True,
        column_config={
            "sales_per_year": st.column_config.NumberColumn("sales/yr", format="%.0f"),
            "qpv_share": st.column_config.NumberColumn("in QPV", format="percent"),
            "price_m2": st.column_config.NumberColumn("EUR/m2", format="%.0f"),
            "rent_m2": st.column_config.NumberColumn("rent/m2", format="%.1f"),
            "gross_yield": st.column_config.NumberColumn("gross yield", format="percent"),
            "net_yield": st.column_config.NumberColumn("net yield", format="percent"),
            "irr_median": st.column_config.NumberColumn("median IRR", format="percent"),
            "irr_p05": st.column_config.NumberColumn("IRR 5%", format="percent"),
            "prob_loss": st.column_config.NumberColumn("P(loss)", format="percent"),
            "effort_month": st.column_config.NumberColumn("effort/month", format="%.0f"),
            "share_F": st.column_config.NumberColumn("F rated", format="percent"),
            "share_G": st.column_config.NumberColumn("G rated", format="percent"),
            "rank_p05": st.column_config.NumberColumn("best rank", format="%.0f"),
            "rank_p95": st.column_config.NumberColumn("worst rank", format="%.0f"),
        },
    )
    m = t.dropna(subset=["lat", "lon"]).copy()
    m["size"] = 300 + 3_000 * np.sqrt(m["sales_per_year"] / m["sales_per_year"].max())
    q = m["irr_median"].clip(0, 0.08) / 0.08
    m["color"] = [(int(239 - 129 * v), int(230 - 186 * v), int(220 - 200 * v)) for v in q]
    st.map(m, latitude="lat", longitude="lon", size="size", color="color")

with one:
    left, right = st.columns([1, 2])
    names = table.sort_values("name")
    label = names["name"] + " (" + names["dep"] + ")"
    default = int(np.flatnonzero(names["commune"].to_numpy() == "87085")[0]) if (names["commune"] == "87085").any() else 0
    pick = left.selectbox("Commune", label.tolist(), index=default)
    code = names["commune"].iloc[label.tolist().index(pick)]
    regime = left.selectbox("Tax regime", ["best", "lmnp", "reel", "micro_foncier"],
                            format_func={"best": "Best for this commune", "lmnp": "Furnished (LMNP), actual",
                                         "reel": "Unfurnished, actual expenses",
                                         "micro_foncier": "Unfurnished, flat allowance"}.get)
    tmi = left.select_slider("Marginal tax rate", [0.0, 0.11, 0.30, 0.41, 0.45], value=0.30)
    rate = left.slider("Loan rate", 0.015, 0.06, 0.032, 0.001, format="%.3f")
    down = left.slider("Down payment (share of price, on top of fees)", 0.0, 0.5, 0.10, 0.05)
    growth = left.slider("Long-run price growth", -0.02, 0.05, 0.015, 0.005, format="%.3f")
    years = left.slider("Holding period (years)", 5, 25, 15)
    mgmt = left.slider("Letting agent fee", 0.0, 0.10, 0.07, 0.01)
    transition = left.checkbox("Energy rating rental bans", value=True)

    a = Assumptions().with_(
        tax={"regime": regime, "marginal_rate": tmi}, financing={"rate": rate, "down_payment_share": down},
        market={"price_growth": growth, "horizon_years": years, "n_paths": 3_000},
        operating={"management_fee": mgmt}, transition={"enabled": transition},
    )
    uni = load_universe()
    rows = uni[uni["commune"] == code]
    if rows.empty:
        right.warning("Not enough sales to simulate this commune.")
    else:
        if regime == "best":
            a = a.with_(tax={"regime": simulate.best_regime(rows, a, model)[0]})
            left.caption(f"Best regime here: {a.tax.regime}")
        H, P = a.market.horizon_years, a.market.n_paths
        paths = market.simulate_market(model, P, H, a.market.price_growth, a.market.rent_growth,
                                       np.random.default_rng([a.market.seed, 0]))
        cf = simulate.cash_flows(rows, a, paths, simulate.draw_local(rows, a, model, P, H))
        v = np.nan_to_num(irr(cf.cash)[0], nan=-1.0)
        base, bcf = simulate.base_case(rows, a, model)
        r = rows.iloc[0]
        k = right.columns(4)
        k[0].metric("Median IRR", f"{np.median(v):.1%}")
        k[1].metric("1 in 20 below", f"{np.quantile(v, 0.05):.1%}")
        k[2].metric("P(loss)", f"{np.mean(v < 0):.0%}")
        k[3].metric("Cash at purchase", f"{bcf.equity0[0, 0]:,.0f} EUR")
        right.write(f"Price {r['price_m2']:,.0f} EUR/m2 (+/- {r['price_sd_log']:.1%} estimation error), rent "
                    f"{r['rent_m2']:.2f} EUR/m2 charges included, gross yield {base['gross_yield'].iloc[0]:.2%}, "
                    f"net yield {base['net_yield'].iloc[0]:.2%}. {r['sales_per_year']:.0f} flat sales a year, "
                    f"{r['qpv_share']:.0%} in priority neighbourhoods, {r['vacancy_months']:.1f} months empty between tenants, "
                    f"F {r['share_F']:.0%} and G {r['share_G']:.0%} rated flats.")
        hist, edges = np.histogram(np.clip(v, -0.15, 0.20), bins=50)
        right.bar_chart(pd.DataFrame({"paths": hist}, index=np.round(100 * 0.5 * (edges[1:] + edges[:-1]), 1)),
                        x_label="IRR, %", y_label="paths")
        d = bcf.detail
        cash = pd.DataFrame({k: d[k][0, 0] for k in ("rents", "owner_charges", "property_tax", "management",
                                                     "upkeep", "reletting", "lmnp_costs", "debt_service", "income_tax")})
        cash["works"] = d["works"][0, 0, 1:]
        cash["cash"] = bcf.cash[0, 0, 1:]
        cash.index = pd.RangeIndex(1, H + 1, name="year")
        right.write("Expected case, EUR per year (the last year includes the sale):")
        right.dataframe(cash.round(0).astype(int), use_container_width=True)

with method:
    st.markdown(
        "- **Prices**: hedonic two-way fixed effects model on 1.8 million single-flat sales (DVF 2021-2025), "
        "then Fay-Herriot small area estimation so that communes with few sales borrow strength from their "
        "department and their rent level.\n"
        "- **Rents**: rent map 2025, T1-T2 reference flat; its 95% prediction interval gives the spread of "
        "rents a given flat can fetch.\n"
        "- **Market risk**: AR(1) momentum on quarterly INSEE notaires indices (Paris, inner and outer suburbs, "
        "rest of France) and the IRL, with correlated shocks; department and commune random walks calibrated on DVF.\n"
        "- **Vacancy**: months empty between tenants from 1 (tightest market) to 3 (slackest), ranked on the share "
        "of homes empty for more than two years (LOVAC).\n"
        "- **Energy ratings**: the flat's rating is drawn from the commune's ADEME diagnoses; works before the "
        "G (2025), F (2028) and E (2034) rental bans.\n"
        "- **Taxes**: micro-foncier, regime reel with the land deficit rules, or LMNP with depreciation; capital "
        "gains with holding period allowances and depreciation recapture.")
