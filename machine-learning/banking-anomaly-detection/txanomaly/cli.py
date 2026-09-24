"""Command line.

    txanomaly generate [--customers N] [--days N] [--out data/transactions.csv.gz]
    txanomaly report   [--quick] [--out out]
    txanomaly app      launch the Streamlit investigation dashboard
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="txanomaly", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--customers", type=int, default=3000)
    g.add_argument("--days", type=int, default=120)
    g.add_argument("--seed", type=int, default=7)
    g.add_argument("--out", default="data/transactions.csv.gz")
    r = sub.add_parser("report")
    r.add_argument("--quick", action="store_true")
    r.add_argument("--out", default="out")
    sub.add_parser("app")
    a, rest = ap.parse_known_args(argv)
    if a.cmd == "generate":
        from .data import Config, generate
        tx, _, _ = generate(Config(n_customers=a.customers, n_days=a.days, seed=a.seed))
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        tx.to_csv(a.out, index=False)
        print(f"wrote {a.out}: {len(tx):,} transactions, fraud rate {tx.is_fraud.mean():.3%}")
    elif a.cmd == "report":
        from .report import main as report_main
        report_main(["--out", a.out] + (["--quick"] if a.quick else []) + rest)
    else:
        app = Path(__file__).resolve().parent.parent / "app" / "streamlit_app.py"
        sys.exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app)] + rest))


if __name__ == "__main__":
    main()
