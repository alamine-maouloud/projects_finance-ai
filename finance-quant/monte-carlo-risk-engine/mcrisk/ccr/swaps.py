"""Interest rate swaps revalued path by path under Hull-White.

Single-curve valuation. At time t, with (reset_c, pay_c) the accrual period
running at t:

    floating leg = P(t, pay_c) / P(reset_c, pay_c) - P(t, T_end)
    fixed leg    = K * sum_{T_i > t} tau_i P(t, T_i)

The fixing P(reset_c, pay_c) is path-dependent and is captured when the path
reaches the reset date; every reset and payment date is added to the
simulation grid (the Hull-White simulation is exact on any grid).
Cash flows paid at t are excluded from the value at t.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..curves import NelsonSiegelSvensson
from ..models.hull_white import HullWhite, HullWhitePaths


@dataclass
class InterestRateSwap:
    name: str
    notional: float
    maturity: float                 # years from today
    payer: bool = True              # pay fixed / receive floating
    fixed_rate: float | None = None # None -> par rate at inception
    start: float = 0.0              # negative for seasoned trades
    fixed_freq: int = 1
    float_freq: int = 4
    fixed_times: np.ndarray = field(init=False, repr=False)
    resets: np.ndarray = field(init=False, repr=False)
    float_pays: np.ndarray = field(init=False, repr=False)

    def __post_init__(self):
        def schedule(freq):
            n = int(round((self.maturity - self.start) * freq))
            return self.start + np.arange(1, n + 1) / freq

        fx = schedule(self.fixed_freq)
        self.fixed_times = fx[fx > 1e-12]
        fl = schedule(self.float_freq)
        keep = fl > 1e-12
        self.float_pays = fl[keep]
        self.resets = self.float_pays - 1.0 / self.float_freq

    def par_rate(self, curve: NelsonSiegelSvensson) -> float:
        return curve.par_swap_rate(max(self.start, 0.0), self.maturity, self.fixed_freq)

    def resolve(self, curve: NelsonSiegelSvensson) -> "InterestRateSwap":
        if self.fixed_rate is None:
            self.fixed_rate = self.par_rate(curve)
        return self

    @property
    def dates(self) -> np.ndarray:
        return np.unique(np.concatenate([self.fixed_times, self.resets[self.resets > 0], self.float_pays]))


@dataclass
class ExposureCube:
    times: np.ndarray        # (m + 1,)
    values: np.ndarray       # (n, m + 1, n_trades) mark-to-market, EUR
    discount: np.ndarray     # (n, m + 1)
    trade_names: list[str]

    @property
    def net(self) -> np.ndarray:
        return self.values.sum(axis=2)


def build_grid(trades, horizon: float, step: float) -> np.ndarray:
    base = np.arange(1, int(np.ceil(horizon / step)) + 1) * step
    dates = np.concatenate([t.dates for t in trades])
    grid = np.unique(np.round(np.concatenate([base, dates]), 10))
    return grid[(grid > 0) & (grid <= horizon + 1e-12)]


def simulate_exposures(trades: list[InterestRateSwap], model: HullWhite,
                       n_paths: int = 5000, step: float = 1 / 24, seed: int = 0,
                       antithetic: bool = True) -> ExposureCube:
    """Mark-to-market of every trade on every path and grid date."""
    curve = model.curve
    trades = [t.resolve(curve) for t in trades]
    horizon = max(t.maturity for t in trades)
    grid = build_grid(trades, horizon, step)
    paths: HullWhitePaths = model.simulate(grid, n_paths, np.random.default_rng(seed), antithetic)
    times = paths.times
    n, m1 = paths.x.shape
    values = np.zeros((n, m1, len(trades)))
    # fixing factors 1 / P(reset, pay) per trade and period (path-dependent)
    fixings = [np.ones((n, t.resets.size)) for t in trades]
    for j, t in enumerate(trades):
        seasoned = t.resets <= 1e-12
        if np.any(seasoned):
            # current period fixed before today: use today's money-market rate
            tau = 1.0 / t.float_freq
            fixings[j][:, seasoned] = 1 + tau * float(curve.zero(tau))

    all_dates = np.unique(np.concatenate([t.dates for t in trades]))
    for k, tk in enumerate(times):
        future = all_dates[all_dates > tk + 1e-12]
        if future.size == 0:
            continue
        pz = model.zcb(tk, future, paths.x[:, k])
        col = {d: i for i, d in enumerate(np.round(future, 10))}

        def p(ts):
            return pz[:, [col[d] for d in np.round(ts, 10)]]

        for j, t in enumerate(trades):
            # capture fixings reset at this date
            hit = np.flatnonzero(np.abs(t.resets - tk) < 1e-10)
            for h in hit:
                fixings[j][:, h] = 1.0 / p([t.float_pays[h]])[:, 0]
            if t.maturity <= tk + 1e-12:
                continue
            fx = t.fixed_times[t.fixed_times > tk + 1e-12]
            tau_fx = 1.0 / t.fixed_freq
            fixed = t.fixed_rate * tau_fx * p(fx).sum(axis=1)
            live = np.flatnonzero(t.float_pays > tk + 1e-12)
            first = live[0]
            p_end = p([t.maturity])[:, 0]
            if t.resets[first] > tk + 1e-12:          # forward-starting period
                flt = p([t.resets[first]])[:, 0] - p_end
            else:                                      # period already fixed
                flt = fixings[j][:, first] * p([t.float_pays[first]])[:, 0] - p_end
            v = t.notional * (flt - fixed)
            values[:, k, j] = v if t.payer else -v
    return ExposureCube(times=times, values=values, discount=paths.discount,
                        trade_names=[t.name for t in trades])


def sample_netting_set() -> list[InterestRateSwap]:
    """Swaps with one corporate counterparty (EUR, notionals in EUR)."""
    m = 1e6
    return [
        InterestRateSwap("Payer 10y (loan hedge)", 400 * m, 10.0, payer=True),
        InterestRateSwap("Payer 7y seasoned", 250 * m, 5.6, payer=True, fixed_rate=0.018, start=-1.4),
        InterestRateSwap("Receiver 5y", 300 * m, 5.0, payer=False),
        InterestRateSwap("Payer 15y fwd-start 2y", 150 * m, 15.0, payer=True, start=2.0),
        InterestRateSwap("Receiver 3y seasoned", 200 * m, 2.35, payer=False, fixed_rate=0.034, start=-0.65),
        InterestRateSwap("Payer 12y", 120 * m, 12.0, payer=True),
    ]
