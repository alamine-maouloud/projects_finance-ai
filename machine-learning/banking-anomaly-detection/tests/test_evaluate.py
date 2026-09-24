import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score

from txanomaly.evaluate import (
    bootstrap_customers, daily_budget_alerts, evaluate, loss_prevented, temporal_split,
)


def test_temporal_split_is_ordered_and_disjoint(features):
    sp = temporal_split(features)
    tr, te = features.loc[sp.train], features.loc[sp.test]
    assert tr.ts.max() < te.ts.min()
    assert not set(sp.train) & set(sp.test)
    assert (tr.ts - features.ts.min()).dt.days.min() >= sp.burn_in_days


def test_daily_budget():
    ts = pd.to_datetime(["2026-01-01 01:00"] * 1000 + ["2026-01-02 01:00"] * 300)
    f = pd.DataFrame({"ts": ts})
    a = daily_budget_alerts(f, np.random.default_rng(0).random(1300), 0.01)
    assert a[:1000].sum() == 10 and a[1000:].sum() == 3


def test_loss_prevented_blocks_card_after_first_alert():
    f = pd.DataFrame({
        "ts": pd.date_range("2026-01-01", periods=5, freq="h"), "is_fraud": [1, 1, 1, 0, 1],
        "incident_id": [7, 7, 7, -1, 8], "fraud_type": ["x", "x", "x", "", "y"],
        "amount": [10.0, 200.0, 500.0, 50.0, 80.0]})
    alert = np.array([False, True, False, True, False])
    inc = loss_prevented(f, alert)
    assert inc.loc[7, "prevented"] == 700.0 and inc.loc[7, "total"] == 710.0
    assert inc.loc[8, "prevented"] == 0.0 and not inc.loc[8, "detected"]


def test_metrics_match_sklearn_and_ci_brackets(features):
    rng = np.random.default_rng(1)
    te = features.loc[temporal_split(features).test]
    s = te.amount_ratio.to_numpy() + rng.normal(0, 0.1, len(te))
    e = evaluate(te, s, 0.005)
    assert e["pr_auc"] == pytest.approx(average_precision_score(te.is_fraud, s))
    assert 0 <= e["loss_prevented_share"] <= 1
    ci = bootstrap_customers(te, s, 0.005, n_boot=40)
    assert ci["pr_auc_ci"][0] <= e["pr_auc"] <= ci["pr_auc_ci"][1]
