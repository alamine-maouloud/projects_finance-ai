"""Exact simulation of correlated geometric Brownian motion and of
Merton jump-diffusions."""

from __future__ import annotations

import numpy as np

from ..rng import brownian_bridge, standard_normals


def gbm_paths(s0, mu, sigma, corr, times, n_paths: int, *, method: str = "pseudo",
              bridge: bool = False, rng: np.random.Generator | None = None) -> np.ndarray:
    """Correlated GBM sampled exactly at ``times`` (no discretisation bias).

    s0, mu, sigma : (d,) spot, drift, volatility
    corr          : (d, d) correlation of the Brownian drivers
    returns       : (n_paths, len(times), d)

    ``method='sobol'`` with ``bridge=True`` gives randomised QMC with a
    Brownian-bridge construction per asset (dimension = d * len(times)).
    """
    rng = rng or np.random.default_rng()
    s0, mu, sigma = map(np.atleast_1d, (s0, mu, sigma))
    d = s0.size
    times = np.asarray(times, dtype=float)
    m = times.size
    chol = np.linalg.cholesky(np.atleast_2d(corr))
    z = standard_normals(n_paths, m * d, method=method, rng=rng)
    if bridge:
        # bridge dimensions first: asset j uses columns j, j+d, j+2d, ...
        w = np.stack([brownian_bridge(z[:, j::d], times) for j in range(d)], axis=-1)
        dw = np.diff(np.concatenate([np.zeros((n_paths, 1, d)), w], axis=1), axis=1)
    else:
        dt = np.diff(np.concatenate([[0.0], times]))
        dw = z.reshape(n_paths, m, d) * np.sqrt(dt)[None, :, None]
    dw = dw @ chol.T
    t = times[None, :, None]
    drift = (mu - 0.5 * sigma**2)[None, None, :] * t
    return s0 * np.exp(drift + sigma * np.cumsum(dw, axis=1))


def merton_terminal(s0, r, sigma, lam, mu_j, sig_j, t, n_paths, q=0.0,
                    rng: np.random.Generator | None = None) -> np.ndarray:
    """Terminal values of a Merton jump-diffusion under the risk-neutral
    measure (compensated so that E[S_T] = S_0 exp((r - q) T))."""
    rng = rng or np.random.default_rng()
    kbar = np.exp(mu_j + 0.5 * sig_j**2) - 1
    n_jumps = rng.poisson(lam * t, n_paths)
    jump = mu_j * n_jumps + sig_j * np.sqrt(n_jumps) * rng.standard_normal(n_paths)
    diff = (r - q - lam * kbar - 0.5 * sigma**2) * t + sigma * np.sqrt(t) * rng.standard_normal(n_paths)
    return s0 * np.exp(diff + jump)
