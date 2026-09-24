"""Behavioural features, computed strictly from each customer's past.

A transaction is scored at authorisation time, so every feature of row i may
only use transactions of the same customer that happened *before* it. Time
windows are evaluated for all rows at once: rows are sorted by (customer,
time), which makes key = customer * BIG + t strictly increasing, and the
start of each window is found by binary search on that key. Window sums then
come from cumulative sums. `tests/test_features.py` checks that appending
future data never changes a past feature (no look-ahead leakage).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

NUMERIC = [
    "log_amount", "amount_ratio", "amount_ratio_channel", "amount_z",
    "n_1h", "n_24h", "amount_24h_ratio", "n_small_10min", "n_new_merchant_1h",
    "log_secs_since_prev", "hour_dev", "dist_home_km", "speed_kmh", "n_prev",
    "is_new_merchant", "is_new_device", "is_new_payee", "is_new_country",
    "foreign", "ip_foreign", "ip_mismatch_card", "night", "near_contactless_limit",
    "round_amount", "n_contactless_2h",
]
CATEGORICAL = ["channel", "mcc"]
BIG = 1e9


def _haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _window(key: np.ndarray, width: float) -> np.ndarray:
    """Index of the first row inside (t - width, t) for every row."""
    return np.searchsorted(key, key - width, side="left")


def _rolling_past(values: pd.Series, groups: pd.Series, n: int, fn: str, min_periods: int = 3) -> pd.Series:
    """Statistic over the previous ``n`` rows of the same group (row excluded)."""
    past = values.groupby(groups, sort=False).shift(1)
    roll = past.groupby(groups, sort=False).rolling(n, min_periods=min_periods)
    out = getattr(roll, fn)()
    return out.reset_index(level=0, drop=True).reindex(values.index)


def _causal_channel_prior(t: np.ndarray, channel: np.ndarray, log_amount: np.ndarray) -> np.ndarray:
    """Geometric-mean amount of all *earlier* transactions of the same channel
    (all customers), used until a customer has enough history of their own."""
    order = np.argsort(t, kind="stable")
    prior = np.full(t.size, np.expm1(3.3))                  # about EUR 26 before any data
    for ch in np.unique(channel):
        idx = order[channel[order] == ch]
        cs = np.cumsum(log_amount[idx])
        k = np.arange(idx.size)
        prev_mean = np.where(k > 0, (cs - log_amount[idx]) / np.maximum(k, 1), 3.3)
        prior[idx] = np.expm1(prev_mean)
    return prior


def build_features(tx: pd.DataFrame, customers: pd.DataFrame) -> pd.DataFrame:
    """Feature table aligned with ``tx`` (same index), plus the label columns."""
    df = tx.sort_values(["customer_id", "ts", "txn_id"], kind="stable").copy()
    home = customers.set_index("customer_id")[["home_country", "h_lat", "h_lon"]]
    df = df.join(home, on="customer_id")
    cid = df["customer_id"]
    t = (df["ts"] - df["ts"].min()).dt.total_seconds().to_numpy()
    key = cid.to_numpy() * BIG + t
    pos = np.arange(len(df))
    amt = df["amount"].to_numpy()
    out = pd.DataFrame(index=df.index)

    # amount relative to the customer's own history
    la = np.log1p(df["amount"])
    out["log_amount"] = la
    med = _rolling_past(df["amount"], cid, 30, "median")
    glob_med = pd.Series(_causal_channel_prior(t, df["channel"].to_numpy(), la.to_numpy()), index=df.index)
    out["amount_ratio"] = df["amount"] / med.fillna(glob_med).clip(lower=1.0)
    grp_ch = cid.astype(str) + "|" + df["channel"]
    med_ch = _rolling_past(df["amount"], grp_ch, 20, "median", min_periods=2)
    out["amount_ratio_channel"] = df["amount"] / med_ch.fillna(med).fillna(glob_med).clip(lower=1.0)
    mu = _rolling_past(la, cid, 50, "mean")
    sd = _rolling_past(la, cid, 50, "std").clip(lower=0.25)
    out["amount_z"] = ((la - mu) / sd).fillna(0.0)

    # velocity: counts and sums over past windows (current row excluded)
    csum_amt = np.concatenate([[0.0], np.cumsum(amt)])
    for name, width in (("n_1h", 3600.0), ("n_24h", 86400.0)):
        lo = _window(key, width)
        out[name] = pos - lo
    lo24 = _window(key, 86400.0)
    past_24 = csum_amt[pos] - csum_amt[lo24]
    out["amount_24h_ratio"] = (past_24 + amt) / med.fillna(glob_med).clip(lower=1.0).to_numpy()
    small = (amt < 5.0).astype(float)
    csum_small = np.concatenate([[0.0], np.cumsum(small)])
    lo10 = _window(key, 600.0)
    out["n_small_10min"] = csum_small[pos] - csum_small[lo10]

    # first-seen flags: merchant, device, payee, country
    def first_seen(col, valid):
        seen = df.groupby([cid, df[col]], sort=False).cumcount() == 0
        return (seen & valid).astype(float)

    new_m = first_seen("merchant_id", df["merchant_id"] >= 0)
    out["is_new_merchant"] = new_m
    csum_new = np.concatenate([[0.0], np.cumsum(new_m.to_numpy())])
    lo1 = _window(key, 3600.0)
    out["n_new_merchant_1h"] = csum_new[pos] - csum_new[lo1]
    out["is_new_device"] = first_seen("device_id", df["device_id"] != "")
    out["is_new_payee"] = first_seen("payee_id", df["payee_id"] >= 0)
    place = np.where(df["channel"].isin(["ECOM", "P2P"]), df["ip_country"], df["merchant_country"])
    df["_place"] = place
    out["is_new_country"] = first_seen("_place", pd.Series(place, index=df.index) != "")
    out["n_prev"] = df.groupby(cid, sort=False).cumcount()

    # timing
    prev_t = pd.Series(t, index=df.index).groupby(cid, sort=False).shift(1)
    out["log_secs_since_prev"] = np.log1p((t - prev_t).fillna(30 * 86400.0))
    hour = df["ts"].dt.hour + df["ts"].dt.minute / 60
    ang = 2 * np.pi * hour / 24
    s_mean = _rolling_past(np.sin(ang), cid, 50, "mean")
    c_mean = _rolling_past(np.cos(ang), cid, 50, "mean")
    usual = (np.arctan2(s_mean, c_mean) % (2 * np.pi)) * 24 / (2 * np.pi)
    diff = np.abs(hour - usual.fillna(hour))
    out["hour_dev"] = np.minimum(diff, 24 - diff)
    out["night"] = ((hour >= 0) & (hour < 5)).astype(float)

    # geography: card-present chain for impossible travel
    present = df["channel"].isin(["POS", "ATM"]).to_numpy()
    dist_home = _haversine(df["h_lat"], df["h_lon"], df["lat"], df["lon"])
    out["dist_home_km"] = np.where(present, dist_home, 0.0)
    cp = df.loc[present, ["customer_id", "lat", "lon"]].copy()
    cp["t"] = t[present]
    g = cp.groupby("customer_id", sort=False)
    d = _haversine(g["lat"].shift(1), g["lon"].shift(1), cp["lat"], cp["lon"])
    hrs = (cp["t"] - g["t"].shift(1)) / 3600.0
    speed = (d / hrs.clip(lower=0.25)).fillna(0.0)
    out["speed_kmh"] = 0.0
    out.loc[cp.index, "speed_kmh"] = speed.to_numpy()
    out["foreign"] = ((df["merchant_country"] != "") & (df["merchant_country"] != df["home_country"])
                      & present).astype(float)
    remote = ~present
    out["ip_foreign"] = (remote & (df["ip_country"] != df["home_country"])).astype(float)
    # a remote session from one country while the card was just used in another
    last_cp_country = pd.Series(np.where(present, df["merchant_country"], None), index=df.index)
    last_cp_country = last_cp_country.groupby(cid, sort=False).ffill()
    last_cp_country = last_cp_country.groupby(cid, sort=False).shift(1)
    out["ip_mismatch_card"] = (remote & last_cp_country.notna() & (df["ip_country"] != last_cp_country)
                               & (df["ip_country"] != df["home_country"])).astype(float)

    # payment patterns
    out["near_contactless_limit"] = ((df["channel"] == "POS") & (amt >= 35) & (amt < 50)).astype(float)
    csum_cl = np.concatenate([[0.0], np.cumsum(out["near_contactless_limit"].to_numpy())])
    lo2h = _window(key, 7200.0)
    out["n_contactless_2h"] = csum_cl[pos] - csum_cl[lo2h]
    out["round_amount"] = (((amt % 100) == 0) & (amt >= 500) | ((amt >= 900) & (amt < 1000))).astype(float)

    for c in CATEGORICAL:
        out[c] = df[c]
    for c in ("txn_id", "ts", "customer_id", "amount", "is_fraud", "fraud_type", "incident_id"):
        out[c] = df[c]
    out = out.reindex(tx.index)
    return out
