from __future__ import annotations
import numpy as np
import pandas as pd

BANKING_COLUMNS = ["amount","currency","country","hour","channel","distance_km","txn_24h","is_fraud"]
CURRENCIES = ["SGD","USD","EUR"]
COUNTRIES = ["SG","MY","ID","TH","PH","CN","IN","AU","US","FR"]
CHANNELS = ["POS","ECOM","ATM","P2P"]

def simulate_banking(n:int=2000, seed:int=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    amount = rng.gamma(shape=2.0, scale=50.0, size=n)
    hour = rng.integers(0, 24, size=n)
    distance = np.abs(rng.normal(loc=5.0, scale=10.0, size=n))
    txn_24h = np.clip(np.round(rng.normal(loc=3.0, scale=2.0, size=n)), 0, None)
    currency = rng.choice(CURRENCIES, size=n, p=[0.7, 0.2, 0.1])
    country = rng.choice(COUNTRIES, size=n, p=[0.35,0.1,0.1,0.08,0.07,0.07,0.06,0.05,0.06,0.06])
    channel = rng.choice(CHANNELS, size=n, p=[0.5,0.35,0.1,0.05])

    df = pd.DataFrame({
        "amount": amount,
        "currency": currency,
        "country": country,
        "hour": hour,
        "channel": channel,
        "distance_km": distance,
        "txn_24h": txn_24h,
    })

    # ~2% d'anomalies/fraudes simulées
    k = max(1, n // 50)
    idx = rng.choice(n, size=k, replace=False)
    df.loc[idx, "amount"] *= rng.integers(8, 20, size=k)
    df.loc[idx, "hour"] = rng.choice([0,1,2,3,4], size=k)
    df.loc[idx, "country"] = rng.choice(["RU","NG","BR","MX","UA"], size=k)
    df.loc[idx, "distance_km"] = rng.normal(loc=2000, scale=300, size=k)
    df["is_fraud"] = 0
    df.loc[idx, "is_fraud"] = 1
    return df
