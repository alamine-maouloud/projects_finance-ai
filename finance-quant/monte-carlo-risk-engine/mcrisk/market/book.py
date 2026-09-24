"""Trading book positions with full revaluation under risk-factor shocks.

All values are reported in EUR. A scenario is a vector of factor shocks:
log-returns for equity and FX, absolute changes for rates, credit spreads
and implied volatilities. Every position revalues all scenarios at once.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..pricing.black_scholes import bs_price
from .data import FACTORS, NAMES, RiskFactor

KEY_TENORS = np.array([2.0, 5.0, 10.0, 30.0])
RATE_FACTORS = ("IR_EUR_2Y", "IR_EUR_5Y", "IR_EUR_10Y", "IR_EUR_30Y")


def shocked_levels(shocks: np.ndarray, factors: tuple[RiskFactor, ...] = FACTORS) -> dict:
    """Map an (n, F) shock matrix to factor levels, one array per factor."""
    shocks = np.atleast_2d(shocks)
    out = {}
    for j, f in enumerate(factors):
        x = shocks[:, j]
        if f.is_log:
            out[f.name] = f.level * np.exp(x)
        elif f.kind == "vol":
            out[f.name] = np.maximum(f.level + x, 0.01)
        elif f.kind == "spread":
            out[f.name] = np.maximum(f.level + x, 0.0)
        else:
            out[f.name] = f.level + x
    return out


def _fx(levels, ccy_factor, n):
    return np.ones(n) if ccy_factor is None else levels[ccy_factor]


@dataclass
class Equity:
    name: str
    desk: str
    factor: str
    amount: float                    # market value in local currency today
    ccy_factor: str | None = None    # FX quoted as local ccy per EUR

    def factors(self):
        return {self.factor, self.ccy_factor} - {None}

    def value(self, lv: dict) -> np.ndarray:
        s = lv[self.factor]
        s0 = FACTORS[NAMES.index(self.factor)].level
        return self.amount * s / s0 / _fx(lv, self.ccy_factor, s.size)


@dataclass
class EquityOption:
    name: str
    desk: str
    factor: str
    vol_factor: str
    strike: float                    # relative to today's spot
    maturity: float
    call: bool
    notional: float                  # underlying notional in local ccy (sign = long/short)
    ccy_factor: str | None = None
    rate: float = 0.022

    def factors(self):
        return {self.factor, self.vol_factor, self.ccy_factor} - {None}

    def value(self, lv: dict) -> np.ndarray:
        s = lv[self.factor]
        s0 = FACTORS[NAMES.index(self.factor)].level
        units = self.notional / s0
        px = bs_price(s, self.strike * s0, self.maturity, self.rate, lv[self.vol_factor],
                      call=self.call)
        return units * px / _fx(lv, self.ccy_factor, s.size)


@dataclass
class Bond:
    """Fixed-coupon bond discounted on the EUR key-rate curve plus a spread."""

    name: str
    desk: str
    notional: float
    coupon: float
    maturity: float
    freq: int = 1
    spread_factor: str | None = None
    times: np.ndarray = field(init=False, repr=False)
    flows: np.ndarray = field(init=False, repr=False)

    def __post_init__(self):
        n = int(round(self.maturity * self.freq))
        self.times = np.arange(1, n + 1) / self.freq
        self.flows = np.full(n, self.notional * self.coupon / self.freq)
        self.flows[-1] += self.notional

    def factors(self):
        return set(RATE_FACTORS) | ({self.spread_factor} - {None})

    def value(self, lv: dict) -> np.ndarray:
        keys = np.column_stack([lv[f] for f in RATE_FACTORS])          # (n, 4)
        # linear interpolation of the zero curve in maturity, flat outside
        z = np.stack([np.interp(t, KEY_TENORS, [0, 1, 2, 3]) for t in self.times])
        lo = np.floor(z).astype(int).clip(0, 2)
        wgt = z - lo
        zr = keys[:, lo] * (1 - wgt) + keys[:, lo + 1] * wgt            # (n, m)
        if self.spread_factor is not None:
            zr = zr + lv[self.spread_factor][:, None]
        return np.exp(-zr * self.times) @ self.flows


@dataclass
class TradingBook:
    positions: list
    factors: tuple[RiskFactor, ...] = FACTORS

    @property
    def names(self) -> list[str]:
        return [p.name for p in self.positions]

    @property
    def desks(self) -> list[str]:
        return [p.desk for p in self.positions]

    def values(self, shocks: np.ndarray) -> np.ndarray:
        """(n, P) position values in EUR under each scenario."""
        lv = shocked_levels(shocks, self.factors)
        return np.column_stack([p.value(lv) for p in self.positions])

    def base_values(self) -> np.ndarray:
        return self.values(np.zeros((1, len(self.factors))))[0]

    def pnl(self, shocks: np.ndarray, chunk: int = 50_000) -> np.ndarray:
        """(n, P) P&L of every position, computed in chunks of scenarios."""
        base = self.base_values()
        shocks = np.atleast_2d(shocks)
        out = np.empty((shocks.shape[0], len(self.positions)))
        for i in range(0, shocks.shape[0], chunk):
            out[i:i + chunk] = self.values(shocks[i:i + chunk]) - base
        return out

    def sensitivities(self, bump: dict | None = None) -> tuple[np.ndarray, np.ndarray]:
        """Portfolio delta vector and gamma matrix w.r.t. factor shocks by
        central finite differences (used for the delta-gamma approximation)."""
        f = len(self.factors)
        h = np.array([bump.get(x.name, 1e-4) if bump else
                      (1e-3 if x.is_log or x.kind == "vol" else 1e-5) for x in self.factors])
        e = np.eye(f) * h
        total = lambda s: self.values(s).sum(axis=1)  # noqa: E731
        up, dn = total(e), total(-e)
        v0 = total(np.zeros((1, f)))[0]
        delta = (up - dn) / (2 * h)
        gamma = np.diag((up - 2 * v0 + dn) / h**2)
        for i in range(f):
            for j in range(i + 1, f):
                pp = np.zeros(f); pp[i] = h[i]; pp[j] = h[j]
                pm = pp.copy(); pm[j] = -h[j]
                mp = -pm
                mm = -pp
                v = total(np.stack([pp, pm, mp, mm]))
                gamma[i, j] = gamma[j, i] = (v[0] - v[1] - v[2] + v[3]) / (4 * h[i] * h[j])
        return delta, gamma


def sample_trading_book() -> TradingBook:
    """A diversified EUR trading book of a universal bank (EUR notionals)."""
    m = 1e6
    return TradingBook([
        Equity("EU large caps", "Cash equity", "EQ_EUROPE", 180 * m),
        Equity("US large caps", "Cash equity", "EQ_US", 140 * m, "FX_EURUSD"),
        Equity("Japan equities", "Cash equity", "EQ_JAPAN", 7_000 * m, "FX_EURJPY"),
        Equity("EM equities", "Cash equity", "EQ_EM", 60 * m, "FX_EURUSD"),
        Equity("EU banks", "Cash equity", "EQ_EU_BANKS", 70 * m),
        Equity("Index hedge (short EU futures)", "Cash equity", "EQ_EUROPE", -120 * m),
        EquityOption("Short 1y 90% puts EU", "Equity derivatives", "EQ_EUROPE", "VOL_EQ_EU",
                     0.90, 1.0, False, -400 * m),
        EquityOption("Short 3m 85% puts EU", "Equity derivatives", "EQ_EUROPE", "VOL_EQ_EU",
                     0.85, 0.25, False, -250 * m),
        EquityOption("Short 3m 115% calls EU", "Equity derivatives", "EQ_EUROPE", "VOL_EQ_EU",
                     1.15, 0.25, True, -250 * m),
        EquityOption("Long 6m ATM calls US", "Equity derivatives", "EQ_US", "VOL_EQ_US",
                     1.00, 0.5, True, 200 * m, "FX_EURUSD"),
        Bond("EUR govt 2y", "Rates", 250 * m, 0.022, 2.0),
        Bond("EUR govt 10y", "Rates", 300 * m, 0.028, 10.0),
        Bond("EUR govt 30y", "Rates", 120 * m, 0.030, 30.0),
        Bond("Short EUR govt 5y", "Rates", -200 * m, 0.024, 5.0),
        Bond("EUR IG corporates 7y", "Credit", 260 * m, 0.035, 7.0, spread_factor="CS_EUR_IG"),
        Bond("EUR HY bonds 5y", "Credit", 90 * m, 0.060, 5.0, spread_factor="CS_EUR_HY"),
    ])
