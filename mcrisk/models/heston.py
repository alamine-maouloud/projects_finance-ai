"""Heston stochastic volatility: semi-analytic pricing and QE simulation.

    dS = (r - q) S dt + sqrt(v) S dW1
    dv = kappa (theta - v) dt + xi sqrt(v) dW2,   d<W1, W2> = rho dt
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.integrate import quad


@dataclass(frozen=True)
class Heston:
    v0: float
    kappa: float
    theta: float
    xi: float
    rho: float

    @property
    def feller(self) -> float:
        """2 kappa theta / xi^2; below 1 the variance touches zero."""
        return 2 * self.kappa * self.theta / self.xi**2

    def char_fn(self, u, t: float, s0: float, r: float, q: float = 0.0):
        """E[exp(i u log S_T)] in the 'little Heston trap' form of Albrecher
        et al. (2007), which avoids branch-cut discontinuities of the log."""
        k, th, xi, rho, v0 = self.kappa, self.theta, self.xi, self.rho, self.v0
        iu = 1j * u
        b = k - rho * xi * iu
        d = np.sqrt(b * b + xi * xi * (iu + u * u))
        g = (b - d) / (b + d)
        e = np.exp(-d * t)
        c = (r - q) * iu * t + k * th / xi**2 * ((b - d) * t - 2 * np.log((1 - g * e) / (1 - g)))
        dd = (b - d) / xi**2 * (1 - e) / (1 - g * e)
        return np.exp(c + dd * v0 + iu * np.log(s0))

    def call(self, s0: float, k: float, t: float, r: float, q: float = 0.0) -> float:
        """European call by Gil-Pelaez inversion: C = S e^{-qT} P1 - K e^{-rT} P2."""
        lk = np.log(k)
        phi_mi = self.char_fn(-1j, t, s0, r, q)

        def p_integrand(u, j):
            if j == 1:
                f = self.char_fn(u - 1j, t, s0, r, q) / phi_mi
            else:
                f = self.char_fn(u, t, s0, r, q)
            return (np.exp(-1j * u * lk) * f / (1j * u)).real

        p1 = 0.5 + quad(p_integrand, 1e-10, 250, args=(1,), limit=400)[0] / np.pi
        p2 = 0.5 + quad(p_integrand, 1e-10, 250, args=(2,), limit=400)[0] / np.pi
        return float(s0 * np.exp(-q * t) * p1 - k * np.exp(-r * t) * p2)

    def put(self, s0, k, t, r, q=0.0) -> float:
        return self.call(s0, k, t, r, q) - s0 * np.exp(-q * t) + k * np.exp(-r * t)

    def simulate(self, s0: float, t: float, n_steps: int, n_paths: int, r: float,
                 q: float = 0.0, rng: np.random.Generator | None = None,
                 psi_c: float = 1.5) -> tuple[np.ndarray, np.ndarray]:
        """Andersen (2008) Quadratic-Exponential scheme with the martingale-
        corrected log-price step (gamma1 = gamma2 = 1/2).

        Returns (log S paths, v paths), each (n_paths, n_steps + 1).
        """
        rng = rng or np.random.default_rng()
        k, th, xi, rho = self.kappa, self.theta, self.xi, self.rho
        dt = t / n_steps
        ek = np.exp(-k * dt)
        g1 = g2 = 0.5
        k1 = g1 * dt * (k * rho / xi - 0.5) - rho / xi
        k2 = g2 * dt * (k * rho / xi - 0.5) + rho / xi
        k3 = g1 * dt * (1 - rho**2)
        k4 = g2 * dt * (1 - rho**2)
        x = np.empty((n_paths, n_steps + 1))
        v = np.empty((n_paths, n_steps + 1))
        x[:, 0] = np.log(s0)
        v[:, 0] = self.v0
        for i in range(n_steps):
            vt = v[:, i]
            m = th + (vt - th) * ek
            s2 = vt * xi**2 * ek * (1 - ek) / k + th * xi**2 * (1 - ek) ** 2 / (2 * k)
            psi = s2 / (m * m)
            zv = rng.standard_normal(n_paths)
            uv = rng.random(n_paths)
            vn = np.empty(n_paths)
            quad_ = psi <= psi_c
            ip = 1 / psi[quad_]
            b2 = 2 * ip - 1 + np.sqrt(2 * ip) * np.sqrt(2 * ip - 1)
            a = m[quad_] / (1 + b2)
            vn[quad_] = a * (np.sqrt(b2) + zv[quad_]) ** 2
            ex = ~quad_
            p = (psi[ex] - 1) / (psi[ex] + 1)
            beta = (1 - p) / m[ex]
            u = uv[ex]
            vn[ex] = np.where(u <= p, 0.0, np.log((1 - p) / np.maximum(1 - u, 1e-300)) / beta)
            # martingale correction (Andersen, section 4.3.3): the drift term
            # replaces k0 so that E[S_{t+dt} | S_t] = S_t exp((r - q) dt) exactly
            a_ = k2 + 0.5 * k4
            k0_star = np.empty(n_paths)
            if np.any(quad_):
                k0_star[quad_] = (-a_ * b2 * a / (1 - 2 * a_ * a)
                                  + 0.5 * np.log(1 - 2 * a_ * a)
                                  - (k1 + 0.5 * k3) * vt[quad_])
            if np.any(ex):
                k0_star[ex] = (-np.log(p + beta * (1 - p) / (beta - a_))
                               - (k1 + 0.5 * k3) * vt[ex])
            zs = rng.standard_normal(n_paths)
            x[:, i + 1] = (x[:, i] + (r - q) * dt + k0_star + k1 * vt + k2 * vn
                           + np.sqrt(np.maximum(k3 * vt + k4 * vn, 0)) * zs)
            v[:, i + 1] = vn
        return x, v
