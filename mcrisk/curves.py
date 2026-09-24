"""Zero-coupon yield curves."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class NelsonSiegelSvensson:
    """z(t) = b0 + b1 L1(t/t1) + b2 C(t/t1) + b3 C(t/t2), continuously compounded,
    with L(x) = (1 - e^-x)/x and C(x) = L(x) - e^-x."""

    b0: float = 0.0300
    b1: float = -0.0085
    b2: float = -0.0120
    b3: float = 0.0150
    t1: float = 1.6
    t2: float = 9.0

    def zero(self, t):
        t = np.maximum(np.asarray(t, dtype=float), 1e-10)
        x1, x2 = t / self.t1, t / self.t2
        l1 = (1 - np.exp(-x1)) / x1
        l2 = (1 - np.exp(-x2)) / x2
        return (self.b0 + self.b1 * l1 + self.b2 * (l1 - np.exp(-x1))
                + self.b3 * (l2 - np.exp(-x2)))

    def forward(self, t):
        """Instantaneous forward f(0, t) = d/dt [t z(t)]."""
        t = np.asarray(t, dtype=float)
        x1, x2 = t / self.t1, t / self.t2
        return (self.b0 + self.b1 * np.exp(-x1) + self.b2 * x1 * np.exp(-x1)
                + self.b3 * x2 * np.exp(-x2))

    def discount(self, t):
        t = np.asarray(t, dtype=float)
        return np.exp(-self.zero(t) * t)

    def par_swap_rate(self, start: float, end: float, freq: int = 1) -> float:
        n = int(round((end - start) * freq))
        pay = start + np.arange(1, n + 1) / freq
        annuity = np.sum(self.discount(pay)) / freq
        return float((self.discount(start) - self.discount(end)) / annuity)


EUR_CURVE = NelsonSiegelSvensson()
