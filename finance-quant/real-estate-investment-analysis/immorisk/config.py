"""Investment assumptions and data locations.

Every number that is a judgement call rather than an estimate lives here, so it
can be changed in one place and shows up in the report.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "out"

DVF_YEARS = (2021, 2022, 2023, 2024, 2025)


@dataclass(frozen=True)
class Property:
    """The reference flat, aligned with the rent map's T1-T2 reference unit."""

    surface_m2: float = 37.0
    furnished_rent_premium: float = 0.10  # furnished lets rent about 10% above unfurnished
    furniture_cost: float = 5_000.0
    furniture_life_years: int = 7


@dataclass(frozen=True)
class Financing:
    rate: float = 0.032  # fixed nominal rate, 20-year loan
    years: int = 20
    insurance_rate: float = 0.0030  # borrower insurance, share of initial capital per year
    guarantee_fee: float = 0.010  # mutual guarantee (caution), share of the loan
    down_payment_share: float = 0.10  # cash put in on top of fees, share of the price
    notary_fees: float = 0.080  # transfer duties and notary fees on existing flats


@dataclass(frozen=True)
class Operating:
    recoverable_charges_m2_month: float = 1.5  # charges in the advertised rent, passed on to the tenant
    owner_charges_m2_year: float = 12.0  # non recoverable condominium charges
    property_tax_months: float = 1.0  # taxe fonciere, in months of rent
    landlord_insurance: float = 130.0  # PNO insurance, EUR per year
    management_fee: float = 0.07  # letting agent, share of rent collected (the flat may be far away)
    capex_m2_year: float = 15.0  # upkeep and condominium works, EUR per m2 per year
    reletting_cost_m2: float = 13.0  # legal cap for landlord side letting fees (visit, lease, inventory)
    tenancy_months_unfurnished: float = 36.0  # average stay of a tenant in a small flat
    tenancy_months_furnished: float = 18.0
    vacancy_months_tight: float = 1.0  # months empty between tenants in the tightest market
    vacancy_months_slack: float = 3.0  # and in the slackest (ranked on long-term vacancy, LOVAC)


@dataclass(frozen=True)
class Tax:
    regime: str = "best"  # "micro_foncier", "reel", "lmnp", or "best": the one with the highest expected IRR
    marginal_rate: float = 0.30  # income tax bracket (TMI)
    social_rate: float = 0.172  # prelevements sociaux
    micro_foncier_allowance: float = 0.30
    deficit_cap: float = 10_700.0  # land deficit that can offset other income each year
    carryforward_years: int = 10
    land_share: float = 0.15  # non depreciable part of the price
    building_life_years: int = 30
    capital_gains_rate: float = 0.19
    sale_forfait_fees: float = 0.075  # flat rate acquisition costs allowed on a sale
    sale_forfait_works: float = 0.15  # flat rate works allowed after five years of ownership
    lmnp_recapture: bool = True  # 2025 finance law: depreciation taken is added back to the gain
    lmnp_accounting: float = 350.0  # accountant for furnished lets under actual expenses
    lmnp_cfe: float = 250.0  # business property tax (CFE) of a furnished let...
    cfe_exemption: float = 5_000.0  # ...unless rents received stay below this threshold


@dataclass(frozen=True)
class Transition:
    """Energy rating rental bans (loi Climat et resilience) and their cost.

    A flat rated G cannot be let since 2025, F from 2028, E from 2034. The
    rating of the flat bought is drawn from the commune's mix of diagnoses;
    works bring it to D before the ban. Costs and price gaps are orders of
    magnitude, not estimates: they are scenario inputs.
    """

    enabled: bool = True
    purchase_year: int = 2026
    ban_year_g: int = 2025
    ban_year_f: int = 2028
    ban_year_e: int = 2034
    works_m2_g: float = 450.0  # EUR per m2 to bring a flat to D
    works_m2_f: float = 350.0
    works_m2_e: float = 250.0
    discount_g: float = -0.12  # price gap against a D-or-better flat of the same commune
    discount_f: float = -0.07
    discount_e: float = -0.03
    works_months_g: float = 3.0  # a G flat is empty while works are done before the first letting
    works_life_years: int = 15  # depreciation period of works for furnished lets


@dataclass(frozen=True)
class Market:
    horizon_years: int = 15
    price_growth: float = 0.015  # long-run nominal price growth, a scenario, not an estimate
    rent_growth: float = 0.018  # long-run IRL growth
    selling_costs: float = 0.04
    discount_rate: float = 0.04  # opportunity cost used for NPV
    n_paths: int = 2_000
    seed: int = 20260924


@dataclass(frozen=True)
class Assumptions:
    property: Property = field(default_factory=Property)
    financing: Financing = field(default_factory=Financing)
    operating: Operating = field(default_factory=Operating)
    tax: Tax = field(default_factory=Tax)
    transition: Transition = field(default_factory=Transition)
    market: Market = field(default_factory=Market)

    def to_dict(self) -> dict:
        return asdict(self)

    def with_(self, **sections) -> "Assumptions":
        """Copy with some fields changed, e.g. a.with_(tax={"regime": "reel"})."""
        changes = {}
        for name, values in sections.items():
            changes[name] = replace(getattr(self, name), **values)
        return replace(self, **changes)
