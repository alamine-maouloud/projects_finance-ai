"""Risk-factor scenario generators for VaR / Expected Shortfall.

historical   overlapping h-day changes from the look-back window
normal       multivariate normal, EWMA (RiskMetrics) or equal-weight covariance
student_t    multivariate Student-t with the same covariance
fhs          filtered historical simulation: GARCH(1,1) per factor, bootstrap
             of standardised residual *vectors* (keeps cross-dependence and
             fat tails), vol propagated path-wise over the horizon
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize
from scipy.signal import lfilter


# --------------------------------------------------------------------------
# GARCH(1,1)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Garch:
    omega: float
    alpha: float
    beta: float

    @property
    def persistence(self) -> float:
        return self.alpha + self.beta

    @property
    def long_run_var(self) -> float:
        return self.omega / (1 - self.persistence)

    def filter(self, r: np.ndarray, h0: float | None = None) -> np.ndarray:
        """Conditional variances h_t = omega + alpha r_{t-1}^2 + beta h_{t-1},
        h_t known at t-1. Returns (T + 1,) with the one-step-ahead forecast last."""
        h0 = float(np.mean(r * r)) if h0 is None else h0
        u = self.omega + self.alpha * np.concatenate([[h0], r * r])
        return lfilter([1.0], [1.0, -self.beta], u, zi=[self.beta * h0])[0]


def fit_garch(r: np.ndarray) -> Garch:
    """Gaussian quasi-maximum likelihood with variance targeting."""
    r = np.asarray(r, dtype=float)
    var = float(np.mean(r * r))

    def nll(x):
        a, b = x
        if a <= 0 or b <= 0 or a + b >= 0.999:
            return 1e10
        g = Garch(var * (1 - a - b), a, b)
        h = g.filter(r, var)[:-1]
        return 0.5 * np.sum(np.log(h) + r * r / h)

    best = None
    for x0 in ((0.05, 0.90), (0.10, 0.85), (0.03, 0.95)):
        res = minimize(nll, x0, method="Nelder-Mead", options={"xatol": 1e-6, "fatol": 1e-6})
        if best is None or res.fun < best.fun:
            best = res
    a, b = best.x
    return Garch(var * (1 - a - b), a, b)


# --------------------------------------------------------------------------
# Generators
# --------------------------------------------------------------------------

def historical(returns: np.ndarray, horizon: int = 1) -> np.ndarray:
    """Overlapping h-day sums of daily shocks (log-returns and absolute
    changes are both additive over time)."""
    c = np.cumsum(np.vstack([np.zeros(returns.shape[1]), returns]), axis=0)
    return c[horizon:] - c[:-horizon]


def ewma_cov(returns: np.ndarray, lam: float | None = 0.94) -> np.ndarray:
    if lam is None:
        return np.cov(returns.T, bias=True) if returns.shape[0] > 1 else np.outer(returns, returns)
    w = lam ** np.arange(returns.shape[0])[::-1]
    w /= w.sum()
    return (returns * w[:, None]).T @ returns


def normal(returns, n, horizon=1, lam: float | None = 0.94, rng=None) -> np.ndarray:
    rng = rng or np.random.default_rng()
    cov = ewma_cov(returns, lam) * horizon
    l = np.linalg.cholesky(cov + 1e-18 * np.eye(cov.shape[0]))
    return rng.standard_normal((n, cov.shape[0])) @ l.T


def student_t(returns, n, horizon=1, nu: float = 5.0, lam: float | None = 0.94,
              rng=None) -> np.ndarray:
    """Multivariate t scaled to the same covariance (sqrt-of-time scaling)."""
    rng = rng or np.random.default_rng()
    g = normal(returns, n, horizon, lam, rng)
    w = rng.chisquare(nu, size=n)
    return g * np.sqrt((nu - 2) / w)[:, None]


@dataclass
class FilteredHS:
    """GARCH-filtered historical simulation (Barone-Adesi et al., 1999)."""

    models: list[Garch]
    residuals: np.ndarray     # (T, F) standardised residuals
    h_next: np.ndarray        # (F,) one-step-ahead conditional variances

    @classmethod
    def fit(cls, returns: np.ndarray, models: list[Garch] | None = None) -> "FilteredHS":
        f = returns.shape[1]
        models = models or [fit_garch(returns[:, j]) for j in range(f)]
        res = np.empty_like(returns)
        h_next = np.empty(f)
        for j, g in enumerate(models):
            h = g.filter(returns[:, j])
            res[:, j] = returns[:, j] / np.sqrt(h[:-1])
            h_next[j] = h[-1]
        # rescale residuals to unit variance (QMLE residuals are close to it)
        res /= res.std(axis=0)
        return cls(models, res, h_next)

    def simulate(self, n: int, horizon: int = 1, rng=None) -> np.ndarray:
        rng = rng or np.random.default_rng()
        om = np.array([g.omega for g in self.models])
        al = np.array([g.alpha for g in self.models])
        be = np.array([g.beta for g in self.models])
        h = np.tile(self.h_next, (n, 1))
        total = np.zeros((n, h.shape[1]))
        for _ in range(horizon):
            z = self.residuals[rng.integers(0, self.residuals.shape[0], n)]
            eps = np.sqrt(h) * z
            total += eps
            h = om + al * eps * eps + be * h
        return total
