"""Market risk measures on a TradingBook.

* VaR / ES of the full-revaluation P&L
* FRTB internal-model ES with the liquidity-horizon cascade (MAR33.4)
      ES = sqrt( ES_T(P)^2 + sum_{j>=2} ( ES_T(P, j) sqrt((LH_j - LH_{j-1}) / T) )^2 )
  ES_T(P, j): 10-day ES when only factors with liquidity horizon >= LH_j move
* IMCC = rho * ES_total + (1 - rho) * sum_classes ES_class,  rho = 0.5 (MAR33.5)
* Euler (component) ES by position and desk
* Delta-gamma approximation vs full revaluation
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..stats import var_es
from .book import TradingBook

LH_BUCKETS = (10, 20, 40, 60, 120)
FRTB_ALPHA = 0.975


def loss_measures(pnl_total: np.ndarray, alphas=(0.99, 0.975)) -> dict:
    loss = -np.asarray(pnl_total)
    out = {}
    for a in alphas:
        v, e = var_es(loss, a)
        out[a] = {"VaR": v, "ES": e}
    return out


def component_es(pnl: np.ndarray, alpha: float = FRTB_ALPHA) -> np.ndarray:
    """Euler allocation: ES_i = E[-P&L_i | L >= VaR], sums to the tail mean."""
    loss = -pnl.sum(axis=1)
    v, _ = var_es(loss, alpha)
    tail = loss >= v
    return -pnl[tail].mean(axis=0)


def _mask_shocks(book: TradingBook, shocks: np.ndarray, keep) -> np.ndarray:
    m = np.array([keep(f) for f in book.factors])
    return shocks * m[None, :]


def frtb_es(book: TradingBook, shocks_10d: np.ndarray, alpha: float = FRTB_ALPHA,
            factor_filter=None) -> dict:
    """Liquidity-adjusted ES from 10-day scenarios (T = 10 days)."""
    t = 10
    keep_base = factor_filter or (lambda f: True)
    es_j = []
    for lh in LH_BUCKETS:
        s = _mask_shocks(book, shocks_10d, lambda f: keep_base(f) and f.liquidity_horizon >= lh)
        if not np.any(s):
            es_j.append(0.0)
            continue
        es_j.append(var_es(-book.pnl(s).sum(axis=1), alpha)[1])
    es_j = np.array(es_j)
    scale = np.sqrt(np.diff(np.concatenate([[0], LH_BUCKETS])) / t)
    scale[0] = 1.0
    es_lh = float(np.sqrt(np.sum((es_j * scale) ** 2)))
    return {"es_10d": float(es_j[0]), "es_by_bucket": dict(zip(LH_BUCKETS, es_j)),
            "es_liquidity_adjusted": es_lh}


def imcc(book: TradingBook, shocks_10d: np.ndarray, rho: float = 0.5) -> dict:
    """Internally modelled capital charge (unstressed calibration)."""
    total = frtb_es(book, shocks_10d)["es_liquidity_adjusted"]
    classes = sorted({f.asset_class for f in book.factors})
    by_class = {c: frtb_es(book, shocks_10d, factor_filter=lambda f, c=c: f.asset_class == c)
                ["es_liquidity_adjusted"] for c in classes}
    return {"es_total": total, "es_by_class": by_class,
            "imcc": rho * total + (1 - rho) * sum(by_class.values()),
            "diversification": 1 - total / sum(by_class.values())}


@dataclass
class DeltaGamma:
    delta: np.ndarray
    gamma: np.ndarray

    @classmethod
    def from_book(cls, book: TradingBook) -> "DeltaGamma":
        return cls(*book.sensitivities())

    def pnl(self, shocks: np.ndarray, gamma: bool = True) -> np.ndarray:
        out = shocks @ self.delta
        if gamma:
            out += 0.5 * np.einsum("ni,ij,nj->n", shocks, self.gamma, shocks)
        return out
