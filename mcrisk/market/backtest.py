"""VaR backtesting: coverage and independence tests, Basel traffic light,
and a rolling out-of-sample backtest of competing VaR models."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import binom, chi2

from . import scenarios as sc
from ..stats import var_es
from .book import TradingBook


def _xlogy(x, y):
    return 0.0 if x == 0 else x * np.log(y)


def kupiec_pof(hits: np.ndarray, p: float) -> dict:
    """Kupiec (1995) proportion-of-failures likelihood ratio, chi2(1)."""
    n, x = hits.size, int(hits.sum())
    phat = x / n
    lr = -2 * (_xlogy(n - x, 1 - p) + _xlogy(x, p)
               - _xlogy(n - x, 1 - phat) - _xlogy(x, phat))
    return {"exceptions": x, "expected": n * p, "lr": lr, "p_value": float(chi2.sf(lr, 1))}


def christoffersen(hits: np.ndarray, p: float) -> dict:
    """Christoffersen (1998) independence and conditional coverage tests."""
    h = hits.astype(int)
    a, b = h[:-1], h[1:]
    n00 = np.sum((a == 0) & (b == 0)); n01 = np.sum((a == 0) & (b == 1))
    n10 = np.sum((a == 1) & (b == 0)); n11 = np.sum((a == 1) & (b == 1))
    p01 = n01 / max(n00 + n01, 1)
    p11 = n11 / max(n10 + n11, 1)
    p1 = (n01 + n11) / max(n00 + n01 + n10 + n11, 1)
    lr_ind = -2 * (_xlogy(n00 + n10, 1 - p1) + _xlogy(n01 + n11, p1)
                   - _xlogy(n00, 1 - p01) - _xlogy(n01, p01)
                   - _xlogy(n10, 1 - p11) - _xlogy(n11, p11))
    lr_cc = kupiec_pof(hits, p)["lr"] + lr_ind
    return {"lr_ind": lr_ind, "p_ind": float(chi2.sf(lr_ind, 1)),
            "lr_cc": lr_cc, "p_cc": float(chi2.sf(lr_cc, 2)),
            "clustered_exceptions": int(n11)}


def traffic_light(exceptions: int, n: int = 250, p: float = 0.01) -> str:
    """Basel zones from the binomial CDF: green < 95%, red >= 99.99%.
    For n = 250 at 99% this gives green 0-4, yellow 5-9, red 10+."""
    c = binom.cdf(exceptions, n, p)
    return "green" if c < 0.95 else ("yellow" if c < 0.9999 else "red")


def zone_multiplier(exceptions: int) -> float:
    """Basel plus-factor added to the multiplier of 3 (250-day window)."""
    return 3.0 + {5: 0.40, 6: 0.50, 7: 0.65, 8: 0.75, 9: 0.85}.get(
        exceptions, 0.0 if exceptions <= 4 else 1.0)


@dataclass
class BacktestResult:
    model: str
    var: np.ndarray       # forecast 1-day VaR (positive = loss)
    pnl: np.ndarray       # realised P&L
    alpha: float

    @property
    def hits(self) -> np.ndarray:
        return -self.pnl > self.var

    def report(self) -> dict:
        p = 1 - self.alpha
        k = kupiec_pof(self.hits, p)
        c = christoffersen(self.hits, p)
        last = self.hits[-250:]
        return {"model": self.model, "days": self.hits.size, **k,
                "p_ind": c["p_ind"], "p_cc": c["p_cc"],
                "clustered": c["clustered_exceptions"],
                "worst_250d_exceptions": int(np.max(np.convolve(self.hits, np.ones(250), "valid"))),
                "last_250d_zone": traffic_light(int(last.sum()), last.size, p)}


def rolling_backtest(book: TradingBook, returns: np.ndarray, start: int,
                     window: int = 500, alpha: float = 0.99, n_mc: int = 4000,
                     refit_every: int = 20, seed: int = 0,
                     models=("historical", "normal_ewma", "fhs")) -> dict[str, BacktestResult]:
    """Out-of-sample 1-day VaR forecasts from day ``start`` to the end.

    Realised P&L is the full revaluation of the (static) book under each
    day's actual factor moves. GARCH parameters are refitted every
    ``refit_every`` days and the volatility filter is updated daily.
    """
    rng = np.random.default_rng(seed)
    t_end = returns.shape[0]
    pnl = book.pnl(returns[start:t_end]).sum(axis=1)
    out = {m: np.empty(t_end - start) for m in models}
    garch_models = None
    for i, t in enumerate(range(start, t_end)):
        hist = returns[t - window:t]
        if "historical" in models:
            out["historical"][i] = var_es(-book.pnl(hist).sum(axis=1), alpha)[0]
        if "normal_ewma" in models:
            s = sc.normal(hist, n_mc, 1, lam=0.94, rng=rng)
            out["normal_ewma"][i] = var_es(-book.pnl(s).sum(axis=1), alpha)[0]
        if "fhs" in models:
            if garch_models is None or i % refit_every == 0:
                garch_models = [sc.fit_garch(hist[:, j]) for j in range(hist.shape[1])]
            fhs = sc.FilteredHS.fit(hist, garch_models)
            s = fhs.simulate(n_mc, 1, rng=rng)
            out["fhs"][i] = var_es(-book.pnl(s).sum(axis=1), alpha)[0]
    return {m: BacktestResult(m, out[m], pnl, alpha) for m in models}
