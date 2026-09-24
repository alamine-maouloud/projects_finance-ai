"""Monte Carlo pricers with variance reduction.

* European options: antithetic variates and the terminal spot as control
* Arithmetic Asian options: geometric Asian control variate (closed form),
  randomised Sobol + Brownian bridge
* American options: Longstaff-Schwartz least-squares regression
"""

from __future__ import annotations

import numpy as np

from ..models.gbm import gbm_paths
from ..rng import standard_normals
from ..stats import Estimate, mc_mean
from .black_scholes import geometric_asian_call


def european_mc(s0, k, t, r, sigma, n_paths, *, call=True, antithetic=False,
                control=False, rng=None) -> Estimate:
    rng = rng or np.random.default_rng()
    z = standard_normals(n_paths, 1, method="antithetic" if antithetic else "pseudo", rng=rng)[:, 0]
    st = s0 * np.exp((r - 0.5 * sigma**2) * t + sigma * np.sqrt(t) * z)
    pay = np.exp(-r * t) * (np.maximum(st - k, 0) if call else np.maximum(k - st, 0))
    if antithetic:
        # average each antithetic pair so the i.i.d. standard error is honest
        h = n_paths // 2
        pay = 0.5 * (pay[:h] + pay[h:2 * h])
        st = 0.5 * (st[:h] + st[h:2 * h])
    if control:
        # E[e^{-rT} S_T] = S_0 is known exactly
        ctl = np.exp(-r * t) * st - s0
        beta = np.cov(pay, ctl)[0, 1] / ctl.var(ddof=1)
        pay = pay - beta * ctl
    return mc_mean(pay)


def asian_call_mc(s0, k, t, r, sigma, n_fix, n_paths, *, method="pseudo",
                  bridge=False, control=True, rng=None) -> Estimate:
    """Arithmetic-average Asian call with fixings t_i = i T / n_fix."""
    rng = rng or np.random.default_rng()
    times = np.arange(1, n_fix + 1) * t / n_fix
    s = gbm_paths(s0, r, sigma, np.eye(1), times, n_paths, method=method,
                  bridge=bridge, rng=rng)[:, :, 0]
    df = np.exp(-r * t)
    arith = df * np.maximum(s.mean(axis=1) - k, 0)
    if not control:
        return mc_mean(arith)
    geo = df * np.maximum(np.exp(np.log(s).mean(axis=1)) - k, 0)
    exact = geometric_asian_call(s0, k, t, r, sigma, n_fix)
    beta = np.cov(arith, geo)[0, 1] / geo.var(ddof=1)
    return mc_mean(arith - beta * (geo - exact))


def rqmc(pricer, n_reps: int = 16, seed: int = 0, **kw) -> Estimate:
    """Randomised QMC: independent scramblings give an unbiased error bar."""
    gens = np.random.SeedSequence(seed).spawn(n_reps)
    vals = np.array([pricer(rng=np.random.default_rng(g), **kw).value for g in gens])
    return Estimate(float(vals.mean()), float(vals.std(ddof=1) / np.sqrt(n_reps)))


def _laguerre_basis(x: np.ndarray, degree: int) -> np.ndarray:
    """Weighted Laguerre polynomials, the basis of Longstaff & Schwartz."""
    e = np.exp(-x / 2)
    cols = [e, e * (1 - x), e * (1 - 2 * x + x * x / 2), e * (1 - 3 * x + 1.5 * x**2 - x**3 / 6)]
    return np.column_stack([np.ones_like(x)] + cols[:degree])


def american_put_lsm(s0, k, t, r, sigma, n_steps=50, n_paths=100_000, degree=3,
                     rng=None) -> Estimate:
    """Longstaff-Schwartz (2001) with in-the-money regression.

    A second, independent set of paths applies the fitted exercise rule, so
    the estimate is a true lower bound (no look-ahead bias)."""
    rng = rng or np.random.default_rng()
    dt = t / n_steps
    times = np.arange(1, n_steps + 1) * dt
    df = np.exp(-r * dt)

    def paths(n):
        return gbm_paths(s0, r, sigma, np.eye(1), times, n, rng=rng)[:, :, 0]

    # 1) regression on training paths, backward induction
    s = paths(n_paths)
    cash = np.maximum(k - s[:, -1], 0)
    coefs = [None] * n_steps
    for i in range(n_steps - 2, -1, -1):
        cash *= df
        itm = k - s[:, i] > 0
        if itm.sum() < 50:
            continue
        x = s[itm, i] / k
        basis = _laguerre_basis(x, degree)
        beta, *_ = np.linalg.lstsq(basis, cash[itm], rcond=None)
        coefs[i] = beta
        ex = (k - s[itm, i]) > basis @ beta
        idx = np.flatnonzero(itm)[ex]
        cash[idx] = k - s[idx, i]

    # 2) out-of-sample valuation with the frozen exercise boundary
    s = paths(n_paths)
    value = np.zeros(n_paths)
    alive = np.ones(n_paths, dtype=bool)
    for i in range(n_steps - 1):
        if coefs[i] is None:
            continue
        itm = alive & (k - s[:, i] > 0)
        cont = _laguerre_basis(s[itm, i] / k, degree) @ coefs[i]
        ex_idx = np.flatnonzero(itm)[(k - s[itm, i]) > cont]
        value[ex_idx] = np.exp(-r * times[i]) * (k - s[ex_idx, i])
        alive[ex_idx] = False
    value[alive] = np.exp(-r * t) * np.maximum(k - s[alive, -1], 0)
    return mc_mean(value)
