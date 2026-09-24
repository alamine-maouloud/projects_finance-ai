"""Command line: immorisk run | report | commune <code or name>."""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd


def _commune(args) -> None:
    from . import data, market, prices, simulate, universe
    from .config import Assumptions
    from .finance import irr

    a = Assumptions().with_(
        tax={"regime": args.regime, "marginal_rate": args.tmi},
        financing={"rate": args.rate},
        market={"price_growth": args.growth, "horizon_years": args.years, "n_paths": args.paths},
    )
    sales_all = data.load_sales()
    uni, _ = universe.build(a, sales=sales_all[sales_all["date"].dt.year.isin(universe.CURRENT_YEARS)])
    q = args.commune.lower()
    rows = uni[(uni["commune"] == args.commune) | (uni["name"].str.lower() == q)]
    if rows.empty:
        rows = uni[uni["name"].str.lower().str.startswith(q)].head(1)
    if rows.empty:
        raise SystemExit(f"no investable commune matches {args.commune!r}")
    model = market.fit_market(data.load_insee())
    model.dep_sd, _ = market.dep_idio_sd(prices.fit_hedonic(sales_all).index, data.load_insee())
    rows = rows.head(1)
    if a.tax.regime == "best":
        a = a.with_(tax={"regime": simulate.best_regime(rows, a, model)[0]})
    r = rows.iloc[0]
    H, P = a.market.horizon_years, a.market.n_paths
    paths = market.simulate_market(model, P, H, a.market.price_growth, a.market.rent_growth, np.random.default_rng([a.market.seed, 0]))
    cf = simulate.cash_flows(rows.head(1), a, paths, simulate.draw_local(rows.head(1), a, model, P, H))
    v = np.nan_to_num(irr(cf.cash)[0], nan=-1.0)
    base, bcf = simulate.base_case(rows.head(1), a, model)
    print(f"{r['name']} ({r['commune']}), {r['sales_per_year']:.0f} flat sales a year, {r['qpv_share']:.0%} in priority neighbourhoods")
    print(f"reference flat {a.property.surface_m2:.0f} m2: price {r['price_m2']:,.0f} EUR/m2 (+/- {r['price_sd_log']:.1%}), "
          f"advertised rent {r['rent_m2']:.2f} EUR/m2 charges included")
    print(f"gross yield {base['gross_yield'].iloc[0]:.2%}, net yield {base['net_yield'].iloc[0]:.2%}, "
          f"expected case IRR {base['irr_base'].iloc[0]:.2%}")
    print(f"IRR over {H} years ({a.tax.regime}, loan at {a.financing.rate:.2%}): median {np.median(v):.2%}, "
          f"5% {np.quantile(v, 0.05):.2%}, 95% {np.quantile(v, 0.95):.2%}, P(loss) {np.mean(v < 0):.1%}")
    d = bcf.detail
    table = pd.DataFrame({k: d[k][0, 0] for k in ("rents", "owner_charges", "property_tax", "management", "upkeep",
                                                  "reletting", "lmnp_costs", "debt_service", "income_tax")})
    table["works"] = d["works"][0, 0, 1:]
    table["cash"] = bcf.cash[0, 0, 1:]
    table.index = pd.RangeIndex(1, H + 1, name="year")
    print(f"\nexpected case, EUR (outlay at purchase {bcf.equity0[0, 0]:,.0f}):")
    print(table.round(0).astype(int).to_string())


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="immorisk", description="Buy-to-let risk and return in every French commune, on open data.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run", help="download data, estimate, simulate every commune, write out/")
    sub.add_parser("report", help="draw the charts from out/")
    c = sub.add_parser("commune", help="detailed simulation for one commune")
    c.add_argument("commune", help="INSEE code or name, e.g. 87085 or Limoges")
    c.add_argument("--regime", default="best", choices=["best", "micro_foncier", "reel", "lmnp"])
    c.add_argument("--tmi", type=float, default=0.30, help="marginal income tax rate")
    c.add_argument("--rate", type=float, default=0.032, help="loan rate")
    c.add_argument("--growth", type=float, default=0.015, help="long-run price growth")
    c.add_argument("--years", type=int, default=15, help="holding period")
    c.add_argument("--paths", type=int, default=5_000)
    args = p.parse_args(argv)

    if args.cmd == "run":
        from . import pipeline

        pipeline.run()
    elif args.cmd == "report":
        from . import report

        print(f"charts written to {report.build()}")
    else:
        _commune(args)


if __name__ == "__main__":
    main()
