"""Closed-form prices used as revaluation functions and MC benchmarks."""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr
from scipy.stats import norm, poisson


def bs_price(s, k, t, r, sigma, q=0.0, call=True):
    """Black-Scholes-Merton price, vectorised over every argument."""
    s, k, t, sigma = map(np.asarray, (s, k, t, sigma))
    vol = sigma * np.sqrt(t)
    d1 = (np.log(s / k) + (r - q + 0.5 * sigma**2) * t) / vol
    d2 = d1 - vol
    df, dq = np.exp(-r * t), np.exp(-q * t)
    if call:
        return s * dq * ndtr(d1) - k * df * ndtr(d2)
    return k * df * ndtr(-d2) - s * dq * ndtr(-d1)


def bs_greeks(s, k, t, r, sigma, q=0.0, call=True) -> dict:
    vol = sigma * np.sqrt(t)
    d1 = (np.log(s / k) + (r - q + 0.5 * sigma**2) * t) / vol
    d2 = d1 - vol
    pdf = norm.pdf(d1)
    dq, df = np.exp(-q * t), np.exp(-r * t)
    delta = dq * (ndtr(d1) if call else ndtr(d1) - 1)
    gamma = dq * pdf / (s * vol)
    vega = s * dq * pdf * np.sqrt(t)
    theta_common = -s * dq * pdf * sigma / (2 * np.sqrt(t))
    if call:
        theta = theta_common - r * k * df * ndtr(d2) + q * s * dq * ndtr(d1)
        rho = k * t * df * ndtr(d2)
    else:
        theta = theta_common + r * k * df * ndtr(-d2) - q * s * dq * ndtr(-d1)
        rho = -k * t * df * ndtr(-d2)
    return {"delta": delta, "gamma": gamma, "vega": vega, "theta": theta, "rho": rho}


def implied_vol(price, s, k, t, r, q=0.0, call=True) -> float:
    intrinsic = max((s * np.exp(-q * t) - k * np.exp(-r * t)) * (1 if call else -1), 0.0)
    if price <= intrinsic + 1e-14:
        return 0.0
    return brentq(lambda v: bs_price(s, k, t, r, v, q, call) - price, 1e-6, 5.0, xtol=1e-12)


def geometric_asian_call(s, k, t, r, sigma, n_fix: int, q=0.0):
    """Discretely monitored geometric-average Asian call (Kemna & Vorst).

    Fixings at t_i = i T / n. log G is Gaussian with
      mean  log S + (r - q - sigma^2/2) T (n+1)/(2n)
      var   sigma^2 T (n+1)(2n+1) / (6 n^2)
    """
    mu = np.log(s) + (r - q - 0.5 * sigma**2) * t * (n_fix + 1) / (2 * n_fix)
    var = sigma**2 * t * (n_fix + 1) * (2 * n_fix + 1) / (6 * n_fix**2)
    sd = np.sqrt(var)
    d1 = (mu - np.log(k) + var) / sd
    d2 = d1 - sd
    return np.exp(-r * t) * (np.exp(mu + 0.5 * var) * ndtr(d1) - k * ndtr(d2))


def merton_jump_call(s, k, t, r, sigma, lam, mu_j, sig_j, q=0.0, n_terms: int = 80):
    """Merton (1976) jump-diffusion call as a Poisson mixture of BS prices.

    Jumps: log(1 + J) ~ N(mu_j, sig_j^2), intensity lam.
    """
    kbar = np.exp(mu_j + 0.5 * sig_j**2) - 1
    lam_p = lam * (1 + kbar)
    n = np.arange(n_terms)
    sig_n = np.sqrt(sigma**2 + n * sig_j**2 / t)
    r_n = r - lam * kbar + n * np.log(1 + kbar) / t
    w = poisson.pmf(n, lam_p * t)
    return float(np.sum(w * bs_price(s, k, t, r_n, sig_n, q)))


def crr_american(s, k, t, r, sigma, steps: int = 4000, call=False, q=0.0) -> float:
    """Cox-Ross-Rubinstein binomial tree with early exercise (benchmark)."""
    dt = t / steps
    u = np.exp(sigma * np.sqrt(dt))
    d = 1 / u
    p = (np.exp((r - q) * dt) - d) / (u - d)
    disc = np.exp(-r * dt)
    j = np.arange(steps + 1)
    st = s * u ** (steps - j) * d**j
    v = np.maximum(st - k, 0) if call else np.maximum(k - st, 0)
    for i in range(steps - 1, -1, -1):
        st = st[:-1] / u
        cont = disc * (p * v[:-1] + (1 - p) * v[1:])
        ex = np.maximum(st - k, 0) if call else np.maximum(k - st, 0)
        v = np.maximum(cont, ex)
    return float(v[0])
