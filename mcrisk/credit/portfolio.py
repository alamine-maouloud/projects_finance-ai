"""Credit portfolio description and a realistic synthetic corporate book."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

import numpy as np

from .irb import corporate_correlation

RATINGS = ("AAA", "AA", "A", "BBB", "BB", "B", "CCC")
# One-year PDs, long-run averages floored at the Basel III 5 bp corporate floor.
RATING_PD = np.array([0.0005, 0.0005, 0.0008, 0.0022, 0.0085, 0.0380, 0.2400])
RATING_MIX = np.array([0.02, 0.06, 0.18, 0.34, 0.24, 0.13, 0.03])

SECTORS = (
    "Energy", "Materials", "Industrials", "Consumer Disc.", "Consumer Staples",
    "Health Care", "Financials", "Technology", "Communication", "Utilities",
    "Real Estate",
)
REGIONS = ("Europe", "North America", "Asia-Pacific", "Emerging Markets")

SENIORITY = ("Secured", "Senior unsecured", "Subordinated")
SENIORITY_LGD = np.array([0.25, 0.45, 0.75])
SENIORITY_MIX = np.array([0.30, 0.60, 0.10])


@dataclass
class CreditPortfolio:
    """A book of obligors driven by a set of correlated systematic factors.

    Each obligor i has latent asset return

        X_i = sqrt(R_i) * (w_i . F) / sd(w_i . F) + sqrt(1 - R_i) * eps_i

    where F ~ N(0, factor_corr) are the systematic factors, w_i the obligor's
    factor weights and R_i its asset correlation. Default <=> X_i < q(PD_i).
    """

    ead: np.ndarray
    pd: np.ndarray
    lgd: np.ndarray
    rsq: np.ndarray
    factor_weights: np.ndarray            # (N, K) weights on correlated factors
    factor_corr: np.ndarray               # (K, K)
    factor_names: tuple[str, ...]
    sector: np.ndarray                    # (N,) int, reporting only
    sector_names: tuple[str, ...] = SECTORS
    region: np.ndarray | None = None
    rating: np.ndarray | None = None
    maturity: np.ndarray | None = None
    names: list[str] = field(default_factory=list)

    def __post_init__(self):
        n = self.ead.size
        for a in ("pd", "lgd", "rsq", "sector"):
            if getattr(self, a).shape != (n,):
                raise ValueError(f"{a} must have shape ({n},)")
        if self.factor_weights.shape != (n, self.factor_corr.shape[0]):
            raise ValueError("factor_weights must be (N, K)")
        if np.any((self.pd <= 0) | (self.pd >= 1)):
            raise ValueError("PD must lie in (0, 1)")
        if np.any((self.rsq < 0) | (self.rsq >= 1)):
            raise ValueError("asset correlation must lie in [0, 1)")
        if np.linalg.eigvalsh(self.factor_corr).min() < -1e-10:
            raise ValueError("factor correlation matrix is not PSD")
        if not self.names:
            self.names = [f"OBL-{i + 1:05d}" for i in range(n)]

    @property
    def n(self) -> int:
        return self.ead.size

    @property
    def n_factors(self) -> int:
        return self.factor_corr.shape[0]

    @property
    def total_exposure(self) -> float:
        return float(self.ead.sum())

    @property
    def expected_loss(self) -> float:
        return float(np.sum(self.ead * self.pd * self.lgd))

    def loadings(self) -> np.ndarray:
        """(N, K) loadings b_i on the correlated factors: Y_i = b_i . F."""
        w = self.factor_weights
        var = np.einsum("ik,kl,il->i", w, self.factor_corr, w)
        return w * (np.sqrt(self.rsq / var))[:, None]

    def hhi(self) -> float:
        """Herfindahl index of exposures (1/HHI = effective number of names)."""
        s = self.ead / self.ead.sum()
        return float(np.sum(s * s))

    def with_pd(self, pd: np.ndarray) -> "CreditPortfolio":
        return replace(self, pd=np.clip(pd, 1e-8, 0.999), names=list(self.names))

    def subset(self, mask: np.ndarray) -> "CreditPortfolio":
        opt = lambda a: None if a is None else a[mask]  # noqa: E731
        return replace(
            self, ead=self.ead[mask], pd=self.pd[mask], lgd=self.lgd[mask],
            rsq=self.rsq[mask], factor_weights=self.factor_weights[mask],
            sector=self.sector[mask], region=opt(self.region),
            rating=opt(self.rating), maturity=opt(self.maturity),
            names=[nm for nm, k in zip(self.names, mask) if k],
        )


def _nearest_correlation(c: np.ndarray) -> np.ndarray:
    w, v = np.linalg.eigh((c + c.T) / 2)
    c = (v * np.maximum(w, 1e-6)) @ v.T
    d = np.sqrt(np.diag(c))
    return c / np.outer(d, d)


def default_factor_correlation() -> tuple[np.ndarray, tuple[str, ...]]:
    """Sector + region factors correlated through a global business cycle.

    corr(k, l) = sqrt(g_k g_l) + bumps for economically linked sectors, then
    projected to the nearest valid correlation matrix.
    """
    g_sector = np.array([0.55, 0.60, 0.65, 0.60, 0.40, 0.35, 0.70, 0.55, 0.50, 0.35, 0.55])
    g_region = np.array([0.70, 0.70, 0.60, 0.50])
    g = np.concatenate([g_sector, g_region])
    c = np.sqrt(np.outer(g, g))
    idx = {s: i for i, s in enumerate(SECTORS)}
    for a, b, bump in [
        ("Energy", "Materials", 0.15), ("Financials", "Real Estate", 0.15),
        ("Technology", "Communication", 0.15), ("Industrials", "Materials", 0.10),
        ("Consumer Disc.", "Industrials", 0.08),
    ]:
        c[idx[a], idx[b]] += bump
        c[idx[b], idx[a]] += bump
    np.fill_diagonal(c, 1.0)
    return _nearest_correlation(np.clip(c, -0.99, 0.99)), SECTORS + REGIONS


def synthetic_portfolio(n: int = 2_000, seed: int = 7, sector_weight: float = 0.75) -> CreditPortfolio:
    """A realistic large-corporate book (EUR).

    * ratings skewed to investment grade, PDs from a long-run rating table
    * lognormal exposures with a fat right tail (single-name concentration)
    * LGD by seniority; Basel IRB asset correlation R(PD)
    * each obligor loads on its sector factor and its region factor
    """
    rng = np.random.default_rng(seed)
    corr, fnames = default_factor_correlation()
    n_sec, n_reg = len(SECTORS), len(REGIONS)
    sector_mix = np.array([0.08, 0.07, 0.14, 0.10, 0.08, 0.07, 0.15, 0.10, 0.07, 0.06, 0.08])
    region_mix = np.array([0.45, 0.25, 0.18, 0.12])
    sector = rng.choice(n_sec, size=n, p=sector_mix / sector_mix.sum())
    region = rng.choice(n_reg, size=n, p=region_mix)
    rating = rng.choice(len(RATINGS), size=n, p=RATING_MIX)
    # PD jitter within the grade so that obligors are not all identical
    pd = RATING_PD[rating] * np.exp(rng.normal(0.0, 0.25, size=n))
    pd = np.clip(pd, 0.0005, 0.35)
    seniority = rng.choice(3, size=n, p=SENIORITY_MIX)
    lgd = np.clip(SENIORITY_LGD[seniority] + rng.normal(0, 0.05, n), 0.05, 0.95)
    ead = np.exp(rng.normal(np.log(12e6), 1.1, size=n))
    ead *= np.where(rating <= 2, 1.8, 1.0)          # IG names get larger limits
    ead = np.minimum(ead, 1.2e9)
    rsq = corporate_correlation(pd)
    w = np.zeros((n, n_sec + n_reg))
    w[np.arange(n), sector] = np.sqrt(sector_weight)
    w[np.arange(n), n_sec + region] = np.sqrt(1 - sector_weight)
    maturity = rng.uniform(1.0, 5.0, size=n)
    return CreditPortfolio(
        ead=ead, pd=pd, lgd=lgd, rsq=rsq, factor_weights=w, factor_corr=corr,
        factor_names=fnames, sector=sector, region=region, rating=rating,
        maturity=maturity,
    )


def homogeneous_portfolio(n: int, pd: float, rho: float, lgd: float = 1.0,
                          ead: float = 1.0) -> CreditPortfolio:
    """Single-factor homogeneous pool (benchmark with an exact solution)."""
    return CreditPortfolio(
        ead=np.full(n, ead), pd=np.full(n, pd), lgd=np.full(n, lgd),
        rsq=np.full(n, rho), factor_weights=np.ones((n, 1)),
        factor_corr=np.ones((1, 1)), factor_names=("Global",),
        sector=np.zeros(n, dtype=int), sector_names=("All",),
    )
