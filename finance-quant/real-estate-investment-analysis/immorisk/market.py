"""Market risk: price and rent paths, calibrated on INSEE and DVF.

Prices. Quarterly log returns of the four INSEE notaires indices of existing
flats (Paris, inner suburbs, outer suburbs, rest of France) follow AR(1)
processes around a long-run growth rate,

    r_t - m = phi (r_{t-1} - m) + sigma e_t,   e_t ~ N(0, C),

with correlated shocks. House prices have momentum (phi is about 0.8 on
quarterly data), so a shock keeps pushing prices in the same direction for a
couple of years; this is why a 15-year horizon carries a lot of price risk. The
persistence, the volatilities and the correlations are estimated; the long-run
growth m is a scenario, because 30 years of history (including the 1998-2007
boom) say little about the next 15.

Rents. Rents in place are revised once a year by the IRL, simulated in the same
system (it is nearly uncorrelated with prices).

Local risk. On top of its zone, every department and every commune drifts away
by an independent random walk. The department volatility comes from the gap
between each department's DVF hedonic index and its INSEE zone index, net of
the sampling noise of the DVF index. The commune volatility comes from the
dispersion of commune price changes between 2022 and 2025 around their
department, net of estimation noise (see backtest.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .data import ZONES, zone_of

SERIES = ZONES + ("irl",)


@dataclass
class MarketModel:
    phi: np.ndarray  # (5,) AR(1) coefficients, zones then IRL
    sigma: np.ndarray  # (5,) quarterly shock volatilities
    corr: np.ndarray  # (5, 5) shock correlations
    start: np.ndarray  # (5,) current quarterly log change (average of the last 4 quarters)
    sample: str = ""
    dep_sd: float = 0.0185  # annual idiosyncratic volatility of a department
    commune_sd: float = 0.02  # annual idiosyncratic volatility of a commune
    history: pd.DataFrame = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            "series": list(SERIES), "phi": self.phi.round(4).tolist(),
            "sigma_quarterly": self.sigma.round(5).tolist(),
            "corr": self.corr.round(3).tolist(), "start_quarterly": self.start.round(5).tolist(),
            "sample": self.sample, "dep_sd_annual": round(self.dep_sd, 5),
            "commune_sd_annual": round(self.commune_sd, 5),
        }


def fit_market(levels: pd.DataFrame, start_window: int = 4) -> MarketModel:
    """Estimate the AR(1) system on quarterly log changes of the INSEE series."""
    r = np.log(levels[list(SERIES)]).diff()
    phi, sigma, resid = [], [], {}
    for c in SERIES:
        s = r[c].dropna()
        x, y = s.shift(1).iloc[1:], s.iloc[1:]
        xm, ym = x - x.mean(), y - y.mean()
        b = float((xm * ym).sum() / (xm * xm).sum())
        e = ym - b * xm
        phi.append(b)
        sigma.append(float(e.std(ddof=2)))
        resid[c] = e
    e = pd.DataFrame(resid).dropna()
    corr = e.corr().to_numpy()
    start = r.tail(start_window).mean().to_numpy()
    sample = f"{r.dropna(how='all').index[0]} to {r.index[-1]}"
    return MarketModel(np.array(phi), np.array(sigma), corr, start, sample=sample, history=r)


def dep_idio_sd(index: pd.DataFrame, levels: pd.DataFrame) -> tuple[float, pd.DataFrame]:
    """Annual idiosyncratic volatility of department prices around their INSEE zone.

    `index` is the DVF hedonic index (dep, quarter, delta, se). We compare Q4 to
    Q4 changes, subtract the sampling variance of the DVF index and average
    over departments weighted by their number of sales.
    """
    li = np.log(levels)
    q4 = index[index["quarter"] % 10 == 4].sort_values(["dep", "quarter"]).copy()
    q4["period"] = pd.PeriodIndex([f"{q // 10}Q4" for q in q4["quarter"]], freq="Q")
    q4["zone_level"] = [li[zone_of(d)].get(p, np.nan) for d, p in zip(q4["dep"], q4["period"])]
    g = q4.groupby("dep")
    q4["gap"] = g["delta"].diff() - g["zone_level"].diff()
    q4["noise"] = q4["se"] ** 2 + g["se"].shift(1) ** 2
    per_dep = q4.dropna(subset=["gap"]).groupby("dep").agg(
        n=("n", "sum"), var_gap=("gap", "var"), noise=("noise", "mean"))
    per_dep["idio_var"] = per_dep["var_gap"] - per_dep["noise"]
    pooled = float(np.average(per_dep["idio_var"], weights=per_dep["n"]))
    return float(np.sqrt(max(pooled, 0.0))), per_dep


@dataclass
class Paths:
    """Annual market paths shared by every commune (common random numbers)."""

    zone_log_growth: dict  # zone -> (P, H) annual log price change
    irl_log_growth: np.ndarray  # (P, H) annual log change of the IRL


def simulate_market(model: MarketModel, n_paths: int, years: int, price_growth: float,
                    rent_growth: float, rng: np.random.Generator) -> Paths:
    """Quarterly simulation, aggregated to years."""
    k = len(SERIES)
    m = np.array([np.log1p(price_growth) / 4] * len(ZONES) + [np.log1p(rent_growth) / 4])
    chol = np.linalg.cholesky(model.corr + 1e-12 * np.eye(k))
    q = 4 * years
    shocks = rng.standard_normal((n_paths, q, k)) @ chol.T * model.sigma
    dev = np.empty((n_paths, q, k))
    prev = np.broadcast_to(model.start - m, (n_paths, k))
    for t in range(q):
        prev = model.phi * prev + shocks[:, t]
        dev[:, t] = prev
    r = dev + m
    annual = r.reshape(n_paths, years, 4, k).sum(axis=2)
    return Paths(
        zone_log_growth={z: annual[:, :, i] for i, z in enumerate(ZONES)},
        irl_log_growth=annual[:, :, k - 1],
    )
