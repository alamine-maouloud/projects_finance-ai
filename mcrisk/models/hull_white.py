"""One-factor Hull-White short-rate model fitted to today's curve.

    r(t) = x(t) + phi(t),   dx = -a x dt + sigma dW,   x(0) = 0

phi is chosen so that the model reproduces P(0, T) exactly. Bond prices
(Brigo & Mercurio, 2006, section 4.2):

    P(t, T) = P(0,T)/P(0,t) exp{ [V(t,T) - V(0,T) + V(0,t)] / 2 - B(t,T) x(t) }
    B(t, T) = (1 - e^{-a(T-t)}) / a
    V(t, T) = sigma^2/a^2 [T - t + 2/a e^{-a(T-t)} - 1/(2a) e^{-2a(T-t)} - 3/(2a)]

The pair (x(t), int x du) is Gaussian, so it is simulated *exactly* on any
grid; the stochastic discount factor is D(0,t) = P(0,t) exp(-I(t) - V(0,t)/2)
with I(t) = int_0^t x(u) du, which makes E[D(0,t)] = P(0,t) hold exactly.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq
from scipy.special import ndtr

from ..curves import EUR_CURVE, NelsonSiegelSvensson


@dataclass(frozen=True)
class HullWhitePaths:
    times: np.ndarray        # (m + 1,) with times[0] = 0
    x: np.ndarray            # (n, m + 1) state
    discount: np.ndarray     # (n, m + 1) stochastic discount factors D(0, t)


@dataclass(frozen=True)
class HullWhite:
    a: float = 0.03
    sigma: float = 0.009
    curve: NelsonSiegelSvensson = EUR_CURVE

    def b(self, t, T):
        return (1 - np.exp(-self.a * (np.asarray(T) - np.asarray(t)))) / self.a

    def v(self, t, T):
        a, s = self.a, self.sigma
        tau = np.asarray(T) - np.asarray(t)
        return s * s / (a * a) * (tau + 2 / a * np.exp(-a * tau)
                                  - 1 / (2 * a) * np.exp(-2 * a * tau) - 1.5 / a)

    def zcb(self, t: float, T, x):
        """P(t, T) for every path state x (n,) and maturities T (k,) -> (n, k)."""
        T = np.atleast_1d(np.asarray(T, dtype=float))
        x = np.asarray(x, dtype=float)
        lnA = (np.log(self.curve.discount(T) / self.curve.discount(t))
               + 0.5 * (self.v(t, T) - self.v(0, T) + self.v(0, t)))
        return np.exp(lnA[None, :] - self.b(t, T)[None, :] * x[:, None])

    def simulate(self, times, n_paths: int, rng: np.random.Generator | None = None,
                 antithetic: bool = False) -> HullWhitePaths:
        rng = rng or np.random.default_rng()
        a, s = self.a, self.sigma
        t = np.concatenate([[0.0], np.asarray(times, dtype=float)])
        dt = np.diff(t)
        e = np.exp(-a * dt)
        bh = (1 - e) / a
        var_x = s * s / (2 * a) * (1 - e * e)
        var_i = s * s / (a * a) * (dt - 2 * bh + (1 - e * e) / (2 * a))
        cov = s * s / 2 * bh * bh
        # Cholesky of the 2x2 step covariance
        l11 = np.sqrt(var_x)
        l21 = cov / l11
        l22 = np.sqrt(np.maximum(var_i - l21 * l21, 0.0))
        half = (n_paths + 1) // 2 if antithetic else n_paths
        z = rng.standard_normal((half, dt.size, 2))
        if antithetic:
            z = np.concatenate([z, -z])[:n_paths]
        x = np.zeros((n_paths, t.size))
        integ = np.zeros((n_paths, t.size))
        for k in range(dt.size):
            x[:, k + 1] = x[:, k] * e[k] + l11[k] * z[:, k, 0]
            integ[:, k + 1] = integ[:, k] + x[:, k] * bh[k] + l21[k] * z[:, k, 0] + l22[k] * z[:, k, 1]
        disc = self.curve.discount(t)[None, :] * np.exp(-integ - 0.5 * self.v(0, t)[None, :])
        return HullWhitePaths(times=t, x=x, discount=disc)

    # -- analytic European swaption (Jamshidian decomposition) -------------

    def zero_bond_put(self, T0: float, T: float, strike: float) -> float:
        p0, p = self.curve.discount(T0), self.curve.discount(T)
        sp = self.sigma * np.sqrt((1 - np.exp(-2 * self.a * T0)) / (2 * self.a)) * self.b(T0, T)
        h = np.log(p / (p0 * strike)) / sp + sp / 2
        return float(strike * p0 * ndtr(-h + sp) - p * ndtr(-h))

    def payer_swaption(self, T0: float, pay_times, fixed_rate: float, notional: float = 1.0) -> float:
        """Payer swaption = put on the fixed-coupon bond; Jamshidian splits it
        into zero-bond puts struck at P(T0, T_i; x*)."""
        pay_times = np.asarray(pay_times, dtype=float)
        tau = np.diff(np.concatenate([[T0], pay_times]))
        c = fixed_rate * tau
        c[-1] += 1.0
        f = lambda x: float(self.zcb(T0, pay_times, np.array([x]))[0] @ c) - 1.0  # noqa: E731
        xs = brentq(f, -1.0, 1.0)
        k = self.zcb(T0, pay_times, np.array([xs]))[0]
        return notional * sum(ci * self.zero_bond_put(T0, ti, ki) for ci, ti, ki in zip(c, pay_times, k))
