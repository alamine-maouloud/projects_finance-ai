"""End-to-end run of every engine, exported as a JSON results file.

    python -m mcrisk.report --out out/results.json [--quick]

The JSON feeds the dashboard and the README tables. Every figure is
reproducible from the seeds used here.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

from .ccr import CSA, cva, cva_wrong_way, dva, netting_benefit, profile, sample_netting_set
from .ccr import simulate_exposures, trade_ee_contributions
from .ccr.exposure import exposure_paths, negative_exposure_paths
from .credit import (
    CreditModel, conditional_factor_sampler, homogeneous_exact, homogeneous_portfolio,
    pmf_var_es, portfolio_irb, simulate, synthetic_portfolio,
)
from .credit import native
from .credit.portfolio import RATINGS
from .curves import EUR_CURVE
from .market import FilteredHS, component_es, frtb_es, imcc, loss_measures, sample_trading_book
from .market import scenarios as sc
from .market import synthetic_history
from .market.backtest import rolling_backtest
from .market.risk import DeltaGamma
from .models.heston import Heston
from .models.hull_white import HullWhite
from .pricing.black_scholes import bs_price, crr_american, merton_jump_call
from .pricing.montecarlo import american_put_lsm, asian_call_mc, european_mc, rqmc

M = 1e6


def _r(x, nd=4):
    return float(np.round(x, nd))


def credit_section(quick: bool) -> dict:
    n_obl = 2000
    n_scen = 300_000 if quick else 2_000_000
    pf = synthetic_portfolio(n_obl, seed=7)
    backend = "native" if native.available() else "numpy"
    base = CreditModel(pf)
    t0 = time.perf_counter()
    res = simulate(base, n_scen, seed=1, contributions=True, backend=backend,
                   alphas=(0.99, 0.999, 0.9997))
    t_base = time.perf_counter() - t0
    irb = portfolio_irb(pf)

    # loss distribution histogram (EUR m) and tail curve
    losses = res.losses / M
    edges = np.linspace(0, np.quantile(losses, 0.99995), 121)
    hist, _ = np.histogram(losses, edges)
    qs = 1 - np.logspace(-1, -4.5, 60)
    tail_curve = [[_r(1 - q, 8), _r(np.quantile(losses, q), 2)] for q in qs]

    def risk_row(name, r):
        el = r.expected_loss().value
        row = {"model": name, "EL": _r(el / M, 2)}
        for a in (0.99, 0.999, 0.9997):
            v, e = r.risk_estimates(a)
            row[f"VaR_{a}"] = _r(v.value / M, 1)
            row[f"VaR_{a}_se"] = _r(v.stderr / M, 2)
            row[f"ES_{a}"] = _r(e.value / M, 1)
            row[f"ES_{a}_se"] = _r(e.stderr / M, 2)
        row["EC_0.999"] = _r((r.var(0.999) - el) / M, 1)
        return row

    rows = [risk_row("Gaussian copula", res)]
    n_var = n_scen // 2
    variants = [
        ("Student-t copula (nu = 8)", CreditModel(pf, copula="t", nu=8.0)),
        ("Downturn LGD (beta, rho = 0.5)", CreditModel(pf, lgd_model="beta", pd_lgd_corr=0.5)),
    ]
    for name, mdl in variants:
        bk = backend if mdl.lgd_model == "fixed" else "numpy"
        rows.append(risk_row(name, simulate(mdl, n_var, seed=2, backend=bk,
                                            alphas=(0.99, 0.999, 0.9997))))

    # Euler allocation by sector, rating and top names
    esc = res.es_contrib
    sectors = [{"sector": s, "ead": _r(pf.ead[pf.sector == i].sum() / M, 1),
                "el": _r(np.sum((pf.ead * pf.pd * pf.lgd)[pf.sector == i]) / M, 2),
                "es_contrib": _r(esc[pf.sector == i].sum() / M, 2)}
               for i, s in enumerate(pf.sector_names)]
    ratings = [{"rating": g, "ead": _r(pf.ead[pf.rating == i].sum() / M, 1),
                "es_contrib": _r(esc[pf.rating == i].sum() / M, 2)}
               for i, g in enumerate(RATINGS)]
    top = np.argsort(esc)[::-1][:12]
    top_names = [{"name": pf.names[i], "sector": pf.sector_names[pf.sector[i]],
                  "rating": RATINGS[pf.rating[i]], "ead": _r(pf.ead[i] / M, 1),
                  "pd": _r(pf.pd[i], 5), "lgd": _r(pf.lgd[i], 3),
                  "es_contrib": _r(esc[i] / M, 2),
                  "irb_capital": _r(irb["k"][i] * pf.ead[i] / M, 2)} for i in top]

    # importance sampling vs plain: relative error of ES as scenarios grow
    conv = []
    for n in ([10_000, 40_000] if quick else [10_000, 30_000, 100_000, 300_000]):
        p = simulate(base, n, seed=11, alphas=(0.999,))
        t = time.perf_counter()
        q = simulate(base, n, seed=12, method="is", alphas=(0.999,))
        t_is = time.perf_counter() - t
        (_, ep), (_, eq) = p.risk_estimates(0.999), q.risk_estimates(0.999)
        conv.append({"n": n, "plain_es": _r(ep.value / M, 1), "plain_rel_se": _r(ep.stderr / ep.value, 5),
                     "is_es": _r(eq.value / M, 1), "is_rel_se": _r(eq.stderr / eq.value, 5),
                     "is_seconds": _r(t_is, 2)})

    # stress scenarios: conditional on factor levels
    stresses = []
    for label, shocks in [("Baseline", None),
                          ("Energy & Materials crash (-3sd / -2sd)", {"Energy": -3.0, "Materials": -2.0}),
                          ("Real-estate & banks (-3sd / -2sd)", {"Real Estate": -3.0, "Financials": -2.0}),
                          ("European recession (-2.5sd)", {"Europe": -2.5}),
                          ("Global downturn (all regions -2sd)",
                           {"Europe": -2.0, "North America": -2.0, "Asia-Pacific": -2.0, "Emerging Markets": -2.0})]:
        samp = None if shocks is None else conditional_factor_sampler(base, shocks)
        r = simulate(base, n_scen // 8, seed=21, factor_sampler=samp, alphas=(0.999,))
        stresses.append({"scenario": label, "EL": _r(r.expected_loss().value / M, 1),
                         "VaR_0.999": _r(r.var(0.999) / M, 1), "ES_0.999": _r(r.es(0.999) / M, 1)})

    return {
        "portfolio": {"obligors": pf.n, "exposure_bn": _r(pf.total_exposure / 1e9, 2),
                      "expected_loss_m": _r(pf.expected_loss / M, 1),
                      "effective_names": _r(1 / pf.hhi(), 0),
                      "largest_exposure_m": _r(pf.ead.max() / M, 1),
                      "ead_weighted_pd": _r(np.average(pf.pd, weights=pf.ead), 5),
                      "factors": len(pf.factor_names)},
        "run": {"scenarios": n_scen, "backend": backend, "seconds": _r(t_base, 2)},
        "irb": {"capital_m": _r(irb["capital"] / M, 1), "rwa_bn": _r(irb["rwa"] / 1e9, 2),
                "asrf_var_m": _r(irb["asrf_var"] / M, 1)},
        "models": rows,
        "histogram": {"edges": [_r(e, 2) for e in edges], "counts": hist.tolist()},
        "tail_curve": tail_curve,
        "sectors": sectors, "ratings": ratings, "top_contributors": top_names,
        "convergence": conv, "stress": stresses,
    }


def market_section(quick: bool) -> dict:
    book = sample_trading_book()
    hist = synthetic_history()
    rng = np.random.default_rng(3)
    look = hist.returns[-500:]
    n = 40_000 if quick else 200_000
    gens = {
        "Historical (10d overlapping)": sc.historical(look, 10),
        "Normal (EWMA 0.94)": sc.normal(look, n, 10, rng=rng),
        "Student-t (nu = 5)": sc.student_t(look, n, 10, rng=rng),
        "Filtered HS (GARCH)": FilteredHS.fit(look).simulate(n, 10, rng=rng),
    }
    models = []
    for name, s in gens.items():
        lm = loss_measures(book.pnl(s).sum(axis=1), (0.99, 0.975))
        models.append({"model": name, "scenarios": int(s.shape[0]),
                       "VaR_99": _r(lm[0.99]["VaR"] / M, 2), "ES_975": _r(lm[0.975]["ES"] / M, 2)})
    fhs = gens["Filtered HS (GARCH)"]
    pnl = book.pnl(fhs)
    f = frtb_es(book, fhs)
    im = imcc(book, fhs)
    comp = component_es(pnl)
    desks = {}
    for d, c in zip(book.desks, comp):
        desks[d] = desks.get(d, 0.0) + c
    dg = DeltaGamma.from_book(book)
    full = pnl.sum(axis=1)
    approx = {"Full revaluation": _r(loss_measures(full)[0.975]["ES"] / M, 2),
              "Delta-gamma": _r(loss_measures(dg.pnl(fhs, True))[0.975]["ES"] / M, 2),
              "Delta only": _r(loss_measures(dg.pnl(fhs, False))[0.975]["ES"] / M, 2)}

    start = 600
    bt = rolling_backtest(book, hist.returns, start=start, window=500,
                          n_mc=1500 if quick else 4000, seed=5)
    reports = []
    series = {"day": list(range(start, hist.n_days)),
              "pnl": [_r(x / M, 3) for x in next(iter(bt.values())).pnl],
              "crisis": hist.crisis[start:].astype(int).tolist()}
    for name, b in bt.items():
        rep = b.report()
        rep["exceptions_in_crisis"] = int(b.hits[hist.crisis[start:]].sum())
        reports.append({k: (_r(v, 4) if isinstance(v, (float, np.floating)) else v) for k, v in rep.items()})
        series[name] = [_r(x / M, 3) for x in b.var]
    return {
        "positions": [{"name": p.name, "desk": p.desk, "value_m": _r(v / M, 2),
                       "es_contrib_m": _r(c / M, 2)}
                      for p, v, c in zip(book.positions, book.base_values(), comp)],
        "models": models,
        "frtb": {"es_10d_m": _r(f["es_10d"] / M, 2),
                 "es_liquidity_adjusted_m": _r(f["es_liquidity_adjusted"] / M, 2),
                 "es_by_bucket_m": {str(k): _r(v / M, 2) for k, v in f["es_by_bucket"].items()},
                 "imcc_m": _r(im["imcc"] / M, 2),
                 "es_by_class_m": {k: _r(v / M, 2) for k, v in im["es_by_class"].items()},
                 "diversification": _r(im["diversification"], 4)},
        "desks": {k: _r(v / M, 2) for k, v in desks.items()},
        "approximations": approx,
        "backtest": {"reports": reports, "series": series},
    }


def ccr_section(quick: bool) -> dict:
    hw = HullWhite()
    trades = sample_netting_set()
    cube = simulate_exposures(trades, hw, n_paths=4000 if quick else 20_000, seed=1)
    v = cube.net
    t = cube.times
    unc = profile(v, t)
    csa = CSA(threshold_cpty=10e6, threshold_own=10e6, mta=0.5e6)
    col = profile(v, t, csa)
    im = profile(v, t, CSA(initial_margin=15e6))
    nb = netting_benefit(cube.values, t)
    e = exposure_paths(v, t)
    ne = negative_exposure_paths(v, t)
    spread, own = 0.0150, 0.0060
    base_cva = cva(e, cube.discount, t, spread)
    e_col = exposure_paths(v, t, csa)
    wwr = [{"b": b, **{k: _r(x / M, 4) for k, x in cva_wrong_way(v, e, cube.discount, t, spread, b=b).items()
                       if k in ("cva", "stderr")}} for b in (-1.0, -0.5, 0.0, 0.5, 1.0, 1.5)]
    contrib = trade_ee_contributions(cube.values)
    dt = np.diff(np.minimum(t, 1.0))
    trade_epe = (contrib[1:] * dt[:, None]).sum(axis=0)
    step = max(1, t.size // 180)
    idx = np.arange(0, t.size, step)
    return {
        "trades": [{"name": tr.name, "notional_m": _r(tr.notional / M, 0), "maturity": tr.maturity,
                    "payer": tr.payer, "fixed_rate": _r(tr.fixed_rate, 5),
                    "mtm_m": _r(cube.values[0, 0, j] / M, 3), "epe_contrib_m": _r(trade_epe[j] / M, 3)}
                   for j, tr in enumerate(trades)],
        "paths": int(v.shape[0]), "dates": int(t.size),
        "profiles": {"t": [_r(x, 4) for x in t[idx]],
                     "ee": [_r(x / M, 3) for x in unc.ee[idx]],
                     "pfe": [_r(x / M, 3) for x in unc.pfe[idx]],
                     "ene": [_r(x / M, 3) for x in unc.ene[idx]],
                     "ee_csa": [_r(x / M, 3) for x in col.ee[idx]],
                     "pfe_csa": [_r(x / M, 3) for x in col.pfe[idx]],
                     "ee_gross": [_r(x / M, 3) for x in nb["gross_ee"][idx]]},
        "metrics": [
            {"setup": "Uncollateralised", "epe_m": _r(unc.epe / M, 2), "eepe_m": _r(unc.eepe / M, 2),
             "ead_imm_m": _r(unc.ead_imm / M, 2), "peak_pfe_m": _r(unc.peak_pfe / M, 2)},
            {"setup": "CSA (10m threshold, 10d MPoR)", "epe_m": _r(col.epe / M, 2),
             "eepe_m": _r(col.eepe / M, 2), "ead_imm_m": _r(col.ead_imm / M, 2),
             "peak_pfe_m": _r(col.peak_pfe / M, 2)},
            {"setup": "CSA + 15m initial margin", "epe_m": _r(im.epe / M, 2), "eepe_m": _r(im.eepe / M, 2),
             "ead_imm_m": _r(im.ead_imm / M, 2), "peak_pfe_m": _r(im.peak_pfe / M, 2)},
        ],
        "netting": {"net_epe_m": _r(nb["net_epe"] / M, 2), "gross_epe_m": _r(nb["gross_epe"] / M, 2)},
        "xva": {"cva_m": _r(base_cva / M, 3), "cva_csa_m": _r(cva(e_col, cube.discount, t, spread) / M, 3),
                "dva_m": _r(dva(ne, cube.discount, t, own) / M, 3), "cpty_spread": spread,
                "own_spread": own, "wwr": wwr},
        "curve": [{"t": x, "zero": _r(float(EUR_CURVE.zero(x)), 5)} for x in (0.25, 1, 2, 3, 5, 7, 10, 15, 20, 30)],
        "hull_white": {"a": hw.a, "sigma": hw.sigma},
    }


def validation_section(quick: bool) -> list[dict]:
    out = []

    def add(test, model, mc, se, ref):
        g = lambda v: float(f"{float(v):.6g}")  # noqa: E731
        out.append({"test": test, "model": model, "mc": g(mc), "stderr": g(se),
                    "reference": g(ref), "z": _r((mc - ref) / se if se > 0 else 0.0, 2)})

    n, pd, rho = 400, 0.01, 0.15
    pool = CreditModel(homogeneous_portfolio(n, pd, rho))
    pmf = homogeneous_exact(n, pd, rho)
    r = simulate(pool, 200_000 if quick else 1_000_000, seed=31)
    ri = simulate(pool, 100_000 if quick else 400_000, method="is", seed=32, alphas=(0.9999,))
    for x in (30.5, 60.5):
        tp = r.tail_probability(x)
        add(f"P(L > {int(x)}) plain MC", "Credit, finite pool (exact quadrature)", tp.value, tp.stderr, pmf[int(x + .5):].sum())
    for x in (60.5, 100.5):
        tp = ri.tail_probability(x)
        add(f"P(L > {int(x)}) importance sampling", "Credit, finite pool (exact quadrature)", tp.value, tp.stderr, pmf[int(x + .5):].sum())
    es = ri.es_estimate(0.9999)
    add("ES 99.99% importance sampling", "Credit, finite pool (exact quadrature)", es.value, es.stderr, pmf_var_es(pmf, 1.0, 0.9999)[1])

    S, K, T, R, V = 100.0, 100.0, 1.0, 0.03, 0.25
    e = european_mc(S, K, T, R, V, 400_000, antithetic=True, control=True, rng=np.random.default_rng(1))
    add("European call, antithetic + control", "Black-Scholes", e.value, e.stderr, bs_price(S, K, T, R, V))
    q = rqmc(asian_call_mc, n_reps=16, s0=S, k=K, t=T, r=R, sigma=V, n_fix=12, n_paths=2**13,
             method="sobol", bridge=True, control=False)
    g = rqmc(asian_call_mc, n_reps=16, s0=S, k=K, t=T, r=R, sigma=V, n_fix=12, n_paths=2**13,
             method="sobol", bridge=True, control=True)
    add("Asian call: Sobol+bridge vs +control variate", "Arithmetic Asian (cross-check)", q.value, q.stderr, g.value)
    lsm = american_put_lsm(S, K, T, R, V, n_steps=50, n_paths=100_000, rng=np.random.default_rng(3))
    add("American put, Longstaff-Schwartz", "CRR binomial tree (5000 steps)", lsm.value, lsm.stderr, crr_american(S, K, T, R, V, 5000))
    from .models.gbm import merton_terminal
    st = merton_terminal(S, R, 0.2, 0.5, -0.1, 0.15, T, 1_000_000, rng=np.random.default_rng(4))
    pay = np.exp(-R * T) * np.maximum(st - K, 0)
    add("Merton jump-diffusion call", "Poisson series (80 terms)", pay.mean(), pay.std() / np.sqrt(pay.size),
        merton_jump_call(S, K, T, R, 0.2, 0.5, -0.1, 0.15))
    h = Heston(v0=0.04, kappa=1.5, theta=0.04, xi=0.6, rho=-0.7)
    x, _ = h.simulate(S, T, 50, 100_000 if quick else 400_000, R, rng=np.random.default_rng(5))
    for k_ in (90.0, 110.0):
        pay = np.exp(-R * T) * np.maximum(np.exp(x[:, -1]) - k_, 0)
        add(f"Heston call K={int(k_)}, QE scheme (Feller < 1)", "Heston semi-analytic", pay.mean(),
            pay.std() / np.sqrt(pay.size), h.call(S, k_, T, R))
    hw = HullWhite()
    p = hw.simulate([5.0], 400_000, np.random.default_rng(6))
    pay_t = np.arange(6.0, 16.0)
    kk = EUR_CURVE.par_swap_rate(5.0, 15.0)
    zz = hw.zcb(5.0, np.concatenate([[5.0], pay_t]), p.x[:, 1])
    po = p.discount[:, 1] * np.maximum(zz[:, 0] - zz[:, -1] - kk * zz[:, 1:].sum(axis=1), 0)
    add("5y x 10y payer swaption (x 100)", "Hull-White / Jamshidian", 100 * po.mean(),
        100 * po.std() / np.sqrt(po.size), 100 * hw.payer_swaption(5.0, pay_t, kk))
    d = p.discount[:, 1]
    add("Discount factor E[D(0,5y)]", "Curve P(0,5y)", d.mean(), d.std() / np.sqrt(d.size), float(EUR_CURVE.discount(5.0)))

    from .lob import execution as lx, flow as lf, hawkes as lh
    ip = lx.ImpactParams(sigma=1.0, eta=15.0, gamma=0.3, eps=0.7)
    sc = lx.ac_schedule(180, 1200, 20, 3e-4, ip)
    e_ac, _ = lx.ac_moments(sc, ip)
    sh = lx.ac_simulate(sc, ip, 400_000, np.random.default_rng(7))
    add("Almgren-Chriss expected cost (ticks x lots)", "Almgren-Chriss closed form", sh.mean(),
        sh.std() / np.sqrt(sh.size), e_ac)
    ht = lh.simulate(0.4, 0.9, 1.5, 40_000.0, np.random.default_rng(8))
    hf = lh.fit(ht, 40_000.0)
    add("Hawkes MLE, excitation alpha", "True parameter (alpha = 0.9)", hf.alpha, hf.stderr[1], 0.9)
    if lf.available():
        m = lf.FlowModel.cst()
        r = lf.simulate(m, 23_400.0, seed=9, record_mo=False)
        th = r.n_cancel[0] / r.queue_time[0]
        add("Order book MLE, cancellation rate theta_1", "True parameter (CST)", th,
            th / np.sqrt(r.n_cancel[0]), m.theta[0])
    return out


def lob_section(quick: bool) -> dict | None:
    from .lob import BID, FlowModel, available, simulate
    from .lob import execution as E
    from .lob import stylized as S

    if not available():
        return None
    day = 23_400.0
    base, hk = FlowModel.cst(), FlowModel.cst(hawkes_branching=0.7)
    t = time.perf_counter()
    rp = simulate(base, day, seed=11)
    t_sim = time.perf_counter() - t
    rh = simulate(hk, day, seed=12)
    k_lags = [1, 2, 5, 10, 30, 60, 120, 300]
    s_lags = [1, 2, 5, 10, 30, 60, 120, 300, 600]
    r_lags = [0, 1, 2, 5, 10, 30, 60, 120, 300]

    def facts(r):
        buys = r.mo_t[r.mo_side == BID]
        return {"spread": [_r(x) for x in S.spread_distribution(r.spread)],
                "depth": [_r(x, 3) for x in S.depth_profile(r.depth_bid, r.depth_ask)],
                "kurtosis": [_r(x, 3) for x in S.kurtosis_by_horizon(r.mid, k_lags)],
                "signature": [_r(x, 4) for x in S.signature_plot(r.mid, s_lags)],
                "response": [_r(x, 4) for x in S.response_function(r.mo_t, r.mo_side, r.mo_mid_before, r.mid, r_lags)],
                "acf1": _r(S.autocorrelation(S.increments(r.mid, 1), [1])[0], 4),
                "dispersion": _r(S.dispersion_index(buys, day, 60), 3),
                "duration_cv": _r(S.duration_cv(buys), 3),
                "events": r.n_events, "market_orders": r.n_market}

    est = rp.calibrate()
    h0 = FlowModel.cst(hawkes_branching=0.7, cross_share=0.0)
    rh0 = simulate(h0, 40_000.0, seed=13)
    hf = rh0.fit_hawkes(BID)

    m = FlowModel.cst(hawkes_branching=0.7, levels=20)
    p, diag = E.estimate_impact(m, seed=1, perm_paths=300 if quick else 1000)
    bps = 1e4 / m.p0
    n_paths = 200 if quick else 1000
    x_f, t_f, n_f = 180, 1200.0, 20
    lams = [0.0, 1e-5, 3e-5, 6e-5, 1e-4, 3e-4, 1e-3]
    curve = E.ac_frontier(x_f, t_f, n_f, p, np.concatenate([[1e-9], np.geomspace(1e-5, 5e-3, 40)]))
    pts = []
    for lam in lams:
        sc = E.ac_schedule(x_f, t_f, n_f, lam, p)
        rr = E.execute_in_book(m, sc, n_paths, seed=int(lam * 1e6) + 17)
        shb = rr["shortfall"] * bps / x_f
        e_ac, v_ac = E.ac_moments(sc, p)
        pts.append({"lambda": lam, "lob_mean": _r(shb.mean(), 3), "lob_sd": _r(shb.std(ddof=1), 3),
                    "lob_mean_se": _r(shb.std(ddof=1) / np.sqrt(shb.size), 3),
                    "ac_mean": _r(e_ac * bps / x_f, 3), "ac_sd": _r(np.sqrt(v_ac) * bps / x_f, 3),
                    "first_child": _r(sc.trades[0], 1), "fill_rate": _r(rr["fill_rate"], 4)})
    study = E.liquidity_study(m, p, sizes=(60, 180, 540),
                              horizons_min=(2, 5, 10, 20, 40) if quick else (2, 5, 10, 20, 40, 80),
                              n_paths=n_paths, seed=3)
    for row in study["rows"]:
        for k_, v in list(row.items()):
            if isinstance(v, float):
                row[k_] = _r(v, 4)
    mo_30min = m.mu * 1800
    return {
        "sim": {"events_per_day": rp.n_events, "seconds_per_day": _r(t_sim, 4),
                "events_per_second": _r(rp.n_events / t_sim, 0), "levels": base.depth,
                "tick_bp": _r(bps, 3)},
        "lags": {"kurtosis": k_lags, "signature": s_lags, "response": r_lags},
        "poisson": facts(rp), "hawkes": facts(rh), "hawkes_branching": hk.branching_ratio,
        "calibration": {"lam_true": [_r(x) for x in base.lam], "lam_est": [_r(x) for x in est.lam],
                        "theta_true": [_r(x) for x in base.theta], "theta_est": [_r(x) for x in est.theta],
                        "mu_true": base.mu, "mu_est": _r(est.mu),
                        "hawkes_true": {"alpha": h0.alpha_self, "beta": h0.beta, "mu0": _r(h0.mu * (1 - h0.branching_ratio))},
                        "hawkes_fit": {"alpha": _r(hf.alpha), "beta": _r(hf.beta), "mu0": _r(hf.mu),
                                       "se": [_r(x, 4) for x in hf.stderr], "events": hf.n_events}},
        "impact": {"sigma": _r(p.sigma, 4), "eta": _r(p.eta, 4), "gamma": _r(p.gamma, 4), "eps": _r(p.eps, 4),
                   "concession": [_r(x, 4) for x in diag["concession"]], "child_sizes": diag["child_sizes"],
                   "perm_drift": _r(diag["perm_drift"], 3), "perm_drift_se": _r(diag["perm_drift_se"], 3)},
        "frontier": {"size": x_f, "minutes": t_f / 60, "children": n_f,
                     "curve": [[_r(r_[2] * bps / x_f, 4), _r(r_[1] * bps / x_f, 4)] for r_ in curve],
                     "points": pts},
        "liquidity": {"rows": study["rows"], "best": {str(k_): v for k_, v in study["best"].items()},
                      "mo_volume_30min": _r(mo_30min, 0), "book_depth_lots": _r(float(np.sum(
                          S.depth_profile(rp.depth_bid, rp.depth_ask))), 1)},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="out/results.json")
    ap.add_argument("--quick", action="store_true", help="smaller runs (~20 s)")
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    results = {"meta": {"version": "0.1.0", "quick": args.quick, "threads": os.cpu_count(),
                        "native_kernel": native.available()}}
    for name, fn in [("validation", validation_section), ("credit", credit_section),
                     ("market", market_section), ("ccr", ccr_section), ("lob", lob_section)]:
        t = time.perf_counter()
        results[name] = fn(args.quick)
        print(f"{name:<10} done in {time.perf_counter() - t:6.1f}s")
    results["meta"]["seconds"] = _r(time.perf_counter() - t0, 1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print(f"wrote {out} ({out.stat().st_size / 1e3:.0f} kB, {results['meta']['seconds']}s)")


if __name__ == "__main__":
    main()
