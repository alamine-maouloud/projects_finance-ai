"""Order-flow model of a limit order book and its Monte Carlo simulation.

Background flow follows Cont, Stoikov & Talreja (2010): unit limit orders at
i ticks from the opposite best quote arrive at rate lam[i], resting orders are
cancelled at rate theta[i] each, and market orders arrive at rate mu per
side. Market orders can be made self- and cross-exciting (bivariate Hawkes),
which reproduces the clustering of trades seen on real markets while keeping
the mean rate mu. The event loop runs in C++ (mcrisk._native).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from . import hawkes

try:
    from .. import _native
except ImportError:  # extension not compiled
    _native = None

BID, ASK = 0, 1

# Rates of the order found by Cont, Stoikov & Talreja (2010) on a liquid
# Tokyo Stock Exchange stock (events per second, unit lot size): power-law
# limit order arrivals lam(i) = k / i^a and decaying cancellation rates.
CST_K, CST_A, CST_MU = 1.92, 0.52, 0.94
CST_THETA = (0.71, 0.81, 0.68, 0.56, 0.47, 0.47, 0.37, 0.30, 0.26, 0.19)


def available() -> bool:
    return _native is not None


@dataclass(frozen=True)
class FlowModel:
    lam: tuple[float, ...]
    theta: tuple[float, ...]
    mu: float = CST_MU
    alpha_self: float = 0.0
    alpha_cross: float = 0.0
    beta: float = 1.0
    tick: float = 0.01            # currency per tick
    p0: int = 10_000              # initial ask in ticks (100.00 at a 1-cent tick: 1 tick = 1 bp)
    n_ticks: int = 1 << 14

    @classmethod
    def cst(cls, hawkes_branching: float = 0.0, beta: float = 1.0, cross_share: float = 0.2,
            levels: int = 10, **kw) -> "FlowModel":
        """CST parameters; optional Hawkes market orders with branching ratio n
        split between self- and cross-excitation. ``levels`` > 10 extends the
        book with the same power law and the deepest cancellation rate."""
        i = np.arange(1, levels + 1)
        lam = tuple(float(x) for x in CST_K / i**CST_A)
        theta = tuple(CST_THETA[min(j, len(CST_THETA)) - 1] for j in i)
        n = hawkes_branching
        return cls(lam=lam, theta=theta, beta=beta,
                   alpha_self=n * beta * (1 - cross_share), alpha_cross=n * beta * cross_share, **kw)

    @property
    def depth(self) -> int:
        return len(self.lam)

    @property
    def branching_ratio(self) -> float:
        return (self.alpha_self + self.alpha_cross) / self.beta

    def _args(self):
        return (list(self.lam), list(self.theta), self.mu, self.alpha_self, self.alpha_cross, self.beta)


@dataclass
class FlowResult:
    model: FlowModel
    horizon: float
    grid_dt: float
    bid: np.ndarray               # ticks, sampled every grid_dt
    ask: np.ndarray
    depth_bid: np.ndarray         # (n_snap, K) volume at 0..K-1 ticks from own best
    depth_ask: np.ndarray
    mo_t: np.ndarray
    mo_side: np.ndarray
    mo_mid_before: np.ndarray
    mo_mid_after: np.ndarray
    n_limit: np.ndarray
    n_cancel: np.ndarray
    queue_time: np.ndarray
    n_market: int
    n_events: int
    agent: dict = field(default_factory=dict)

    @property
    def mid(self) -> np.ndarray:
        return 0.5 * (self.bid + self.ask)

    @property
    def spread(self) -> np.ndarray:
        return self.ask - self.bid

    def calibrate(self) -> FlowModel:
        """Poisson maximum likelihood from the sufficient statistics:
        lam_i = N_limit(i) / (2T), theta_i = N_cancel(i) / int Q_i dt, mu = N_mo / (2T)."""
        t = self.horizon
        return replace(self.model, lam=tuple(self.n_limit / (2 * t)),
                       theta=tuple(self.n_cancel / self.queue_time), mu=self.n_market / (2 * t),
                       alpha_self=0.0, alpha_cross=0.0)

    def fit_hawkes(self, side: int = BID) -> hawkes.HawkesFit:
        """Univariate Hawkes fit on one side's market-order times."""
        return hawkes.fit(self.mo_t[self.mo_side == side], self.horizon)


def simulate(model: FlowModel, horizon: float, seed: int = 0, grid_dt: float = 1.0,
             depth_dt: float = 10.0, record_mo: bool = True,
             agent: list[tuple[float, int, int]] | None = None) -> FlowResult:
    """Simulate ``horizon`` seconds of order flow. ``agent`` is an optional
    list of (time, side, quantity) market orders submitted by the user."""
    if _native is None:
        raise RuntimeError("the order-book simulator needs the native kernel (python setup.py build_ext --inplace)")
    agent = agent or []
    r = _native.simulate_flow(*model._args(), horizon, int(seed) % 2**64, grid_dt, depth_dt,
                              [a[0] for a in agent], [int(a[1]) for a in agent],
                              [int(a[2]) for a in agent], record_mo, model.n_ticks, model.p0)
    if r["hit_edge"]:
        raise RuntimeError("price reached the edge of the tick grid: increase n_ticks")
    k = model.depth
    return FlowResult(
        model=model, horizon=horizon, grid_dt=grid_dt, bid=r["bid"], ask=r["ask"],
        depth_bid=r["depth_bid"].reshape(-1, k), depth_ask=r["depth_ask"].reshape(-1, k),
        mo_t=r["mo_t"], mo_side=r["mo_side"], mo_mid_before=r["mo_mid_before"],
        mo_mid_after=r["mo_mid_after"], n_limit=r["n_limit"], n_cancel=r["n_cancel"],
        queue_time=r["queue_time"], n_market=int(r["n_market"]), n_events=int(r["n_events"]),
        agent={k_: r[k_] for k_ in ("ag_t", "ag_mid_before", "ag_filled", "ag_notional")},
    )


def simulate_agent(model: FlowModel, schedule: list[tuple[float, int, int]], horizon: float,
                   n_paths: int, seed: int = 0, warmup: float = 600.0, threads: int | None = None) -> dict:
    """Run the same execution schedule on ``n_paths`` independent books, in
    parallel. Every path first lets the book reach its stationary regime for
    ``warmup`` seconds. Returns fills and notionals per path and child order."""
    import os

    if _native is None:
        raise RuntimeError("the order-book simulator needs the native kernel")
    return _native.simulate_agent_paths(
        *model._args(), horizon, warmup, [s[0] for s in schedule], [int(s[1]) for s in schedule],
        [int(s[2]) for s in schedule], n_paths, int(seed) % 2**64, threads or os.cpu_count() or 1,
        model.n_ticks, model.p0)
