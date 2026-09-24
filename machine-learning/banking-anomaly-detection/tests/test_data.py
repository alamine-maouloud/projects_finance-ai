import numpy as np

from txanomaly.data import FRAUD_TYPES, Config, generate


def test_reproducible():
    a = generate(Config(n_customers=100, n_days=20, seed=1))[0]
    b = generate(Config(n_customers=100, n_days=20, seed=1))[0]
    assert a.equals(b)


def test_fraud_rate_and_typologies(dataset):
    tx, cust, _ = dataset
    assert 0.001 < tx.is_fraud.mean() < 0.006
    assert set(tx.loc[tx.is_fraud == 1, "fraud_type"]) == set(FRAUD_TYPES)
    assert (tx.loc[tx.is_fraud == 0, "fraud_type"] == "").all()
    assert tx.ts.is_monotonic_increasing


def test_typology_signatures(dataset):
    tx, cust, _ = dataset
    home = cust.set_index("customer_id").home_country.reindex(tx.customer_id).to_numpy()
    ct = tx[tx.fraud_type == "card_testing"]
    assert (ct.channel == "ECOM").all() and (ct.amount < 5).mean() > 0.5
    sk = tx[tx.fraud_type == "skimming"]
    assert sk.channel.isin(["POS", "ATM"]).all() and (sk.merchant_country.to_numpy() != home[sk.index]).all()
    st = tx[tx.fraud_type == "stolen_card"]
    assert (st.channel == "POS").all() and (st.merchant_country.to_numpy() == home[st.index]).all()
    app = tx[tx.fraud_type == "app_scam"]
    assert (app.channel == "P2P").all() and (app.payee_id >= 8_000_000).all()
    ato = tx[tx.fraud_type == "account_takeover"]
    assert ato.device_id.str.startswith("X").all()


def test_genuine_look_alikes_exist(dataset):
    """Each fraud signal also occurs in genuine traffic, so no single field
    separates the classes."""
    tx, cust, _ = dataset
    g = tx[tx.is_fraud == 0]
    home = cust.set_index("customer_id").home_country.reindex(g.customer_id).to_numpy()
    assert ((g.channel.isin(["POS", "ATM"])) & (g.merchant_country.to_numpy() != home)).sum() > 1000   # travel
    assert ((g.channel == "ECOM") & (g.amount < 5)).sum() > 1000                                      # micro-payments
    assert ((g.channel == "P2P") & (g.amount >= 900)).sum() > 200                                     # rent, big transfers
    assert g.device_id.str.endswith("-new").sum() > 500                                               # new phones
    assert (g.ts.dt.hour < 5).mean() > 0.01                                                            # night shifts
