"""Synthetic card and payment transactions with labelled fraud.

Genuine behaviour is customer-specific: each customer has a home location, a
spending scale, usual merchants, active hours, devices and payees, and
sometimes travels abroad (so "foreign" is not a fraud signal on its own).

Fraud is injected as *incidents*, each a short sequence of transactions that
follows a known typology:

card_testing        a burst of tiny e-commerce payments at new merchants from a
                    new device, then a few large purchases
account_takeover    a new device abroad, several high-value online purchases or
                    transfers to new payees, often at night
skimming            a counterfeit card used at shops and ATMs far from where the
                    customer is transacting at the same time (impossible travel)
stolen_card         a burst of local contactless payments just under the
                    no-PIN limit, then larger in-store purchases
app_scam            authorised push payment scam: the customer's own device sends
                    one to three large transfers to a new payee

The ground truth (fraud type and incident id) is kept so that detection can
be measured per typology and per incident.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MCC = {
    # category: (amount multiplier, share of card-present, weight)
    "grocery": (0.8, 0.95, 20),
    "restaurants": (1.0, 0.85, 14),
    "fuel": (1.3, 1.0, 7),
    "retail": (1.6, 0.7, 12),
    "pharmacy": (0.7, 0.95, 4),
    "transport": (0.6, 0.6, 6),
    "entertainment": (1.3, 0.4, 5),
    "online_services": (0.6, 0.0, 9),
    "electronics": (4.0, 0.3, 3),
    "travel": (6.0, 0.1, 2),
    "luxury": (8.0, 0.8, 1),
    "gambling": (2.0, 0.1, 1),
    "crypto_exchange": (5.0, 0.0, 0.5),
}
CATEGORIES = tuple(MCC)

COUNTRIES = {  # code: (lat, lon, weight as home country)
    "FR": (46.6, 2.4, 40), "DE": (51.2, 10.4, 10), "ES": (40.4, -3.7, 8), "IT": (42.8, 12.6, 8),
    "GB": (52.4, -1.5, 7), "BE": (50.6, 4.6, 5), "NL": (52.2, 5.3, 5), "PT": (39.6, -8.0, 3),
    "CH": (46.8, 8.2, 3), "US": (39.8, -98.6, 4), "MA": (31.8, -7.1, 3), "SN": (14.5, -14.5, 2),
    "AE": (24.0, 54.0, 1), "TR": (39.0, 35.2, 1),
}
CODES = tuple(COUNTRIES)
FRAUD_TYPES = ("card_testing", "account_takeover", "skimming", "stolen_card", "app_scam")

SEGMENTS = {  # name: (share, median basket EUR, transactions per day, e-commerce share)
    "student": (0.20, 14.0, 1.0, 0.45),
    "mass": (0.50, 28.0, 1.3, 0.30),
    "affluent": (0.22, 60.0, 1.6, 0.35),
    "business": (0.08, 110.0, 2.2, 0.40),
}


@dataclass(frozen=True)
class Config:
    n_customers: int = 3000
    n_days: int = 120
    start: str = "2026-01-05"
    n_merchants: int = 1600
    incidents_per_1000_customers: float = 110.0
    fraud_mix: tuple[float, ...] = (0.24, 0.20, 0.18, 0.20, 0.18)
    seed: int = 7


def _haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def _merchants(cfg: Config, rng: np.random.Generator) -> pd.DataFrame:
    cats = np.array(CATEGORIES)
    w = np.array([MCC[c][2] for c in cats], dtype=float)
    cat = rng.choice(cats, size=cfg.n_merchants, p=w / w.sum())
    cw = np.array([COUNTRIES[c][2] for c in CODES], dtype=float)
    country = rng.choice(np.array(CODES), size=cfg.n_merchants, p=cw / cw.sum())
    lat = np.array([COUNTRIES[c][0] for c in country]) + rng.normal(0, 1.5, cfg.n_merchants)
    lon = np.array([COUNTRIES[c][1] for c in country]) + rng.normal(0, 2.0, cfg.n_merchants)
    online = np.array([MCC[c][1] for c in cat]) < rng.random(cfg.n_merchants)
    return pd.DataFrame({"merchant_id": np.arange(cfg.n_merchants), "mcc": cat, "merchant_country": country,
                         "m_lat": lat, "m_lon": lon, "online": online})


def _customers(cfg: Config, rng: np.random.Generator) -> pd.DataFrame:
    n = cfg.n_customers
    seg_names = np.array(list(SEGMENTS))
    seg = rng.choice(seg_names, size=n, p=[SEGMENTS[s][0] for s in seg_names])
    cw = np.array([COUNTRIES[c][2] for c in CODES], dtype=float)
    home = rng.choice(np.array(CODES), size=n, p=cw / cw.sum())
    lat = np.array([COUNTRIES[c][0] for c in home]) + rng.normal(0, 1.2, n)
    lon = np.array([COUNTRIES[c][1] for c in home]) + rng.normal(0, 1.6, n)
    scale = np.array([SEGMENTS[s][1] for s in seg]) * np.exp(rng.normal(0, 0.35, n))
    rate = np.array([SEGMENTS[s][2] for s in seg]) * np.exp(rng.normal(0, 0.3, n))
    ecom = np.clip(np.array([SEGMENTS[s][3] for s in seg]) + rng.normal(0, 0.08, n), 0.05, 0.8)
    return pd.DataFrame({
        "customer_id": np.arange(n), "segment": seg, "home_country": home, "h_lat": lat, "h_lon": lon,
        "scale": scale, "rate": rate, "ecom_share": ecom,
        # 8% night-shift workers, whose normal activity is around midnight
        "hour_center": np.where(rng.random(n) < 0.08, rng.uniform(21.5, 26.0, n) % 24,
                                np.clip(rng.normal(14.0, 2.5, n), 9, 20)),
        "hour_sd": rng.uniform(2.5, 4.5, n),
        "n_devices": rng.choice([1, 2, 3], size=n, p=[0.55, 0.35, 0.10]),
        "travel_rate": rng.uniform(0.0, 0.05, n),      # trips started per day
        # a genuine new phone for some customers, and a monthly rent transfer
        "new_device_day": np.where(rng.random(n) < 0.3, rng.integers(10, cfg.n_days, n), cfg.n_days + 1),
        "rent": np.where(rng.random(n) < 0.4, np.round(scale * rng.uniform(8, 20, n), -1), 0.0),
        # look-alikes of fraud that are genuine
        "micro_rate": np.where(rng.random(n) < 0.35, rng.uniform(1 / 40, 1 / 10, n), 0.0),
        "big_transfer_rate": np.where(rng.random(n) < 0.3, rng.uniform(1 / 150, 1 / 50, n), 0.0),
    })


def _genuine(cfg: Config, cust: pd.DataFrame, merch: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    days = cfg.n_days
    by_country = {c: merch.index[(merch.merchant_country == c) & ~merch.online].to_numpy() for c in CODES}
    online_ids = merch.index[merch.online].to_numpy()
    mult = merch.mcc.map(lambda c: MCC[c][0]).to_numpy()
    rows = []
    for c in cust.itertuples(index=False):
        local = by_country[c.home_country]
        # a customer's usual shops and sites, with a popularity skew
        usual_local = rng.choice(local, size=min(25, local.size), replace=False)
        usual_online = rng.choice(online_ids, size=12, replace=False)
        pref_local = rng.dirichlet(np.full(usual_local.size, 0.6))
        pref_online = rng.dirichlet(np.full(usual_online.size, 0.6))
        payees = 1000 * c.customer_id + np.arange(4)
        # trips abroad: (start day, length, country)
        trips = []
        d = rng.exponential(1 / max(c.travel_rate, 1e-6))
        while d < days:
            length = int(rng.integers(3, 11))
            dest = rng.choice([x for x in CODES if x != c.home_country])
            trips.append((int(d), length, dest))
            d += length + rng.exponential(1 / max(c.travel_rate, 1e-6))
        abroad = np.full(days, None, dtype=object)
        for s, l, dest in trips:
            abroad[s:s + l] = dest
        n_per_day = rng.poisson(c.rate, days)

        def device(day):
            if day >= c.new_device_day and rng.random() < 0.6:
                return f"D{c.customer_id}-new"
            return f"D{c.customer_id}-{rng.integers(c.n_devices)}"

        def ip(day):
            if rng.random() < 0.02:                      # VPN / roaming noise
                return str(rng.choice(np.array(CODES)))
            return abroad[day] if abroad[day] is not None else c.home_country

        if c.rent > 0:                                   # rent on the first working day of the month
            for day in range(1, days, 30):
                rows.append((day * 86400 + rng.uniform(8, 11) * 3600, c.customer_id, -1, "P2P", float(c.rent),
                             device(day), int(1000 * c.customer_id + 99), ip(day)))
        # genuine bursts of in-app micro-payments at a usual site
        for day in np.flatnonzero(rng.random(days) < c.micro_rate):
            m = usual_online[rng.choice(usual_online.size, p=pref_online)]
            t = day * 86400 + (rng.normal(c.hour_center, c.hour_sd) % 24) * 3600
            for _ in range(rng.integers(2, 6)):
                rows.append((t, c.customer_id, int(m), "ECOM", round(rng.uniform(0.49, 4.99), 2), device(day), -1, ip(day)))
                t += rng.uniform(30, 400)
        # genuine one-off large transfers to a new payee (car, deposit, notary)
        for day in np.flatnonzero(rng.random(days) < c.big_transfer_rate):
            amt = float(rng.choice([round(rng.uniform(5, 50)) * 100.0, rng.uniform(500, 3000)]))
            rows.append((day * 86400 + rng.uniform(9, 18) * 3600, c.customer_id, -1, "P2P", round(amt, 2),
                         device(day), int(1000 * c.customer_id + 100 + rng.integers(0, 900)), ip(day)))
        # a new phone often comes with a large online purchase the same day
        if c.new_device_day < days and rng.random() < 0.35:
            big = online_ids[mult[online_ids] >= 4.0]
            day = int(c.new_device_day)
            rows.append((day * 86400 + (rng.normal(c.hour_center, c.hour_sd) % 24) * 3600, c.customer_id,
                         int(rng.choice(big)), "ECOM", round(c.scale * rng.uniform(8, 30), 2), f"D{c.customer_id}-new",
                         -1, ip(day)))
        for day in np.flatnonzero(n_per_day):
            k = n_per_day[day]
            hours = rng.normal(c.hour_center, c.hour_sd, k) % 24
            secs = day * 86400 + hours * 3600
            kind = rng.random(k)
            for j in range(k):
                ch_u = kind[j]
                if ch_u < c.ecom_share:
                    ch = "ECOM"
                    m = usual_online[rng.choice(usual_online.size, p=pref_online)] if rng.random() < 0.85 \
                        else rng.choice(online_ids)
                    dev = device(day)
                    payee = -1
                elif ch_u < c.ecom_share + 0.05:
                    ch, m, dev = "P2P", -1, device(day)
                    payee = int(payees[rng.integers(payees.size)]) if rng.random() < 0.9 \
                        else int(1000 * c.customer_id + rng.integers(4, 60))
                else:
                    ch = "ATM" if rng.random() < 0.08 else "POS"
                    pool = by_country[abroad[day]] if abroad[day] is not None else None
                    if pool is not None and pool.size:
                        m = rng.choice(pool)
                    else:
                        m = usual_local[rng.choice(usual_local.size, p=pref_local)] if rng.random() < 0.8 \
                            else rng.choice(local)
                    dev, payee = "", -1
                if ch == "ATM":
                    amt = 20.0 * rng.integers(1, 11)
                elif ch == "P2P":
                    amt = round(float(np.exp(rng.normal(np.log(c.scale * 2.5), 0.9))), 0)
                else:
                    amt = float(np.exp(rng.normal(np.log(c.scale * mult[m]), 0.75)))
                    if rng.random() < 0.004:                     # rare genuine big-ticket purchase
                        amt *= rng.uniform(8, 25)
                rows.append((secs[j], c.customer_id, int(m), ch, round(amt, 2), dev, payee,
                             ip(day) if ch in ("ECOM", "P2P") else ""))
    return pd.DataFrame(rows, columns=["t", "customer_id", "merchant_id", "channel", "amount", "device_id",
                                       "payee_id", "ip_country"])


def _incident(kind: str, c, t0: float, merch: pd.DataFrame, rng: np.random.Generator, iid: int) -> list:
    online = merch.index[merch.online].to_numpy()

    rows = []

    foreign_ip = str(rng.choice(np.array([x for x in CODES if x != c.home_country])))

    def add(t, m, ch, amt, dev="", payee=-1):
        if ch in ("ECOM", "P2P"):
            ip = foreign_ip if kind == "account_takeover" or (kind == "card_testing" and rng.random() < 0.5) \
                else c.home_country
        else:
            ip = ""
        rows.append((t, c.customer_id, int(m), ch, round(float(amt), 2), dev, payee, ip, 1, kind, iid))

    if kind == "card_testing":
        dev = f"X{iid}"
        t = t0
        for _ in range(rng.integers(3, 8)):
            add(t, rng.choice(online), "ECOM", rng.uniform(0.5, 4.99), dev)
            t += rng.uniform(20, 240)
        t += rng.uniform(1800, 20 * 3600)
        big = merch.index[merch.online & merch.mcc.isin(["electronics", "luxury", "travel"])].to_numpy()
        for _ in range(rng.integers(1, 3)):
            add(t, rng.choice(big), "ECOM", rng.uniform(150, 1500), dev)
            t += rng.uniform(300, 5400)
    elif kind == "account_takeover":
        dev = f"X{iid}"
        t = t0
        risky = merch.index[merch.online & merch.mcc.isin(["electronics", "crypto_exchange", "luxury", "gambling"])].to_numpy()
        for _ in range(rng.integers(2, 6)):
            if rng.random() < 0.4:
                add(t, -1, "P2P", round(c.scale * rng.uniform(4, 25), 0), dev, int(9_000_000 + iid * 10 + rng.integers(3)))
            else:
                add(t, rng.choice(risky), "ECOM", c.scale * rng.uniform(3, 20), dev)
            t += rng.uniform(300, 3 * 3600)
    elif kind == "skimming":
        far = merch.index[~merch.online & (merch.merchant_country != c.home_country)].to_numpy()
        t = t0
        for _ in range(rng.integers(2, 7)):
            if rng.random() < 0.5:
                add(t, rng.choice(far), "ATM", 20.0 * rng.integers(5, 26))
            else:
                add(t, rng.choice(far), "POS", c.scale * rng.uniform(1.5, 8))
            t += rng.uniform(600, 10 * 3600)
    elif kind == "stolen_card":
        local = merch.index[~merch.online & (merch.merchant_country == c.home_country)].to_numpy()
        t = t0
        for _ in range(rng.integers(2, 6)):                      # contactless without PIN
            add(t, rng.choice(local), "POS", rng.uniform(35, 49.99))
            t += rng.uniform(120, 1800)
        shops = merch.index[~merch.online & (merch.merchant_country == c.home_country)
                            & merch.mcc.isin(["electronics", "luxury", "retail"])].to_numpy()
        for _ in range(rng.integers(0, 3)):
            add(t, rng.choice(shops if shops.size else local), "POS", c.scale * rng.uniform(3, 12))
            t += rng.uniform(600, 3600)
    elif kind == "app_scam":
        dev = f"D{c.customer_id}-0"                              # the customer's own phone
        payee = int(8_000_000 + iid)
        t = t0
        for _ in range(rng.integers(1, 4)):
            amt = rng.choice([rng.uniform(900, 999), round(rng.uniform(5, 30)) * 100.0])
            add(t, -1, "P2P", amt, dev, payee)
            t += rng.uniform(3600, 36 * 3600)
    else:
        raise ValueError(kind)
    return rows


def generate(cfg: Config = Config()) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (transactions, customers, merchants). Transactions are sorted by time."""
    rng = np.random.default_rng(cfg.seed)
    merch = _merchants(cfg, rng)
    cust = _customers(cfg, rng)
    tx = _genuine(cfg, cust, merch, rng)
    tx["is_fraud"] = 0
    tx["fraud_type"] = ""
    tx["incident_id"] = -1
    n_inc = rng.poisson(cfg.incidents_per_1000_customers * cfg.n_customers / 1000)
    kinds = rng.choice(np.array(FRAUD_TYPES), size=n_inc, p=np.array(cfg.fraud_mix) / sum(cfg.fraud_mix))
    victims = rng.choice(cfg.n_customers, size=n_inc, replace=True)
    starts = rng.uniform(3 * 86400, (cfg.n_days - 2) * 86400, n_inc)   # leave some history first
    fr = []
    for i, (k, v, t0) in enumerate(zip(kinds, victims, starts)):
        fr.extend(_incident(k, cust.iloc[v], t0, merch, rng, i))
    fraud = pd.DataFrame(fr, columns=list(tx.columns))
    tx = pd.concat([tx, fraud], ignore_index=True)
    tx = tx[tx.t < cfg.n_days * 86400].sort_values(["t", "customer_id"], kind="stable").reset_index(drop=True)
    tx.insert(0, "txn_id", np.arange(len(tx)))
    tx["ts"] = pd.Timestamp(cfg.start) + pd.to_timedelta(tx.t, unit="s")
    m = merch.set_index("merchant_id")
    ok = tx.merchant_id >= 0
    tx["mcc"] = np.where(ok, m.mcc.reindex(tx.merchant_id).to_numpy(), "p2p_transfer")
    tx["merchant_country"] = np.where(ok, m.merchant_country.reindex(tx.merchant_id).to_numpy(), "")
    tx["lat"] = np.where(ok, m.m_lat.reindex(tx.merchant_id).to_numpy(), np.nan)
    tx["lon"] = np.where(ok, m.m_lon.reindex(tx.merchant_id).to_numpy(), np.nan)
    tx["currency"] = "EUR"
    cols = ["txn_id", "ts", "customer_id", "channel", "mcc", "merchant_id", "merchant_country", "lat", "lon",
            "ip_country", "device_id", "payee_id", "amount", "currency", "is_fraud", "fraud_type", "incident_id"]
    return tx[cols], cust, merch
