"""Risk measures and Monte Carlo error estimation.

Losses are positive numbers (a gain is a negative loss). All estimators accept
optional likelihood-ratio weights so that the same code serves plain Monte
Carlo (weights = 1) and importance sampling.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import binom, norm


@dataclass(frozen=True)
class Estimate:
    value: float
    stderr: float

    @property
    def ci95(self) -> tuple[float, float]:
        h = 1.959963984540054 * self.stderr
        return self.value - h, self.value + h

    def __format__(self, spec: str) -> str:
        spec = spec or ".6g"
        return f"{self.value:{spec}} ± {self.stderr:{spec}}"


def mc_mean(x: np.ndarray) -> Estimate:
    x = np.asarray(x, dtype=float)
    return Estimate(float(x.mean()), float(x.std(ddof=1) / np.sqrt(x.size)))


def var_es(
    losses: np.ndarray,
    alpha: float | np.ndarray,
    weights: np.ndarray | None = None,
) -> tuple[np.ndarray | float, np.ndarray | float]:
    """Value-at-Risk and Expected Shortfall at confidence ``alpha``.

    VaR_a = inf{x : P(L > x) <= 1 - a}
    ES_a  = VaR_a + E[(L - VaR_a)^+] / (1 - a)      (Acerbi-Tasche, exact for
                                                     discrete distributions)

    With importance sampling, ``weights`` are the likelihood ratios dP/dQ of
    each scenario; tail probabilities are estimated as mean(w * 1{L > x}).
    """
    losses = np.asarray(losses, dtype=float)
    n = losses.size
    scalar = np.ndim(alpha) == 0
    alphas = np.atleast_1d(np.asarray(alpha, dtype=float))
    order = np.argsort(losses)[::-1]
    l_desc = losses[order]
    w_desc = np.ones(n) if weights is None else np.asarray(weights, float)[order]
    tail = np.cumsum(w_desc) / n
    var = np.empty_like(alphas)
    es = np.empty_like(alphas)
    for j, a in enumerate(alphas):
        k = min(np.searchsorted(tail, (1.0 - a) * (1 + 1e-12), side="right"), n - 1)
        v = l_desc[k]
        excess = np.maximum(l_desc[:k] - v, 0.0)
        var[j] = v
        es[j] = v + np.dot(w_desc[:k], excess) / (n * (1.0 - a))
    if scalar:
        return float(var[0]), float(es[0])
    return var, es


def tail_probability(
    losses: np.ndarray, x: float, weights: np.ndarray | None = None
) -> Estimate:
    """P(L > x) with its standard error (plain or importance sampling)."""
    ind = (np.asarray(losses) > x).astype(float)
    if weights is not None:
        ind = ind * weights
    return mc_mean(ind)


def quantile_ci(losses: np.ndarray, alpha: float, conf: float = 0.95) -> tuple[float, float]:
    """Distribution-free confidence interval for the alpha-quantile.

    The number of samples below the true quantile is Binomial(n, alpha), so
    order statistics give an exact interval without any density estimate.
    """
    s = np.sort(np.asarray(losses, dtype=float))
    n = s.size
    lo = int(binom.ppf((1 - conf) / 2, n, alpha))
    hi = int(binom.ppf((1 + conf) / 2, n, alpha))
    return float(s[max(lo - 1, 0)]), float(s[min(hi, n - 1)])


def batch_estimate(fn, losses: np.ndarray, weights: np.ndarray | None = None,
                   n_batches: int = 20) -> Estimate:
    """Standard error of any statistic ``fn(losses, weights)`` by batch means.

    Used for VaR/ES under importance sampling where no closed-form variance
    is available. Batches are contiguous blocks of i.i.d. scenarios.
    """
    losses = np.asarray(losses)
    idx = np.array_split(np.arange(losses.size), n_batches)
    vals = np.array([
        fn(losses[i], None if weights is None else weights[i]) for i in idx
    ])
    full = fn(losses, weights)
    return Estimate(float(full), float(vals.std(ddof=1) / np.sqrt(n_batches)))


def es_stderr_plain(losses: np.ndarray, alpha: float) -> float:
    """Asymptotic standard error of the plain MC Expected Shortfall.

    Var(ES_hat) ~ Var((L - VaR)^+) / (n (1 - a)^2)  (Hong & Liu, 2009).
    """
    v, _ = var_es(losses, alpha)
    excess = np.maximum(np.asarray(losses) - v, 0.0)
    return float(excess.std(ddof=1) / (np.sqrt(excess.size) * (1 - alpha)))


def var_stderr_plain(losses: np.ndarray, alpha: float) -> float:
    """Standard error of the empirical quantile from its binomial CI width."""
    lo, hi = quantile_ci(losses, alpha, conf=0.6826894921370859)
    return (hi - lo) / 2.0


def normal_quantile(alpha: float) -> float:
    return float(norm.ppf(alpha))
