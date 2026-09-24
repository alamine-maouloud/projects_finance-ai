*[Version française](README.fr.md)*

# Card and payment fraud detection, evaluated like a fraud team

`txanomaly` is a fraud-detection benchmark for card and payment transactions. It generates a realistic synthetic bank with known fraud, builds behavioural features that only look at each customer's past, compares first-line rules, Isolation Forest, logistic regression and gradient boosting, and measures them the way a fraud department is measured: alerts per day, precision, and money actually saved.

The data is **synthetic by design**. Every fraud has a known typology and incident, so detection can be measured per scheme, and no customer data is involved.

## Headline results

3,000 customers, 557,553 transactions over 120 days, fraud rate 0.24% (326 incidents). Models learn on 64 days after a 14-day burn-in and are tested on the following 42 days (194,040 transactions, 435 frauds, 108 incidents). Analysts review **0.2% of each day's transactions** (about 10 alerts a day):

| Detector | PR-AUC [95% interval] | Precision | Frauds caught | Incidents detected | Loss prevented | Net savings |
|---|---:|---:|---:|---:|---:|---:|
| Isolation Forest on raw fields (the original approach) | 0.019 [0.010, 0.036] | 6% | 5% | 15% | 8% | EUR 9.7k |
| First-line rules | 0.130 [0.098, 0.162] | 20% | 19% | 50% | 51% | EUR 75.9k |
| Isolation Forest on behavioural features | 0.209 [0.166, 0.258] | 29% | 28% | 63% | 67% | EUR 99.8k |
| Logistic regression | 0.397 [0.320, 0.464] | 41% | 39% | 69% | 68% | EUR 101.6k |
| **Gradient boosting** | **0.864 [0.823, 0.894]** | **70%** | **67%** | **85%** | **76%** | **EUR 112.9k** |

Intervals come from a bootstrap over customers. Net savings are the loss prevented minus EUR 4 of review cost per alert. The random-guess PR-AUC is 0.002 (the fraud rate).

What the benchmark shows:

- **Features matter more than the algorithm.** The same Isolation Forest goes from 0.019 to 0.209 PR-AUC when it sees behavioural features (amount relative to the customer's history, velocity, novelty of merchant, device or payee, impossible travel) instead of raw fields.
- **Labels matter too.** A supervised model trained on past confirmed fraud beats the best unsupervised detector by a factor of four in PR-AUC.
- **Authorised push payment scams stay hard.** The customer's own phone sends the money, so only the payee and the amount look unusual: 50% of these losses are prevented, against 95 to 100% for card testing and account takeover.

Loss prevented by fraud type at the same budget:

| Detector | Card testing | Account takeover | Skimming | Stolen card | Push payment scam |
|---|---:|---:|---:|---:|---:|
| Isolation Forest, raw fields | 0% | 0% | 61% | 0% | 0% |
| Rules | 49% | 96% | 17% | 61% | 32% |
| Gradient boosting | 100% | 95% | 77% | 75% | 50% |

As the budget grows, gradient boosting prevents 49% of losses at 0.1% of transactions reviewed, 76% at 0.2% and 91% at 0.5%.

## Every alert comes with its reasons

Each alert is explained by occlusion: every family of related features (amount, velocity, novelty, geography, session, contactless pattern ...) is reset to its normal value, and the drop in the model score measures its contribution. The top three become sentences an analyst can act on:

| Scheme | Transaction | Reasons given |
|---|---|---|
| Stolen card | in-store, EUR 45.76 | 4 payments just under the contactless limit within 2 hours; 2 payments in the previous hour, 3 in 24 hours; 8.3 h away from the customer's usual hours, at night |
| Card testing | online, EUR 1.20 | 4 payments under EUR 5 in the previous 10 minutes, 6 new merchants in the hour; 6 payments in the previous hour |
| Skimming | cash withdrawal, EUR 460 | first payment at this merchant; 1,375 km/h from the previous card-present payment (impossible travel) |
| Account takeover | bank transfer, EUR 242 | online session from abroad, while the card was last used elsewhere; 24-hour spend 24x the usual payment |
| Push payment scam | bank transfer, EUR 1,300 | a round or just-below-threshold amount, 45.9x the customer's median payment; 24-hour spend 145x the usual payment |

The lead reason matches the scheme: the contactless pattern leads every stolen-card alert, the amount leads every push payment scam alert.

## How it works

**Data** (`txanomaly/data.py`). Customers have a segment, a home, a spending scale, usual shops and websites, active hours, one to three devices and a few regular payees. Five fraud schemes are injected as incidents:

| Scheme | Pattern |
|---|---|
| Card testing | a burst of tiny online payments at new merchants from a new device, then large purchases |
| Account takeover | a new device and a foreign session, high-value purchases or transfers to new payees |
| Skimming | a counterfeit card at shops and ATMs abroad while the real card is used at home |
| Stolen card | local contactless payments just under the no-PIN limit, then larger purchases |
| Push payment scam | the customer's own phone sends one to three large transfers to a new payee |

Genuine customers also travel, pay from abroad, change phones, make in-app micro-payments, pay rent and occasionally send a large transfer to someone new, so no single field gives fraud away: the best single feature reaches a ROC-AUC of 0.74.

**Features** (`txanomaly/features.py`). Twenty-five behavioural features per transaction, computed only from the same customer's earlier transactions: amount against the customer's rolling median (overall and per channel), z-score, counts and spend over 10 minutes, 1 hour and 24 hours, first use of a merchant, device, payee or country, deviation from usual hours, distance from home, speed since the previous card-present payment, foreign session while the card was elsewhere, contactless-limit patterns. Time windows are vectorised with a binary search on a (customer, time) key, which builds all features for 560,000 transactions in 1.7 s. A test checks there is no look-ahead: adding future data never changes a past feature. That test caught a real leak during development (a fallback median computed on the whole data set).

**Detectors** (`txanomaly/models.py`). Weighted first-line rules, Isolation Forest on raw fields, Isolation Forest on behavioural features, balanced logistic regression, and histogram gradient boosting with native categorical handling and early stopping on PR-AUC.

**Evaluation** (`txanomaly/evaluate.py`):

- a temporal split, because a random split leaks each customer's future into training;
- a daily alert budget, so every detector gets the same analyst capacity;
- loss prevented, with the card blocked at its first alert;
- a bootstrap over customers, because frauds cluster on compromised customers;
- permutation importance of the gradient boosting model.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,app]"
pytest -q                          # 18 tests, about 10 s
txanomaly report                   # full benchmark into out/ (about 80 s); --quick for 1,000 customers
txanomaly app                      # investigation dashboard (Streamlit)
txanomaly generate --out data/transactions.csv.gz
```

The dashboard shows the daily alert queue with reasons, performance by fraud type, loss prevented as the budget grows, a customer timeline and the model comparison. The detector, the alert budget and the review cost are adjustable.

## Layout

```
txanomaly/
  data.py        synthetic customers, merchants, genuine behaviour and fraud incidents
  features.py    causal behavioural features
  models.py      rules, Isolation Forest, logistic regression, gradient boosting
  evaluate.py    temporal split, alert budget, loss prevented, bootstrap
  explain.py     reason codes by occlusion
  pipeline.py    end-to-end run
  report.py      benchmark written to out/results.json and out/alerts.csv
  cli.py         txanomaly generate | report | app
app/streamlit_app.py   investigation dashboard
tests/                 data, features (including leakage), evaluation, models, reason codes
```

## Limitations

- Synthetic data: the absolute scores (a PR-AUC of 0.86 in particular) are higher than on real portfolios, where fraud is rarer, more varied and adapts to the controls. The comparison between approaches and the evaluation method carry over; the numbers do not.
- Labels are known immediately. In production, confirmed fraud arrives with a delay of days to weeks and some fraud is never reported, which a production model must account for.
- The model is trained once. Real fraud drifts, which calls for periodic retraining and monitoring of the alert mix.
- Reason codes by occlusion are model-agnostic and cheap, but they are not Shapley values: interactions between families are not split.

## References

- Bolton, R. & Hand, D. (2002). Statistical fraud detection: a review. *Statistical Science*, 17(3).
- Dal Pozzolo, A., Caelen, O., Le Borgne, Y.-A., Waterschoot, S. & Bontempi, G. (2014). Learned lessons in credit card fraud detection from a practitioner perspective. *Expert Systems with Applications*, 41(10).
- Liu, F. T., Ting, K. M. & Zhou, Z.-H. (2008). Isolation Forest. *IEEE ICDM*.
- Saito, T. & Rehmsmeier, M. (2015). The precision-recall plot is more informative than the ROC plot when evaluating binary classifiers on imbalanced datasets. *PLoS ONE*, 10(3).
