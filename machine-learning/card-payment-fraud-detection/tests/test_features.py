import numpy as np
import pandas as pd
import pytest

from txanomaly.features import NUMERIC, build_features


def _toy():
    t0 = pd.Timestamp("2026-01-01 10:00")
    rows = [  # (seconds after t0, channel, merchant, amount, lat, lon, device, payee)
        (0, "POS", 1, 20.0, 48.85, 2.35, "", -1),
        (60, "ECOM", 2, 2.0, np.nan, np.nan, "D0", -1),
        (120, "ECOM", 3, 3.0, np.nan, np.nan, "D0", -1),
        (300, "ECOM", 3, 4.0, np.nan, np.nan, "D1", -1),
        (4000, "POS", 1, 25.0, 48.85, 2.35, "", -1),
        (4000 + 3600, "POS", 4, 30.0, 40.71, -74.0, "", -1),   # New York one hour after Paris
    ]
    tx = pd.DataFrame({
        "txn_id": range(len(rows)), "ts": [t0 + pd.Timedelta(seconds=r[0]) for r in rows], "customer_id": 0,
        "channel": [r[1] for r in rows], "mcc": "retail", "merchant_id": [r[2] for r in rows],
        "merchant_country": ["FR", "FR", "FR", "FR", "FR", "US"], "lat": [r[4] for r in rows],
        "lon": [r[5] for r in rows], "ip_country": ["", "FR", "FR", "FR", "", ""],
        "device_id": [r[6] for r in rows], "payee_id": [r[7] for r in rows], "amount": [r[3] for r in rows],
        "currency": "EUR", "is_fraud": 0, "fraud_type": "", "incident_id": -1})
    cust = pd.DataFrame({"customer_id": [0], "home_country": ["FR"], "h_lat": [48.85], "h_lon": [2.35]})
    return tx, cust


def test_window_counts_and_flags_on_toy_history():
    tx, cust = _toy()
    f = build_features(tx, cust)
    assert f.n_1h.tolist() == [0, 1, 2, 3, 0, 1]
    assert f.n_small_10min.tolist() == [0, 0, 1, 2, 0, 0]
    assert f.is_new_merchant.tolist() == [1, 1, 1, 0, 0, 1]
    assert f.is_new_device.tolist() == [0, 1, 0, 1, 0, 0]
    assert f.speed_kmh.iloc[4] == pytest.approx(0.0)
    assert 5000 < f.speed_kmh.iloc[5] < 6000              # ~5,840 km in one hour
    assert f.foreign.tolist() == [0, 0, 0, 0, 0, 1]


def test_no_look_ahead_leakage(dataset):
    """Appending the future must not change any past feature."""
    tx, cust, _ = dataset
    cut = tx.ts.min() + pd.Timedelta(days=40)
    full = build_features(tx, cust)
    past = build_features(tx[tx.ts < cut], cust)
    a = full.loc[past.index, NUMERIC].astype(float)
    b = past[NUMERIC].astype(float)
    pd.testing.assert_frame_equal(a, b, check_exact=False, rtol=1e-9, atol=1e-9)


def test_features_are_finite(features):
    assert np.isfinite(features[NUMERIC].to_numpy(dtype=float)).all()


def test_fraud_differs_from_genuine_but_no_single_feature_separates(features):
    from sklearn.metrics import roc_auc_score
    aucs = {c: roc_auc_score(features.is_fraud, features[c]) for c in NUMERIC}
    assert max(aucs.values()) < 0.9          # the task is not trivial
    assert aucs["n_small_10min"] > 0.55 and aucs["ip_mismatch_card"] > 0.55
