"""Monte Carlo engine for the loss distribution of a credit portfolio.

Model (multi-factor structural / CreditMetrics-type):

    X_i = b_i . F + sqrt(1 - R_i) eps_i,    F ~ N(0, Sigma_F)
    default_i  <=>  X_i < q_i

* Gaussian copula:   q_i = Phi^{-1}(PD_i)
* Student-t copula:  X_i is scaled by sqrt(nu / W), W ~ chi2(nu), which adds
                     tail dependence (joint defaults in crises)
* LGD: fixed, or Beta with a correlation to the obligor's systematic factor
       (downturn LGD: loss severity rises when many firms default)

Scenarios are simulated in chunks, each with its own reproducible random
stream, and chunks run in parallel threads (NumPy releases the GIL in the
heavy kernels). Defaults are sparse, so losses and Euler contributions are
accumulated from the (row, col) indices of defaulted obligors only.
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize
from scipy.special import betaincinv, expit, logit, ndtr, ndtri
from scipy.stats import t as student_t

from ..rng import spawn_generators
from ..stats import Estimate, var_es
from .portfolio import CreditPortfolio


@dataclass
class CreditModel:
    portfolio: CreditPortfolio
    copula: str = "gaussian"
    nu: float = 6.0
    lgd_model: str = "fixed"
    lgd_precision: float = 4.0
    pd_lgd_corr: float = 0.0

    def __post_init__(self):
        if self.copula not in ("gaussian", "t"):
            raise ValueError("copula must be 'gaussian' or 't'")
        if self.lgd_model not in ("fixed", "beta"):
            raise ValueError("lgd_model must be 'fixed' or 'beta'")
        p = self.portfolio
        k = p.n_factors
        self.chol = np.linalg.cholesky(p.factor_corr + 1e-12 * np.eye(k))
        self.b_f = p.loadings()
        self.b_z = self.b_f @ self.chol
        self.idio = np.sqrt(1.0 - p.rsq)
        if self.copula == "gaussian":
            self.threshold = ndtri(p.pd)
        else:
            self.threshold = student_t.ppf(p.pd, self.nu)
        self.total = p.total_exposure
        self.ead_frac = p.ead / self.total
        self.c = self.ead_frac * p.lgd              # loss given default, fraction
        kappa = self.lgd_precision
        self.beta_a = p.lgd * kappa
        self.beta_b = (1.0 - p.lgd) * kappa
        # float32 copies for the hot loop
        self._bf_t32 = self.b_f.T.astype(np.float32)
        self._idio32 = self.idio.astype(np.float32)
        self._thr32 = self.threshold.astype(np.float32)

    @property
    def supports_importance_sampling(self) -> bool:
        return self.copula == "gaussian" and self.lgd_model == "fixed"


# --------------------------------------------------------------------------
# Importance sampling (Glasserman & Li, Management Science 2005)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ISPlan:
    """Two-step IS: shift the factor mean to ``mu``, then exponentially twist
    the conditional default probabilities towards the loss level ``x``.

    ``defensive`` is the fraction of scenarios drawn from the original
    measure (defensive mixture, Hesterberg 1995). With the balance-heuristic
    weight w = f / (l f + (1 - l) h) <= 1 / l, the body of the distribution
    (expected loss, lower quantiles) stays accurately estimated."""

    mu: np.ndarray
    x: float
    defensive: float = 0.1


def _twist(p: np.ndarray, c: np.ndarray, x: float, tol: float = 1e-9,
           max_iter: int = 50) -> tuple[np.ndarray, np.ndarray]:
    """Solve psi'(theta) = x row by row (theta = 0 when E[L|z] >= x).

    psi(theta) = sum_i log(1 - p_i + p_i exp(theta c_i)) is the conditional
    cumulant generating function of the loss. psi' grows roughly
    exponentially then saturates, so Newton is applied to log psi'(theta)
    (close to concave): starting from theta = 0 it converges monotonically,
    typically in 4-6 iterations. A bracket guards the rare non-concave rows.
    Returns theta (m,) and psi(theta) (m,).
    """
    p = np.atleast_2d(p)
    m = p.shape[0]
    theta = np.zeros(m)
    psi = np.zeros(m)
    active = np.flatnonzero(p @ c < x)
    if active.size == 0:
        return theta, psi
    log_x = np.log(x)
    c2 = c * c
    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        lp = logit(p[active])
        th = np.zeros(active.size)
        lo = np.zeros(active.size)
        hi = np.full(active.size, np.inf)
        todo = np.arange(active.size)
        for _ in range(max_iter):
            q = expit(lp[todo] + th[todo, None] * c)
            mean = q @ c
            g = np.log(mean) - log_x
            done = np.abs(g) < tol
            if np.all(done):
                break
            slope = ((q * (1 - q)) @ c2) / mean
            pos = g > 0
            hi[todo] = np.where(pos, np.minimum(hi[todo], th[todo]), hi[todo])
            lo[todo] = np.where(pos, lo[todo], np.maximum(lo[todo], th[todo]))
            new = th[todo] - g / slope
            l, h = lo[todo], hi[todo]
            bad = ~np.isfinite(new) | (new < l) | (new > h)
            new = np.where(bad, np.where(np.isfinite(h), 0.5 * (l + h), 2.0 * l + 1.0), new)
            th[todo] = np.where(done, th[todo], new)
            todo = todo[~done]
        pa = p[active]
        ps = np.sum(np.logaddexp(np.log1p(-pa), np.log(pa) + th[:, None] * c), axis=1)
    theta[active] = th
    psi[active] = ps
    return theta, psi


def plan_importance_sampling(model: CreditModel, x: float, defensive: float = 0.1) -> ISPlan:
    """Choose the factor mean shift mu maximising  F(z) - |z|^2 / 2,
    F(z) = -theta(z) x + psi(theta(z), z)  (log Chernoff bound of P(L>x | z)).
    ``x`` is a loss fraction of total exposure."""
    if not model.supports_importance_sampling:
        raise ValueError("importance sampling requires a Gaussian copula with fixed LGD")
    b, thr, sd, c = model.b_z, model.threshold, model.idio, model.c

    def objective(z):
        d = (thr - b @ z) / sd
        p = ndtr(d)
        theta, psi = _twist(p[None, :], c, x)
        th = theta[0]
        value = -th * x + psi[0] - 0.5 * z @ z
        e = np.expm1(th * c)
        dpsi_dp = e / (1.0 + p * e)
        dp_dz = -(np.exp(-0.5 * d * d) / np.sqrt(2 * np.pi) / sd)[:, None] * b
        grad = dpsi_dp @ dp_dz - z
        return -value, -grad

    direction = -(c @ b)
    direction /= np.linalg.norm(direction)
    best = None
    for s in (2.0, 3.0, 4.5):
        res = minimize(objective, s * direction, jac=True, method="BFGS")
        if best is None or res.fun < best.fun:
            best = res
    return ISPlan(mu=best.x, x=float(x), defensive=defensive)


# --------------------------------------------------------------------------
# Scenario generation
# --------------------------------------------------------------------------

@dataclass
class _Chunk:
    rows: np.ndarray        # scenario index of each default
    cols: np.ndarray        # obligor index of each default
    loss_vals: np.ndarray   # loss of each default (fraction of total exposure)
    loss: np.ndarray        # (m,) portfolio loss per scenario
    logw: np.ndarray | None


def _simulate_chunk(model: CreditModel, rng: np.random.Generator, m: int,
                    plan: ISPlan | None, factor_sampler=None) -> _Chunk:
    n = model.portfolio.n
    k = model.portfolio.n_factors
    if plan is not None:
        # defensive draws are interleaved so that any block of scenarios holds
        # the same proportion; lam is the realised fraction in this chunk
        stride = int(round(1.0 / plan.defensive)) if plan.defensive > 0 else 0
        from_f = (np.arange(m) % stride == 0) if stride else np.zeros(m, bool)
        lam = from_f.mean()
        z = rng.standard_normal((m, k))
        z[~from_f] += plan.mu
        p = ndtr((model.threshold - z @ model.b_z.T) / model.idio)
        theta, psi = _twist(p, model.c, plan.x)
        theta_draw = theta.copy()
        theta_draw[from_f] = 0.0
        with np.errstate(divide="ignore"):
            q = expit(logit(p) + theta_draw[:, None] * model.c)
        u = rng.random((m, n))
        rows, cols = np.nonzero(u < q)
        loss_vals = model.c[cols]
        loss = np.bincount(rows, weights=loss_vals, minlength=m)
        # log h/f for every scenario, whichever component it was drawn from
        log_hf = theta * loss - psi + z @ plan.mu - 0.5 * plan.mu @ plan.mu
        if lam > 0:
            logw = -np.logaddexp(np.log(lam), np.log1p(-lam) + log_hf)
        else:
            logw = -log_hf
        return _Chunk(rows, cols, loss_vals, loss, logw)

    if factor_sampler is None:
        f = rng.standard_normal((m, k)) @ model.chol.T
    else:
        f = factor_sampler(rng, m)
    sys = f.astype(np.float32) @ model._bf_t32
    x = rng.standard_normal((m, n), dtype=np.float32)
    x *= model._idio32
    x += sys
    if model.copula == "t":
        w = rng.chisquare(model.nu, size=m)
        x *= np.sqrt(model.nu / w).astype(np.float32)[:, None]
    rows, cols = np.nonzero(x < model._thr32)
    if model.lgd_model == "fixed":
        loss_vals = model.c[cols]
    else:
        s = sys[rows, cols] / np.sqrt(model.portfolio.rsq[cols])
        rho = model.pd_lgd_corr
        eta = rng.standard_normal(rows.size)
        u = ndtr(-rho * s + np.sqrt(1.0 - rho * rho) * eta)
        lgd = betaincinv(model.beta_a[cols], model.beta_b[cols], u)
        loss_vals = model.ead_frac[cols] * lgd
    loss = np.bincount(rows, weights=loss_vals, minlength=m)
    return _Chunk(rows, cols, loss_vals, loss, None)


def conditional_factor_sampler(model: CreditModel, shocks: dict[str, float]):
    """Sampler of F | F_S = y_S (Gaussian conditioning) for stress scenarios."""
    names = model.portfolio.factor_names
    s = np.array([names.index(k) for k in shocks])
    y = np.array(list(shocks.values()), dtype=float)
    r = np.setdiff1d(np.arange(len(names)), s)
    sig = model.portfolio.factor_corr
    gain = sig[np.ix_(r, s)] @ np.linalg.inv(sig[np.ix_(s, s)])
    cond_mean = gain @ y
    cond_cov = sig[np.ix_(r, r)] - gain @ sig[np.ix_(s, r)]
    lc = np.linalg.cholesky(cond_cov + 1e-12 * np.eye(r.size)) if r.size else None

    def sampler(rng, m):
        f = np.empty((m, len(names)))
        f[:, s] = y
        if r.size:
            f[:, r] = cond_mean + rng.standard_normal((m, r.size)) @ lc.T
        return f

    return sampler


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------

@dataclass
class CreditRiskResult:
    method: str
    losses: np.ndarray                  # currency
    weights: np.ndarray | None
    alphas: tuple[float, ...]
    total_exposure: float
    analytic_el: float
    elapsed: float
    plan: ISPlan | None = None
    es_contrib: np.ndarray | None = None      # currency, per obligor
    var_contrib: np.ndarray | None = None
    contrib_alpha: float | None = None
    extra: dict = field(default_factory=dict)

    @property
    def n_scenarios(self) -> int:
        return self.losses.size

    def expected_loss(self) -> Estimate:
        w = np.ones_like(self.losses) if self.weights is None else self.weights
        x = w * self.losses
        return Estimate(float(x.mean()), float(x.std(ddof=1) / np.sqrt(x.size)))

    def unexpected_loss(self) -> float:
        el = self.expected_loss().value
        w = np.ones_like(self.losses) if self.weights is None else self.weights
        return float(np.sqrt(np.mean(w * (self.losses - el) ** 2)))

    def var(self, alpha: float) -> float:
        return var_es(self.losses, alpha, self.weights)[0]

    def es(self, alpha: float) -> float:
        return var_es(self.losses, alpha, self.weights)[1]

    def risk_estimates(self, alpha: float, n_batches: int = 20) -> tuple[Estimate, Estimate]:
        """VaR and ES with batch-means standard errors (valid for IS too)."""
        v, e = var_es(self.losses, alpha, self.weights)
        parts = np.array_split(np.arange(self.n_scenarios), n_batches)
        b = np.array([var_es(self.losses[i], alpha,
                             None if self.weights is None else self.weights[i]) for i in parts])
        se = b.std(axis=0, ddof=1) / np.sqrt(n_batches)
        return Estimate(v, float(se[0])), Estimate(e, float(se[1]))

    def var_estimate(self, alpha: float, n_batches: int = 20) -> Estimate:
        return self.risk_estimates(alpha, n_batches)[0]

    def es_estimate(self, alpha: float, n_batches: int = 20) -> Estimate:
        return self.risk_estimates(alpha, n_batches)[1]

    def economic_capital(self, alpha: float) -> float:
        return self.var(alpha) - self.expected_loss().value

    def tail_probability(self, x: float) -> Estimate:
        ind = (self.losses > x).astype(float)
        if self.weights is not None:
            ind *= self.weights
        return Estimate(float(ind.mean()), float(ind.std(ddof=1) / np.sqrt(ind.size)))

    def summary(self, unit: float = 1e6, label: str = "m") -> str:
        u = unit
        el = self.expected_loss()
        lines = [
            f"Method            : {self.method}   ({self.n_scenarios:,} scenarios, {self.elapsed:.2f}s)",
            f"Total exposure    : {self.total_exposure / u:,.2f} {label}",
            f"Expected loss     : {el.value / u:,.4g} {label}  (sum EAD.PD.LGD {self.analytic_el / u:,.4g}, "
            f"s.e. {el.stderr / u:,.2g})",
            f"Unexpected loss   : {self.unexpected_loss() / u:,.4g} {label}",
        ]
        for a in self.alphas:
            v, e = self.risk_estimates(a)
            lines.append(
                f"VaR {a:>7.3%} : {v.value / u:11,.4f} ± {v.stderr / u:<9,.3g}"
                f"ES {e.value / u:11,.4f} ± {e.stderr / u:<9,.3g}"
                f"EC {(v.value - el.value) / u:11,.4f} {label}"
            )
        return "\n".join(lines)


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def _default_chunk(n_obligors: int) -> int:
    return int(np.clip(4_000_000 // max(n_obligors, 1), 256, 50_000))


def simulate(
    model: CreditModel,
    n_scenarios: int = 200_000,
    *,
    method: str = "plain",
    alphas: tuple[float, ...] = (0.99, 0.999),
    seed: int = 0,
    is_threshold: float | None = None,
    defensive: float = 0.1,
    contributions: bool = False,
    contrib_alpha: float | None = None,
    factor_sampler=None,
    chunk: int | None = None,
    threads: int | None = None,
    backend: str = "numpy",
) -> CreditRiskResult:
    """Simulate the portfolio loss distribution.

    method="plain"  crude Monte Carlo
    method="is"     importance sampling; the twisting level defaults to a
                    pilot estimate of VaR at max(alphas)
    contributions   Euler allocation of ES (and VaR) to obligors, by exact
                    replay of the random streams (second pass)
    backend         "numpy" (vectorised, every feature) or "native" (C++
                    Bernoulli-thinning kernel: plain MC, fixed LGD, cost per
                    scenario ~ number of defaults instead of number of obligors)
    """
    if backend == "native":
        return _simulate_native(model, n_scenarios, alphas=alphas, seed=seed,
                                contributions=contributions, contrib_alpha=contrib_alpha,
                                method=method, factor_sampler=factor_sampler,
                                chunk=chunk, threads=threads)
    if backend != "numpy":
        raise ValueError("backend must be 'numpy' or 'native'")
    t0 = time.perf_counter()
    p = model.portfolio
    chunk = chunk or _default_chunk(p.n)
    threads = threads or os.cpu_count() or 1
    sizes = [chunk] * (n_scenarios // chunk)
    if n_scenarios % chunk:
        sizes.append(n_scenarios % chunk)
    offsets = np.concatenate([[0], np.cumsum(sizes)])
    target = contrib_alpha or max(alphas)

    plan = None
    if method == "is":
        if factor_sampler is not None:
            raise ValueError("importance sampling with a stress sampler is not supported")
        if is_threshold is None:
            pilot = simulate(model, max(n_scenarios // 10, 20_000), method="plain",
                             alphas=(target,), seed=seed + 7919, threads=threads)
            x0 = pilot.var(target) / pilot.total_exposure
            pilot_is = simulate(model, max(n_scenarios // 10, 20_000), method="is",
                                alphas=(target,), seed=seed + 104729,
                                is_threshold=x0, defensive=defensive, threads=threads)
            is_threshold = pilot_is.var(target)
        plan = plan_importance_sampling(model, is_threshold / model.total, defensive)
    elif method != "plain":
        raise ValueError("method must be 'plain' or 'is'")

    gens = spawn_generators(seed, len(sizes))
    losses = np.empty(n_scenarios)
    logw = np.empty(n_scenarios) if plan is not None else None

    def run(i):
        ch = _simulate_chunk(model, gens[i], sizes[i], plan, factor_sampler)
        losses[offsets[i]:offsets[i + 1]] = ch.loss
        if logw is not None:
            logw[offsets[i]:offsets[i + 1]] = ch.logw

    with ThreadPoolExecutor(threads) as ex:
        list(ex.map(run, range(len(sizes))))
    weights = None if logw is None else np.exp(logw)

    result = CreditRiskResult(
        method="importance sampling" if plan is not None else "plain Monte Carlo",
        losses=losses * model.total,
        weights=weights,
        alphas=tuple(alphas),
        total_exposure=model.total,
        analytic_el=p.expected_loss,
        elapsed=0.0,
        plan=plan,
    )

    if contributions:
        _euler_contributions(model, result, sizes, offsets, seed, plan,
                             factor_sampler, target, threads)
    result.elapsed = time.perf_counter() - t0
    return result


def _euler_contributions(model, result, sizes, offsets, seed, plan,
                         factor_sampler, alpha, threads):
    """Replay every chunk and accumulate obligor losses in the tail.

    ES_i  = E[L_i | L >= VaR]            (coherent, sums to the tail mean)
    VaR_i = E[L_i | L ~ VaR]  estimated in a window holding ~0.5% of the
            tail mass, then rescaled to add up to VaR.
    """
    frac = result.losses / model.total
    w = np.ones_like(frac) if result.weights is None else result.weights
    var = result.var(alpha) / model.total
    dist = np.abs(frac - var)
    order = np.argsort(dist)
    k = max(int(0.02 * np.count_nonzero(frac >= var)), 100)
    h = dist[order[min(k, dist.size - 1)]]
    gens = spawn_generators(seed, len(sizes))
    n = model.portfolio.n
    es_parts, var_parts = [], []

    def run(i):
        ch = _simulate_chunk(model, gens[i], sizes[i], plan, factor_sampler)
        sl = slice(offsets[i], offsets[i + 1])
        wr = w[sl][ch.rows]
        in_tail = ch.loss[ch.rows] >= var
        in_win = np.abs(ch.loss[ch.rows] - var) <= h
        es_parts.append(np.bincount(ch.cols[in_tail], weights=(wr * ch.loss_vals)[in_tail], minlength=n))
        var_parts.append(np.bincount(ch.cols[in_win], weights=(wr * ch.loss_vals)[in_win], minlength=n))

    with ThreadPoolExecutor(threads) as ex:
        list(ex.map(run, range(len(sizes))))
    tail_mass = np.sum(w[frac >= var])
    win_mass = np.sum(w[dist <= h])
    es_c = np.sum(es_parts, axis=0) / tail_mass
    var_c = np.sum(var_parts, axis=0) / win_mass
    var_c *= var / var_c.sum()
    result.es_contrib = es_c * model.total
    result.var_contrib = var_c * model.total
    result.contrib_alpha = alpha


def _simulate_native(model, n_scenarios, *, alphas, seed, contributions, contrib_alpha,
                     method, factor_sampler, chunk, threads) -> CreditRiskResult:
    from . import native

    if method != "plain" or factor_sampler is not None:
        raise ValueError("the native backend supports plain Monte Carlo without stress samplers")
    t0 = time.perf_counter()
    kern = native.kernel(model)
    threads = threads or os.cpu_count() or 1
    chunk = chunk or 4096
    seed = int(seed) % 2**64
    frac = kern.simulate(n_scenarios, seed, threads, chunk)
    result = CreditRiskResult(
        method="plain Monte Carlo (native)", losses=frac * model.total, weights=None,
        alphas=tuple(alphas), total_exposure=model.total,
        analytic_el=model.portfolio.expected_loss, elapsed=0.0,
    )
    if contributions:
        alpha = contrib_alpha or max(alphas)
        var = result.var(alpha) / model.total
        dist = np.abs(frac - var)
        k = max(int(0.02 * np.count_nonzero(frac >= var)), 100)
        h = np.sort(dist)[min(k, dist.size - 1)]
        es_sum, n_tail = kern.conditional_sums(n_scenarios, seed, threads, chunk, var, np.inf)
        var_sum, n_win = kern.conditional_sums(n_scenarios, seed, threads, chunk, var - h, var + h)
        var_c = var_sum / n_win
        result.es_contrib = es_sum / n_tail * model.total
        result.var_contrib = var_c * (var / var_c.sum()) * model.total
        result.contrib_alpha = alpha
    result.elapsed = time.perf_counter() - t0
    return result
