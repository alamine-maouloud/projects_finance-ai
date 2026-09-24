"""Render the results JSON into a self-contained HTML dashboard.

    python -m mcrisk.dashboard out/results.json out/dashboard.html
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TEMPLATE = Path(__file__).with_name("dashboard_template.html")
BENCH = Path(__file__).resolve().parent.parent / "benchmarks" / "results_credit.txt"


def _benchmarks() -> list[dict]:
    if not BENCH.exists():
        return []
    rows = []
    for line in BENCH.read_text().splitlines():
        m = re.match(r"\s*([\d,]+)\s+([\d,]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)x", line)
        if m:
            rows.append({"obligors": int(m[1].replace(",", "")), "scenarios": int(m[2].replace(",", "")),
                         "numpy_s": float(m[3]), "native_s": float(m[4]), "speedup": float(m[5])})
    return rows


def render(results_path: str, out_path: str) -> Path:
    data = json.loads(Path(results_path).read_text())
    data["benchmarks"] = _benchmarks()
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    html = TEMPLATE.read_text().replace("/*__DATA__*/{}", payload)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    return out


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else "out/results.json"
    dst = sys.argv[2] if len(sys.argv) > 2 else "out/dashboard.html"
    print(f"wrote {render(src, dst)}")
