import pickle

import numpy as np
import pandas as pd
import pytest

from txanomaly.evaluate import daily_budget_alerts, evaluate, temporal_split
from txanomaly.explain import reason_codes, reference_values
from txanomaly.models import GradientBoosting, RuleEngine, all_models


@pytest.fixture(scope="module")
def fitted(features):
    sp = temporal_split(features)
    tr, te = features.loc[sp.train], features.loc[sp.test]
    out = {}
    for m in all_models():
        m.fit(tr)
        out[m.name] = (m, m.score(te))
    return tr, te, out


def test_scores_are_finite(fitted):
    _, te, out = fitted
    for m, s in out.values():
        assert s.shape == (len(te),) and np.isfinite(s).all()


def test_ranking_of_detectors(fitted):
    _, te, out = fitted
    pr = {k: evaluate(te, s, 0.002)["pr_auc"] for k, (_, s) in out.items()}
    assert pr["Gradient boosting"] > pr["Logistic regression"] > pr["Isolation Forest, raw fields"]
    assert pr["Gradient boosting"] > pr["Rules"] > pr["Isolation Forest, raw fields"]
    assert pr["Isolation Forest, behavioural features"] > 3 * pr["Isolation Forest, raw fields"]
    assert evaluate(te, out["Gradient boosting"][1], 0.005)["loss_prevented_share"] > 0.5


def test_rules_fire_on_their_pattern():
    f = pd.DataFrame({"amount_ratio": [1.0, 10.0], "is_new_device": [0, 0], "amount": [20.0, 300.0],
                      "speed_kmh": [0.0, 1500.0], "n_small_10min": [0, 0], "night": [0, 0],
                      "is_new_payee": [0, 0], "n_1h": [0, 0], "n_contactless_2h": [0, 0], "ip_mismatch_card": [0, 0]})
    h = RuleEngine().hits(f)
    assert not h.iloc[0].any()
    assert h.iloc[1][["big_vs_history", "impossible_travel"]].all()


def test_reason_codes_match_typologies(fitted):
    tr, te, out = fitted
    gbm = out["Gradient boosting"][0]
    al = te[daily_budget_alerts(te, out["Gradient boosting"][1], 0.005)]
    rc = reason_codes(gbm, al, reference_values(tr))
    assert rc.reasons.map(len).between(1, 3).all()
    top = rc.families
    stolen = (al.fraud_type == "stolen_card").to_numpy()
    assert top[stolen].map(lambda v: "contactless" in v).mean() > 0.6
    testing = (al.fraud_type == "card_testing").to_numpy()
    expected = {"card_testing", "new_merchant", "velocity", "new_device", "session"}
    assert top[testing].map(lambda v: bool(expected & set(v))).mean() > 0.9


def test_fitted_models_pickle(fitted):
    _, te, out = fitted
    m, s = out["Gradient boosting"]
    m2 = pickle.loads(pickle.dumps(m))
    np.testing.assert_allclose(m2.score(te.head(100)), s[:100])
