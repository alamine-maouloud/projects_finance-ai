"""Throughput of the order-flow simulator (one thread per path).

    python benchmarks/bench_lob.py
"""

import os
import time

from mcrisk.lob import FlowModel, simulate, simulate_agent

DAY = 23_400.0

if __name__ == "__main__":
    print(f"{'model':<34} {'events/day':>11} {'s/day':>7} {'M events/s':>11}")
    for name, m in [("CST, Poisson market orders", FlowModel.cst()),
                    ("CST, Hawkes market orders (n=0.7)", FlowModel.cst(hawkes_branching=0.7)),
                    ("CST, 20 levels, Hawkes", FlowModel.cst(hawkes_branching=0.7, levels=20))]:
        simulate(m, 600.0, seed=0)
        dt = float("inf")
        for s in range(3):
            t0 = time.perf_counter()
            r = simulate(m, DAY, seed=s, record_mo=False, depth_dt=0)
            dt = min(dt, time.perf_counter() - t0)
        print(f"{name:<34} {r.n_events:>11,d} {dt:>7.3f} {r.n_events / dt / 1e6:>11.1f}")
    m = FlowModel.cst(hawkes_branching=0.7, levels=20)
    sched = [(60.0 * k, 1, 6) for k in range(30)]
    t0 = time.perf_counter()
    simulate_agent(m, sched, 1800.0, 2000, seed=1)
    dt = time.perf_counter() - t0
    print(f"\n2,000 independent 40-min books with a 30-order TWAP on {os.cpu_count()} threads: {dt:.2f} s")
