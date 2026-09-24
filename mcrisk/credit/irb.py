"""Basel IRB (Asymptotic Single Risk Factor) formulas.

References: BCBS, "An Explanatory Note on the Basel II IRB Risk Weight
Functions" (2005); CRE31 of the consolidated Basel framework.
"""

from __future__ import annotations

import numpy as np
from scipy.special import ndtr, ndtri


def corporate_correlation(pd, sales_meur=None):
    """Supervisory asset correlation R(PD) for corporates, with SME relief."""
    pd = np.asarray(pd, dtype=float)
    f = (1 - np.exp(-50 * pd)) / (1 - np.exp(-50))
    r = 0.12 * f + 0.24 * (1 - f)
    if sales_meur is not None:
        s = np.clip(np.asarray(sales_meur, dtype=float), 5.0, 50.0)
        r = r - 0.04 * (1 - (s - 5.0) / 45.0) * (np.asarray(sales_meur) < 50)
    return r


def maturity_adjustment(pd, maturity):
    b = (0.11852 - 0.05478 * np.log(pd)) ** 2
    return (1 + (np.asarray(maturity) - 2.5) * b) / (1 - 1.5 * b)


def conditional_pd(pd, rsq, z):
    """PD conditional on the systematic factor at level z (worst = negative)."""
    return ndtr((ndtri(pd) - np.sqrt(rsq) * z) / np.sqrt(1 - rsq))


def capital_requirement(pd, lgd, rsq=None, maturity=None, alpha=0.999):
    """IRB capital K per unit of EAD: unexpected loss at the ASRF quantile."""
    pd = np.asarray(pd, dtype=float)
    rsq = corporate_correlation(pd) if rsq is None else np.asarray(rsq)
    k = np.asarray(lgd) * (conditional_pd(pd, rsq, -ndtri(alpha)) - pd)
    if maturity is not None:
        k = k * maturity_adjustment(pd, maturity)
    return k


def portfolio_irb(portfolio, alpha: float = 0.999, with_maturity: bool = False) -> dict:
    """IRB capital of a CreditPortfolio (portfolio-invariant by construction)."""
    p = portfolio
    k = capital_requirement(p.pd, p.lgd, p.rsq,
                            p.maturity if with_maturity else None, alpha)
    capital = float(np.sum(k * p.ead))
    return {
        "capital": capital,
        "rwa": 12.5 * capital,
        "expected_loss": p.expected_loss,
        "asrf_var": capital + p.expected_loss,
        "k": k,
    }
