"""Full benchmark, written to out/: results.json, alerts.csv and the run
artefacts the dashboard reads.

    python -m txanomaly.report [--customers N] [--days N] [--quick]
"""

from __future__ import annotations

import argparse
import json
import pickle
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance

from .data import FRAUD_TYPES, Config
from .evaluate import bootstrap_customers, budget_curve, daily_budget_alerts, evaluate, pr_curve
from .explain import reason_codes, reference_values
from .features import CATEGORICAL, NUMERIC
from .models import GradientBoosting
from .pipeline import run

BUDGETS = (0.001, 0.002, 0.005, 0.01)
HEADLINE_BUDGET = 0.002


def _r(x, nd=4):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), nd)


def build(cfg: Config, out_dir: Path, quick: bool = False) -> dict:
    t0 = time.perf_counter()
    r = run(cfg)
    te, tr = r.test, r.train
    y = te["is_fraud"].to_numpy()
    days = te["ts"].dt.floor("D").nunique()
    models = []
    for m in r.models:
        s = r.scores[m.name]
        by_budget = {str(b): {k: (_r(v) if not isinstance(v, dict) else
                                  {t: {kk: _r(vv) for kk, vv in d.items()} for t, d in v.items()})
                              for k, v in evaluate(te, s, b).items()} for b in BUDGETS}
        ci = bootstrap_customers(te, s, HEADLINE_BUDGET, n_boot=60 if quick else 300)
        models.append({"name": m.name, "seconds": _r(r.timings[m.name], 2), "by_budget": by_budget,
                       "pr_auc_ci": [_r(x) for x in ci["pr_auc_ci"]],
                       "loss_prevented_ci": [_r(x) for x in ci["loss_prevented_ci"]],
                       "pr_curve": [[_r(a, 4), _r(b, 4)] for a, b in pr_curve(y, s)],
                       "budget_curve": [{k: _r(v) for k, v in row.items()} for row in
                                        budget_curve(te, s, np.round(np.geomspace(0.0005, 0.03, 16), 5))]})

    gbm = next(m for m in r.models if isinstance(m, GradientBoosting))
    s = r.scores[gbm.name]
    alert = daily_budget_alerts(te, s, HEADLINE_BUDGET)
    al = te[alert].copy()
    rc = reason_codes(gbm, al, reference_values(tr))
    al["score"] = rc["score"]
    al["reasons"] = rc["reasons"].map(lambda v: " | ".join(v))
    al["reason_families"] = rc["families"].map(lambda v: " | ".join(v))
    out_dir.mkdir(parents=True, exist_ok=True)
    cols = ["txn_id", "ts", "customer_id", "channel", "mcc", "amount", "score", "reasons", "reason_families",
            "is_fraud", "fraud_type", "incident_id"]
    al.sort_values("score", ascending=False)[cols].to_csv(out_dir / "alerts.csv", index=False)

    # which reason families explain each typology (share of alerts led by it)
    lead = al.assign(first=rc["families"].map(lambda v: v[0] if v else "none"),
                     kind=al["fraud_type"].replace("", "genuine"))
    reason_mix = {k: g["first"].value_counts(normalize=True).round(3).head(4).to_dict()
                  for k, g in lead.groupby("kind")}

    # permutation importance on the test period (drop in PR-AUC)
    sub = te.sample(n=min(len(te), 60_000 if quick else 150_000), random_state=0)
    sub = pd.concat([sub, te[te["is_fraud"] == 1]]).drop_duplicates("txn_id")
    pi = permutation_importance(gbm.pipe, sub[NUMERIC + CATEGORICAL], sub["is_fraud"],
                                scoring="average_precision", n_repeats=2 if quick else 4, random_state=0,
                                n_jobs=-1)
    importance = sorted(zip(NUMERIC + CATEGORICAL, pi.importances_mean), key=lambda x: -x[1])

    daily = pd.DataFrame({"day": te["ts"].dt.floor("D"), "fraud": y, "alert": alert,
                          "tp": alert & (y == 1)}).groupby("day").sum()
    results = {
        "config": asdict(cfg),
        "data": {"transactions": len(r.tx), "customers": len(r.customers), "fraud_rate": _r(r.tx["is_fraud"].mean(), 5),
                 "incidents": int(r.tx["incident_id"].nunique() - 1),
                 "by_type": {t: {"transactions": int((r.tx.fraud_type == t).sum()),
                                 "amount": _r(r.tx.loc[r.tx.fraud_type == t, "amount"].sum(), 0)} for t in FRAUD_TYPES},
                 "train_rows": len(tr), "test_rows": len(te), "test_frauds": int(y.sum()),
                 "test_incidents": int(te["incident_id"].nunique() - 1), "test_days": int(days),
                 "burn_in_days": r.split.burn_in_days, "train_days": r.split.train_days},
        "timings": {k: _r(v, 2) for k, v in r.timings.items()},
        "budgets": list(BUDGETS), "headline_budget": HEADLINE_BUDGET,
        "models": models,
        "importance": [[k, _r(v, 5)] for k, v in importance],
        "reason_mix": reason_mix,
        "examples": al.sort_values("score", ascending=False).groupby(al["fraud_type"].replace("", "genuine"))
                      .head(2)[["txn_id", "channel", "mcc", "amount", "fraud_type", "reasons"]]
                      .assign(amount=lambda d: d.amount.round(2)).to_dict("records"),
        "daily": {"day": [d.strftime("%Y-%m-%d") for d in daily.index], "fraud": daily.fraud.astype(int).tolist(),
                  "alerts": daily.alert.astype(int).tolist(), "caught": daily.tp.astype(int).tolist()},
        "seconds": _r(time.perf_counter() - t0, 1),
    }
    (out_dir / "results.json").write_text(json.dumps(results, indent=1, default=str))
    # what the dashboard needs: the test period, its scores and the fitted models
    slim = te.copy()
    for c in NUMERIC:
        slim[c] = slim[c].astype("float32")
    with open(out_dir / "run.pkl", "wb") as fh:
        pickle.dump({"test": slim, "scores": r.scores, "models": r.models, "reference": reference_values(tr),
                     "customers": r.customers}, fh, protocol=5)
    return results


def print_summary(res: dict) -> None:
    d = res["data"]
    b = str(res["headline_budget"])
    print(f"{d['transactions']:,} transactions, {d['customers']:,} customers, fraud rate {d['fraud_rate']:.3%}, "
          f"{d['incidents']} incidents; test: {d['test_frauds']} frauds in {d['test_incidents']} incidents over {d['test_days']} days")
    print(f"\n{'model':<40}{'PR-AUC':>16}{'ROC':>7}{'prec':>7}{'recall':>8}{'loss prev.':>12}{'net EUR':>11}")
    for m in res["models"]:
        e = m["by_budget"][b]
        lo, hi = m["pr_auc_ci"]
        print(f"{m['name']:<40}{e['pr_auc']:>7.3f} [{lo:.2f},{hi:.2f}]{e['roc_auc']:>7.3f}{e['precision']:>7.2f}"
              f"{e['recall']:>8.2f}{e['loss_prevented_share']:>12.2f}{e['net_savings']:>11,.0f}")
    print(f"\n(at an alert budget of {float(b):.1%} of daily transactions; {res['seconds']}s)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--customers", type=int, default=3000)
    ap.add_argument("--days", type=int, default=120)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="out")
    ap.add_argument("--quick", action="store_true", help="1,000 customers, fewer bootstrap draws")
    a = ap.parse_args(argv)
    cfg = Config(n_customers=1000 if a.quick else a.customers, n_days=a.days, seed=a.seed)
    print_summary(build(cfg, Path(a.out), quick=a.quick))


if __name__ == "__main__":
    main()
