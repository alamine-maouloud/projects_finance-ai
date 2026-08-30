# WP2 Platform - v1.1

Research-grade developmental-care documentation platform for NICU research.
Build Specification v1.1 · Vocabulary voc_1.1.0 · Schema v1.1 (71 fields)

## Requirements

- **Python 3.10 or newer** (required - uses syntax introduced in Python 3.10)
- macOS (primary), Windows (secondary)

> ⚠️ macOS ships with Python 3.9 by default. The app will not start on 3.9.
> Install Python 3.10+ via [python.org](https://python.org) or `brew install python@3.11`

## Quick start

```bash
# 1. Check your Python version
python3 --version   # must be 3.10 or higher

# 2. Go to the project folder
cd wp2_platform

# 3. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate   # macOS/Linux
# .venv\Scripts\activate    # Windows

# 4. Install dependencies
pip install -r requirements.txt

# 5. Launch
streamlit run app/main.py
```

Opens at http://localhost:8501

**First launch:** enter your Site ID (`{ISO2}-{INST}-{NNN}`, e.g. `AE-CUD-001`) and user ID.

## Run tests

```bash
cd wp2_platform
python3 tests/test_wp2.py
```

Tests cover: schema field count (71 fields / 8 layers), validation, privacy scan, vocabulary.

## Project structure

```
wp2_platform/
├── app/
│   ├── main.py            # Streamlit UI (5 tabs)
│   ├── database.py        # SQLite schema v1.1 (71 fields) + DuckDB
│   ├── vocabulary.py      # Vocabulary loader (voc_1.1.0)
│   ├── validation.py      # Layer 8 validation engine
│   └── export_module.py   # CSV/JSON export + de-id scan
├── vocabulary/
│   └── voc_1.1.0.json     # Authoritative vocabulary manifest (PI)
├── .streamlit/
│   └── config.toml        # Disables Deploy button + telemetry
├── tests/
│   └── test_wp2.py        # Test suite (16 tests)
├── data/                  # SQLite .db file (auto-created)
├── exports/               # CSV/JSON exports
└── requirements.txt       # Pinned dependencies
```

## What changed in v1.1

- Schema: 70 → 71 fields (brain injury split into l1_brain_injury_ivh + l1_brain_injury_pvl)
- Vocabulary: voc_1.0.0 → voc_1.1.0 (117 codes, all field names per spec)
- De-id scan: hard-block vs soft-warn distinction; case-sensitivity fixed
- Clinician ID: format validated at entry (no spaces, alphanumeric + underscore)
- Completeness: booleans changed to Yes/No dropdowns; zero treated as valid value
- Export: column names preserved as spec field names
- Blocked exports logged to audit trail
- Deploy button and telemetry disabled via config.toml
- Future intervention types disabled (not selectable)
- Required fields start empty (no pre-fill)
- Persistent success message across refresh
- Active infant context shown in sidebar and persisted across tabs
- Edit function for discharge fields added
- Tests added (16 tests, 4 categories)
