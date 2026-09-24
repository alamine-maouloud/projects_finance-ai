"""Exposure profiles, netting and collateral (CSA with margin period of risk).

EE(t)    = E[max(V(t), 0)]                    expected exposure
ENE(t)   = E[min(V(t), 0)]                    expected negative exposure
PFE_q(t) = q-quantile of max(V(t), 0)         potential future exposure
EEE(t)   = max_{s <= t} EE(s)                 effective EE (non-decreasing)
EEPE     = time average of EEE over year one  Basel IMM, EAD = 1.4 * EEPE
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CSA:
    """Variation-margin agreement. Collateral at t reflects the portfolio value
    at t - MPoR (the last successful margin call before the close-out)."""

    threshold_cpty: float = 0.0      # counterparty posts above this
    threshold_own: float = 0.0       # we post above this
    mta: float = 0.0                 # minimum transfer amount
    initial_margin: float = 0.0      # held by us, reduces exposure
    mpor: float = 10 / 252


def collateral(v: np.ndarray, times: np.ndarray, csa: CSA) -> np.ndarray:
    """Collateral balance C(t) per path (positive = held by us).

    The MTA is folded into the thresholds (standard conservative proxy)."""
    # the balance today already reflects today's mark-to-market, so dates
    # within one MPoR of today use V(0)
    lag_t = times - csa.mpor
    idx = np.clip(np.searchsorted(times, lag_t + 1e-12, side="right") - 1, 0, None)
    v_lag = v[:, idx]
    held = np.maximum(v_lag - csa.threshold_cpty - csa.mta, 0.0)
    posted = np.maximum(-v_lag - csa.threshold_own - csa.mta, 0.0)
    return held - posted


def exposure_paths(v: np.ndarray, times: np.ndarray, csa: CSA | None = None) -> np.ndarray:
    """Positive exposure per path after collateral and initial margin."""
    if csa is None:
        return np.maximum(v, 0.0)
    c = collateral(v, times, csa)
    return np.maximum(v - c - csa.initial_margin, 0.0)


def negative_exposure_paths(v, times, csa: CSA | None = None) -> np.ndarray:
    if csa is None:
        return np.minimum(v, 0.0)
    c = collateral(v, times, csa)
    return np.minimum(v - c + csa.initial_margin, 0.0)


@dataclass
class ExposureProfile:
    times: np.ndarray
    ee: np.ndarray
    ene: np.ndarray
    pfe: np.ndarray
    eee: np.ndarray
    epe: float
    eepe: float
    pfe_quantile: float
    peak_pfe: float

    @property
    def ead_imm(self) -> float:
        return 1.4 * self.eepe


def _time_average(values, times, horizon=1.0):
    """Average of a step function over [0, horizon] (value at t_k on (t_{k-1}, t_k])."""
    t = np.minimum(times, horizon)
    dt = np.diff(t)
    return float(np.sum(values[1:] * dt) / horizon)


def profile(v: np.ndarray, times: np.ndarray, csa: CSA | None = None,
            q: float = 0.975) -> ExposureProfile:
    e = exposure_paths(v, times, csa)
    ne = negative_exposure_paths(v, times, csa)
    ee = e.mean(axis=0)
    pfe = np.quantile(e, q, axis=0)
    eee = np.maximum.accumulate(ee)
    horizon = min(1.0, times[-1])
    return ExposureProfile(
        times=times, ee=ee, ene=ne.mean(axis=0), pfe=pfe, eee=eee,
        epe=_time_average(ee, times, horizon), eepe=_time_average(eee, times, horizon),
        pfe_quantile=q, peak_pfe=float(pfe.max()),
    )


def netting_benefit(values: np.ndarray, times: np.ndarray) -> dict:
    """Compare the netted EE with the sum of stand-alone trade EEs."""
    net_ee = np.maximum(values.sum(axis=2), 0).mean(axis=0)
    gross_ee = np.maximum(values, 0).mean(axis=0).sum(axis=1)
    h = min(1.0, times[-1])
    return {"net_epe": _time_average(net_ee, times, h),
            "gross_epe": _time_average(gross_ee, times, h),
            "net_ee": net_ee, "gross_ee": gross_ee}


def trade_ee_contributions(values: np.ndarray) -> np.ndarray:
    """Euler allocation of the netted EE: E[V_i 1{V_net > 0}] (sums to EE)."""
    pos = values.sum(axis=2) > 0
    return (values * pos[:, :, None]).mean(axis=0)
