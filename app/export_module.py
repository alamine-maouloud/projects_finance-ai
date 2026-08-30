"""
WP2 Platform - Export module v1.1
Fixes applied per build review (13 Aug 2026):
  - De-id scan: unambiguous identifiers block; possible names WARN only
  - Case-sensitivity fixed (no re.IGNORECASE on name pattern)
  - Clinician field validated at entry (not scanned at export)
  - Column names preserved as spec field names (not prefixed)
  - Blocked exports are logged to sys_export_audit
  - Removed inert column-name scanner
"""

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from database import get_connection, get_site_config

EXPORTS_DIR = Path(__file__).parent.parent / "exports"

# ── PII patterns ──────────────────────────────────────────────────────────────
# HARD BLOCK - unambiguous identifiers
HARD_BLOCK_PATTERNS = [
    (r"\b\d{6,}\b",                              "possible ID / record number (6+ digits)"),
    (r"\b\d{2}[/-]\d{2}[/-]\d{2,4}\b",          "possible date of birth"),
    (r"\b(dob|date of birth|born on)\b",          "date of birth reference"),
    (r"\b07\d{9}\b",                              "possible UK mobile number"),
    (r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",         "possible phone number"),
    (r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b","possible UK postcode"),
    (r"\b(NHS|MRN|patient id|record number|hospital number)\s*:?\s*\d+",
                                                  "NHS/MRN/hospital number reference"),
    (r"\b\d{3}-\d{2}-\d{4}\b",                   "possible SSN"),
]

# SOFT WARN - possible name (case-sensitive: requires Capital letters, no IGNORECASE)
SOFT_WARN_PATTERNS = [
    (r"\b[A-Z][a-z]{2,}\s[A-Z][a-z]{2,}\b",
     "possible patient name (two capitalised words)"),
]


def scan_text(text: str) -> tuple[list[str], list[str]]:
    """
    Scan free text for PII.
    Returns (hard_blocks: list[str], soft_warnings: list[str])
    Hard blocks prevent export. Soft warnings prompt confirmation.
    """
    if not text:
        return [], []

    hard = []
    for pattern, description in HARD_BLOCK_PATTERNS:
        # Hard blocks use IGNORECASE (phone, dob references are case-insensitive)
        if re.search(pattern, text, re.IGNORECASE):
            hard.append(description)

    soft = []
    for pattern, description in SOFT_WARN_PATTERNS:
        # Possible name: case-SENSITIVE - requires actual Capital letters
        # This prevents "settled well" from matching
        if re.search(pattern, text):
            soft.append(description)

    return hard, soft


def log_export_audit(site_id: str, exported_by: str, record_count: int | None,
                     schema_version: str, vocab_version: str,
                     filename: str | None, check_result: str,
                     block_reason: str | None = None) -> None:
    """Log every export attempt - both successes and refusals."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO sys_export_audit
            (timestamp, site_id, exported_by, record_count, schema_version,
             vocabulary_version, export_filename, deidentification_check, block_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(timezone.utc).isoformat(),
        site_id, exported_by, record_count,
        schema_version, vocab_version,
        filename, check_result, block_reason
    ))
    conn.commit()
    conn.close()


def run_deidentification_check(
    sessions: list[dict],
    units: list[dict]
) -> tuple[str, list[str], list[str]]:
    """
    Run de-identification check on free-text fields only.
    (Clinician IDs are validated at entry - format enforced, no names allowed.)
    Returns: ('passed'|'blocked'|'warning', hard_blocks, soft_warnings)
    """
    all_hard = []
    all_soft = []

    for session in sessions:
        notes = session.get("l5_free_text_notes") or ""
        hard, soft = scan_text(notes)
        for v in hard:
            all_hard.append(f"Session {session.get('session_id','?')} notes: {v}")
        for v in soft:
            all_soft.append(f"Session {session.get('session_id','?')} notes: {v}")

    for unit in units:
        interruptions = unit.get("l3_unit_interruptions") or ""
        hard, soft = scan_text(interruptions)
        for v in hard:
            all_hard.append(f"Unit {unit.get('unit_id','?')} interruptions: {v}")
        for v in soft:
            all_soft.append(f"Unit {unit.get('unit_id','?')} interruptions: {v}")

    if all_hard:
        return "blocked", all_hard, all_soft
    elif all_soft:
        return "warning", all_hard, all_soft
    else:
        return "passed", [], []


def export_data(user_id: str,
                force_despite_warning: bool = False) -> tuple[str, str, list[str]]:
    """
    Main export function.
    Returns: (status: 'success'|'blocked'|'warning', message, file_paths)
    """
    cfg = get_site_config()
    site_id = cfg["site_id"]
    schema_version = cfg.get("schema_version", "1.1")
    vocab_version = cfg.get("vocabulary_version", "1.1.0")
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%dT%H%M%SZ")

    conn = get_connection()
    infants  = [dict(r) for r in conn.execute(
        "SELECT * FROM infants WHERE is_void = 0").fetchall()]
    sessions = [dict(r) for r in conn.execute(
        "SELECT * FROM sessions WHERE is_void = 0").fetchall()]
    units    = [dict(r) for r in conn.execute(
        "SELECT * FROM intervention_units").fetchall()]
    conn.close()

    if not infants and not sessions:
        return "blocked", "No data to export.", []

    # ── De-identification check ───────────────────────────────────────────────
    check_result, hard_blocks, soft_warns = run_deidentification_check(sessions, units)

    if check_result == "blocked":
        block_str = "\n".join(f"  • {v}" for v in hard_blocks)
        log_export_audit(site_id, user_id, None, schema_version, vocab_version,
                         None, "blocked", block_reason=block_str)
        return "blocked", (
            f"Export BLOCKED - prohibited identifiers detected:\n{block_str}\n\n"
            "Please remove the identified content from the free-text fields before exporting."
        ), []

    if check_result == "warning" and not force_despite_warning:
        warn_str = "\n".join(f"  • {v}" for v in soft_warns)
        return "warning", (
            f"Export requires confirmation - possible names detected:\n{warn_str}\n\n"
            "These may be clinical descriptions rather than patient names. "
            "If you are certain no patient names are present, confirm to proceed."
        ), []

    # ── Build CSV rows ────────────────────────────────────────────────────────
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    safe_site = site_id.replace("-", "_")
    csv_filename  = f"export_{safe_site}_{date_str}.csv"
    meta_filename = f"export_{safe_site}_{date_str}_metadata.json"
    csv_path  = EXPORTS_DIR / csv_filename
    meta_path = EXPORTS_DIR / meta_filename

    # Get actual column names from DB schema
    conn = get_connection()
    infant_cols  = [d[0] for d in conn.execute("SELECT * FROM infants LIMIT 0").description or []]
    session_cols = [d[0] for d in conn.execute("SELECT * FROM sessions LIMIT 0").description or []]
    unit_cols    = [d[0] for d in conn.execute("SELECT * FROM intervention_units LIMIT 0").description or []]
    conn.close()

    # Build fieldnames - use spec names directly (no prefix)
    # Deduplicate: session/unit overlap with l8_ fields handled by suffix
    seen = set()
    fieldnames = []
    for col in infant_cols:
        key = col
        if key not in seen:
            seen.add(key)
            fieldnames.append(key)
    for col in session_cols:
        key = col if col not in seen else f"session_{col}"
        seen.add(key)
        fieldnames.append(key)
    for col in unit_cols:
        key = col if col not in seen else f"unit_{col}"
        seen.add(key)
        fieldnames.append(key)

    rows = []
    for session in sessions:
        infant = next((i for i in infants
                       if i["l1_infant_id"] == session["l1_infant_id"]), {})
        session_units = [u for u in units if u["session_id"] == session["session_id"]]

        base_row = {k: None for k in fieldnames}
        # Infant fields
        for col in infant_cols:
            base_row[col] = infant.get(col)
        # Session fields (with collision handling)
        for col in session_cols:
            key = col if col in fieldnames else f"session_{col}"
            base_row[key] = session.get(col)

        if session_units:
            for unit in session_units:
                row = dict(base_row)
                for col in unit_cols:
                    key = col if (col in fieldnames and col not in session_cols) else f"unit_{col}"
                    row[key] = unit.get(col)
                # Ensure federation stamps
                row["l8_site_id"] = site_id
                row["l8_schema_version"] = schema_version
                row["l8_vocabulary_version"] = vocab_version
                rows.append(row)
        else:
            base_row["l8_site_id"] = site_id
            base_row["l8_schema_version"] = schema_version
            base_row["l8_vocabulary_version"] = vocab_version
            rows.append(base_row)

    if rows:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

    # ── JSON metadata ─────────────────────────────────────────────────────────
    metadata = {
        "schema_version": schema_version,
        "vocabulary_version": vocab_version,
        "site_id": site_id,
        "export_date": now.isoformat(),
        "record_count": len(rows),
        "infant_count": len(infants),
        "session_count": len(sessions),
        "unit_count": len(units),
        "layers": ["L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"],
        "deidentification_check": check_result,
        "soft_warnings": soft_warns,
        "variables": fieldnames,
        "export_files": {"csv": csv_filename, "metadata": meta_filename}
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    # ── Log success ───────────────────────────────────────────────────────────
    log_export_audit(site_id, user_id, len(rows), schema_version, vocab_version,
                     csv_filename, check_result)

    msg = (f"✅ Export successful - {len(rows)} records, "
           f"{len(infants)} infants, {len(sessions)} sessions, {len(units)} units.")
    if soft_warns:
        msg += f"\n⚠️ Exported with {len(soft_warns)} soft warning(s) confirmed by user."

    return "success", msg, [str(csv_path), str(meta_path)]
