*[Version française](README.fr.md)*

# Buy-to-let risk and return in every French commune, on open data

`immorisk` answers a question banks and investors ask every day: if I buy a small flat to let, with a loan, where in France does it pay, and how much can I lose? It prices the same 37 m2 flat in 2,376 communes from 1.8 million real sales, and adds real rents, vacancy and energy ratings. It then runs 15 years of after-tax cash flows under French taxation, 2,000 times per commune, through a market model calibrated on 34 years of INSEE price indices.

Everything comes from open data, joined by INSEE code: DVF sales, the rent map, LOVAC vacancy, ADEME energy diagnoses, priority neighbourhood perimeters and INSEE indices. There is no synthetic input anywhere in the pipeline.

![Median IRR by commune](out/charts/map_irr.png)

## Headline results

The investor puts down 10% of the price plus fees, borrows the rest over 20 years at 3.2%, has a 30% marginal tax rate and lets the flat through an agent. Each commune gets the letting regime that suits it best. Over 15 years, with prices assumed to grow 1.5% a year in the long run:

- The **median IRR on equity is 3.0%** across communes, from 1.7% (10th percentile) to 4.7% (90th).
- The **median probability of losing money is 30%**.
- The median investor puts in **21,700 EUR** at purchase, then **270 EUR a month** over the first five years.

**The large cities**, by median IRR:

| City | EUR/m2 | Rent EUR/m2 | Gross yield | Net yield | Best regime | Median IRR | 1 in 20 below | P(loss) | Effort EUR/month | F or G rated | Rank /2,376 |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| Limoges | 1,596 | 13.4 | 8.9% | 4.5% | unfurnished, actual | **4.2%** | -6.2% | 21% | 129 | 4% | 400 |
| Saint-Etienne | 1,347 | 11.4 | 8.9% | 4.0% | unfurnished, actual | **3.2%** | -7.7% | 28% | 128 | 10% | 994 |
| Marseille 5e | 3,553 | 18.6 | 5.8% | 3.3% | unfurnished, actual | **3.1%** | -8.2% | 30% | 349 | 4% | 1,054 |
| Clermont-Ferrand | 2,225 | 14.5 | 7.0% | 3.7% | unfurnished, actual | **3.1%** | -7.0% | 27% | 212 | 9% | 1,110 |
| Montpellier | 3,460 | 17.9 | 5.7% | 3.4% | unfurnished, actual | **3.0%** | -8.0% | 30% | 334 | 2% | 1,139 |
| Nice | 5,049 | 22.7 | 5.0% | 3.1% | unfurnished, actual | **2.8%** | -8.6% | 31% | 509 | 5% | 1,371 |
| Le Havre | 2,387 | 13.9 | 6.2% | 3.2% | unfurnished, actual | **2.7%** | -8.7% | 31% | 246 | 9% | 1,392 |
| Paris 11e | 9,641 | 33.3 | 4.0% | 2.6% | furnished (LMNP) | **2.6%** | -8.5% | 30% | 1,078 | 19% | 1,513 |
| Nantes | 3,563 | 16.6 | 5.1% | 2.9% | unfurnished, actual | **2.5%** | -9.1% | 34% | 373 | 5% | 1,583 |
| Toulouse | 3,455 | 16.3 | 5.1% | 2.9% | unfurnished, actual | **2.5%** | -8.5% | 33% | 362 | 4% | 1,647 |
| Lille | 3,930 | 18.1 | 5.1% | 2.9% | unfurnished, actual | **2.4%** | -9.6% | 34% | 418 | 8% | 1,683 |
| Rennes | 3,892 | 17.2 | 4.8% | 2.8% | unfurnished, actual | **2.3%** | -9.3% | 33% | 414 | 5% | 1,746 |
| Lyon 3e | 4,710 | 18.9 | 4.4% | 2.7% | unfurnished, actual | **2.3%** | -9.9% | 35% | 519 | 6% | 1,797 |
| Bordeaux | 4,350 | 18.5 | 4.7% | 2.7% | unfurnished, actual | **2.3%** | -9.7% | 35% | 474 | 6% | 1,809 |

Prices are for the reference flat (37 m2, two rooms, outside a priority neighbourhood). Rents are the rent map's advertised rents, charges included. The net yield is after vacancy and every running cost, before financing and tax. "1 in 20 below" is the 5% quantile of the IRR.

**The top of the ranking.** The top 10 all have at least 30 flat sales a year:

| Rank | Commune | Sales/yr | In QPV | EUR/m2 | Gross yield | Median IRR | 1 in 20 below | P(loss) | Rank, 90% range |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | Épinay-sous-Sénart (91) | 56 | 45% | 2,299 | 10.2% | **8.2%** | 2.5% | 1% | 1 to 1 |
| 2 | Grigny (91) | 65 | 81% | 1,861 | 11.1% | **7.6%** | 0.0% | 5% | 2 to 5 |
| 3 | Villepinte (93) | 134 | 42% | 2,987 | 8.6% | **7.5%** | 0.1% | 5% | 2 to 6 |
| 4 | Villeneuve-la-Garenne (92) | 84 | 26% | 3,695 | 8.3% | **7.5%** | 0.2% | 5% | 2 to 6 |
| 5 | Aubergenville (78) | 58 | 0% | 2,298 | 9.8% | **7.4%** | 0.7% | 3% | 3 to 8 |
| 6 | Évry-Courcouronnes (91) | 411 | 24% | 2,582 | 9.0% | **7.3%** | 0.6% | 4% | 5 to 8 |
| 7 | Les Ulis (91) | 146 | 3% | 2,642 | 8.8% | **7.3%** | 1.4% | 2% | 4 to 9 |
| 8 | Ris-Orangis (91) | 179 | 37% | 2,457 | 9.3% | **7.2%** | 1.3% | 3% | 6 to 9 |
| 9 | Sevran (93) | 128 | 38% | 2,700 | 8.7% | **6.9%** | -0.5% | 6% | 9 to 13 |
| 10 | Prémanon (39) | 31 | 0% | 2,920 | 9.1% | **6.9%** | -1.2% | 7% | 6 to 20 |

The winners are the outer Paris suburbs, where rents are close to Paris levels and prices are not. Several have a large share of sales in priority neighbourhoods (QPV). There, condominium quality, tenant risk and resale liquidity carry risks the model does not price. They are shown with a flag rather than silently dropped, and the app filters them out with one slider.

What the results say:

- **A high gross yield is not a high return.** Only 10 of the 50 highest gross yields make the top 50 by IRR. Saint-Etienne yields 8.9% gross, like Limoges, but returns a full point less. Its market is slack (three months empty between tenants), and fixed costs per m2 (property tax, condominium charges, upkeep) weigh far more on a cheap flat.

  ![Gross yield against IRR](out/charts/yield_vs_irr.png)

- **Leverage makes most outcomes a coin flip on prices.** Paris 11e has a 2.6% median IRR, 0.1% if prices stay flat and 4.8% if they grow 3% a year. Its probability of loss goes from 30% to 49% with flat prices. The momentum in house prices (quarterly AR(1) coefficient of 0.75 to 0.85) spreads 15-year outcomes wide.

  ![Distribution of outcomes](out/charts/irr_distributions.png)

- **The tax regime matters as much as the city.** The flat allowance regime (micro-foncier) taxes 70% of the rent and ignores interest, so it brings the IRR to about 0% everywhere. Under actual expenses, a leveraged investor makes losses in the early years. Unfurnished, the part not due to interest offsets other income up to 10,700 EUR a year. Furnished (LMNP), losses only carry forward, and the depreciation shield is useless while the result is negative. Unfurnished letting under actual expenses wins in 84% of communes. LMNP wins in 16%, mostly expensive ones (median 3,841 EUR/m2 against 2,716).

  | City | Micro-foncier | Unfurnished, actual | Furnished (LMNP) |
  |---|---:|---:|---:|
  | Paris 11e | 0.5% | 2.5% | **2.6%** |
  | Nice | 0.5% | **2.8%** | 2.8% |
  | Lyon 3e | -0.1% | **2.3%** | 1.9% |
  | Saint-Etienne | -0.6% | **3.2%** | 0.8% |
  | Limoges | 0.8% | **4.2%** | 2.9% |

- **Expensive markets behaved like long-duration bonds when rates rose.** The backtest sorts communes by their 2022 gross yield (2022 rent map, 2021-2022 sales) and measures their price change to 2025. The lowest-yield decile lost 6.4% while the highest gained 1.5%. The within-department slope is 0.033 (standard error 0.009). One rate shock is not a law of nature, so this is reported, not built into the simulation.

  ![Backtest of 2022 yields](out/charts/backtest_yield.png)

- **Energy rating bans hit Paris more than its suburbs.** In Paris 11e, 19% of diagnosed flats are rated F or G (small old flats score badly). In Évry-Courcouronnes the figure is 2%. A G flat cannot be let since 2025, F from 2028, E from 2034. The simulation draws the flat's rating from the commune's mix and pays for the works before each ban.

## How it works

| Source | What it gives | Used for |
|---|---|---|
| DVF 2021-2025 (Etalab geolocated files) | 1,812,404 sales of a single flat after cleaning | price levels, local price risk, backtests |
| Carte des loyers 2025 and 2022 (ANIL) | advertised rent per m2 of a T1-T2 flat, with a 95% prediction interval | rent level and the rent a given flat can fetch |
| LOVAC 2026 (Cerema) | private homes vacant, and vacant for more than two years | months empty between tenants |
| ADEME DPE since July 2021 | 9.7 million diagnoses of flats, by rating | risk of rental bans |
| QPV 2024 perimeters (ANCT) | 1,580 priority neighbourhoods | price model and risk flag |
| INSEE notaires indices and IRL, 1992-2026 | quarterly flat prices in four zones, rent index | market risk |

Rent data: "Estimations ANIL, à partir des données du Groupe SeLoger et de leboncoin".

**1. Clean sales** (`immorisk/data.py`). DVF has one row per sale, parcel and premises, with the sale price repeated on every row. Only plain sales of exactly one flat, with optional cellar or parking, are kept. Bundles of flats, flats sold with a shop, off-plan sales and auctions are dropped, as are repeated rows and the 1% tails of price per m2 in each department. Each sale is geolocated inside or outside a priority neighbourhood (point in polygon, 0.6 seconds for 1.8 million points).

**2. Hedonic price model** (`immorisk/prices.py`). The regression is

`log(price/m2) = index[department, quarter] + level[commune] + size and rooms + QPV[zone] + e`

It is fitted by backfitting the two sets of fixed effects on 975,000 sales from 2023 to 2025, with residuals winsorised at three standard deviations. Small flats cost more per m2 (elasticity -0.14). A flat in a priority neighbourhood sells 15% below a comparable flat in Paris, 18% in the suburbs and 28% elsewhere. The reference flat is priced outside priority neighbourhoods.

**3. Small area estimation** (Fay-Herriot, the method statistics offices use for small areas). A commune with 12 sales has a noisy price. Each direct estimate is treated as the truth plus known sampling noise. The truth is modelled as a department mean plus a rent effect plus a commune deviation, and each commune is pulled towards that prediction in proportion to its noise. Within a department, 1% more rent means 1.54% higher prices, so yields fall as markets get dearer. Out of sample (levels estimated on 2023-2024 sales, checked against 2025 sales the estimator never saw), the empirical best linear unbiased predictor (EBLUP) cuts the error by 7% to 13% for communes with 4 to 20 sales:

| Sales in 2023-2024 | Communes | RMSE direct | RMSE EBLUP | Error cut |
|---|---:|---:|---:|---:|
| 4-6 | 14 | 11.2% | 9.7% | 13% |
| 7-10 | 29 | 6.9% | 6.3% | 8% |
| 11-20 | 238 | 8.1% | 7.6% | 7% |
| 21-50 | 758 | 5.9% | 5.6% | 4% |
| 51+ | 1,438 | 4.0% | 4.0% | 1% |

**4. Rents, vacancy and energy** (`immorisk/universe.py`).
- **Rent.** It is the rent map's value minus 1.5 EUR/m2 of recoverable charges. The width of the 95% prediction interval (about +/-23%) gives the spread of rents one flat can fetch.
- **Vacancy.** Months empty between two tenants run from 1 in the tightest market to 3 in the slackest. Markets are ranked on the share of homes empty for more than two years. The short-term vacancy rate is not used: it is highest in big cities, where tenants move often but flats let fast.
- **Energy.** The E, F and G shares come from ADEME diagnoses. Communes with few diagnoses are shrunk towards their department (beta-binomial).

**5. Market model** (`immorisk/market.py`).
- **Zone prices.** Quarterly log returns of the four INSEE flat price indices (Paris, inner suburbs, outer suburbs, rest of France) follow AR(1) processes with correlated shocks. The persistence is 0.75 to 0.85, and quarterly volatilities are 0.8% to 1.2%.
- **Rents.** The rent index (IRL) is part of the same system and is nearly uncorrelated with prices.
- **Growth.** The long-run growth is a scenario (1.5% a year for prices, 1.8% for rents), because 30 years of history, including the 1998-2007 boom, say little about the next 15. The simulation starts from the latest four quarters, so current momentum carries into the first years.
- **Local risk.** Departments and communes drift around their zone by random walks. The department volatility is 1.8% a year, from the gap between each department's DVF index and its INSEE zone net of sampling noise. The commune volatility is 2.4% a year, from 2022-2025 commune price changes around their department net of estimation noise.

**6. Cash flows and taxes** (`immorisk/finance.py`, `immorisk/simulate.py`).
- **Purchase and loan.** The loan is an annuity, with borrower insurance and a guarantee fee. Notary fees are 8%. Selling before maturity triggers the early repayment penalty.
- **Running costs.** They cover condominium charges, property tax, landlord insurance, the letting agent (7%), upkeep, and re-letting fees at the legal cap. Furnished lets add an accountant and the business tax (CFE) above 5,000 EUR of rent.
- **Energy works.** They are paid in the year of the ban. The flat is bought at a discount for its rating and resold at a D value once renovated.
- **Taxation.** Three regimes are modelled:
  - micro-foncier;
  - unfurnished under actual expenses: the land deficit offsets other income up to 10,700 EUR, the interest part only carries forward, and losses expire after ten years;
  - furnished (LMNP): depreciation of the building, purchase costs, furniture and works cannot create a loss, and unused depreciation carries forward.
- **Capital gains.** They get the holding period allowances (income tax exempt after 22 years, social charges after 30). Under LMNP, the depreciation taken is added back to the gain (2025 finance law).

**7. Monte Carlo and ranking** (`immorisk/simulate.py`, `immorisk/rank.py`).
- **Draws.** Each commune gets 2,000 paths. Each path draws the true price level (from the Fay-Herriot posterior), the flat's rent, its energy rating, tenant turnover and vacancy, and the local price paths.
- **Common random numbers.** Zone and rent paths are shared by all communes, so differences between communes are not simulation noise. Each commune's own draws are seeded by its INSEE code, so results do not depend on batching.
- **Regime choice.** Each commune is let under the regime with the highest expected IRR.
- **Rank ranges.** A 90% range comes from redrawing every price level from its posterior 200 times and ranking again.
- **Speed.** The whole run (2,376 communes, 4.75 million simulated investments) takes about a minute.

## Scenarios

Median IRR, with the probability of loss in brackets:

| City | Base | Prices flat | Prices +3% | Loan 4.2% | Loan 2.5% | 10 years | 20 years | Self-managed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Paris 11e | 2.6% (30%) | 0.1% (49%) | 4.8% (18%) | 1.7% (40%) | 3.4% (24%) | 0.9% (46%) | 3.4% (18%) | 3.2% (26%) |
| Lyon 3e | 2.3% (35%) | -0.6% (54%) | 4.5% (20%) | 1.4% (41%) | 2.8% (32%) | 0.4% (49%) | 2.6% (22%) | 2.6% (33%) |
| Bordeaux | 2.3% (35%) | -0.7% (55%) | 4.5% (19%) | 1.4% (41%) | 2.8% (31%) | 0.4% (48%) | 2.7% (26%) | 2.7% (32%) |
| Limoges | 4.2% (21%) | 1.6% (39%) | 6.5% (10%) | 3.5% (26%) | 4.8% (18%) | 2.9% (37%) | 4.4% (12%) | 5.1% (16%) |
| Saint-Etienne | 3.2% (28%) | 0.5% (46%) | 5.3% (14%) | 2.4% (35%) | 3.7% (25%) | 1.4% (44%) | 3.6% (18%) | 3.9% (24%) |

Holding ten years instead of fifteen adds 14 to 16 points to the chance of losing money: purchase costs are not yet amortised, and the capital gains allowances have barely started.

## Limitations

- **Rents.** They are advertised, not signed, and rent caps are not applied. Paris, Lyon, Lille, Bordeaux, Montpellier and parts of the Paris suburbs cap rents, so those cities may look slightly better than they are.
- **Price growth.** It is a scenario. The model estimates dynamics and dispersion, not the long-run trend.
- **Condominiums.** Their quality is not observed. Charges are the same per m2 everywhere, and the national condominium register no longer publishes legal procedures, so distressed condominiums cannot be identified. The priority neighbourhood share is shown as a proxy.
- **Energy.** Diagnoses since July 2021 predate the 2026 change in the electricity conversion factor, which moved some electrically heated flats out of F and G. Works costs and price gaps by rating are orders of magnitude, set as parameters.
- **Vacancy.** The mapping from long-term vacancy to months between tenants is calibrated, not estimated.
- **Coverage.** Alsace-Moselle is not in DVF, and overseas departments are left out.
- **Taxes.** The model has no surtax on large capital gains, and social charges are held at 17.2%.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[app,dev]"
immorisk run          # downloads about 600 MB of open data once, then simulates every commune (about a minute)
immorisk report       # charts in out/charts
immorisk commune Limoges --regime reel --rate 0.035
streamlit run app/streamlit_app.py
pytest
```

The app ranks every commune with filters (zone, liquidity, priority neighbourhoods, price) on a map. It also simulates one commune live with your own tax bracket, loan, down payment, horizon and price scenario, and shows the distribution of outcomes and the year-by-year cash flows.

## Layout

```
immorisk/
  config.py     every assumption in one place (dataclasses)
  data.py       downloads and loaders: DVF, rent map, LOVAC, DPE, QPV, INSEE
  prices.py     hedonic model and Fay-Herriot small area estimation
  universe.py   joins everything by INSEE code
  market.py     AR(1) market model, calibration, simulation
  finance.py    loan, French rental taxation, capital gains, IRR
  simulate.py   Monte Carlo of cash flows, regime choice
  rank.py       rank ranges under estimation uncertainty
  backtest.py   out-of-sample checks
  pipeline.py   end to end run, writes out/results.json and out/communes.csv
  report.py     charts
app/            Streamlit app
tests/          35 tests: taxes, loan, IRR, estimators, market model, cash flow identities
```
