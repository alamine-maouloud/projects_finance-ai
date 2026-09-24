"""Evaluation the way a fraud team is judged.

* Temporal split: learn on the past, test on the future (a random split leaks
  a customer's future behaviour into training). The first days are a burn-in
  during which the behavioural history is still being built.
* Alert budget: analysts review a fixed share of each day's transactions, so
  every detector is compared at the same number of alerts per day.
* Money, not only counts: a card is blocked at its first alert, so the loss
  prevented is the fraud amount from that alert to the end of the incident.
* Uncertainty: frauds cluster on compromised customers, so confidence
  intervals come from a bootstrap over customers, not over transactions.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score

from .data import FRAUD_TYPES


@dataclass(frozen=True)
class Split:
    train: pd.Index
    test: pd.Index
    burn_in_days: int
    train_days: int


def temporal_split(f: pd.DataFrame, burn_in_days: int = 14, train_frac: float = 0.6) -> Split:
    day = (f["ts"] - f["ts"].min()).dt.days
    last = int(day.max()) + 1
    cut = burn_in_days + int(round((last - burn_in_days) * train_frac))
    train = f.index[(day >= burn_in_days) & (day < cut)]
    test = f.index[day >= cut]
    return Split(train, test, burn_in_days, cut - burn_in_days)


def daily_budget_alerts(f: pd.DataFrame, score: np.ndarray, budget: float) -> np.ndarray:
    """Alert the top ``budget`` share of transactions of each day."""
    d = pd.DataFrame({"day": f["ts"].dt.floor("D").to_numpy(), "s": score}, index=f.index)
    rank = d.groupby("day")["s"].rank(ascending=False, method="first")
    size = d.groupby("day")["s"].transform("size")
    return (rank <= np.ceil(budget * size)).to_numpy()


def _blocked(f: pd.DataFrame, alert: np.ndarray) -> pd.DataFrame:
    """Fraud rows with a flag telling whether the card was already blocked
    (an alert on this or an earlier transaction of the same incident)."""
    fr = f.loc[f["is_fraud"] == 1, ["incident_id", "fraud_type", "ts", "amount"]].copy()
    fr["alert"] = np.asarray(alert)[f.index.get_indexer(fr.index)]
    fr = fr.sort_values(["incident_id", "ts"], kind="stable")
    fr["blocked"] = fr.groupby("incident_id")["alert"].cummax()
    fr["prevented"] = fr["amount"] * fr["blocked"]
    return fr


def loss_prevented(f: pd.DataFrame, alert: np.ndarray) -> pd.DataFrame:
    """Per incident: total fraud amount and the amount stopped once the card
    is blocked at its first alerted fraud transaction."""
    return _blocked(f, alert).groupby("incident_id").agg(
        fraud_type=("fraud_type", "first"), total=("amount", "sum"),
        prevented=("prevented", "sum"), detected=("alert", "max"))


def evaluate(f: pd.DataFrame, score: np.ndarray, budget: float = 0.005, review_cost: float = 4.0) -> dict:
    y = f["is_fraud"].to_numpy()
    alert = daily_budget_alerts(f, score, budget)
    tp = int((alert & (y == 1)).sum())
    inc = loss_prevented(f, alert)
    by_type = {}
    for t in FRAUD_TYPES:
        m = (f["fraud_type"] == t).to_numpy()
        it = inc[inc.fraud_type == t]
        by_type[t] = {
            "recall": float(alert[m].mean()) if m.any() else np.nan,
            "incidents_detected": float(it.detected.mean()) if len(it) else np.nan,
            "loss_prevented": float(it.prevented.sum() / it.total.sum()) if len(it) else np.nan,
        }
    total = float(inc.total.sum())
    prevented = float(inc.prevented.sum())
    return {
        "roc_auc": float(roc_auc_score(y, score)),
        "pr_auc": float(average_precision_score(y, score)),
        "alerts": int(alert.sum()),
        "precision": tp / max(int(alert.sum()), 1),
        "recall": tp / max(int(y.sum()), 1),
        "incidents_detected": float(inc.detected.mean()),
        "fraud_amount": total,
        "loss_prevented": prevented,
        "loss_prevented_share": prevented / total if total else np.nan,
        "net_savings": prevented - review_cost * int(alert.sum()),
        "by_type": by_type,
    }


def bootstrap_customers(f: pd.DataFrame, score: np.ndarray, budget: float = 0.005,
                        n_boot: int = 200, seed: int = 0) -> dict:
    """95% intervals for PR-AUC and loss-prevented share, resampling customers."""
    rng = np.random.default_rng(seed)
    alert = daily_budget_alerts(f, score, budget)
    cust = f["customer_id"].to_numpy()
    ids, inv = np.unique(cust, return_inverse=True)
    rows = [np.flatnonzero(inv == k) for k in range(ids.size)]
    y = f["is_fraud"].to_numpy()
    amt = f["amount"].to_numpy()
    blocked = pd.Series(0.0, index=f.index)
    fr = _blocked(f, alert)
    blocked.loc[fr.index] = fr["prevented"]
    blocked = blocked.to_numpy()
    pr, lp = [], []
    for _ in range(n_boot):
        pick = rng.integers(0, ids.size, ids.size)
        idx = np.concatenate([rows[k] for k in pick])
        if y[idx].sum() == 0:
            continue
        pr.append(average_precision_score(y[idx], score[idx]))
        fraud_amt = (amt[idx] * y[idx]).sum()
        lp.append(blocked[idx].sum() / fraud_amt)
    q = lambda v: (float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975)))  # noqa: E731
    return {"pr_auc_ci": q(pr), "loss_prevented_ci": q(lp)}


def pr_curve(y: np.ndarray, score: np.ndarray, n: int = 200) -> list[tuple[float, float]]:
    p, r, _ = precision_recall_curve(y, score)
    idx = np.unique(np.linspace(0, len(r) - 1, n).astype(int))
    return [(float(r[i]), float(p[i])) for i in idx]


def budget_curve(f: pd.DataFrame, score: np.ndarray, budgets, review_cost: float = 4.0) -> list[dict]:
    """Loss prevented and net savings as the alert budget grows."""
    out = []
    for b in budgets:
        e = evaluate(f, score, b, review_cost)
        out.append({"budget": b, "alerts": e["alerts"], "precision": e["precision"],
                    "loss_prevented_share": e["loss_prevented_share"], "net_savings": e["net_savings"]})
    return out
