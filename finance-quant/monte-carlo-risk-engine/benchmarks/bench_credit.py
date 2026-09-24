"""Throughput of the credit engine backends (plain MC, Gaussian copula).

    python benchmarks/bench_credit.py
"""

import os
import time

import numpy as np

from mcrisk.credit import CreditModel, simulate, synthetic_portfolio
from mcrisk.credit import native


def bench(n_obligors, n_scen, backend, repeats=2):
    model = CreditModel(synthetic_portfolio(n_obligors, seed=7))
    simulate(model, 2000, seed=0, backend=backend)          # warm-up / kernel build
    best = np.inf
    for r in range(repeats):
        t = time.perf_counter()
        res = simulate(model, n_scen, seed=r, backend=backend)
        best = min(best, time.perf_counter() - t)
    return best, res.var(0.999)


if __name__ == "__main__":
    print(f"threads: {os.cpu_count()}   native kernel: {native.available()}")
    print(f"{'obligors':>9} {'scenarios':>10} {'numpy s':>9} {'native s':>9} {'speed-up':>9}"
          f" {'Mscen*obl/s native':>19}")
    for n, s in [(2_000, 1_000_000), (10_000, 400_000), (50_000, 200_000), (200_000, 100_000)]:
        t_np, _ = bench(n, s, "numpy")
        t_nat, _ = bench(n, s, "native")
        print(f"{n:9,d} {s:10,d} {t_np:9.2f} {t_nat:9.2f} {t_np / t_nat:8.1f}x {n * s / t_nat / 1e6:19,.0f}")
