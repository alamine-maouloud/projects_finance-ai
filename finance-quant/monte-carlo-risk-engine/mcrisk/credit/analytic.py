"""Closed-form benchmarks used to validate the Monte Carlo engine."""

from __future__ import annotations

import numpy as np
from scipy.special import ndtr, ndtri
from scipy.stats import binom


def vasicek_cdf(x, pd: float, rho: float, lgd: float = 1.0):
    """P(L <= x) for an infinitely granular homogeneous pool (Vasicek 1991)."""
    u = np.clip(np.asarray(x, dtype=float) / lgd, 1e-300, 1 - 1e-16)
    return ndtr((np.sqrt(1 - rho) * ndtri(u) - ndtri(pd)) / np.sqrt(rho))


def vasicek_quantile(alpha, pd: float, rho: float, lgd: float = 1.0):
    """Loss fraction quantile of the Vasicek distribution."""
    return lgd * ndtr((ndtri(pd) + np.sqrt(rho) * ndtri(alpha)) / np.sqrt(1 - rho))


def homogeneous_exact(n: int, pd: float, rho: float, n_nodes: int = 4000) -> np.ndarray:
    """Exact distribution of the number of defaults in a finite pool.

    P(K = k) = int Binom(k; n, p(z)) phi(z) dz with p(z) the conditional PD,
    computed by Gauss-Legendre quadrature on [-12, 12]. Accurate to ~1e-14 in
    the far tail, which makes it a reference for importance sampling.
    """
    x, w = np.polynomial.legendre.leggauss(n_nodes)
    z, w = 12.0 * x, 12.0 * w
    phi = np.exp(-0.5 * z * z) / np.sqrt(2 * np.pi)
    pz = ndtr((ndtri(pd) - np.sqrt(rho) * z) / np.sqrt(1 - rho))
    k = np.arange(n + 1)
    pmf = binom.pmf(k[None, :], n, pz[:, None])
    out = (w * phi) @ pmf
    return out / out.sum()


def pmf_var_es(pmf: np.ndarray, unit_loss: float, alpha: float) -> tuple[float, float]:
    """VaR and ES of a lattice loss distribution L = unit_loss * K."""
    cdf = np.cumsum(pmf)
    k = int(np.searchsorted(cdf, alpha - 1e-15))
    losses = unit_loss * np.arange(pmf.size)
    var = losses[k]
    es = var + np.sum(pmf * np.maximum(losses - var, 0.0)) / (1 - alpha)
    return float(var), float(es)
