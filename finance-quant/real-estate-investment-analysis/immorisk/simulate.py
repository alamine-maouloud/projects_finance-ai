"""Monte Carlo of a leveraged buy-to-let in every commune.

For each commune and each path we draw

* the true current price level, from the Fay-Herriot posterior (estimation risk),
* the rent this particular flat achieves, from the rent map's prediction
  interval (a flat is not the commune average),
* market paths: zone prices and the IRL (shared by all communes: common random
  numbers, so differences between communes are not simulation noise), plus
  department and commune random walks,
* tenant turnover and the months empty between tenants,

then build 15 years of after-tax cash flows of the investor's equity (loan,
charges, property tax, management, upkeep, income tax under the chosen regime)
and the sale at the end (early repayment penalty, capital gains tax). The IRR
of each path gives a distribution per commune.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import finance
from .config import Assumptions
from .market import MarketModel, Paths, simulate_market


def _key(text: str) -> int:
    return zlib.crc32(text.encode())


@dataclass
class Draws:
    """Random inputs for C communes x P paths x H years."""

    price_z: np.ndarray  # (C, P) standard normal, estimation error of the price level
    rent_z: np.ndarray  # (C, P) standard normal, this flat's rent against the commune estimate
    local_log_growth: np.ndarray  # (C, P, H) department + commune random walks (annual increments)
    relets: np.ndarray  # (C, P, H) number of lettings each year
    vacant_months: np.ndarray  # (C, P, H)
    energy: np.ndarray  # (C, P, 4) weights of the flat's rating: D or better, E, F, G (one-hot on random paths)


def draw_local(rows: pd.DataFrame, a: Assumptions, model: MarketModel, n_paths: int, years: int, zero: bool = False) -> Draws:
    """Commune specific randomness, seeded by the commune code so a commune gets
    the same draws whatever batch it is simulated in."""
    C = len(rows)
    seed = a.market.seed
    tenancy = a.operating.tenancy_months_furnished if a.tax.regime == "lmnp" else a.operating.tenancy_months_unfurnished
    price_z = np.zeros((C, n_paths))
    rent_z = np.zeros((C, n_paths))
    local = np.zeros((C, n_paths, years))
    relets = np.zeros((C, n_paths, years))
    vacant = np.zeros((C, n_paths, years))
    mix = energy_shares(rows)  # (C, 4)
    energy = np.zeros((C, n_paths, 4))
    dep_cache: dict[str, np.ndarray] = {}
    for i, (commune, dep, months) in enumerate(zip(rows["commune"], rows["dep"], rows["vacancy_months"])):
        if zero:
            # expected case: no shocks, expected number of lettings and vacancy, average rating mix
            relets[i] = 12.0 / tenancy
            relets[i, :, 0] += 1.0
            vacant[i] = np.minimum(relets[i] * months, 12.0)
            energy[i] = mix[i]
            continue
        if dep not in dep_cache:
            rd = np.random.default_rng([seed, 1, _key(dep)])
            dep_cache[dep] = model.dep_sd * rd.standard_normal((n_paths, years))
        rng = np.random.default_rng([seed, 2, _key(commune)])
        price_z[i] = rng.standard_normal(n_paths)
        rent_z[i] = rng.standard_normal(n_paths)
        local[i] = dep_cache[dep] + model.commune_sd * rng.standard_normal((n_paths, years))
        k = rng.poisson(12.0 / tenancy, (n_paths, years)).astype(float)
        k[:, 0] += 1.0  # first letting after purchase
        relets[i] = k
        vacant[i] = np.minimum(rng.gamma(np.maximum(k, 1e-12), months) * (k > 0), 12.0)
        label = np.searchsorted(np.cumsum(mix[i]), rng.random(n_paths), side="right").clip(0, 3)
        energy[i, np.arange(n_paths), label] = 1.0
    return Draws(price_z, rent_z, local, relets, vacant, energy)


def energy_shares(rows: pd.DataFrame) -> np.ndarray:
    """(C, 4) probabilities that the flat is rated D or better, E, F, G."""
    efg = rows[["share_E", "share_F", "share_G"]].to_numpy(float) if "share_E" in rows else np.zeros((len(rows), 3))
    return np.column_stack([1.0 - efg.sum(axis=1), efg])


@dataclass
class CashFlows:
    cash: np.ndarray  # (C, P, H+1) equity cash flows, year 0 is the outlay
    price0: np.ndarray  # (C, P) purchase price
    equity0: np.ndarray  # (C, P) cash put in at year 0
    rent_year1: np.ndarray  # (C, P) rent collected in year 1
    sale_net: np.ndarray  # (C, P) sale price after selling costs
    tax_income: np.ndarray  # (C, P, H)
    tax_gain: np.ndarray  # (C, P)
    detail: dict  # (C, P, H) components for reporting


def cash_flows(rows: pd.DataFrame, a: Assumptions, paths: Paths, draws: Draws) -> CashFlows:
    """After-tax equity cash flows of the investor, vectorised over communes and paths."""
    H = a.market.horizon_years
    S = a.property.surface_m2
    fin, op, tx = a.financing, a.operating, a.tax
    if tx.regime == "best":
        raise ValueError("resolve the regime first (best_regime), cash flows need a concrete one")
    furnished = tx.regime == "lmnp"
    C, P = draws.price_z.shape

    # energy rating: the commune level averages flats of every rating; a poorly
    # rated flat costs less, needs works before its rental ban, then is worth a D
    tr = a.transition
    w = draws.energy if tr.enabled else np.concatenate([np.ones(draws.energy.shape[:-1] + (1,)), np.zeros(draws.energy.shape[:-1] + (3,))], axis=-1)
    gap = np.array([0.0, tr.discount_e, tr.discount_f, tr.discount_g])
    mean_gap = energy_shares(rows) @ gap if tr.enabled else np.zeros(C)
    works_year = np.array([H + 1] + [max(y - tr.purchase_year, 0) for y in (tr.ban_year_e, tr.ban_year_f, tr.ban_year_g)])
    works_cost = np.array([0.0, tr.works_m2_e, tr.works_m2_f, tr.works_m2_g]) * S

    # purchase price: posterior draw of the commune level for the reference flat
    level = rows["eblup"].to_numpy()[:, None] + rows["price_sd_log"].to_numpy()[:, None] * draws.price_z
    value_d = np.exp(level) * S / (1.0 + mean_gap)[:, None]  # the same flat rated D or better
    price0 = value_d * (1.0 + w @ gap)

    # rent: advertised rent includes charges; recoverable charges go to the tenant
    rent_cc = rows["rent_m2"].to_numpy()[:, None] * np.exp(rows["rent_sd_log"].to_numpy()[:, None] * draws.rent_z)
    rent_month = np.maximum(rent_cc - op.recoverable_charges_m2_month, 0.0) * S
    if furnished:
        rent_month = rent_month * (1 + a.property.furnished_rent_premium)
    typical_rent_month = np.maximum(rows["rent_m2"].to_numpy() - op.recoverable_charges_m2_month, 0.0)[:, None] * S

    # indexation: rents in place follow the IRL, revised every year; costs follow it too
    irl = np.concatenate([np.zeros((P, 1)), np.cumsum(paths.irl_log_growth, axis=1)[:, :-1]], axis=1)
    idx = np.exp(irl)[None, :, :]  # (1, P, H), 1 in year 1
    vacant_months = draws.vacant_months.copy()
    vacant_months[:, :, 0] = np.minimum(vacant_months[:, :, 0] + w[..., 3] * tr.works_months_g, 12.0)
    occupied = 1.0 - vacant_months / 12.0
    rents = rent_month[:, :, None] * 12.0 * idx * occupied

    # works before each ban, paid in the ban year (G: at purchase), in money of that year
    works = np.zeros((C, P, H + 1))
    for k in (1, 2, 3):
        y = works_year[k]
        if y <= H:
            infl = idx[0, :, y - 1] if y >= 1 else 1.0
            works[:, :, y] += w[..., k] * works_cost[k] * infl

    owner_charges = op.owner_charges_m2_year * S * idx
    property_tax = op.property_tax_months * typical_rent_month[:, :, None] * idx
    insurance = op.landlord_insurance * idx
    management = op.management_fee * rents
    upkeep = op.capex_m2_year * S * idx
    reletting = op.reletting_cost_m2 * S * idx * draws.relets
    lmnp_costs = np.zeros_like(rents)
    if furnished:
        lmnp_costs = (tx.lmnp_accounting + tx.lmnp_cfe * (rents >= tx.cfe_exemption)) * idx
    expenses = owner_charges + property_tax + insurance + management + upkeep + reletting + lmnp_costs
    expenses = np.broadcast_to(expenses, rents.shape)

    # financing: the loan scales with the price, so one schedule per unit borrowed
    loan = price0 * (1 - fin.down_payment_share)
    unit = finance.amortizing_loan(1.0, fin.rate, fin.years)
    yrs = np.arange(H)
    in_loan = yrs < fin.years
    interest = np.where(in_loan, unit.interest[np.minimum(yrs, fin.years - 1)], 0.0)
    principal = np.where(in_loan, unit.principal[np.minimum(yrs, fin.years - 1)], 0.0)
    borrower_ins = np.where(in_loan, fin.insurance_rate, 0.0)
    debt_service = loan[:, :, None] * (interest + principal + borrower_ins)[None, None, :]
    finance_costs = loan[:, :, None] * (interest + borrower_ins)[None, None, :]
    finance_costs[:, :, 0] += fin.guarantee_fee * loan  # loan guarantee, deductible in year 1

    # depreciation for furnished lets: building share of price and purchase costs, furniture
    notary = fin.notary_fees * price0
    if furnished:
        base = (price0 + notary) * (1 - tx.land_share)
        dep_building = np.where(yrs < tx.building_life_years, 1.0 / tx.building_life_years, 0.0)
        dep_furniture = np.where(yrs < a.property.furniture_life_years, a.property.furniture_cost / a.property.furniture_life_years, 0.0)
        depreciation = base[:, :, None] * dep_building + dep_furniture
    else:
        depreciation = None

    # works: deductible when paid for unfurnished lets (actual expenses), depreciated when furnished
    works_paid = works[:, :, 1:].copy()
    works_paid[:, :, 0] += works[:, :, 0]
    deductible = expenses
    if tx.regime == "reel":
        deductible = expenses + works_paid
    elif furnished:
        life = tr.works_life_years
        spread = np.zeros_like(works_paid)
        for y in range(H):
            spread[:, :, y:min(H, y + life)] += works_paid[:, :, y:y + 1] / life
        depreciation = depreciation + spread

    tax_income, dep_used = finance.rental_income_tax(rents, deductible, finance_costs, tx, depreciation)

    # exit at the horizon
    zone_growth = np.stack([paths.zone_log_growth[z] for z in rows["zone"]])  # (C, P, H)
    log_growth = (zone_growth + draws.local_log_growth).sum(axis=2)
    done = np.array([1.0] + [1.0 if works_year[k] <= H else 1.0 + gap[k] for k in (1, 2, 3)])
    sale_gross = value_d * (w @ done) * np.exp(log_growth)
    sale_net = sale_gross * (1 - a.market.selling_costs)
    balance = loan * (unit.balance_end[H - 1] if H <= fin.years else 0.0)
    penalty = finance.early_repayment_penalty(1.0, fin.rate) * balance if H < fin.years else 0.0
    recapture = dep_used.sum(axis=2) if (furnished and tx.lmnp_recapture) else 0.0
    tax_gain = finance.capital_gains_tax(sale_net, price0, notary, H, tx, recapture)

    equity0 = price0 * fin.down_payment_share + notary + fin.guarantee_fee * loan + works[:, :, 0]
    if furnished:
        equity0 = equity0 + a.property.furniture_cost

    cash = np.zeros((C, P, H + 1))
    cash[:, :, 0] = -equity0
    cash[:, :, 1:] = rents - expenses - debt_service - tax_income - works[:, :, 1:]
    cash[:, :, H] += sale_net - balance - penalty - tax_gain

    detail = {
        "rents": rents, "owner_charges": np.broadcast_to(owner_charges, rents.shape),
        "lmnp_costs": lmnp_costs,
        "property_tax": np.broadcast_to(property_tax, rents.shape), "insurance": np.broadcast_to(insurance, rents.shape),
        "management": management, "upkeep": np.broadcast_to(upkeep, rents.shape), "reletting": reletting,
        "debt_service": debt_service, "interest": loan[:, :, None] * interest, "income_tax": tax_income,
        "vacant_months": vacant_months, "works": works,
    }
    return CashFlows(cash, price0, equity0, rents[:, :, 0], sale_net, tax_income, tax_gain, detail)


def summarize(rows: pd.DataFrame, cf: CashFlows, a: Assumptions) -> pd.DataFrame:
    irr = finance.irr(cf.cash)  # (C, P)
    irr_filled = np.where(np.isnan(irr), -1.0, irr)  # no root: equity wiped out
    npv = finance.npv(cf.cash, a.market.discount_rate)
    q = np.quantile(irr_filled, [0.05, 0.25, 0.5, 0.75, 0.95], axis=1)
    k = max(1, int(round(0.05 * npv.shape[1])))
    worst = np.sort(npv, axis=1)[:, :k]
    early = cf.cash[:, :, 1:6]
    effort = np.mean(np.maximum(-early, 0.0).mean(axis=2), axis=1) / 12.0
    return pd.DataFrame({
        "commune": rows["commune"].to_numpy(),
        "irr_p05": q[0], "irr_p25": q[1], "irr_median": q[2], "irr_p75": q[3], "irr_p95": q[4],
        "irr_mean": irr_filled.mean(axis=1),
        "prob_loss": (irr_filled < 0).mean(axis=1),
        "prob_below_hurdle": (irr_filled < a.market.discount_rate).mean(axis=1),
        "npv_mean": npv.mean(axis=1), "npv_es05": worst.mean(axis=1),
        "effort_month": effort,
        "equity0": cf.equity0.mean(axis=1),
    })


def base_case(rows: pd.DataFrame, a: Assumptions, model: MarketModel) -> tuple[pd.DataFrame, CashFlows]:
    """Deterministic expected case: no shocks, expected vacancy, market at its forecast mean."""
    H = a.market.horizon_years
    paths = expected_paths(model, a, H)
    draws = draw_local(rows, a, model, 1, H, zero=True)
    cf = cash_flows(rows, a, paths, draws)
    irr = finance.irr(cf.cash)[:, 0]
    S = a.property.surface_m2
    price = np.exp(rows["eblup"].to_numpy()) * S
    rent_hc_year = np.maximum(rows["rent_m2"].to_numpy() - a.operating.recoverable_charges_m2_month, 0.0) * S * 12
    # net yield in a normal year (year 2: the first letting after purchase is behind)
    t = min(1, H - 1)
    rent_t = cf.detail["rents"][:, 0, t]
    costs_t = sum(cf.detail[k][:, 0, t] for k in ("owner_charges", "property_tax", "insurance", "management", "upkeep", "reletting", "lmnp_costs"))
    growth = np.exp(np.cumsum(paths.irl_log_growth[0]))[t - 1] if t > 0 else 1.0
    out = pd.DataFrame({
        "commune": rows["commune"].to_numpy(),
        "price": price,
        "gross_yield": rent_hc_year / price,
        "net_yield": (rent_t - costs_t) / growth / (price * (1 + a.financing.notary_fees)),
        "irr_base": irr,
    })
    return out, cf


def expected_paths(model: MarketModel, a: Assumptions, years: int) -> Paths:
    """Market paths with all shocks set to zero: the AR(1) forecast from today."""
    rng = _ZeroRng()
    return simulate_market(model, 1, years, a.market.price_growth, a.market.rent_growth, rng)


class _ZeroRng:
    def standard_normal(self, shape):
        return np.zeros(shape)


REGIMES = ("micro_foncier", "reel", "lmnp")


def best_regime(rows: pd.DataFrame, a: Assumptions, model: MarketModel) -> np.ndarray:
    """The tax regime (and so furnished or not) with the highest expected case IRR, per commune."""
    irr = np.column_stack([base_case(rows, a.with_(tax={"regime": r}), model)[0]["irr_base"].to_numpy() for r in REGIMES])
    return np.array(REGIMES)[np.argmax(np.nan_to_num(irr, nan=-1.0), axis=1)]


def run(universe: pd.DataFrame, a: Assumptions, model: MarketModel, batch: int = 40, progress=None) -> pd.DataFrame:
    """Simulate every commune; returns one row of metrics per commune.

    With regime "best", each commune is let the way that maximises its
    expected IRR (a choice the investor makes up front), then simulated.
    """
    H, P = a.market.horizon_years, a.market.n_paths
    rng = np.random.default_rng([a.market.seed, 0])
    paths = simulate_market(model, P, H, a.market.price_growth, a.market.rent_growth, rng)
    out = []
    for start in range(0, len(universe), batch):
        rows = universe.iloc[start:start + batch]
        regimes = best_regime(rows, a, model) if a.tax.regime == "best" else np.full(len(rows), a.tax.regime)
        for regime in pd.unique(regimes):
            sub = rows[regimes == regime]
            ar = a.with_(tax={"regime": regime})
            cf = cash_flows(sub, ar, paths, draw_local(sub, ar, model, P, H))
            m = summarize(sub, cf, ar)
            base, _ = base_case(sub, ar, model)
            out.append(m.merge(base, on="commune").assign(regime=regime))
        if progress:
            progress(min(start + batch, len(universe)), len(universe))
    res = pd.concat(out, ignore_index=True)
    return res.set_index("commune").loc[universe["commune"]].reset_index()
