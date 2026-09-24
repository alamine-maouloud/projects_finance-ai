"""Fraud investigation dashboard.

    txanomaly report          # builds out/ once (about 80 s)
    txanomaly app             # or: streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from txanomaly.data import FRAUD_TYPES
from txanomaly.evaluate import daily_budget_alerts, evaluate
from txanomaly.explain import CHANNEL_NAMES, reason_codes
from txanomaly.models import RuleEngine

OUT = Path(__file__).resolve().parent.parent / "out"
TYPE_NAMES = {"card_testing": "Card testing", "account_takeover": "Account takeover", "skimming": "Skimming",
              "stolen_card": "Stolen card", "app_scam": "Authorised push payment scam", "": "Genuine"}

st.set_page_config(page_title="Card fraud investigation", layout="wide")


@st.cache_resource
def load():
    if not (OUT / "run.pkl").exists():
        return None, None
    with open(OUT / "run.pkl", "rb") as fh:
        run = pickle.load(fh)
    return run, json.loads((OUT / "results.json").read_text())


run, res = load()
st.title("Card fraud investigation")
if run is None:
    st.error("No results yet. Build them with `txanomaly report` (or `txanomaly report --quick`), then reload.")
    st.stop()

te: pd.DataFrame = run["test"]
models = {m.name: m for m in run["models"]}
st.caption(f"Synthetic bank: {res['data']['customers']:,} customers, {res['data']['transactions']:,} transactions, "
           f"fraud rate {res['data']['fraud_rate']:.2%}. Models are trained on the first "
           f"{res['data']['train_days']} days after a {res['data']['burn_in_days']}-day burn-in, and evaluated "
           f"on the following {res['data']['test_days']} days, which they have never seen.")

with st.sidebar:
    st.header("Settings")
    name = st.selectbox("Detector", list(models), index=list(models).index("Gradient boosting"))
    budget = st.select_slider("Daily alert budget (share of transactions reviewed)",
                              options=[0.0005, 0.001, 0.002, 0.003, 0.005, 0.0075, 0.01, 0.02],
                              value=0.002, format_func=lambda b: f"{b:.2%}")
    cost = st.number_input("Review cost per alert (EUR)", min_value=0.0, max_value=50.0, value=4.0, step=1.0)

score = run["scores"][name]
e = evaluate(te, score, budget, cost)
alert = daily_budget_alerts(te, score, budget)
days = te["ts"].dt.floor("D").nunique()


def eur(x: float) -> str:
    return f"EUR {x / 1000:,.0f}k" if abs(x) >= 10_000 else f"EUR {x:,.0f}"


c = st.columns(5)
c[0].metric("Alerts per day", f"{e['alerts'] / days:.1f}")
c[1].metric("Precision", f"{e['precision']:.0%}", help="Share of alerts that are fraud")
c[2].metric("Frauds caught", f"{e['recall']:.0%}", help="Share of fraud transactions alerted")
c[3].metric("Loss prevented", eur(e["loss_prevented"]), f"{e['loss_prevented_share']:.0%} of losses",
            delta_color="off", help="The card is blocked at its first alert, so later fraud of the same incident is stopped too")
c[4].metric("Net savings", eur(e["net_savings"]), help="Loss prevented minus review cost")

tab_q, tab_perf, tab_cust, tab_cmp = st.tabs(["Alert queue", "Performance by fraud type", "Customer timeline",
                                              "Model comparison"])


def explain_rows(rows: pd.DataFrame) -> list[str]:
    m = models[name]
    if isinstance(m, RuleEngine):
        hits = m.hits(rows)
        text = {r.name: r.reason for r in m.rules}
        return [" | ".join(text[k] for k, v in h.items() if v) or "no rule fired" for _, h in hits.iterrows()]
    rc = reason_codes(m, rows, run["reference"])
    return [" | ".join(r) for r in rc["reasons"]]


with tab_q:
    alerted = te[alert].copy()
    alerted["score"] = score[alert]
    day_list = sorted(alerted["ts"].dt.date.unique())
    left, right = st.columns([1, 2])
    day = left.selectbox("Day", day_list, index=len(day_list) - 1)
    show_truth = right.toggle("Show the ground truth (for evaluation only)", value=True)
    q = alerted[alerted["ts"].dt.date == day].sort_values("score", ascending=False)
    q["reasons"] = explain_rows(q) if len(q) else []
    view = pd.DataFrame({
        "time": q["ts"].dt.strftime("%H:%M"), "customer": q["customer_id"],
        "type": q["channel"].map(CHANNEL_NAMES), "category": q["mcc"].str.replace("_", " "),
        "amount (EUR)": q["amount"].round(2), "score": q["score"].round(2), "why": q["reasons"]})
    if show_truth:
        view["ground truth"] = q["fraud_type"].map(TYPE_NAMES)
    st.dataframe(view, hide_index=True, width="stretch",
                 column_config={"why": st.column_config.TextColumn(width="large")})
    st.caption(f"{len(q)} alerts on {day}; {int(q['is_fraud'].sum())} are fraud.")

with tab_perf:
    rows = []
    for t in FRAUD_TYPES:
        bt = e["by_type"][t]
        rows.append({"fraud type": TYPE_NAMES[t], "transactions caught": bt["recall"],
                     "incidents detected": bt["incidents_detected"], "loss prevented": bt["loss_prevented"]})
    perf = pd.DataFrame(rows)
    st.bar_chart(perf.set_index("fraud type")[["loss prevented", "transactions caught"]], stack=False, height=320)
    st.dataframe(perf.style.format({c: "{:.0%}" for c in perf.columns[1:]}), hide_index=True, width="stretch")
    st.subheader("Loss prevented as the alert budget grows")
    curves = []
    for m in res["models"]:
        for p in m["budget_curve"]:
            curves.append({"alert budget (%)": 100 * p["budget"], "loss prevented": p["loss_prevented_share"],
                           "detector": m["name"]})
    st.line_chart(pd.DataFrame(curves), x="alert budget (%)", y="loss prevented", color="detector", height=340)

with tab_cust:
    ids = te.loc[alert & (te["is_fraud"] == 1), "customer_id"].drop_duplicates()
    ids = ids.tolist() or te["customer_id"].drop_duplicates().tolist()
    cid = st.selectbox("Customer (alerted fraud victims listed first)", ids + [x for x in te["customer_id"].unique() if x not in ids][:200])
    h = te[te["customer_id"] == cid].copy()
    h["status"] = np.where(h["is_fraud"] == 1, "fraud", "genuine")
    h["alert"] = alert[te["customer_id"].to_numpy() == cid]
    st.scatter_chart(h, x="ts", y="amount", color="status", height=320)
    st.dataframe(pd.DataFrame({
        "time": h["ts"].dt.strftime("%Y-%m-%d %H:%M"), "type": h["channel"].map(CHANNEL_NAMES),
        "category": h["mcc"].str.replace("_", " "), "amount (EUR)": h["amount"].round(2),
        "x median": h["amount_ratio"].round(1), "new merchant": h["is_new_merchant"] > 0,
        "new device": h["is_new_device"] > 0, "alert": h["alert"], "truth": h["fraud_type"].map(TYPE_NAMES)}),
        hide_index=True, width="stretch")

with tab_cmp:
    b = str(res["headline_budget"])
    rows = []
    for m in res["models"]:
        x = m["by_budget"][b]
        rows.append({"detector": m["name"], "PR-AUC": x["pr_auc"],
                     "95% interval": f"{m['pr_auc_ci'][0]:.2f} to {m['pr_auc_ci'][1]:.2f}",
                     "precision": x["precision"], "recall": x["recall"],
                     "loss prevented": x["loss_prevented_share"], "net savings (EUR)": x["net_savings"]})
    cmp = pd.DataFrame(rows)
    st.caption(f"At an alert budget of {float(b):.1%} of daily transactions. Intervals from a bootstrap over customers.")
    st.dataframe(cmp.style.format({"PR-AUC": "{:.3f}", "precision": "{:.0%}", "recall": "{:.0%}",
                                   "loss prevented": "{:.0%}", "net savings (EUR)": "{:,.0f}"}),
                 hide_index=True, width="stretch")
    st.subheader("What the gradient boosting model relies on")
    imp = pd.DataFrame(res["importance"][:12], columns=["feature", "drop in PR-AUC when shuffled"])
    st.bar_chart(imp.set_index("feature"), horizontal=True, height=380)
