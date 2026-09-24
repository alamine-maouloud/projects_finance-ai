"""Cash flow building blocks: loan, French rental taxation, capital gains, IRR.

Everything is vectorised over simulated paths: arrays have shape (..., H) with
one column per year of ownership.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import Tax


# ------------------------------------------------------------------ loan

@dataclass
class LoanSchedule:
    payment_month: float
    interest: np.ndarray  # (years,) interest paid each year
    principal: np.ndarray  # (years,) capital repaid each year
    balance_end: np.ndarray  # (years,) outstanding capital at the end of each year


def amortizing_loan(amount: float, rate: float, years: int) -> LoanSchedule:
    """Fixed-rate loan with constant monthly payments (French annuity loan)."""
    n = 12 * years
    i = rate / 12
    pay = amount * i / (1 - (1 + i) ** -n) if i > 0 else amount / n
    k = np.arange(1, n + 1)
    bal_before = amount * (1 + i) ** (k - 1) - pay * ((1 + i) ** (k - 1) - 1) / i if i > 0 else amount - pay * (k - 1)
    interest_m = bal_before * i
    principal_m = pay - interest_m
    balance_end = np.maximum(bal_before - principal_m, 0.0)
    return LoanSchedule(
        payment_month=float(pay),
        interest=interest_m.reshape(years, 12).sum(axis=1),
        principal=principal_m.reshape(years, 12).sum(axis=1),
        balance_end=balance_end.reshape(years, 12)[:, -1],
    )


def early_repayment_penalty(balance: float, rate: float) -> float:
    """French cap: the lower of six months of interest and 3% of the capital repaid."""
    return float(min(0.03 * balance, 0.5 * rate * balance))


# ------------------------------------------------------------------ capital gains

def gains_allowances(years_held: int) -> tuple[float, float]:
    """Holding period allowances on a private capital gain (income tax, social charges).

    Income tax: 6% a year from year 6 to 21, 4% in year 22, so exempt after 22
    years. Social charges: 1.65% a year from year 6 to 21, 1.60% in year 22,
    9% a year from year 23 to 30, so exempt after 30 years.
    """
    n = int(years_held)
    ir = 0.06 * min(max(n - 5, 0), 16) + (0.04 if n >= 22 else 0.0)
    ps = 0.0165 * min(max(n - 5, 0), 16) + (0.016 if n >= 22 else 0.0) + 0.09 * min(max(n - 22, 0), 8)
    return min(ir, 1.0), min(ps, 1.0)


def capital_gains_tax(sale_net: np.ndarray, price: np.ndarray, fees_paid: np.ndarray, years_held: int,
                      tax: Tax, depreciation_taken: np.ndarray | float = 0.0) -> np.ndarray:
    """Tax on the gain of a private (non professional) seller.

    The acquisition price is raised by the purchase costs (actual or 7.5% flat
    rate) and, after five years, by a 15% flat rate for works. For furnished
    lets, the depreciation deducted is taken back out of the basis (2025 finance
    law).
    """
    basis = price + np.maximum(fees_paid, tax.sale_forfait_fees * price)
    if years_held > 5:
        basis = basis + tax.sale_forfait_works * price
    basis = basis - depreciation_taken
    gain = np.maximum(sale_net - basis, 0.0)
    a_ir, a_ps = gains_allowances(years_held)
    return gain * (tax.capital_gains_rate * (1 - a_ir) + tax.social_rate * (1 - a_ps))


# ------------------------------------------------------------------ income tax

def _use_carryforward(taxable: np.ndarray, stock: np.ndarray) -> np.ndarray:
    """Offset a positive result with loss vintages, oldest first. Mutates stock."""
    remaining = taxable.copy()
    for v in range(stock.shape[-1]):
        use = np.minimum(remaining, stock[..., v])
        stock[..., v] -= use
        remaining -= use
    return remaining


def _age_vintages(stock: np.ndarray, new: np.ndarray) -> np.ndarray:
    """Drop the oldest vintage (expired) and add this year's losses as the newest."""
    return np.concatenate([stock[..., 1:], new[..., None]], axis=-1)


def rental_income_tax(rents: np.ndarray, expenses: np.ndarray, interest: np.ndarray, tax: Tax,
                      depreciation: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Yearly tax on the rental income, negative when a loss saves tax elsewhere.

    rents, expenses, interest: (..., H); interest includes borrower insurance and
    loan fees. Returns (tax, depreciation_used), both (..., H).

    * micro_foncier: 30% flat allowance, tax on 70% of the rents.
    * reel (unfurnished, actual expenses): a loss created by expenses other than
      interest offsets other income up to 10,700 EUR a year, at the marginal
      rate only; the rest, and any loss due to interest, is carried forward ten
      years against future rental income.
    * lmnp (furnished, actual expenses): losses are carried forward ten years
      against furnished rental income only; depreciation of the building,
      purchase costs and furniture is deducted first, can cut the result to
      zero but not create a loss, and what is unused is carried forward
      without limit.
    """
    rate_all = tax.marginal_rate + tax.social_rate
    H = rents.shape[-1]
    out = np.zeros_like(rents)
    dep_used = np.zeros_like(rents)

    if tax.regime == "micro_foncier":
        return rate_all * (1 - tax.micro_foncier_allowance) * rents, dep_used

    shape = rents.shape[:-1]
    stock = np.zeros(shape + (tax.carryforward_years,))
    if tax.regime == "reel":
        for t in range(H):
            other = expenses[..., t]
            after_interest = rents[..., t] - interest[..., t]
            result = after_interest - other
            positive = result > 0
            taxable = _use_carryforward(np.where(positive, result, 0.0), stock)
            # losses: the part due to non interest expenses offsets other income up to the cap
            loss_from_other = np.where(after_interest >= 0, np.maximum(-result, 0.0), other)
            loss_interest = np.where(after_interest < 0, -after_interest, 0.0)
            to_income = np.where(positive, 0.0, np.minimum(loss_from_other, tax.deficit_cap))
            carried = np.where(positive, 0.0, loss_from_other - to_income + loss_interest)
            stock = _age_vintages(stock, carried)
            out[..., t] = rate_all * taxable - tax.marginal_rate * to_income
        return out, dep_used

    if tax.regime == "lmnp":
        ard = np.zeros(shape)  # unused depreciation, carried forward without limit
        dep = np.zeros_like(rents) if depreciation is None else depreciation
        for t in range(H):
            result = rents[..., t] - expenses[..., t] - interest[..., t]
            available = ard + dep[..., t]
            used = np.clip(result, 0.0, None)
            used = np.minimum(used, available)
            ard = available - used
            dep_used[..., t] = used
            taxable = _use_carryforward(np.maximum(result - used, 0.0), stock)
            stock = _age_vintages(stock, np.maximum(-result, 0.0))
            out[..., t] = rate_all * taxable
        return out, dep_used

    raise ValueError(f"unknown tax regime {tax.regime!r}")


# ------------------------------------------------------------------ IRR

def npv(cash: np.ndarray, rate: float | np.ndarray) -> np.ndarray:
    t = np.arange(cash.shape[-1])
    r = np.asarray(rate)[..., None] if np.ndim(rate) else rate
    return np.sum(cash / (1.0 + r) ** t, axis=-1)


def irr(cash: np.ndarray, lo: float = -0.99, hi: float = 3.0, iters: int = 80) -> np.ndarray:
    """Internal rate of return of each row of cash (..., T+1), by bisection.

    An investor's flows are an outlay, some years of saving effort or income
    and a sale at the end; NPV is then decreasing in the rate on the bracket,
    so bisection finds the root. Rows without a sign change get NaN.
    """
    cash = np.asarray(cash, float)
    f_lo, f_hi = npv(cash, lo), npv(cash, hi)
    ok = np.sign(f_lo) != np.sign(f_hi)
    a = np.full(cash.shape[:-1], lo)
    b = np.full(cash.shape[:-1], hi)
    fa = f_lo
    for _ in range(iters):
        mid = 0.5 * (a + b)
        fm = npv(cash, mid)
        left = np.sign(fm) == np.sign(fa)
        a = np.where(left, mid, a)
        fa = np.where(left, fm, fa)
        b = np.where(left, b, mid)
    return np.where(ok, 0.5 * (a + b), np.nan)
