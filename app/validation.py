"""
WP2 Platform - Validation engine v1.1
Three check classes per Build Specification v1.1:
  1. Conformance  - required fields, ranges, formats
  2. Completeness - cb_1.0 optional-field coverage (see COMPLETENESS_BASIS)
  3. Plausibility - cross-field logic

IMPORTANT: boolean fields are now stored as 'Yes'/'No'/None (not 0/1).
Zero is a valid numeric value and must NEVER be treated as missing.
"""

import re

# ── Fields included in completeness score ────────────────────────────────────
# Rule: a field counts ONLY if there is a UI input for it.
# Checkboxes replaced by Yes/No dropdowns - None means "not recorded".

INFANT_OPTIONAL_SCORED = [
    "l1_sex", "l1_primary_diagnosis", "l1_birth_length_cm", "l1_birth_hc_cm",
    "l1_ethnicity", "l1_antenatal_corticosteroids", "l1_surfactant",
    "l1_brain_injury_ivh", "l1_brain_injury_pvl", "l1_cld_bpd",
    "l1_sepsis_confirmed", "l1_rop_result", "l1_hearing_result",
    # Discharge group: applicable only once discharge documentation begins
    "l1_discharge_los", "l1_weight_discharge_g", "l1_feeding_status_discharge",
]

SESSION_OPTIONAL_SCORED = [
    "l2_randomization_seed",
    "l2_skin_to_skin",       # Yes/No/None dropdown
    "l2_parent_present",     # Yes/No/None dropdown
    "l2_ambient_noise", "l2_lighting",
    "l2_corrected_gestational_age",
    "l2_respiratory_support", "l2_fio2",
    "l2_nutrition", "l2_recent_surgery",
    "l4_behavioural_state_start", "l4_behavioural_state_end",
    "l5_clinician_impression", "l5_free_text_notes",
    "l6_parental_anxiety", "l6_parent_participation",
    "l6_family_musical_preference",  # Yes/No/None dropdown
    "l7_eeg_recording_linked",       # Yes/No/None dropdown
    "l7_eeg_quality_flag",
]

UNIT_OPTIONAL_SCORED = [
    "l3_unit_delivery_mode",
    "l3_unit_interruptions",
    "l3music_spl_at_incubator",
    "l4_heart_rate_pre_bpm", "l4_heart_rate_during_bpm", "l4_heart_rate_post_bpm",
    "l4_spo2_pre_pct", "l4_spo2_during_pct", "l4_spo2_post_pct",
    "l4_stress_signs",       # Yes/No/None
    "l4_engagement_signs",   # Yes/No/None
    "l7_eeg_marker_timestamps",
]

# Validate clinician ID format: must be CLIN_XXX (no spaces allowed)
CLINICIAN_ID_PATTERN = re.compile(r'^[A-Z0-9_]+$')


def _is_present(val) -> bool:
    """True if value is genuinely recorded (not None, not empty string).
    Note: 0 and 0.0 ARE valid recorded values - never treat as missing."""
    if val is None:
        return False
    if isinstance(val, str) and val.strip() == "":
        return False
    return True


# ── Completeness basis cb_1.0 (PI definition, September 2026) ────────────────
#
# Score on the record  = optional-field COVERAGE:
#       recorded / (recorded + not_recorded)   over optional fields only.
# Required fields are excluded: validation blocks any record missing one, so
# they are always present and would add the same constant to every record.
#
# Every field is in exactly one of three states:
#   "recorded"       - a value is present (0, "No", "None" are VALUES)
#   "not_recorded"   - the field applies here and was left blank
#   "not_applicable" - the field cannot hold a value for this record;
#                      it leaves BOTH numerator and denominator.
#
# Applicability rules (a field counts only when it applies):
#   discharge group (l1_discharge_los, l1_weight_discharge_g,
#     l1_feeding_status_discharge)  -> at least one of the three is recorded
#   l1_ethnicity_scheme             -> l1_ethnicity is recorded
#   l7_eeg_quality_flag (session)   -> l7_eeg_recording_linked == "Yes"
#   l7_eeg_marker_timestamps (unit) -> parent session has an EEG recording
#                                      linked (pass eeg_linked=True/False)
#   l3music_spl_at_incubator (unit) -> the intervention is a music
#                                      intervention (pass intervention_type)
#   everything else                 -> always applicable
COMPLETENESS_BASIS = "cb_1.0"

DISCHARGE_GROUP = ("l1_discharge_los", "l1_weight_discharge_g",
                   "l1_feeding_status_discharge")

# kept for backward compatibility with older tests / callers
INFANT_REQUIRED_SCORED  = ["l1_gestational_age_weeks", "l1_gestational_age_days",
                           "l1_birth_weight_g"]
SESSION_REQUIRED_SCORED = ["l2_session_datetime", "l2_session_number",
                           "l2_clinician_id", "l2_intervention_type",
                           "l2_protocol_id", "l2_protocol_version",
                           "l5_overall_outcome", "l5_adverse_event"]
UNIT_REQUIRED_SCORED    = ["l3_unit_condition", "l3_unit_duration"]


def _is_music(intervention_type) -> bool:
    return isinstance(intervention_type, str) and "MUSIC" in intervention_type.upper()


def field_applies(field: str, record: dict, *,
                  intervention_type=None, eeg_linked=None) -> bool:
    """Return True when `field` is applicable to this record (cb_1.0 rules)."""
    if field in DISCHARGE_GROUP:
        return any(_is_present(record.get(f)) for f in DISCHARGE_GROUP)
    if field == "l1_ethnicity_scheme":
        return _is_present(record.get("l1_ethnicity"))
    if field == "l7_eeg_quality_flag":
        return record.get("l7_eeg_recording_linked") == "Yes"
    if field == "l7_eeg_marker_timestamps":
        if eeg_linked is not None:
            return bool(eeg_linked)
        return record.get("l7_eeg_recording_linked") == "Yes"
    if field == "l3music_spl_at_incubator":
        itype = intervention_type if intervention_type is not None \
                else record.get("l2_intervention_type")
        return _is_music(itype)
    return True


def field_state(field: str, record: dict, **ctx) -> str:
    """'recorded' | 'not_recorded' | 'not_applicable' for one field."""
    if not field_applies(field, record, **ctx):
        return "not_applicable"
    return "recorded" if _is_present(record.get(field)) else "not_recorded"


def completeness_breakdown(record: dict, optional_fields: list[str], **ctx) -> dict:
    """Counts per state over the optional fields of one record."""
    states = {"recorded": 0, "not_recorded": 0, "not_applicable": 0}
    for f in optional_fields:
        states[field_state(f, record, **ctx)] += 1
    return states


def compute_completeness(record: dict,
                         optional_fields: list[str],
                         required_fields: list[str] | None = None,
                         **ctx) -> float:
    """
    cb_1.0 optional-field coverage, 0-100.
    `required_fields` is accepted and IGNORED (kept for call compatibility).
    ctx: intervention_type=..., eeg_linked=... for unit records.
    """
    b = completeness_breakdown(record, optional_fields, **ctx)
    applicable = b["recorded"] + b["not_recorded"]
    if applicable == 0:
        return 100.0     # nothing applicable -> nothing missing
    return round(b["recorded"] / applicable * 100, 1)


def field_missingness(records: list[dict], fields: list[str],
                      ctx_fn=None) -> list[dict]:
    """
    Per-field missingness across a cohort (analytics output, not stored):
      not_recorded / applicable, as %, always with N applicable.
    ctx_fn(record) may return a dict of ctx kwargs (e.g. intervention_type).
    """
    out = []
    for f in fields:
        n_app = n_missing = 0
        for r in records:
            ctx = ctx_fn(r) if ctx_fn else {}
            st = field_state(f, r, **ctx)
            if st == "not_applicable":
                continue
            n_app += 1
            if st == "not_recorded":
                n_missing += 1
        pct = round(n_missing / n_app * 100, 1) if n_app else None
        out.append({"field": f, "n_applicable": n_app,
                    "n_missing": n_missing, "pct_missing": pct})
    return out


def validate_clinician_id(clinician_id: str) -> tuple[bool, str]:
    """Validate clinician ID: no spaces, alphanumeric + underscore only."""
    if not clinician_id or not clinician_id.strip():
        return False, "Clinician ID is required"
    if " " in clinician_id:
        return False, "Clinician ID must not contain spaces (use format CLIN_001)"
    if not CLINICIAN_ID_PATTERN.match(clinician_id.strip()):
        return False, "Clinician ID must contain only letters, digits and underscores (e.g. CLIN_001)"
    return True, ""


def validate_infant(record: dict) -> tuple[bool, list[str], float]:
    issues = []

    # Required fields
    for field in ["l1_infant_id", "l1_gestational_age_weeks",
                  "l1_gestational_age_days", "l1_birth_weight_g"]:
        if not _is_present(record.get(field)):
            issues.append(f"REQUIRED: {field} is missing")

    # Range checks
    ga_wk = record.get("l1_gestational_age_weeks")
    if _is_present(ga_wk):
        try:
            if not (22 <= int(ga_wk) <= 44):
                issues.append(f"RANGE: l1_gestational_age_weeks must be 22-44, got {ga_wk}")
        except (ValueError, TypeError):
            issues.append("TYPE: l1_gestational_age_weeks must be an integer")

    ga_d = record.get("l1_gestational_age_days")
    if _is_present(ga_d):
        try:
            if not (0 <= int(ga_d) <= 6):
                issues.append(f"RANGE: l1_gestational_age_days must be 0-6, got {ga_d}")
        except (ValueError, TypeError):
            issues.append("TYPE: l1_gestational_age_days must be an integer")

    bw = record.get("l1_birth_weight_g")
    if _is_present(bw):
        try:
            if not (300 <= float(bw) <= 6000):
                issues.append(f"RANGE: l1_birth_weight_g must be 300-6000g, got {bw}")
        except (ValueError, TypeError):
            issues.append("TYPE: l1_birth_weight_g must be numeric")

    score = compute_completeness(record, INFANT_OPTIONAL_SCORED)
    conformance_passed = not any(
        i.startswith("REQUIRED") or i.startswith("RANGE") or i.startswith("TYPE")
        for i in issues
    )
    return conformance_passed, issues, score


def validate_session(record: dict) -> tuple[bool, list[str], float]:
    issues = []

    for field in ["l2_session_datetime", "l2_session_number", "l2_clinician_id",
                  "l2_intervention_type", "l2_protocol_id", "l2_protocol_version",
                  "l5_overall_outcome", "l5_adverse_event"]:
        if not _is_present(record.get(field)):
            issues.append(f"REQUIRED: {field} is missing")

    # Clinician ID format
    clin_id = record.get("l2_clinician_id", "")
    if _is_present(clin_id):
        valid, msg = validate_clinician_id(str(clin_id))
        if not valid:
            issues.append(f"FORMAT: {msg}")

    # FiO2 range (note: 21 is valid = room air)
    fio2 = record.get("l2_fio2")
    if _is_present(fio2):
        try:
            fio2_val = float(fio2)
            if not (21 <= fio2_val <= 100):
                issues.append(f"RANGE: l2_fio2 must be 21-100%, got {fio2_val}")
        except (ValueError, TypeError):
            issues.append("TYPE: l2_fio2 must be numeric")

    # Parental anxiety range (note: 0 is valid = calm parent)
    anxiety = record.get("l6_parental_anxiety")
    if _is_present(anxiety):
        try:
            a = int(anxiety)
            if not (0 <= a <= 10):
                issues.append(f"RANGE: l6_parental_anxiety must be 0-10, got {a}")
        except (ValueError, TypeError):
            issues.append("TYPE: l6_parental_anxiety must be an integer")

    notes = record.get("l5_free_text_notes")
    if notes and len(str(notes)) > 500:
        issues.append(f"LENGTH: l5_free_text_notes exceeds 500 chars ({len(str(notes))})")

    # Plausibility
    tolerated = record.get("l4_session_tolerated")
    outcome = record.get("l5_overall_outcome")
    if tolerated == "No" and outcome == "OUT_COMPLETE":
        issues.append("PLAUSIBILITY: session not tolerated but outcome is Complete")

    adverse = record.get("l5_adverse_event")
    if adverse == "Yes" and outcome == "OUT_COMPLETE":
        issues.append("PLAUSIBILITY: adverse event flagged but outcome is Complete - please confirm")

    score = compute_completeness(record, SESSION_OPTIONAL_SCORED)
    conformance_passed = not any(
        i.startswith("REQUIRED") or i.startswith("RANGE") or
        i.startswith("TYPE") or i.startswith("LENGTH") or i.startswith("FORMAT")
        for i in issues
    )
    return conformance_passed, issues, score


def validate_unit(record: dict,
                  intervention_type: str = "ITYPE_MUSIC",
                  eeg_linked: bool | None = None) -> tuple[bool, list[str], float]:
    issues = []

    for field in ["l3_unit_condition", "l3_unit_duration"]:
        if not _is_present(record.get(field)):
            issues.append(f"REQUIRED: {field} is missing")

    duration = record.get("l3_unit_duration")
    if _is_present(duration):
        try:
            if float(duration) <= 0:
                issues.append(f"RANGE: l3_unit_duration must be > 0 seconds")
        except (ValueError, TypeError):
            issues.append("TYPE: l3_unit_duration must be numeric")

    for spo2_field in ["l4_spo2_pre_pct", "l4_spo2_during_pct", "l4_spo2_post_pct"]:
        val = record.get(spo2_field)
        if _is_present(val):
            try:
                v = float(val)
                if not (0 <= v <= 100):
                    issues.append(f"RANGE: {spo2_field} must be 0-100%")
            except (ValueError, TypeError):
                issues.append(f"TYPE: {spo2_field} must be numeric")

    # HR plausibility
    for hr_field in ["l4_heart_rate_pre_bpm", "l4_heart_rate_during_bpm", "l4_heart_rate_post_bpm"]:
        val = record.get(hr_field)
        if _is_present(val):
            try:
                v = float(val)
                if not (40 <= v <= 280):
                    issues.append(f"PLAUSIBILITY: {hr_field}={v} outside 40-280 bpm")
            except (ValueError, TypeError):
                pass

    score = compute_completeness(record, UNIT_OPTIONAL_SCORED,
                                 intervention_type=intervention_type,
                                 eeg_linked=eeg_linked)
    conformance_passed = not any(
        i.startswith("REQUIRED") or i.startswith("RANGE") or i.startswith("TYPE")
        for i in issues
    )
    return conformance_passed, issues, score
