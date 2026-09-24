"""Command-line entry point.

    mcrisk credit  [--obligors N] [--scenarios N] [--method plain|is] [--copula gaussian|t]
                   [--backend numpy|native] [--contributions]
    mcrisk market  [--scenarios N] [--backtest]
    mcrisk ccr     [--paths N] [--csa]
    mcrisk report  [--quick] [--out PATH]
"""

from __future__ import annotations

import argparse

import numpy as np

M = 1e6


def _credit(a):
    from .credit import CreditModel, portfolio_irb, simulate, synthetic_portfolio

    pf = synthetic_portfolio(a.obligors, seed=a.seed)
    model = CreditModel(pf, copula=a.copula, nu=a.nu)
    r = simulate(model, a.scenarios, method=a.method, seed=a.seed, backend=a.backend,
                 contributions=a.contributions, alphas=(0.99, 0.999, 0.9997))
    irb = portfolio_irb(pf)
    print(f"Portfolio: {pf.n:,} obligors, {pf.total_exposure / 1e9:,.2f} bn EAD, "
          f"{1 / pf.hhi():,.0f} effective names, {pf.n_factors} factors")
    print(r.summary())
    print(f"Basel IRB capital (ASRF, no MA) : {irb['capital'] / M:,.1f} m   "
          f"(ASRF VaR {irb['asrf_var'] / M:,.1f} m)")
    if r.es_contrib is not None:
        print(f"\nTop ES contributors at {r.contrib_alpha:.2%}:")
        for i in np.argsort(r.es_contrib)[::-1][:10]:
            print(f"  {pf.names[i]}  {pf.sector_names[pf.sector[i]]:<16} EAD {pf.ead[i] / M:8.1f} m  "
                  f"PD {pf.pd[i]:.4f}  ES contrib {r.es_contrib[i] / M:7.2f} m")


def _market(a):
    from .market import FilteredHS, frtb_es, imcc, loss_measures, sample_trading_book, synthetic_history
    from .market.backtest import rolling_backtest

    book, hist = sample_trading_book(), synthetic_history()
    s = FilteredHS.fit(hist.returns[-500:]).simulate(a.scenarios, 10, rng=np.random.default_rng(a.seed))
    lm = loss_measures(book.pnl(s).sum(axis=1))
    f, im = frtb_es(book, s), imcc(book, s)
    print(f"10-day VaR 99%  : {lm[0.99]['VaR'] / M:8.2f} m     ES 97.5% : {lm[0.975]['ES'] / M:8.2f} m")
    print(f"FRTB liquidity-adjusted ES : {f['es_liquidity_adjusted'] / M:8.2f} m")
    print(f"IMCC                       : {im['imcc'] / M:8.2f} m   "
          + "  ".join(f"{k} {v / M:.2f}" for k, v in im["es_by_class"].items()))
    if a.backtest:
        for name, b in rolling_backtest(book, hist.returns, start=600, seed=a.seed).items():
            r = b.report()
            print(f"  {name:<12} exceptions {r['exceptions']:3d} (exp {r['expected']:.1f})  "
                  f"Kupiec p {r['p_value']:.4f}  Christoffersen p {r['p_cc']:.4f}  "
                  f"worst 250d {r['worst_250d_exceptions']}")


def _ccr(a):
    from .ccr import CSA, cva, profile, sample_netting_set, simulate_exposures
    from .ccr.exposure import exposure_paths
    from .models.hull_white import HullWhite

    cube = simulate_exposures(sample_netting_set(), HullWhite(), n_paths=a.paths, seed=a.seed)
    csa = CSA(threshold_cpty=10e6, threshold_own=10e6) if a.csa else None
    p = profile(cube.net, cube.times, csa)
    e = exposure_paths(cube.net, cube.times, csa)
    print(f"EPE {p.epe / M:.2f} m   EEPE {p.eepe / M:.2f} m   EAD(IMM) {p.ead_imm / M:.2f} m   "
          f"peak PFE97.5 {p.peak_pfe / M:.2f} m")
    print(f"CVA (150 bp counterparty) : {cva(e, cube.discount, cube.times, 0.015) / M:.3f} m")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mcrisk", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=1)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("credit")
    c.add_argument("--obligors", type=int, default=2000)
    c.add_argument("--scenarios", type=int, default=500_000)
    c.add_argument("--method", choices=("plain", "is"), default="plain")
    c.add_argument("--copula", choices=("gaussian", "t"), default="gaussian")
    c.add_argument("--nu", type=float, default=8.0)
    c.add_argument("--backend", choices=("numpy", "native"), default="numpy")
    c.add_argument("--contributions", action="store_true")
    m = sub.add_parser("market")
    m.add_argument("--scenarios", type=int, default=100_000)
    m.add_argument("--backtest", action="store_true")
    x = sub.add_parser("ccr")
    x.add_argument("--paths", type=int, default=10_000)
    x.add_argument("--csa", action="store_true")
    r = sub.add_parser("report")
    r.add_argument("--quick", action="store_true")
    r.add_argument("--out", default="out/results.json")
    a = ap.parse_args(argv)
    if a.cmd == "report":
        from .report import main as report_main
        report_main(["--out", a.out] + (["--quick"] if a.quick else []))
    else:
        {"credit": _credit, "market": _market, "ccr": _ccr}[a.cmd](a)


if __name__ == "__main__":
    main()
