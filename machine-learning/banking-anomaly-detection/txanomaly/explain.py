"""Reason codes for alerts, by occlusion.

For an alerted transaction x and a family of related features F (amount,
velocity, geography ...), the contribution of F is

    c_F(x) = s(x) - s(x with every feature of F set to its normal value)

where s is the model score (log-odds) and "normal" is the median of genuine
training transactions. Occluding a whole family at once avoids splitting
credit between correlated features. The top families are turned into
sentences an analyst can act on.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .features import CATEGORICAL, NUMERIC

FAMILIES = {
    "amount": ["log_amount", "amount_ratio", "amount_ratio_channel", "amount_z", "round_amount"],
    "velocity": ["n_1h", "n_24h", "amount_24h_ratio", "log_secs_since_prev"],
    "card_testing": ["n_small_10min", "n_new_merchant_1h"],
    "new_merchant": ["is_new_merchant"],
    "new_device": ["is_new_device"],
    "new_payee": ["is_new_payee"],
    "new_country": ["is_new_country"],
    "geography": ["dist_home_km", "speed_kmh", "foreign"],
    "session": ["ip_foreign", "ip_mismatch_card"],
    "time": ["hour_dev", "night"],
    "contactless": ["near_contactless_limit", "n_contactless_2h"],
    "history": ["n_prev"],
    "category": ["mcc", "channel"],
}


CHANNEL_NAMES = {"POS": "in-store payment", "ECOM": "online payment", "ATM": "cash withdrawal", "P2P": "bank transfer"}


def _n(k, word: str) -> str:
    k = int(k)
    return f"{k} {word}" if k == 1 else f"{k} {word}s"


def _ratio(x: float) -> str:
    if x < 0.2:
        return "far below the customer's usual payment"
    return f"{x:.1f}x the customer's median payment"


def _text(family: str, r) -> str:
    if family == "amount":
        if r.round_amount > 0:
            return f"EUR {r.amount:,.0f}, a round or just-below-threshold amount, {_ratio(r.amount_ratio)}"
        return f"EUR {r.amount:,.2f}, {_ratio(r.amount_ratio)}"
    if family == "velocity":
        txt = f"{_n(r.n_1h, 'payment')} in the previous hour, {int(r.n_24h)} in 24 hours"
        if r.amount_24h_ratio > 3:
            txt += f"; 24-hour spend {r.amount_24h_ratio:.0f}x the usual payment"
        return txt
    if family == "card_testing":
        return (f"{_n(r.n_small_10min, 'payment')} under EUR 5 in the previous 10 minutes, "
                f"{_n(r.n_new_merchant_1h, 'new merchant')} in the hour")
    if family == "new_merchant":
        return "first payment at this merchant"
    if family == "new_device":
        return "first use of this device"
    if family == "new_payee":
        return "first transfer to this payee"
    if family == "new_country":
        return "first activity in this country"
    if family == "geography":
        if r.speed_kmh > 500:
            return f"{r.speed_kmh:,.0f} km/h from the previous card-present payment (impossible travel)"
        return f"card used {r.dist_home_km:,.0f} km from home"
    if family == "session":
        return "online session from abroad" + (", while the card was last used elsewhere" if r.ip_mismatch_card else "")
    if family == "time":
        return f"{r.hour_dev:.1f} h away from the customer's usual hours" + (", at night" if r.night else "")
    if family == "contactless":
        return f"{int(r.n_contactless_2h) + 1} payments just under the contactless limit within 2 hours"
    if family == "history":
        return f"little history ({_n(r.n_prev, 'previous transaction')})"
    if family == "category":
        kind = CHANNEL_NAMES.get(r.channel, r.channel)
        return kind if r.channel == "P2P" else f"{kind} in category {r.mcc.replace('_', ' ')}"
    return family


def reference_values(train: pd.DataFrame) -> dict:
    genuine = train[train["is_fraud"] == 0]
    ref = {c: float(genuine[c].median()) for c in NUMERIC}
    for c in CATEGORICAL:
        ref[c] = genuine[c].mode().iloc[0]
    return ref


def reason_codes(model, rows: pd.DataFrame, ref: dict, top: int = 3) -> pd.DataFrame:
    """Top ``top`` reasons for each row, with their score contributions."""
    base = model.score(rows)
    fams = list(FAMILIES)
    blocks = []
    for fam in fams:
        x = rows.copy()
        for c in FAMILIES[fam]:
            x[c] = ref[c]
        blocks.append(x)
    occl = model.score(pd.concat(blocks, ignore_index=True)).reshape(len(fams), len(rows))
    contrib = base[None, :] - occl                     # (families, rows)
    out = []
    for j, (_, r) in enumerate(rows.iterrows()):
        order = np.argsort(-contrib[:, j])[:top]
        reasons = [(fams[k], float(contrib[k, j]), _text(fams[k], r)) for k in order if contrib[k, j] > 0]
        out.append({"txn_id": r.txn_id, "score": float(base[j]),
                    "families": [x[0] for x in reasons],
                    "contributions": [round(x[1], 3) for x in reasons],
                    "reasons": [x[2] for x in reasons]})
    return pd.DataFrame(out, index=rows.index)
