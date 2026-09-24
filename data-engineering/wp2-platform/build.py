"""
WP2 Platform - Packaging script (M7)
Builds a standalone executable for macOS and Windows using PyInstaller.

Usage:
    python build.py          # builds for current platform
    python build.py --clean  # removes build artifacts first
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path

ROOT    = Path(__file__).parent
APP_DIR = ROOT / "app"
DIST    = ROOT / "dist"
BUILD   = ROOT / "build"
SPEC    = ROOT / "wp2_platform.spec"

APP_NAME    = "WP2Platform"
ENTRY_POINT = str(APP_DIR / "launcher.py")


def clean():
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)
            print(f"Removed {d}")
    if SPEC.exists():
        SPEC.unlink()
        print(f"Removed {SPEC}")


def check_pyinstaller():
    try:
        import PyInstaller
        print(f"PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"],
                       check=True)


def build():
    check_pyinstaller()

    # Data files to bundle
    datas = [
        (str(ROOT / "vocabulary" / "voc_1.1.0.json"), "vocabulary"),
        (str(ROOT / ".streamlit" / "config.toml"),    ".streamlit"),
    ]

    datas_args = []
    sep = ";" if sys.platform == "win32" else ":"
    for src, dst in datas:
        datas_args += ["--add-data", f"{src}{sep}{dst}"]

    hidden_imports = [
        "streamlit", "duckdb", "pandas", "sqlite3",
        "chromadb", "sentence_transformers",
        "app.database", "app.vocabulary", "app.validation",
        "app.export_module", "app.ai_module",
    ]
    hidden_args = []
    for h in hidden_imports:
        hidden_args += ["--hidden-import", h]

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--onedir",
        "--windowed",
        "--noconfirm",
        *datas_args,
        *hidden_args,
        ENTRY_POINT,
    ]

    print("Building with PyInstaller...")
    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode == 0:
        print(f"\n✅ Build successful: {DIST / APP_NAME}")
        print("The app bundle is in the dist/ folder.")
        print("Copy the entire dist/WP2Platform/ folder to deploy.")
    else:
        print("\n❌ Build failed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build WP2 Platform executable")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts")
    args = parser.parse_args()

    if args.clean:
        clean()

    build()
