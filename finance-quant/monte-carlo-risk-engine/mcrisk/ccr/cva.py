"""Credit and debit valuation adjustments, with wrong-way risk.

Independent case (unilateral, discrete default grid):

    CVA = (1 - R) sum_k E[D(0,t_k) E+(t_k)] (S(t_{k-1}) - S(t_k))

Wrong-way risk (Hull & White, 2012): the counterparty hazard rate depends on
the portfolio value,  lambda(t) = exp(a(t) + b * Z(t)),  Z = V standardised
per date. a(t) is bootstrapped so that the average path survival matches the
market (CDS-implied) curve; b > 0 means default is more likely when our
exposure is high (wrong-way), b < 0 is right-way.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq


def survival_curve(times: np.ndarray, spread: float, recovery: float = 0.4) -> np.ndarray:
    """Flat hazard from the credit-triangle approximation lambda = s / (1 - R)."""
    return np.exp(-spread / (1 - recovery) * np.asarray(times))


def cva(exposure: np.ndarray, discount: np.ndarray, times: np.ndarray,
        spread: float, recovery: float = 0.4) -> float:
    """exposure, discount: (n, m + 1) paths. Returns the CVA (a cost, > 0)."""
    s = survival_curve(times, spread, recovery)
    dpd = s[:-1] - s[1:]
    dee = (discount * exposure).mean(axis=0)
    return float((1 - recovery) * np.sum(dee[1:] * dpd))


def dva(neg_exposure: np.ndarray, discount: np.ndarray, times: np.ndarray,
        own_spread: float, own_recovery: float = 0.4) -> float:
    """Benefit from our own default on negative exposure (returned > 0)."""
    return cva(-neg_exposure, discount, times, own_spread, own_recovery)


def cva_wrong_way(v: np.ndarray, exposure: np.ndarray, discount: np.ndarray,
                  times: np.ndarray, spread: float, recovery: float = 0.4,
                  b: float = 0.5) -> dict:
    s_mkt = survival_curve(times, spread, recovery)
    n, m1 = v.shape
    sd = v.std(axis=0)
    z = np.where(sd > 0, (v - v.mean(axis=0)) / np.where(sd > 0, sd, 1), 0.0)
    s_prev = np.ones(n)
    total = np.zeros(n)
    a = np.zeros(m1)
    for k in range(1, m1):
        dt = times[k] - times[k - 1]
        zk = z[:, k]
        f = lambda ak: np.mean(s_prev * np.exp(-np.exp(ak + b * zk) * dt)) - s_mkt[k]  # noqa: E731
        a[k] = brentq(f, -40.0, 10.0, xtol=1e-12)
        s_new = s_prev * np.exp(-np.exp(a[k] + b * zk) * dt)
        total += discount[:, k] * exposure[:, k] * (s_prev - s_new)
        s_prev = s_new
    value = (1 - recovery) * total
    return {"cva": float(value.mean()), "stderr": float(value.std(ddof=1) / np.sqrt(n)),
            "log_hazard_drift": a}
