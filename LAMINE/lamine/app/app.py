import streamlit as st, pandas as pd, numpy as np, matplotlib.pyplot as plt
from lamine.core.pipeline import fit_predict_scores

st.set_page_config(page_title="lamine — Banque", page_icon="💳", layout="wide")
st.title("lamine — Détection d'anomalies (Banque) 💳")

st.markdown("- Charge **data/banking.csv** (ou dépose ton CSV).\n- Le modèle **IsolationForest** s'entraîne (non supervisé) et calcule un **anomaly_score** (↑ = plus suspect).")

uploaded = st.file_uploader("CSV requis: amount, currency, country, hour, channel, distance_km, txn_24h", type=["csv"])
path_default = "data/banking.csv"

if uploaded is not None:
    df = pd.read_csv(uploaded)
else:
    try:
        df = pd.read_csv(path_default); st.caption(f"Chargé: {path_default}")
    except Exception:
        st.warning("Aucun fichier trouvé. Lance d'abord: python scripts/generate_banking.py"); st.stop()

required = ["amount","currency","country","hour","channel","distance_km","txn_24h"]
missing = [c for c in required if c not in df.columns]
if missing: st.error(f"Colonnes manquantes: {missing}"); st.stop()

with st.spinner("Entraînement IsolationForest…"):
    scores, _ = fit_predict_scores(df)

df_view = df.copy(); df_view["anomaly_score"] = scores

col1, col2 = st.columns(2)
with col1:
    st.subheader("Distribution des scores")
    fig = plt.figure(); plt.hist(df_view["anomaly_score"].values, bins=30)
    plt.xlabel("anomaly_score (↑ = plus anormal)"); plt.ylabel("count"); st.pyplot(fig)
with col2:
    st.subheader("Seuil")
    low, high = float(np.percentile(scores, 75)), float(np.percentile(scores, 99.9))
    threshold = st.slider("Seuil", low, high, float(np.percentile(scores, 95)))
    st.metric("Alertes au-dessus du seuil", int((df_view["anomaly_score"] >= threshold).sum()))

st.subheader("Top anomalies")
top_k = st.slider("Top-N", 5, 100, 20, step=5)
st.dataframe(df_view.sort_values("anomaly_score", ascending=False).head(top_k))
st.download_button(
    "📥 Exporter CSV (Top anomalies)",
    data=df_view.sort_values("anomaly_score", ascending=False).head(top_k).to_csv(index=False).encode("utf-8"),
    file_name="banking_top_alerts.csv", mime="text/csv"
)
