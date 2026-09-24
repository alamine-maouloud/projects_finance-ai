"""Detectors, from bank-style rules to gradient boosting.

Every detector exposes ``fit(features)`` and ``score(features)``: a higher
score means more suspicious. Supervised models learn from the labels of the
training period only; unsupervised ones ignore labels.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, OrdinalEncoder, StandardScaler

from .features import CATEGORICAL, NUMERIC

# heavy-tailed features are log-compressed for linear and distance-based models
LOG_FEATURES = ["amount_ratio", "amount_ratio_channel", "amount_24h_ratio", "n_1h", "n_24h",
                "n_small_10min", "n_new_merchant_1h", "dist_home_km", "speed_kmh", "n_prev",
                "n_contactless_2h"]


def _prep(scale: bool = True) -> ColumnTransformer:
    lin = [c for c in NUMERIC if c not in LOG_FEATURES]
    steps_log = [("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one"))]
    if scale:
        steps_log.append(("sc", StandardScaler()))
    return ColumnTransformer([
        ("log", Pipeline(steps_log), LOG_FEATURES),
        ("lin", StandardScaler() if scale else "passthrough", lin),
        ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=50), CATEGORICAL),
    ])


@dataclass
class Rule:
    name: str
    weight: float
    fires: callable
    reason: str


# rule predicates are module-level functions so that fitted detectors pickle
def _big_vs_history(f): return f.amount_ratio > 6                                  # noqa: E704
def _new_device_big(f): return (f.is_new_device > 0) & (f.amount > 150)           # noqa: E704
def _impossible_travel(f): return f.speed_kmh > 900                                # noqa: E704
def _card_testing(f): return f.n_small_10min >= 2                                  # noqa: E704
def _night_big(f): return (f.night > 0) & (f.amount_ratio > 3)                     # noqa: E704
def _new_payee_big(f): return (f.is_new_payee > 0) & (f.amount >= 500)            # noqa: E704
def _velocity(f): return f.n_1h >= 4                                               # noqa: E704
def _contactless_burst(f): return f.n_contactless_2h >= 2                          # noqa: E704
def _foreign_session(f): return f.ip_mismatch_card > 0                             # noqa: E704


def default_rules() -> list[Rule]:
    """A typical first-line rule set of a card fraud team."""
    return [
        Rule("big_vs_history", 2.0, _big_vs_history, "amount far above the customer's usual"),
        Rule("new_device_big", 2.0, _new_device_big, "large payment from a new device"),
        Rule("impossible_travel", 3.0, _impossible_travel, "card used too far away too fast"),
        Rule("card_testing", 3.0, _card_testing, "several tiny payments in minutes"),
        Rule("night_big", 1.5, _night_big, "large payment at night"),
        Rule("new_payee_big", 2.0, _new_payee_big, "large transfer to a new payee"),
        Rule("velocity", 1.5, _velocity, "many payments in the last hour"),
        Rule("contactless_burst", 2.0, _contactless_burst, "repeated payments just under the contactless limit"),
        Rule("foreign_session", 1.0, _foreign_session, "online session from a country the card was not in"),
    ]


@dataclass
class RuleEngine:
    rules: list[Rule] = field(default_factory=default_rules)
    name: str = "Rules"

    def fit(self, f: pd.DataFrame) -> "RuleEngine":
        return self

    def hits(self, f: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({r.name: r.fires(f).astype(bool).to_numpy() for r in self.rules}, index=f.index)

    def score(self, f: pd.DataFrame) -> np.ndarray:
        h = self.hits(f).to_numpy()
        w = np.array([r.weight for r in self.rules])
        # small tie-breaker so that equal rule scores are ordered by amount ratio
        return h @ w + 1e-3 * np.log1p(f["amount_ratio"].to_numpy())


class RawIsolationForest:
    """The original project's approach: Isolation Forest on raw fields only
    (amount, hour, distance, 24-h count, channel, category, country)."""

    name = "Isolation Forest, raw fields"
    cols_num = ["amount", "hour", "dist_home_km", "n_24h"]

    def __init__(self, seed: int = 0):
        self.pipe = Pipeline([
            ("pre", ColumnTransformer([
                ("num", StandardScaler(), self.cols_num),
                ("cat", OneHotEncoder(handle_unknown="ignore"), ["channel", "mcc", "foreign"]),
            ])),
            ("clf", IsolationForest(n_estimators=300, random_state=seed, n_jobs=-1)),
        ])

    def _x(self, f):
        x = f[["amount", "dist_home_km", "n_24h", "channel", "mcc", "foreign"]].copy()
        x["hour"] = f["ts"].dt.hour
        return x

    def fit(self, f):
        self.pipe.fit(self._x(f))
        return self

    def score(self, f):
        return -self.pipe.decision_function(self._x(f))


class BehaviouralIsolationForest:
    name = "Isolation Forest, behavioural features"

    def __init__(self, seed: int = 0):
        self.pipe = Pipeline([("pre", _prep()), ("clf", IsolationForest(n_estimators=300, random_state=seed, n_jobs=-1))])

    def fit(self, f):
        self.pipe.fit(f[NUMERIC + CATEGORICAL])
        return self

    def score(self, f):
        return -self.pipe.decision_function(f[NUMERIC + CATEGORICAL])


class Logistic:
    name = "Logistic regression"

    def __init__(self, seed: int = 0):
        self.pipe = Pipeline([("pre", _prep()),
                              ("clf", LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000))])

    def fit(self, f):
        self.pipe.fit(f[NUMERIC + CATEGORICAL], f["is_fraud"])
        return self

    def score(self, f):
        return self.pipe.decision_function(f[NUMERIC + CATEGORICAL])


class GradientBoosting:
    """Histogram gradient boosting with native categorical handling."""

    name = "Gradient boosting"

    def __init__(self, seed: int = 0):
        pre = ColumnTransformer([
            ("num", "passthrough", NUMERIC),
            ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CATEGORICAL),
        ])
        n = len(NUMERIC)
        clf = HistGradientBoostingClassifier(
            learning_rate=0.06, max_iter=600, max_leaf_nodes=31, min_samples_leaf=40, l2_regularization=1.0,
            categorical_features=[n + i for i in range(len(CATEGORICAL))], early_stopping=True,
            validation_fraction=0.15, n_iter_no_change=40, scoring="average_precision", random_state=seed)
        self.pipe = Pipeline([("pre", pre), ("clf", clf)])

    def fit(self, f):
        # rebalance: each fraud weighs as much as 20 genuine transactions
        w = np.where(f["is_fraud"].to_numpy() == 1, 20.0, 1.0)
        self.pipe.fit(f[NUMERIC + CATEGORICAL], f["is_fraud"], clf__sample_weight=w)
        return self

    def score(self, f):
        return self.pipe.decision_function(f[NUMERIC + CATEGORICAL])

    def proba(self, f):
        return self.pipe.predict_proba(f[NUMERIC + CATEGORICAL])[:, 1]


def all_models(seed: int = 0) -> list:
    return [RuleEngine(), RawIsolationForest(seed), BehaviouralIsolationForest(seed), Logistic(seed),
            GradientBoosting(seed)]
