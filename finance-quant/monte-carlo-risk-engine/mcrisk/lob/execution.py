"""Optimal execution and liquidity risk.

Almgren & Chriss (2000), discrete time. Selling X shares in N slices of
length tau = T / N, with holdings x_0 = X, ..., x_N = 0 and trades n_k:

    S_k = S_{k-1} + sigma sqrt(tau) xi_k - gamma n_k          permanent impact
    S~_k = S_{k-1} - eps - (eta / tau) n_k                    temporary impact
    shortfall = X S_0 - sum n_k S~_k

    E = gamma X^2 / 2 + eps X + (eta~ / tau) sum n_k^2,   eta~ = eta - gamma tau / 2
    V = sigma^2 tau sum_{k=1}^{N} x_k^2

The mean-variance optimal trajectory is x_j = X sinh(kappa (T - t_j)) / sinh(kappa T)
with cosh(kappa tau) = 1 + lambda sigma^2 tau^2 / (2 eta~).

The same schedules are then executed in the simulated order book, where
impact comes from walking real queues and from the book's own dynamics, not
from a formula. The gap between the two measures model risk in the impact model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from . import flow as F


@dataclass(frozen=True)
class ImpactParams:
    sigma: float      # price volatility per sqrt(time unit)
    eta: float        # temporary impact: price concession per (share / time unit)
    gamma: float      # permanent impact per share
    eps: float = 0.0  # fixed cost per share (half-spread)


@dataclass(frozen=True)
class Schedule:
    times: np.ndarray      # (N,) trade times t_1..t_N
    holdings: np.ndarray   # (N + 1,) x_0..x_N
    trades: np.ndarray     # (N,) n_1..n_N

    @property
    def tau(self) -> float:
        return float(self.times[0])


def ac_schedule(x: float, horizon: float, n: int, risk_aversion: float,
                p: ImpactParams) -> Schedule:
    """Almgren-Chriss trajectory; risk_aversion = 0 gives TWAP."""
    tau = horizon / n
    t = np.arange(n + 1) * tau
    eta_t = p.eta - 0.5 * p.gamma * tau
    if eta_t <= 0:
        raise ValueError("eta must exceed gamma * tau / 2")
    if risk_aversion <= 0:
        hold = x * (1 - t / horizon)
    else:
        kappa = np.arccosh(1 + risk_aversion * p.sigma**2 * tau**2 / (2 * eta_t)) / tau
        hold = x * np.sinh(kappa * (horizon - t)) / np.sinh(kappa * horizon)
    return Schedule(times=t[1:], holdings=hold, trades=-np.diff(hold))


def ac_moments(s: Schedule, p: ImpactParams) -> tuple[float, float]:
    """Expected shortfall-cost and its variance (closed form)."""
    x0 = s.holdings[0]
    tau = s.tau
    eta_t = p.eta - 0.5 * p.gamma * tau
    e = 0.5 * p.gamma * x0**2 + p.eps * np.sum(np.abs(s.trades)) + eta_t / tau * np.sum(s.trades**2)
    v = p.sigma**2 * tau * np.sum(s.holdings[1:] ** 2)
    return float(e), float(v)


def ac_simulate(s: Schedule, p: ImpactParams, n_paths: int,
                rng: np.random.Generator | None = None) -> np.ndarray:
    """Shortfall samples under the Almgren-Chriss price model (validation)."""
    rng = rng or np.random.default_rng()
    tau, n = s.tau, s.trades
    xi = rng.standard_normal((n_paths, n.size))
    moves = p.sigma * np.sqrt(tau) * xi - p.gamma * n          # S_k - S_{k-1}
    s_prev = np.concatenate([np.zeros((n_paths, 1)), np.cumsum(moves, axis=1)[:, :-1]], axis=1)
    exec_px = s_prev - p.eps - p.eta / tau * n
    return -(exec_px * n).sum(axis=1)                          # X S_0 - sum n S~, with S_0 = 0


def ac_frontier(x: float, horizon: float, n: int, p: ImpactParams, risk_aversions) -> np.ndarray:
    """(lambda, E, sd) along the efficient frontier."""
    out = []
    for lam in risk_aversions:
        e, v = ac_moments(ac_schedule(x, horizon, n, lam, p), p)
        out.append((lam, e, np.sqrt(v)))
    return np.array(out)


# --------------------------------------------------------------------------
# Impact estimated on the simulated book
# --------------------------------------------------------------------------

def walk_cost(depth: np.ndarray, qty: int) -> float:
    """Average price concession (ticks from the best quote) of a market order
    of ``qty`` lots against a depth profile (volume at 0, 1, 2 ... ticks)."""
    left, cost = qty, 0.0
    for j, v in enumerate(depth):
        take = min(left, v)
        cost += take * j
        left -= take
        if left == 0:
            return cost / qty
    return (cost + left * len(depth)) / qty


def estimate_impact(model: F.FlowModel, seed: int = 0, horizon: float = 23_400.0,
                    child_sizes=(1, 2, 4, 8, 16), tau: float = 60.0,
                    perm_size: int = 20, perm_paths: int = 400, perm_lag: float = 600.0,
                    threads: int | None = None) -> tuple[ImpactParams, dict]:
    """Almgren-Chriss parameters (in ticks and seconds) from the book itself.

    sigma  mid volatility per sqrt(s), from 60-s changes of a long run
    eps    half-spread; eta from the depth-walk cost of child orders of size q
           executed once per tau seconds (concession = eps + (eta / tau) q)
    gamma  mean mid move ``perm_lag`` seconds after a sell of ``perm_size`` lots
    """
    r = F.simulate(model, horizon, seed=seed, grid_dt=1.0, depth_dt=5.0, record_mo=False)
    mid = r.mid
    ch = np.diff(mid[::60])
    sigma = float(ch.std() / np.sqrt(60.0))
    eps = float(np.mean(r.spread) / 2)
    conc = np.array([np.mean([walk_cost(d, q) for d in r.depth_bid]) for q in child_sizes])
    q = np.asarray(child_sizes, dtype=float)
    slope = float(np.sum(q * conc) / np.sum(q * q))            # regression through the origin
    eta = slope * tau
    # common random numbers: the same streams with and without the agent's
    # order, so the difference isolates the impact
    res = F.simulate_agent(model, [(0.0, F.ASK, perm_size)], perm_lag, perm_paths,
                           seed=seed + 1, threads=threads)
    base = F.simulate_agent(model, [], perm_lag, perm_paths, seed=seed + 1, threads=threads)
    diff = (res["mid_end"] - res["mid0"]) - (base["mid_end"] - base["mid0"])
    drift = float(diff.mean())
    gamma = max(-drift / perm_size, 0.0)
    diag = {"child_sizes": list(child_sizes), "concession": conc.tolist(),
            "mean_spread": float(np.mean(r.spread)), "perm_drift": float(drift),
            "perm_drift_se": float(diff.std(ddof=1) / np.sqrt(perm_paths))}
    return ImpactParams(sigma=sigma, eta=max(eta, 0.5 * gamma * tau + 1e-9), gamma=gamma, eps=eps), diag


def execute_in_book(model: F.FlowModel, schedule: Schedule, n_paths: int, seed: int = 0,
                    side: int = F.ASK, threads: int | None = None) -> dict:
    """Run a schedule of market orders through independent simulated books.

    Child sizes are rounded to whole lots (the rounding error is carried to
    the next child). All costs are in ticks, positive = cost, and split into

    spread_impact  sum q_k m_k - proceeds_k: half-spread plus walking the book
    drift          sum q_k (m_0 - m_k): own permanent impact plus market moves
    unfilled       lots an exhausted book could not absorb, valued at the final
                   mid less the modelled depth (a conservative penalty)
    """
    exact = np.concatenate([[0.0], np.cumsum(schedule.trades)])
    lots = np.diff(np.round(exact)).astype(int)
    plan = [(float(t), side, int(q)) for t, q in zip(schedule.times - schedule.tau, lots) if q > 0]
    horizon = float(schedule.times[-1])
    out = F.simulate_agent(model, plan, horizon + 1.0, n_paths, seed=seed, threads=threads)
    x = int(lots.sum())
    sign = 1.0 if side == F.ASK else -1.0
    q, notion, m_k = out["filled"], out["notional"], out["mid_before"]
    m0 = out["mid0"][:, None]
    spread_impact = sign * (q * m_k - notion).sum(axis=1)
    drift = sign * (q * (m0 - m_k)).sum(axis=1)
    left = x - q.sum(axis=1)
    unfilled = sign * left * (out["mid0"] - (out["mid_end"] - sign * model.depth))
    return {"shortfall": spread_impact + drift + unfilled, "spread_impact": spread_impact,
            "drift": drift, "unfilled": unfilled, "fill_rate": float(1 - left.sum() / (x * n_paths)),
            "qty": x, "children": len(plan), "mid0": out["mid0"]}


def cost_at_risk(shortfall: np.ndarray, alpha: float = 0.99) -> float:
    return float(np.quantile(shortfall, alpha))


def optimal_horizon(x: float, p: ImpactParams, alpha: float = 0.99, n_per_unit: int = 1,
                    horizons=None) -> tuple[float, np.ndarray]:
    """Liquidation horizon minimising the cost-at-risk E + z_alpha sd of a
    TWAP liquidation (normal approximation). Returns (T*, table of
    (T, E, sd, CaR))."""
    z = norm.ppf(alpha)
    horizons = np.asarray(horizons if horizons is not None else np.geomspace(0.05, 200, 400))
    rows = []
    for t in horizons:
        n = max(int(round(t * n_per_unit)), 1)
        tau = t / n
        pp = p if p.eta - 0.5 * p.gamma * tau > 0 else ImpactParams(p.sigma, 0.5 * p.gamma * tau + 1e-12, p.gamma, p.eps)
        e, v = ac_moments(ac_schedule(x, t, n, 0.0, pp), pp)
        rows.append((t, e, np.sqrt(v), e + z * np.sqrt(v)))
    rows = np.array(rows)
    return float(rows[np.argmin(rows[:, 3]), 0]), rows


def liquidity_study(model: F.FlowModel, p: ImpactParams, sizes, horizons_min, n_paths: int = 1000,
                    child_every: float = 60.0, alpha: float = 0.99, seed: int = 0,
                    min_fill: float = 0.995) -> dict:
    """TWAP liquidations of several position sizes over several horizons, in
    the simulated book and under the calibrated Almgren-Chriss model.

    Costs are reported in basis points of the initial notional. For each size,
    ``lob_best`` is the horizon with the lowest cost-at-risk (E + tail) among
    those where the book absorbs at least ``min_fill`` of the position, and
    ``ac_best`` the horizon Almgren-Chriss would choose with the same criterion.
    """
    z = norm.ppf(alpha)
    rows, best = [], {}
    for x in sizes:
        cands = []
        for h in horizons_min:
            t = 60.0 * h
            n = max(int(round(t / child_every)), 1)
            sc = ac_schedule(x, t, n, 0.0, p)
            r = execute_in_book(model, sc, n_paths, seed=seed + 7919 * int(h) + int(x))
            bps = 1e4 / (x * r["mid0"])
            sh = r["shortfall"] * bps
            e_ac, v_ac = ac_moments(sc, p)
            ac_bps = 1e4 / (x * model.p0)
            row = {"size": int(x), "horizon_min": float(h), "fill_rate": r["fill_rate"],
                   "mean": float(sh.mean()), "mean_se": float(sh.std(ddof=1) / np.sqrt(sh.size)),
                   "sd": float(sh.std(ddof=1)), "car": cost_at_risk(sh, alpha),
                   "spread_impact": float((r["spread_impact"] * bps).mean()),
                   "drift": float((r["drift"] * bps).mean()),
                   "ac_mean": e_ac * ac_bps, "ac_sd": np.sqrt(v_ac) * ac_bps,
                   "ac_car": (e_ac + z * np.sqrt(v_ac)) * ac_bps}
            rows.append(row)
            cands.append(row)
        feasible = [c for c in cands if c["fill_rate"] >= min_fill]
        best[int(x)] = {
            "lob_best": min(feasible, key=lambda c: c["car"])["horizon_min"] if feasible else None,
            "ac_best": min(cands, key=lambda c: c["ac_car"])["horizon_min"],
            "min_full_fill": min((c["horizon_min"] for c in feasible), default=None),
        }
    return {"rows": rows, "best": best}
