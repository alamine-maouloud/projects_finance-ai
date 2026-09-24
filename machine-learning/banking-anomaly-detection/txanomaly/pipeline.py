"""End-to-end run: data, features, temporal split, every detector, metrics."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .data import Config, generate
from .evaluate import Split, temporal_split
from .features import build_features
from .models import all_models


@dataclass
class Run:
    tx: pd.DataFrame
    customers: pd.DataFrame
    features: pd.DataFrame
    split: Split
    models: list
    scores: dict            # model name -> scores on the test period
    timings: dict

    @property
    def train(self) -> pd.DataFrame:
        return self.features.loc[self.split.train]

    @property
    def test(self) -> pd.DataFrame:
        return self.features.loc[self.split.test]


def run(cfg: Config = Config(), seed: int = 0) -> Run:
    timings = {}
    t = time.perf_counter()
    tx, cust, _ = generate(cfg)
    timings["generate"] = time.perf_counter() - t
    t = time.perf_counter()
    f = build_features(tx, cust)
    timings["features"] = time.perf_counter() - t
    sp = temporal_split(f)
    tr, te = f.loc[sp.train], f.loc[sp.test]
    models, scores = [], {}
    for m in all_models(seed):
        t = time.perf_counter()
        m.fit(tr)
        scores[m.name] = np.asarray(m.score(te), dtype=float)
        timings[m.name] = time.perf_counter() - t
        models.append(m)
    return Run(tx, cust, f, sp, models, scores, timings)
