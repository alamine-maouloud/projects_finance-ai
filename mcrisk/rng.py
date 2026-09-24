"""Random number generation.

Every simulation in the engine draws from independent, reproducible streams
spawned from a single root seed (``numpy.random.SeedSequence``). A chunk of
scenarios always receives the same stream for a given seed, whatever the
number of worker threads, so results are bit-for-bit reproducible and a chunk
can be replayed exactly (used for the two-pass Euler allocation).
"""

from __future__ import annotations

import numpy as np
from scipy.special import ndtri
from scipy.stats import qmc

_EPS = 1e-15


def spawn_generators(seed: int | None, n: int) -> list[np.random.Generator]:
    """``n`` statistically independent generators derived from ``seed``."""
    children = np.random.SeedSequence(seed).spawn(n)
    return [np.random.Generator(np.random.PCG64DXSM(s)) for s in children]


def standard_normals(
    n: int,
    d: int,
    *,
    method: str = "pseudo",
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Draw an ``(n, d)`` array of standard normals.

    method
        ``pseudo``      plain pseudo-random numbers
        ``antithetic``  pairs (z, -z): exact symmetry, halves variance of
                        monotone payoffs
        ``sobol``       Owen-scrambled Sobol points mapped through the inverse
                        normal CDF (randomised QMC, error ~ O(log(n)^d / n))
    """
    rng = rng if rng is not None else np.random.default_rng()
    if method == "pseudo":
        return rng.standard_normal((n, d))
    if method == "antithetic":
        half = rng.standard_normal(((n + 1) // 2, d))
        return np.concatenate([half, -half])[:n]
    if method == "sobol":
        m = int(np.ceil(np.log2(max(n, 2))))
        u = qmc.Sobol(d, scramble=True, seed=rng).random_base2(m)[:n]
        return ndtri(np.clip(u, _EPS, 1.0 - _EPS))
    raise ValueError(f"unknown method {method!r}")


def brownian_bridge(z: np.ndarray, times: np.ndarray) -> np.ndarray:
    """Build Brownian paths ``W(times)`` from normals with bridge ordering.

    Column 0 of ``z`` sets the terminal value, the next columns fill the
    midpoints recursively. Paired with Sobol points this concentrates the
    variance on the first (best distributed) QMC dimensions.

    z      : (n, m) standard normals
    times  : (m,) strictly increasing, times[0] > 0
    return : (n, m) Brownian motion sampled at ``times``
    """
    n, m = z.shape
    t = np.concatenate([[0.0], np.asarray(times, dtype=float)])
    if len(t) != m + 1 or np.any(np.diff(t) <= 0):
        raise ValueError("times must be strictly increasing, positive, len m")
    w = np.zeros((n, m + 1))
    w[:, m] = np.sqrt(t[m]) * z[:, 0]
    col = 1
    stack = [(0, m)]
    while stack:
        left, right = stack.pop(0)
        if right - left < 2:
            continue
        mid = (left + right) // 2
        tl, tm, tr = t[left], t[mid], t[right]
        mean = ((tr - tm) * w[:, left] + (tm - tl) * w[:, right]) / (tr - tl)
        std = np.sqrt((tm - tl) * (tr - tm) / (tr - tl))
        w[:, mid] = mean + std * z[:, col]
        col += 1
        stack.append((left, mid))
        stack.append((mid, right))
    return w[:, 1:]
