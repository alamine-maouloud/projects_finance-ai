"""
WP2 Platform - Launcher
Entry point used by PyInstaller and for direct launch.
Starts Streamlit programmatically so it works as a bundled app.
"""

import sys
import os
from pathlib import Path

# When bundled by PyInstaller, __file__ points inside the temp extraction dir.
# Set the working directory to the bundle root so relative paths work.
if getattr(sys, "frozen", False):
    bundle_dir = Path(sys.executable).parent
    os.chdir(bundle_dir)
    sys.path.insert(0, str(bundle_dir / "app"))
else:
    # Running from source
    bundle_dir = Path(__file__).parent
    sys.path.insert(0, str(bundle_dir / "app"))

import streamlit.web.cli as stcli

def main():
    main_script = str(bundle_dir / "app" / "main.py")
    sys.argv = [
        "streamlit", "run",
        main_script,
        "--server.headless=true",
        "--server.port=8501",
        "--browser.serverAddress=localhost",
        "--browser.gatherUsageStats=false",
        "--client.toolbarMode=minimal",
    ]
    sys.exit(stcli.main())

if __name__ == "__main__":
    main()
