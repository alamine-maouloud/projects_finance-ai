import pytest

from txanomaly.data import Config, generate
from txanomaly.features import build_features


@pytest.fixture(scope="session")
def dataset():
    tx, cust, merch = generate(Config(n_customers=1200, n_days=90, seed=3))
    return tx, cust, merch


@pytest.fixture(scope="session")
def features(dataset):
    tx, cust, _ = dataset
    return build_features(tx, cust)
