# mcrisk: a Monte Carlo risk engine for banking books

`mcrisk` simulates the three risks that drive a bank's capital from one code base, and checks every engine against a closed-form result:

| Risk | What is computed | Key techniques |
|---|---|---|
| **Portfolio credit** | Loss distribution, VaR / ES, economic capital, Euler allocation per obligor and sector, stress tests, Basel IRB comparison | Multi-factor Gaussian and Student-t copulas, downturn (beta) LGD, Glasserman-Li importance sampling with a defensive mixture, exact two-pass replay, C++ Bernoulli-thinning kernel |
| **Market (FRTB IMA)** | 10-day VaR 99% and ES 97.5%, liquidity-horizon cascade, IMCC, component ES, out-of-sample backtests | Full revaluation of a multi-asset book, filtered historical simulation (GARCH), EWMA and Student-t scenarios, delta-gamma, Kupiec and Christoffersen tests, Basel traffic light |
| **Counterparty (CCR / XVA)** | EE, ENE, PFE, EEPE, EAD (IMM), netting, CSA collateral with margin period of risk, CVA / DVA, wrong-way risk | Hull-White 1F fitted to a Nelson-Siegel-Svensson curve with exact simulation, path-dependent swap fixings, Hull-White (2012) stochastic-intensity wrong-way risk |
| **Pricing library** | European, Asian, American and Heston options, swaptions | Antithetic variates, control variates, Sobol + Brownian bridge RQMC, Longstaff-Schwartz, Andersen QE scheme |

Portfolios, the trading book and the market history are **synthetic**: they are generated from documented processes with known parameters, so every model can be tested against the truth. No client or vendor data is used.

## Headline results

Full run: `python -m mcrisk.report` (71 s on an Apple M4, 10 threads).

**Credit.** A 2,000-name corporate book (EUR 54.8 bn EAD, 15 systematic factors, 590 effective names), 2 million scenarios in 9.5 s:

| Model | EL | VaR 99.9% | ES 99.9% | Economic capital |
|---|---:|---:|---:|---:|
| Gaussian copula | 233 | 1,615 ± 8 | 1,955 ± 12 | 1,382 |
| Student-t copula (ν = 8) | 233 | 4,001 ± 39 | 5,356 ± 62 | 3,768 |
| Downturn LGD (beta, ρ = 0.5) | 279 | 2,785 ± 21 | 3,493 ± 38 | 2,506 |
| *Basel IRB / ASRF (single factor)* | *233* | *1,973* | | *1,740* |

EUR m, ± one standard error. Sector and region diversification puts the multi-factor VaR 18% below the Basel single-factor quantile. Tail dependence (t-copula) multiplies it by 2.5 with unchanged PDs. Importance sampling cuts the variance of ES 99.9% by **~750×** at 300,000 scenarios.

**Market.** A 16-factor EUR trading book (cash equity, equity options, government and corporate bonds):

| Scenario model | VaR 99% (10d) | ES 97.5% (10d) |
|---|---:|---:|
| Historical (overlapping) | 90.95 | 84.39 |
| Normal, EWMA 0.94 | 56.32 | 56.76 |
| Student-t (ν = 5) | 63.19 | 66.42 |
| **Filtered HS (GARCH)** | **71.39** | **74.97** |

Liquidity-adjusted ES is EUR 79.4 m and the IMCC EUR 95.1 m (28% diversification across risk classes). Out-of-sample 1-day VaR 99% over 1,920 days with two crisis regimes:

| Model | Exceptions (19.2 expected) | Kupiec p | Christoffersen p (cc) |
|---|---:|---:|---:|
| Historical simulation | 37 | 0.0003 ✗ | 0.0006 ✗ |
| Normal EWMA | 32 | 0.0074 ✗ | 0.016 ✗ |
| **Filtered HS (GARCH)** | **25** | **0.20 ✓** | **0.32 ✓** |

**Counterparty.** Six EUR swaps with one corporate, including seasoned and forward-starting trades:

| Set-up | EPE | EEPE | EAD (IMM) | Peak PFE 97.5% |
|---|---:|---:|---:|---:|
| Uncollateralised | 21.43 | 22.47 | 31.45 | 147.3 |
| CSA, EUR 10m thresholds, 10-day MPoR | 8.00 | 11.02 | 15.43 | 32.4 |
| CSA + EUR 15m initial margin | 0.17 | 0.45 | 0.63 | 13.6 |

CVA is EUR 3.13 m (0.79 m under the CSA) and DVA EUR 1.01 m. Wrong-way risk with b = 1 raises CVA by 104%, right-way risk with b = −1 lowers it by 71%. Netting saves 34% of EPE.

## Validation

Each estimate is compared with an exact or semi-analytic reference. z is the gap in units of the estimate's standard error.

| Test | Reference | Monte Carlo | Exact | z |
|---|---|---:|---:|---:|
| P(L > 30), plain MC | Finite pool, exact quadrature | 5.432e-3 ± 7.4e-5 | 5.507e-3 | −1.02 |
| P(L > 60), importance sampling | Finite pool, exact quadrature | 2.3605e-4 ± 7.2e-7 | 2.3605e-4 | +0.01 |
| P(L > 100), importance sampling | Finite pool, exact quadrature | 6.634e-6 ± 4.0e-8 | 6.674e-6 | −1.01 |
| ES 99.99%, importance sampling | Finite pool, exact quadrature | 80.933 ± 0.036 | 80.943 | −0.28 |
| European call, antithetic + control | Black-Scholes | 11.338 ± 0.006 | 11.348 | −1.77 |
| American put, Longstaff-Schwartz | CRR tree, 5,000 steps | 8.696 ± 0.031 | 8.675 | +0.67 |
| Merton jump-diffusion call | Poisson series | 10.603 ± 0.016 | 10.627 | −1.50 |
| Heston call K = 90, QE, Feller < 1 | Gil-Pelaez inversion | 15.692 ± 0.019 | 15.717 | −1.30 |
| Heston call K = 110, QE, Feller < 1 | Gil-Pelaez inversion | 3.406 ± 0.010 | 3.416 | −0.99 |
| 5y × 10y payer swaption (× 100) | Hull-White / Jamshidian | 4.874 ± 0.010 | 4.872 | +0.24 |
| E[D(0, 5y)] | Curve P(0, 5y) | 0.87299 ± 8e-5 | 0.87303 | −0.52 |

The test suite (`pytest`, 58 tests) adds more properties: t-copula and beta LGD preserve the expected loss, Euler contributions add up to the tail mean, results are identical for any thread count, the swap value discounted by D(0, t) is a martingale, collateral lowers exposure monotonically, CVA with b = 0 reproduces the independent CVA exactly, and more.

## Performance: the C++ thinning kernel

The NumPy engine draws one latent variable per obligor and scenario, which costs O(N) per scenario. The C++ kernel (`cpp/src/credit_kernel.cpp`, exposed through pybind11) draws **defaults** directly, by exact Bernoulli thinning:

1. obligors are grouped into blocks (same factor pattern, PDs within a factor of 2);
2. conditional on the factors, a cheap upper bound p_max of the block's conditional PDs is computed from precomputed loading ranges;
3. candidates are drawn with probability p_max by geometric skipping, then accepted with probability p_i / p_max.

This is exact, handles the t-copula mixing variable, and costs O(blocks + defaults) per scenario. Each chunk of scenarios has its own xoshiro256** stream, so results do not depend on the thread count and a chunk can be replayed exactly.

| Obligors | Scenarios | NumPy (s) | C++ (s) | Speed-up |
|---:|---:|---:|---:|---:|
| 2,000 | 1,000,000 | 1.89 | 1.70 | ×1.1 |
| 10,000 | 400,000 | 3.98 | 1.46 | ×2.7 |
| 50,000 | 200,000 | 11.08 | 2.19 | ×5.1 |
| 200,000 | 100,000 | 23.94 | 4.99 | ×4.8 |

These timings come from `python benchmarks/bench_credit.py` and vary by about 20% from run to run. The NumPy baseline is already multi-threaded and BLAS-backed, so the gap comes from the algorithm, not from the language.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"                 # also builds the optional C++ kernel
python setup.py build_ext --inplace     # rebuild the kernel after editing C++
pytest -q                               # 58 tests, ~40 s
```

```bash
mcrisk credit --scenarios 1000000 --backend native --contributions
mcrisk credit --method is --scenarios 200000            # importance sampling
mcrisk credit --copula t --nu 6
mcrisk market --backtest
mcrisk ccr --csa
mcrisk report                                           # full run -> out/results.json
python -m mcrisk.dashboard out/results.json out/dashboard.html
```

As a library:

```python
from mcrisk.credit import CreditModel, simulate, synthetic_portfolio

model = CreditModel(synthetic_portfolio(5_000), copula="t", nu=8)
res = simulate(model, 1_000_000, backend="native", contributions=True)
print(res.summary())
var, es = res.risk_estimates(0.999)   # Estimate(value, stderr)
res.es_contrib                        # Euler ES contribution of every obligor
```

## Layout

```
mcrisk/
  rng.py, stats.py           reproducible streams, QMC, Brownian bridge; weighted VaR/ES, error bars
  curves.py                  Nelson-Siegel-Svensson zero curve
  credit/                    portfolio, factor model, engine (plain / IS), IRB, exact benchmarks, native bridge
  market/                    risk factors + synthetic history, trading book, scenarios (HS/EWMA/t/FHS), FRTB, backtests
  ccr/                       swaps under Hull-White, exposure metrics and CSA, CVA/DVA, wrong-way risk
  models/                    GBM, Merton, Heston (analytic + QE), Hull-White
  pricing/                   Black-Scholes family, variance-reduced MC, Longstaff-Schwartz
  report.py, dashboard.py    end-to-end run -> JSON -> self-contained HTML dashboard
cpp/src/                     native credit kernel + pybind11 bindings; original Black-Scholes CLI pricer
tests/                       58 tests: statistical validation against closed forms and invariants
benchmarks/                  throughput of the credit backends
```

## Modelling notes and limitations

- **Credit.** Default-mode (one-year) model. There is no rating migration or mark-to-market, and LGD is not correlated across obligors beyond the systematic factor. Importance sampling is implemented for the Gaussian copula with fixed LGD; for the t-copula or beta LGD, use plain MC (native or NumPy).
- **Market.** GARCH is univariate per factor, and the dependence comes from bootstrapping whole residual vectors. The book is static over the horizon. The IMCC is computed on the current window; the stressed-period calibration ratio ES_R,S / ES_R,C of MAR33 is not implemented.
- **Counterparty.** Single-curve discounting, a one-factor rates model (no smile, no multi-currency). The MTA is folded into the thresholds. Exposure is sampled on a half-monthly grid plus every cash-flow date.
- **Data.** Everything is synthetic by design. Swapping in real inputs means replacing `synthetic_portfolio`, `synthetic_history` and the curve parameters.

## References

- Glasserman, P. & Li, J. (2005). Importance sampling for portfolio credit risk. *Management Science*, 51(11).
- Hesterberg, T. (1995). Weighted average importance sampling and defensive mixture distributions. *Technometrics*, 37(2).
- Tasche, D. (2008). Capital allocation to business units and sub-portfolios: the Euler principle.
- BCBS (2005). An explanatory note on the Basel II IRB risk weight functions. BCBS (2019). *Minimum capital requirements for market risk* (MAR33).
- Barone-Adesi, G., Giannopoulos, K. & Vosper, L. (1999). VaR without correlations for portfolios of derivative securities. *Journal of Futures Markets*.
- Kupiec, P. (1995); Christoffersen, P. (1998). Backtesting VaR models.
- Andersen, L. (2008). Simple and efficient simulation of the Heston stochastic volatility model. *Journal of Computational Finance*.
- Albrecher, H. et al. (2007). The little Heston trap. *Wilmott Magazine*.
- Longstaff, F. & Schwartz, E. (2001). Valuing American options by simulation. *Review of Financial Studies*.
- Brigo, D. & Mercurio, F. (2006). *Interest Rate Models: Theory and Practice*. Springer.
- Hull, J. & White, A. (2012). CVA and wrong-way risk. *Financial Analysts Journal*, 68(5).
