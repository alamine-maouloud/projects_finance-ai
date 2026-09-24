"""Stylised facts of simulated (or real) order-book data.

All functions take plain arrays so they apply to any mid-price series
sampled on a regular grid, in ticks.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import kurtosis


def spread_distribution(spread: np.ndarray, max_ticks: int = 6) -> np.ndarray:
    """P(spread = s ticks) for s = 1..max_ticks (the last bucket is >= max)."""
    s = np.clip(np.round(spread).astype(int), 1, max_ticks)
    return np.bincount(s, minlength=max_ticks + 1)[1:] / s.size


def depth_profile(depth_bid: np.ndarray, depth_ask: np.ndarray) -> np.ndarray:
    """Mean volume at 0..K-1 ticks from the best quote, both sides pooled."""
    return 0.5 * (depth_bid.mean(axis=0) + depth_ask.mean(axis=0))


def increments(mid: np.ndarray, lag: int) -> np.ndarray:
    """Non-overlapping mid-price changes over ``lag`` grid steps."""
    m = mid[:: lag]
    return np.diff(m)


def kurtosis_by_horizon(mid: np.ndarray, lags) -> np.ndarray:
    """Excess kurtosis of mid changes: fat tails at short horizons that fade
    as changes aggregate (aggregational Gaussianity)."""
    return np.array([kurtosis(increments(mid, l)) for l in lags])


def autocorrelation(x: np.ndarray, lags) -> np.ndarray:
    x = np.asarray(x, dtype=float) - np.mean(x)
    v = np.dot(x, x)
    return np.array([np.dot(x[:-l], x[l:]) / v for l in lags])


def signature_plot(mid: np.ndarray, lags, dt: float = 1.0) -> np.ndarray:
    """Realised variance per unit time sampled every ``lag`` steps. Bid-ask
    bounce inflates it at high frequency; it flattens at longer scales."""
    total = (mid.size - 1) * dt
    return np.array([np.sum(increments(mid, l) ** 2) / total for l in lags])


def response_function(mo_t, mo_side, mo_mid_before, mid, lags, dt: float = 1.0) -> np.ndarray:
    """Average signed price move after a market order,
    R(tau) = E[eps (m(t + tau) - m(t-))], eps = +1 for buys, in ticks."""
    eps = np.where(np.asarray(mo_side) == 0, 1.0, -1.0)
    out = []
    for l in lags:
        idx = np.floor(np.asarray(mo_t) / dt).astype(int) + l
        ok = idx < mid.size
        out.append(np.mean(eps[ok] * (mid[idx[ok]] - np.asarray(mo_mid_before)[ok])))
    return np.array(out)


def dispersion_index(event_times: np.ndarray, horizon: float, window: float) -> float:
    """Var / mean of event counts in windows: 1 for Poisson, > 1 when events cluster."""
    counts = np.bincount((np.asarray(event_times) // window).astype(int),
                         minlength=int(horizon // window))[: int(horizon // window)]
    return float(counts.var() / counts.mean())


def duration_cv(event_times: np.ndarray) -> float:
    """Coefficient of variation of inter-event durations (1 for Poisson)."""
    d = np.diff(np.sort(event_times))
    return float(d.std() / d.mean())
