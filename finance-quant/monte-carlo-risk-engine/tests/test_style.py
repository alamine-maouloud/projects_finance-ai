"""House style: no em dash or en dash anywhere in the repository."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = {"—": "em dash", "–": "en dash"}


def test_no_long_dashes_in_tracked_files():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                           check=True).stdout.split()
    offenders = []
    for name in files:
        try:
            text = (ROOT / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for ch, label in FORBIDDEN.items():
                if ch in line:
                    offenders.append(f"{name}:{lineno}: {label}")
    assert not offenders, "long dashes found:\n" + "\n".join(offenders)
