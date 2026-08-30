"""
WP2 Platform - Database module v1.1
SQLite operational store (71-field schema v1.1, 3 tables)
DuckDB analytical engine (reads SQLite read-only)
Schema version: 1.1
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.1"
VOC_VERSION = "1.1.0"
DB_PATH = Path(__file__).parent.parent / "data" / "wp2_platform.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(site_id: str, vocab_version: str = VOC_VERSION) -> None:
    """Initialise all tables. Idempotent."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sys_metadata (
            key   TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    cur.execute("INSERT OR IGNORE INTO sys_metadata VALUES ('schema_version', ?)", (SCHEMA_VERSION,))
    cur.execute("INSERT OR IGNORE INTO sys_metadata VALUES ('vocabulary_version', ?)", (vocab_version,))
    cur.execute("INSERT OR IGNORE INTO sys_metadata VALUES ('site_id', ?)", (site_id,))
    cur.execute("INSERT OR IGNORE INTO sys_metadata VALUES ('created_at', ?)",
                (datetime.now(timezone.utc).isoformat(),))

    # ── Layer 1 - Infant Profile (71 fields total, L1=21) ────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS infants (
            l1_infant_id                 TEXT PRIMARY KEY,
            -- Required
            l1_gestational_age_weeks     INTEGER NOT NULL,
            l1_gestational_age_days      INTEGER NOT NULL,
            l1_birth_weight_g            REAL    NOT NULL,
            -- Optional admission baseline
            l1_sex                       TEXT,
            l1_primary_diagnosis         TEXT,
            l1_birth_length_cm           REAL,
            l1_birth_hc_cm               REAL,
            l1_ethnicity                 TEXT,
            l1_ethnicity_scheme          TEXT,
            l1_antenatal_corticosteroids TEXT,
            l1_surfactant                TEXT,
            l1_brain_injury_ivh          TEXT,
            l1_brain_injury_pvl          TEXT,
            l1_cld_bpd                   TEXT,
            l1_sepsis_confirmed          TEXT,
            l1_rop_result                TEXT,
            l1_hearing_result            TEXT,
            -- Optional discharge (filled later via edit)
            l1_discharge_los             INTEGER,
            l1_weight_discharge_g        REAL,
            l1_feeding_status_discharge  TEXT,
            -- Provenance (system-stamped)
            l8_site_id                   TEXT NOT NULL,
            l8_schema_version            TEXT NOT NULL DEFAULT '1.1',
            l8_vocabulary_version        TEXT NOT NULL DEFAULT '1.1.0',
            l8_created_by                TEXT NOT NULL,
            l8_record_creation_timestamp TEXT NOT NULL,
            -- Soft delete
            is_void                      INTEGER NOT NULL DEFAULT 0,
            void_reason                  TEXT,
            void_timestamp               TEXT,
            -- Constraints
            CHECK (l1_gestational_age_weeks BETWEEN 22 AND 44),
            CHECK (l1_gestational_age_days  BETWEEN 0  AND 6),
            CHECK (l1_birth_weight_g        BETWEEN 300 AND 6000),
            CHECK (l1_sepsis_confirmed IN ('Yes', 'No', NULL)),
            CHECK (is_void IN (0, 1))
        )
    """)

    # ── Sessions (Layers 2,4,5,6,7,8) ────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id               TEXT PRIMARY KEY,
            l1_infant_id             TEXT NOT NULL REFERENCES infants(l1_infant_id),
            -- L2 Required
            l2_session_datetime      TEXT NOT NULL,
            l2_session_number        INTEGER NOT NULL,
            l2_clinician_id          TEXT NOT NULL,
            l2_intervention_type     TEXT NOT NULL,
            l2_protocol_id           TEXT NOT NULL,
            l2_protocol_version      TEXT NOT NULL,
            -- L2 Optional
            l2_randomization_seed    TEXT,
            l2_skin_to_skin          TEXT,
            l2_parent_present        TEXT,
            l2_ambient_noise         TEXT,
            l2_lighting              TEXT,
            l2_corrected_gestational_age REAL,
            l2_respiratory_support   TEXT,
            l2_fio2                  REAL,
            l2_nutrition             TEXT,
            l2_recent_surgery        TEXT,
            -- L4 per-session
            l4_behavioural_state_start TEXT,
            l4_behavioural_state_end   TEXT,
            l4_session_tolerated     TEXT NOT NULL DEFAULT 'Yes',
            -- L5
            l5_overall_outcome       TEXT NOT NULL,
            l5_clinician_impression  TEXT,
            l5_free_text_notes       TEXT,
            l5_adverse_event         TEXT NOT NULL DEFAULT 'No',
            -- L6
            l6_parental_anxiety      INTEGER,
            l6_parent_participation  TEXT,
            l6_family_musical_preference TEXT,
            -- L7
            l7_eeg_recording_linked  TEXT,
            l7_eeg_quality_flag      TEXT,
            -- L8
            l8_completeness_score    REAL,
            l8_consistency_check     TEXT,
            l8_site_id               TEXT NOT NULL,
            l8_schema_version        TEXT NOT NULL DEFAULT '1.1',
            l8_vocabulary_version    TEXT NOT NULL DEFAULT '1.1.0',
            l8_created_by            TEXT NOT NULL,
            l8_record_creation_timestamp TEXT NOT NULL,
            -- Soft delete
            is_void                  INTEGER NOT NULL DEFAULT 0,
            void_reason              TEXT,
            -- Constraints
            CHECK (l2_fio2 IS NULL OR (l2_fio2 BETWEEN 21 AND 100)),
            CHECK (l6_parental_anxiety IS NULL OR (l6_parental_anxiety BETWEEN 0 AND 10)),
            CHECK (l5_free_text_notes IS NULL OR length(l5_free_text_notes) <= 500),
            CHECK (l4_session_tolerated IN ('Yes', 'No')),
            CHECK (l5_adverse_event IN ('Yes', 'No')),
            CHECK (is_void IN (0, 1))
        )
    """)

    # ── Intervention units (Layers 3,4,7) ────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS intervention_units (
            unit_id                  TEXT PRIMARY KEY,
            session_id               TEXT NOT NULL REFERENCES sessions(session_id),
            l1_infant_id             TEXT NOT NULL,
            unit_order               INTEGER NOT NULL,
            -- L3 Required
            l3_unit_condition        TEXT NOT NULL,
            l3_unit_start_end        TEXT,
            l3_unit_duration         REAL NOT NULL,
            -- L3 Optional
            l3_unit_delivery_mode    TEXT,
            l3_unit_interruptions    TEXT,
            l3music_spl_at_incubator REAL,
            -- L4 per-unit
            l4_heart_rate_pre_bpm    REAL,
            l4_heart_rate_during_bpm REAL,
            l4_heart_rate_post_bpm   REAL,
            l4_spo2_pre_pct          REAL,
            l4_spo2_during_pct       REAL,
            l4_spo2_post_pct         REAL,
            l4_stress_signs          TEXT,
            l4_engagement_signs      TEXT,
            -- L7
            l7_eeg_marker_timestamps TEXT,
            -- Provenance
            l8_site_id               TEXT NOT NULL,
            l8_schema_version        TEXT NOT NULL DEFAULT '1.1',
            l8_vocabulary_version    TEXT NOT NULL DEFAULT '1.1.0',
            l8_created_by            TEXT NOT NULL,
            l8_record_creation_timestamp TEXT NOT NULL,
            -- Constraints
            CHECK (l3_unit_duration > 0),
            CHECK (l4_spo2_pre_pct    IS NULL OR (l4_spo2_pre_pct    BETWEEN 0 AND 100)),
            CHECK (l4_spo2_during_pct IS NULL OR (l4_spo2_during_pct BETWEEN 0 AND 100)),
            CHECK (l4_spo2_post_pct   IS NULL OR (l4_spo2_post_pct   BETWEEN 0 AND 100)),
            CHECK (l4_stress_signs    IN ('Yes', 'No', NULL)),
            CHECK (l4_engagement_signs IN ('Yes', 'No', NULL))
        )
    """)

    # ── Audit tables (append-only) ────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sys_data_audit (
            audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            site_id     TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            action      TEXT NOT NULL,
            record_id   TEXT NOT NULL,
            infant_id   TEXT,
            detail      TEXT,
            schema_version     TEXT NOT NULL,
            vocabulary_version TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sys_export_audit (
            export_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            site_id     TEXT NOT NULL,
            exported_by TEXT NOT NULL,
            record_count INTEGER,
            schema_version     TEXT NOT NULL,
            vocabulary_version TEXT NOT NULL,
            export_filename    TEXT,
            deidentification_check TEXT NOT NULL,
            block_reason TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS sys_ai_audit_trail (
            audit_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            user_id     TEXT NOT NULL,
            user_prompt TEXT NOT NULL,
            generated_sql      TEXT,
            retrieved_note_ids TEXT,
            llm_response       TEXT,
            guardrail_triggered INTEGER NOT NULL DEFAULT 0,
            model_version      TEXT,
            vocabulary_version TEXT NOT NULL,
            schema_version     TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def get_site_config() -> dict:
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM sys_metadata").fetchall()
    conn.close()
    return {r["key"]: r["value"] for r in rows}


def log_data_audit(user_id: str, action: str, record_id: str,
                   infant_id: str = None, detail: str = None) -> None:
    cfg = get_site_config()
    conn = get_connection()
    conn.execute("""
        INSERT INTO sys_data_audit
            (timestamp, site_id, user_id, action, record_id, infant_id, detail,
             schema_version, vocabulary_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(timezone.utc).isoformat(),
        cfg["site_id"], user_id, action, record_id, infant_id, detail,
        cfg.get("schema_version", SCHEMA_VERSION),
        cfg.get("vocabulary_version", VOC_VERSION)
    ))
    conn.commit()
    conn.close()
