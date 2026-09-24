import numpy as np
import pytest

from immorisk import finance
from immorisk.config import Tax


def test_loan_matches_annuity_formula_and_amortises_fully():
    s = finance.amortizing_loan(200_000, 0.036, 20)
    i = 0.036 / 12
    assert s.payment_month == pytest.approx(200_000 * i / (1 - (1 + i) ** -240))
    assert s.principal.sum() == pytest.approx(200_000)
    assert s.balance_end[-1] == pytest.approx(0.0, abs=1e-6)
    assert np.allclose(s.interest + s.principal, 12 * s.payment_month)
    assert np.all(np.diff(s.interest) < 0)  # interest falls as capital is repaid


def test_early_repayment_penalty_is_the_lower_cap():
    assert finance.early_repayment_penalty(100_000, 0.032) == pytest.approx(1_600)  # six months of interest
    assert finance.early_repayment_penalty(100_000, 0.08) == pytest.approx(3_000)  # 3% of capital


@pytest.mark.parametrize("years, ir, ps", [
    (5, 0.0, 0.0), (6, 0.06, 0.0165), (15, 0.60, 0.165), (21, 0.96, 0.264),
    (22, 1.0, 0.28), (25, 1.0, 0.55), (30, 1.0, 1.0),
])
def test_capital_gains_allowances(years, ir, ps):
    a_ir, a_ps = finance.gains_allowances(years)
    assert a_ir == pytest.approx(ir)
    assert a_ps == pytest.approx(ps)


def test_capital_gains_tax_uses_flat_rates_and_depreciation_recapture():
    tax = Tax()
    price = np.array([100_000.0])
    fees = np.array([8_000.0])
    # basis after 15 years: 100k + 8k fees + 15k works = 123k
    assert finance.capital_gains_tax(np.array([120_000.0]), price, fees, 15, tax)[0] == 0.0
    t = finance.capital_gains_tax(np.array([153_000.0]), price, fees, 15, tax)[0]
    assert t == pytest.approx(30_000 * (0.19 * 0.40 + 0.172 * 0.835))
    with_recapture = finance.capital_gains_tax(np.array([153_000.0]), price, fees, 15, tax, depreciation_taken=20_000.0)[0]
    assert with_recapture == pytest.approx(50_000 * (0.19 * 0.40 + 0.172 * 0.835))


def test_irr_known_values_and_vectorisation():
    cash = np.array([[-100.0, 110.0, 0.0], [-100.0, 0.0, 121.0], [-100.0, 50.0, 60.0]])
    r = finance.irr(cash)
    assert r[0] == pytest.approx(0.10, abs=1e-9)
    assert r[1] == pytest.approx(0.10, abs=1e-9)
    assert finance.npv(cash[2:], r[2])[0] == pytest.approx(0.0, abs=1e-8)
    assert np.isnan(finance.irr(np.array([[-100.0, -5.0, -5.0]]))[0])


def test_micro_foncier_taxes_seventy_percent_of_rents():
    tax = Tax(regime="micro_foncier", marginal_rate=0.30, social_rate=0.172)
    rents = np.full((1, 3), 10_000.0)
    out, _ = finance.rental_income_tax(rents, np.zeros_like(rents), np.zeros_like(rents), tax)
    assert np.allclose(out, 0.7 * 10_000 * 0.472)


def test_reel_deficit_rules():
    tax = Tax(regime="reel", marginal_rate=0.30, social_rate=0.172)
    # year 1: rents 8k, interest 5k, other expenses 20k -> loss 17k from expenses
    # 10.7k offsets other income (saving 30% of it), 6.3k carried forward
    # year 2: rents 20k, interest 5k, expenses 2k -> profit 13k, minus 6.3k carried = 6.7k taxable
    rents = np.array([[8_000.0, 20_000.0]])
    expenses = np.array([[20_000.0, 2_000.0]])
    interest = np.array([[5_000.0, 5_000.0]])
    out, _ = finance.rental_income_tax(rents, expenses, interest, tax)
    assert out[0, 0] == pytest.approx(-0.30 * 10_700)
    assert out[0, 1] == pytest.approx(0.472 * (13_000 - 6_300))


def test_reel_interest_losses_only_carry_forward():
    tax = Tax(regime="reel")
    # interest above rents: the interest part cannot offset other income
    rents = np.array([[4_000.0, 20_000.0]])
    expenses = np.array([[1_000.0, 0.0]])
    interest = np.array([[6_000.0, 0.0]])
    out, _ = finance.rental_income_tax(rents, expenses, interest, tax)
    assert out[0, 0] == pytest.approx(-tax.marginal_rate * 1_000)  # only the non interest expenses
    assert out[0, 1] == pytest.approx((tax.marginal_rate + tax.social_rate) * (20_000 - 2_000))


def test_reel_losses_expire_after_ten_years():
    tax = Tax(regime="reel", carryforward_years=10)
    H = 12
    rents = np.zeros((1, H))
    interest = np.zeros((1, H))
    interest[0, 0] = 5_000.0  # a pure interest loss, carried forward only
    rents[0, 11] = 5_000.0  # income arrives in year 12, too late
    out, _ = finance.rental_income_tax(rents, np.zeros((1, H)), interest, tax)
    assert out[0, 11] == pytest.approx((tax.marginal_rate + tax.social_rate) * 5_000)
    rents2 = np.zeros((1, H))
    rents2[0, 10] = 5_000.0  # year 11 is the tenth year after the loss: still usable
    out2, _ = finance.rental_income_tax(rents2, np.zeros((1, H)), interest, tax)
    assert out2[0, 10] == pytest.approx(0.0)


def test_lmnp_depreciation_cannot_create_a_loss_and_carries_forward():
    tax = Tax(regime="lmnp")
    rents = np.array([[10_000.0, 10_000.0, 10_000.0]])
    expenses = np.array([[4_000.0, 4_000.0, 4_000.0]])
    interest = np.zeros_like(rents)
    dep = np.array([[9_000.0, 0.0, 0.0]])  # 6k usable in year 1, 3k deferred to year 2
    out, used = finance.rental_income_tax(rents, expenses, interest, tax, dep)
    assert used[0].tolist() == pytest.approx([6_000.0, 3_000.0, 0.0])
    assert out[0].tolist() == pytest.approx([0.0, 0.472 * 3_000, 0.472 * 6_000])
    assert np.all(out >= 0)
