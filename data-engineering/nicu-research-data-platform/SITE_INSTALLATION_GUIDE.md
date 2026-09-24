# WP2 Platform - Site Installation Guide

**Version:** 1.1 | **Schema:** 1.1 | **Vocabulary:** voc_1.1.0
**For:** Research site coordinators and data managers

---

## Overview

The WP2 Platform is a local-first, offline desktop application for documenting
NICU developmental-care research sessions. Each research site runs its own
independent installation. Data never leaves the local machine unless explicitly
exported by the site coordinator.

---

## System requirements

| Component | Minimum |
|---|---|
| Operating system | macOS 12+ or Windows 10+ |
| RAM | 8 GB (16 GB recommended for AI features) |
| Disk space | 2 GB (base) + 5 GB if using local AI |
| Python | 3.10 or higher |
| Internet | Not required after installation |

---

## Installation

### Option A - From source (recommended for pilot sites)

**Step 1 - Check Python version**

```bash
python3 --version
```

Must show 3.10 or higher. If not, download from python.org or use:

```bash
brew install python@3.11   # macOS
```

**Step 2 - Download the platform**

Download and unzip `wp2_platform.zip` to a permanent location
(e.g. `Documents/wp2_platform`). Do not move it after first launch.

**Step 3 - Create virtual environment**

```bash
cd ~/Documents/wp2_platform
python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux
# .venv\Scripts\activate        # Windows
```

**Step 4 - Install dependencies**

```bash
pip install -r requirements.txt
```

**Step 5 - Launch**

```bash
streamlit run app/main.py
```

The app opens automatically at http://localhost:8501

**Step 6 - First-run setup**

Enter your Site ID and user ID when prompted.

Site ID format: `{ISO2}-{INST}-{NNN}`
- ISO2: two-letter country code (e.g. AE, GB, NO, FR)
- INST: short institution code (e.g. CUD, UCL, UIO)
- NNN: three-digit sequence (001, 002, ...)

Example: `AE-CUD-001`, `GB-UCL-001`, `NO-UIO-001`

The Site ID is **permanent** - it cannot be changed after first launch.
Contact the platform curator (Al-Amine Maouloud) before creating your Site ID.

---

### Option B - Pre-built executable (when available)

Download `WP2Platform_macOS.zip` or `WP2Platform_Windows.zip`,
unzip, and double-click `WP2Platform`. No Python installation required.

---

## Daily use

### Starting the app

```bash
cd ~/Documents/wp2_platform
source .venv/bin/activate
streamlit run app/main.py
```

The app opens in your default browser at http://localhost:8501

**Tip:** Create a shell script `launch.sh` for convenience:

```bash
#!/bin/bash
cd ~/Documents/wp2_platform
source .venv/bin/activate
streamlit run app/main.py
```

Then `chmod +x launch.sh` and double-click to launch.

### Stopping the app

Press `Ctrl+C` in the terminal where the app is running.

### Backing up your data

Your data is stored in `data/wp2_platform.db`. Back this file up regularly:

```bash
cp ~/Documents/wp2_platform/data/wp2_platform.db \
   ~/Desktop/wp2_backup_$(date +%Y%m%d).db
```

---

## Optional: AI features (Ollama + Llama 3)

The AI Assistant tab requires Ollama and Llama 3. This is optional -
the rest of the app works without it.

**Install Ollama (macOS):**

```bash
brew install ollama
```

**Start Ollama:**

```bash
ollama serve
```

**Download Llama 3 (first time only, ~4.7 GB):**

```bash
ollama pull llama3
```

The AI features become available automatically once Ollama is running.

**RAM requirements:**
- Llama 3 8B (default): 16 GB RAM recommended
- Mistral 7B (fallback, 12 GB RAM): `ollama pull mistral`

---

## Running the test suite

To verify the installation is correct:

```bash
cd ~/Documents/wp2_platform
source .venv/bin/activate
python3 tests/test_wp2.py
```

Expected output: `20 passed, 0 failed`

---

## Data governance

- **No data leaves the machine** unless you use the Export function
- **Export files** are saved to `exports/` and must be shared securely (encrypted email or institutional file transfer)
- **Void records** (marked as void via the Edit function) are retained in the database for audit purposes but excluded from exports
- **Audit trail** (`sys_data_audit`, `sys_export_audit`, `sys_ai_audit_trail`) is append-only and available for governance review on request
- **Retention:** Per your institutional IRB agreement (default: 15 years post-project-closure per ICH GCP E6(R3))

---

## Site withdrawal

If your site withdraws from the WP2 research network:

1. Produce a final export (Export tab - Run export)
2. Send the export files securely to the platform curator
3. Confirm in writing that the local database has been archived or destroyed per your institutional policy
4. Your site ID will be marked inactive and no new exports can be linked to it

---

## Troubleshooting

**App does not start**
- Check Python version is 3.10+: `python3 --version`
- Check virtual environment is activated: `source .venv/bin/activate`
- Re-install dependencies: `pip install -r requirements.txt`

**"No module named X" error**
- Make sure the virtual environment is activated
- Run `pip install -r requirements.txt` again

**Database error on first launch**
- Check the `data/` folder exists inside `wp2_platform/`
- If missing: `mkdir -p ~/Documents/wp2_platform/data`

**Export blocked - de-id check failed**
- Review the free-text notes in the flagged session(s)
- Remove any content matching the blocked pattern (ID numbers, dates of birth, phone numbers, NHS numbers)
- Re-run the export

**AI features not available**
- Start Ollama: `ollama serve` in a separate terminal
- Check Ollama is running: `curl http://localhost:11434/api/tags`
- If no models: `ollama pull llama3`

---

## Contact

**Platform curator:** Al-Amine Maouloud
**Principal Investigator:** Prof. Efthymios Papatzikis

For new site IDs, schema questions, vocabulary change requests,
or governance issues, contact the platform curator first.
