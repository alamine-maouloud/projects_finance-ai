"""How sure is a ranking? Rank intervals under price estimation uncertainty.

A league table of communes hides that the price of a village with 25 sales is
known to within 5% at best. We redraw every commune's price level from its
Fay-Herriot posterior, recompute the expected case IRR, rank all communes in
each draw and report the 5% to 95% range of each commune's rank.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import finance
from .config import Assumptions
from .market import MarketModel
from .simulate import Draws, _key, cash_flows, draw_local, expected_paths


def rank_intervals(universe: pd.DataFrame, a: Assumptions, model: MarketModel, n_draws: int = 200, batch: int = 200,
                   regimes=None, centre=None) -> pd.DataFrame:
    """`regimes` gives each commune's tax regime (default: the one in `a`).

    `centre` is the statistic the league table ranks on (the median simulated
    IRR); each commune's draws are shifted so that their value at the central
    price estimate equals it, and the intervals surround the displayed rank.
    """
    if regimes is None:
        regimes = pd.Series(a.tax.regime, index=universe.index)
    regimes = pd.Series(np.asarray(regimes), index=universe.index)
    H = a.market.horizon_years
    base_paths = expected_paths(model, a, H)
    paths = type(base_paths)(
        zone_log_growth={z: np.repeat(g, n_draws, axis=0) for z, g in base_paths.zone_log_growth.items()},
        irl_log_growth=np.repeat(base_paths.irl_log_growth, n_draws, axis=0),
    )
    irr = np.full((len(universe), n_draws), np.nan)
    pos = pd.Series(np.arange(len(universe)), index=universe.index)
    for regime in pd.unique(regimes):
        ar = a.with_(tax={"regime": regime})
        group = universe[regimes == regime]
        for start in range(0, len(group), batch):
            rows = group.iloc[start:start + batch]
            irr[pos.loc[rows.index].to_numpy()] = _draw_irr(rows, ar, model, paths, n_draws, H)
    if centre is not None:
        irr = irr - irr[:, :1] + np.asarray(centre, float)[:, None]
    return _ranks(universe, irr)


def _draw_irr(rows, a, model, paths, n_draws, H):
    zero = draw_local(rows, a, model, 1, H, zero=True)
    price_z = np.stack([np.random.default_rng([a.market.seed, 3, _key(c)]).standard_normal(n_draws) for c in rows["commune"]])
    price_z[:, 0] = 0.0  # first draw: the central estimate
    draws = Draws(
        price_z=price_z, rent_z=np.zeros_like(price_z),
        local_log_growth=np.zeros(price_z.shape + (H,)),
        relets=np.repeat(zero.relets, n_draws, axis=1),
        vacant_months=np.repeat(zero.vacant_months, n_draws, axis=1),
        energy=np.repeat(zero.energy, n_draws, axis=1),
    )
    return finance.irr(cash_flows(rows, a, paths, draws).cash)


def _ranks(universe, irr):
    ranks = (-np.nan_to_num(irr, nan=-1.0)).argsort(axis=0).argsort(axis=0) + 1  # 1 = best, per draw
    return pd.DataFrame({
        "commune": universe["commune"].to_numpy(),
        "rank_p05": np.quantile(ranks, 0.05, axis=1),
        "rank_median": np.median(ranks, axis=1),
        "rank_p95": np.quantile(ranks, 0.95, axis=1),
        "irr_base_sd": np.nanstd(irr, axis=1),
    })
