"""Univariate Hawkes process with exponential kernel.

    lambda(t) = mu + alpha * sum_{t_i < t} exp(-beta (t - t_i))

Branching ratio n = alpha / beta (< 1 for stationarity); stationary rate
mu / (1 - n). Used to model the clustering of market orders.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.stats import kstest


@dataclass(frozen=True)
class HawkesFit:
    mu: float
    alpha: float
    beta: float
    stderr: tuple[float, float, float]
    loglik: float
    n_events: int

    @property
    def branching_ratio(self) -> float:
        return self.alpha / self.beta


def simulate(mu: float, alpha: float, beta: float, horizon: float,
             rng: np.random.Generator | None = None) -> np.ndarray:
    """Exact simulation via the cluster (immigrant / offspring) representation:
    immigrants are Poisson(mu), every event has Poisson(alpha / beta)
    children after Exp(beta) delays. Starts with an empty history at t = 0."""
    if alpha >= beta:
        raise ValueError("branching ratio alpha / beta must be < 1")
    rng = rng or np.random.default_rng()
    gen = rng.uniform(0.0, horizon, rng.poisson(mu * horizon))
    out = [gen]
    while gen.size:
        kids = np.repeat(gen, rng.poisson(alpha / beta, gen.size))
        kids = kids + rng.exponential(1.0 / beta, kids.size)
        gen = kids[kids < horizon]
        out.append(gen)
    return np.sort(np.concatenate(out))


def excitation(times: np.ndarray, beta: float) -> np.ndarray:
    """A_i = sum_{j < i} exp(-beta (t_i - t_j)), vectorised by time blocks.

    Within a block starting at r, A_i = e^{-beta (t_i - r)} (A_r + sum_{r <= t_j < t_i} e^{beta (t_j - r)}),
    with blocks short enough (beta * span < 500) that the exponentials stay finite.
    """
    t = np.asarray(times, dtype=float)
    a = np.zeros(t.size)
    if t.size == 0:
        return a
    block = np.floor(beta * (t - t[0]) / 500.0).astype(np.int64)
    starts = np.flatnonzero(np.diff(block, prepend=block[0] - 1))
    ends = np.append(starts[1:], t.size)
    carry = 0.0                       # A at the first time of the block
    for s, e in zip(starts, ends):
        r = t[s]
        g = np.exp(beta * (t[s:e] - r))
        excl = np.concatenate([[0.0], np.cumsum(g)[:-1]])
        a[s:e] = np.exp(-beta * (t[s:e] - r)) * (carry + excl)
        if e < t.size:
            carry = np.exp(-beta * (t[e] - r)) * (carry + g.sum())
    return a


def loglik(times: np.ndarray, horizon: float, mu: float, alpha: float, beta: float) -> float:
    t = np.asarray(times, dtype=float)
    a = excitation(t, beta)
    comp = mu * horizon + alpha / beta * np.sum(1.0 - np.exp(-beta * (horizon - t)))
    return float(np.sum(np.log(mu + alpha * a)) - comp)


def fit(times: np.ndarray, horizon: float, x0: tuple[float, float, float] | None = None) -> HawkesFit:
    """Maximum likelihood on (log mu, log alpha, log beta); standard errors
    from the inverse observed information (finite-difference Hessian)."""
    t = np.asarray(times, dtype=float)
    n = t.size
    if x0 is None:
        x0 = (0.5 * n / horizon, 0.5, 1.0)

    def nll(z):
        mu, al, be = np.exp(z)
        if al >= be:
            return 1e12 * (1 + al - be)
        return -loglik(t, horizon, mu, al, be)

    best = None
    for start in (x0, (0.3 * n / horizon, 1.0, 2.0), (0.8 * n / horizon, 0.1, 0.5)):
        res = minimize(nll, np.log(start), method="Nelder-Mead",
                       options={"xatol": 1e-7, "fatol": 1e-7, "maxiter": 4000})
        if best is None or res.fun < best.fun:
            best = res
    mu, al, be = np.exp(best.x)
    p = np.array([mu, al, be])

    def f(q):
        return -loglik(t, horizon, *q)

    h = 1e-4 * p
    hess = np.empty((3, 3))
    for i in range(3):
        for j in range(3):
            ei, ej = np.eye(3)[i] * h[i], np.eye(3)[j] * h[j]
            hess[i, j] = (f(p + ei + ej) - f(p + ei - ej) - f(p - ei + ej) + f(p - ei - ej)) / (4 * h[i] * h[j])
    try:
        se = tuple(float(x) for x in np.sqrt(np.diag(np.linalg.inv(hess))))
    except np.linalg.LinAlgError:
        se = (np.nan, np.nan, np.nan)
    return HawkesFit(float(mu), float(al), float(be), se, float(-best.fun), n)


def residuals(times: np.ndarray, mu: float, alpha: float, beta: float) -> np.ndarray:
    """Time-rescaling residuals Lambda(t_i) - Lambda(t_{i-1}); i.i.d. Exp(1)
    when the model is right (Brown et al., 2002)."""
    t = np.asarray(times, dtype=float)
    a = excitation(t, beta)
    dt = np.diff(np.concatenate([[0.0], t]))
    after_prev = np.concatenate([[0.0], a[:-1] + 1.0])      # excitation just after t_{i-1}
    after_prev[0] = 0.0
    return mu * dt + alpha / beta * after_prev * (1.0 - np.exp(-beta * dt))


def goodness_of_fit(times: np.ndarray, mu: float, alpha: float, beta: float) -> float:
    """Kolmogorov-Smirnov p-value of the rescaled residuals against Exp(1)."""
    return float(kstest(residuals(times, mu, alpha, beta), "expon").pvalue)
