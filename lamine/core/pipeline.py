```bash
cat > lamine/core/pipeline.py <<'PY'
from __future__ import annotations
from typing import List, Tuple
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.ensemble import IsolationForest

NUM_COLS_DEFAULT = ["amount","hour","distance_km","txn_24h"]
CAT_COLS_DEFAULT = ["currency","country","channel"]

def make_unsupervised_pipeline(num_cols: List[str] = None, cat_cols: List[str] = None) -> Pipeline:
    if num_cols is None: num_cols = NUM_COLS_DEFAULT
    if cat_cols is None: cat_cols = CAT_COLS_DEFAULT

    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
    ])
    categorical = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    pre = ColumnTransformer([
        ("num", numeric, num_cols),
        ("cat", categorical, cat_cols),
    ])
    model = IsolationForest(n_estimators=300, contamination="auto", random_state=42, n_jobs=-1)
    return Pipeline([("pre", pre), ("clf", model)])

def fit_predict_scores(df: pd.DataFrame,
                       num_cols: List[str] = None,
                       cat_cols: List[str] = None) -> Tuple[np.ndarray, Pipeline]:
    pipe = make_unsupervised_pipeline(num_cols, cat_cols)
    X = df[(num_cols or NUM_COLS_DEFAULT) + (cat_cols or CAT_COLS_DEFAULT)]
    pipe.fit(X)
    raw = pipe.decision_function(X)     # plus grand = plus normal
    anomaly_score = -raw                # on inverse : plus grand = plus anormal
    return anomaly_score, pipe
PY
