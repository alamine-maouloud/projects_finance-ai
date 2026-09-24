"""Price level of a reference flat in every commune, with its uncertainty.

Two steps.

1. A hedonic fixed effects model on individual sales,

       log(price per m2)_i = index[dep, quarter] + level[commune] + f(size, rooms) + e_i,

   fitted by backfitting (alternating group means, the same projections a
   two-way fixed effects solver uses). It removes the size mix (small flats
   cost more per m2) and the date of each sale, so communes are compared on the
   same flat at the same date. The department quarterly index is reused to
   calibrate local price risk.

2. Small area estimation. A commune with 8 sales has a noisy level. The
   Fay-Herriot model treats each direct estimate as the truth plus known
   sampling noise, and the truth as a department mean plus a rent effect plus a
   commune deviation:

       direct_c = mu[dep] + gamma * rent_c + u_c + e_c,   u_c ~ N(0, tau2),  e_c ~ N(0, v_c)

   The empirical best linear unbiased predictor (EBLUP) pulls each commune
   towards its prediction by the factor v_c / (tau2 + v_c): hardly at all for
   a big city, a lot for a village. This is the method statistics offices use
   for small area estimates.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import zone_of

REFERENCE_SURFACE = 37.0  # the rent map's T1-T2 reference flat
REFERENCE_ROOMS = 2


def _group_mean(values: np.ndarray, codes: np.ndarray, n_groups: int, weights: np.ndarray | None = None) -> np.ndarray:
    if weights is None:
        s = np.bincount(codes, weights=values, minlength=n_groups)
        n = np.bincount(codes, minlength=n_groups)
    else:
        s = np.bincount(codes, weights=values * weights, minlength=n_groups)
        n = np.bincount(codes, weights=weights, minlength=n_groups)
    return np.divide(s, n, out=np.zeros(n_groups), where=n > 0)


def _design(sales: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Flat characteristics, all zero for the reference flat (37 m2, 2 rooms,
    outside a priority neighbourhood). The priority neighbourhood discount is
    allowed to differ between Paris, its suburbs and the rest of France."""
    z = np.log(sales["surface"].to_numpy(float) / REFERENCE_SURFACE)
    r = np.clip(sales["rooms"].to_numpy(int), 1, 5)
    cols = [z, z**2] + [(r == k).astype(float) for k in (1, 3, 4, 5)]
    names = ["log_size", "log_size_sq", "rooms_1", "rooms_3", "rooms_4", "rooms_5plus"]
    if "qpv" in sales:
        zone = sales["dep"].map(zone_of).to_numpy()
        q = sales["qpv"].to_numpy(bool)
        for zn in ("paris", "petite_couronne", "grande_couronne", "province"):
            col = (q & (zone == zn)).astype(float)
            if col.any():
                cols.append(col)
                names.append(f"qpv_{zn}")
    return np.column_stack(cols), names


@dataclass
class HedonicFit:
    beta: pd.Series
    level: pd.DataFrame  # per commune: dep, n, direct (log EUR/m2 of the reference flat now), v (sampling var)
    index: pd.DataFrame  # per (dep, quarter): delta (log), n, se
    sigma2_dep: pd.Series  # residual variance per department
    residuals: np.ndarray


def fit_hedonic(sales: pd.DataFrame, current_quarters: int = 4, n_iter: int = 60, clip_sd: float = 3.0) -> HedonicFit:
    """Two-way fixed effects hedonic model of log price per m2.

    The department index is normalised to average zero over the last
    `current_quarters` quarters, so commune levels are prices "now" (the
    average of that window) for the reference flat.
    """
    y = np.log(sales["price_m2"].to_numpy(float))
    X, names = _design(sales)
    c_codes, communes = pd.factorize(sales["commune"], sort=True)
    dq = sales["dep"].astype(str) + "|" + sales["quarter"].astype(str)
    g_codes, groups = pd.factorize(dq, sort=True)
    nc, ng = len(communes), len(groups)

    def backfit(y_: np.ndarray):
        beta = np.zeros(X.shape[1])
        alpha = _group_mean(y_, c_codes, nc)
        delta = np.zeros(ng)
        xtx_inv = np.linalg.inv(X.T @ X)
        for _ in range(n_iter):
            xb = X @ beta
            delta = _group_mean(y_ - alpha[c_codes] - xb, g_codes, ng)
            alpha = _group_mean(y_ - delta[g_codes] - xb, c_codes, nc)
            new_beta = xtx_inv @ (X.T @ (y_ - delta[g_codes] - alpha[c_codes]))
            if np.max(np.abs(new_beta - beta)) < 1e-9:
                beta = new_beta
                break
            beta = new_beta
        return alpha, delta, beta

    alpha, delta, beta = backfit(y)
    resid = y - alpha[c_codes] - delta[g_codes] - X @ beta
    # robustness: winsorise residuals at clip_sd standard deviations and refit
    s = resid.std()
    y_rob = y - resid + np.clip(resid, -clip_sd * s, clip_sd * s)
    alpha, delta, beta = backfit(y_rob)
    resid = y_rob - alpha[c_codes] - delta[g_codes] - X @ beta

    idx = pd.DataFrame({"key": groups})
    idx[["dep", "quarter"]] = idx["key"].str.split("|", expand=True)
    idx["quarter"] = idx["quarter"].astype(int)
    idx["delta"] = delta
    idx["n"] = np.bincount(g_codes, minlength=ng)

    # normalise each department's index to mean zero over the current window
    last = sorted(idx["quarter"].unique())[-current_quarters:]
    shift = idx[idx["quarter"].isin(last)].groupby("dep").apply(
        lambda g: np.average(g["delta"], weights=g["n"]), include_groups=False)
    idx["delta"] -= idx["dep"].map(shift).fillna(0.0)

    dep_of_commune = sales.groupby("commune")["dep"].first().reindex(communes)
    alpha_now = alpha + dep_of_commune.map(shift).fillna(0.0).to_numpy()

    dep_codes = sales["dep"].to_numpy()
    sigma2_dep = pd.Series(resid**2).groupby(dep_codes).mean()
    idx["se"] = np.sqrt(idx["dep"].map(sigma2_dep) / idx["n"])

    n_c = np.bincount(c_codes, minlength=nc)
    level = pd.DataFrame({
        "commune": communes,
        "dep": dep_of_commune.to_numpy(),
        "n_sales": n_c,
        "direct": alpha_now,
    })
    level["v"] = level["dep"].map(sigma2_dep).to_numpy() / level["n_sales"]
    level["qpv_share"] = sales.groupby("commune")["qpv"].mean().reindex(communes).to_numpy() if "qpv" in sales else 0.0
    return HedonicFit(beta=pd.Series(beta, index=names), level=level, index=idx.drop(columns="key"), sigma2_dep=sigma2_dep, residuals=resid)


@dataclass
class FayHerriot:
    tau2: float
    gamma: float
    mu: pd.Series  # department means
    table: pd.DataFrame  # per commune: direct, v, synthetic, eblup, mse, shrink


def fay_herriot(direct: np.ndarray, v: np.ndarray, dep: np.ndarray, covariate: np.ndarray, tol: float = 1e-10) -> FayHerriot:
    """EBLUP with department fixed effects and one covariate.

    tau2 solves the Fay-Herriot moment equation
        sum_c (direct_c - x_c'b(tau2))^2 / (tau2 + v_c) = m - p
    where b(tau2) is the weighted least squares fit; the left side decreases in
    tau2, so bisection is safe.
    """
    direct = np.asarray(direct, float)
    v = np.asarray(v, float)
    cov = np.asarray(covariate, float)
    d_codes, deps = pd.factorize(pd.Series(dep).astype(str))
    nd = len(deps)
    m, p = len(direct), nd + 1

    def wls(tau2: float):
        w = 1.0 / (tau2 + v)
        # department fixed effects via weighted within transformation
        ybar = _group_mean(direct, d_codes, nd, w)
        xbar = _group_mean(cov, d_codes, nd, w)
        yt, xt = direct - ybar[d_codes], cov - xbar[d_codes]
        denom = np.sum(w * xt * xt)
        gamma = np.sum(w * xt * yt) / denom if denom > 0 else 0.0
        mu = ybar - gamma * xbar
        fitted = mu[d_codes] + gamma * cov
        return gamma, mu, fitted, w

    def moment(tau2: float) -> float:
        _, _, fitted, w = wls(tau2)
        return np.sum(w * (direct - fitted) ** 2) - (m - p)

    lo, hi = 0.0, max(1.0, 10 * np.var(direct))
    if moment(lo) <= 0:
        tau2 = 0.0
    else:
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            if moment(mid) > 0:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol:
                break
        tau2 = 0.5 * (lo + hi)

    gamma, mu, synthetic, w = wls(tau2)
    shrink = v / (tau2 + v)  # weight on the synthetic prediction
    eblup = synthetic + (1.0 - shrink) * (direct - synthetic)
    g1 = tau2 * v / (tau2 + v)
    # g2: extra error from estimating the regression part (department mean and gamma)
    wsum_dep = np.bincount(d_codes, weights=w, minlength=nd)
    g2 = shrink**2 * (1.0 / wsum_dep[d_codes])
    table = pd.DataFrame({
        "direct": direct, "v": v, "synthetic": synthetic, "eblup": eblup,
        "mse": g1 + g2, "shrink": shrink,
    })
    return FayHerriot(tau2=float(tau2), gamma=float(gamma), mu=pd.Series(mu, index=deps), table=table)


def commune_prices(sales: pd.DataFrame, rents: pd.DataFrame, current_quarters: int = 4) -> tuple[pd.DataFrame, HedonicFit, FayHerriot]:
    """Price per m2 of the reference flat now, per commune, direct and EBLUP.

    `rents` provides the covariate (log advertised rent, from the rent map),
    which carries information on how expensive a commune is even when it has
    few sales.
    """
    fit = fit_hedonic(sales, current_quarters=current_quarters)
    lvl = fit.level.merge(rents[["commune", "rent_m2"]], on="commune", how="inner")
    fh = fay_herriot(lvl["direct"], lvl["v"], lvl["dep"], np.log(lvl["rent_m2"]))
    out = pd.concat([lvl.reset_index(drop=True), fh.table[["synthetic", "eblup", "mse", "shrink"]]], axis=1)
    out["price_m2_direct"] = np.exp(out["direct"])
    out["price_m2"] = np.exp(out["eblup"])
    out["price_sd_log"] = np.sqrt(out["mse"])
    return out.drop(columns=["rent_m2"]), fit, fh


def raw_medians(sales: pd.DataFrame) -> pd.Series:
    """Naive median price per m2 by commune (what the original notebook used)."""
    return sales.groupby("commune")["price_m2"].median()
