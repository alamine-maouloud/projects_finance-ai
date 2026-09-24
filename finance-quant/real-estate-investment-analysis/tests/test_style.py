"""House style: no em dash, en dash or emoji anywhere in the repository."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = {chr(0x2014): "em dash", chr(0x2013): "en dash"}
EMOJI = re.compile("[" + chr(0x1F300) + "-" + chr(0x1FAFF) + chr(0x2600) + "-" + chr(0x27BF) + "]")


def tracked_text_files():
    files = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT,
                           capture_output=True, text=True, check=True).stdout.split()
    for name in files:
        try:
            yield name, (ROOT / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue


def test_no_long_dashes_or_emoji():
    offenders = []
    for name, text in tracked_text_files():
        for lineno, line in enumerate(text.splitlines(), 1):
            for ch, label in FORBIDDEN.items():
                if ch in line:
                    offenders.append(f"{name}:{lineno}: {label}")
            if EMOJI.search(line):
                offenders.append(f"{name}:{lineno}: emoji")
    assert not offenders, "\n".join(offenders)
