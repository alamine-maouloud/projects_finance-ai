# v1.1.2: corrections following the 22 September review

## Fixed
- **Duplicate-infant warning crashed the page** (`st.button() can't be used in an st.form()`).
  Root cause: the post-form block was indented one level too deep and was therefore
  still inside `with st.form(...)`. Dedented lines 468–553 by four spaces. No other change.

## Completeness: basis `cb_1.0` (PI definition, September 2026)
- Score on the record = **optional-field coverage**: `recorded / (recorded + not_recorded)`
  over the optional lists only. Required fields are excluded.
- Three field states: `recorded` (0 / "No" / "None" are values), `not_recorded`, `not_applicable`.
  Not-applicable fields leave numerator **and** denominator.
- Applicability rules: discharge group (once any of the three is recorded);
  `l1_ethnicity_scheme` (if ethnicity recorded); `l7_eeg_quality_flag` and
  `l7_eeg_marker_timestamps` (if EEG linked); `l3music_spl_at_incubator` (music only).
  Denominators with everything applicable: 16 / 19 / 12, unchanged lists.
- **Per-field missingness** added to Analytics: `not_recorded / applicable` per field,
  always shown with N applicable (infant / session / unit tabs).
- Export metadata now carries `completeness_basis: "cb_1.0"` next to schema and
  vocabulary versions, and the score is **recomputed at export time**.
- No new field added (discharge marker left for a proper change-control decision).

## Also
- Session form: intervention type, protocol ID and protocol version no longer pre-filled.
- `requirements-dev.txt` (pytest) and README instructions to run the suite.
- `WP2_DB_PATH` environment variable: database location can be set outside the bundle
  (needed for hospital deployment and for the UI test harness).
- App version 1.1.2.

## Tests
- Three logic-level tests renamed to describe what they actually check
  (`test_duplicate_query_finds_matching_ga_and_weight`, `test_completeness_required_only_record`,
  `test_completeness_full_record`).
- New `tests/test_ui_apptest.py`: real `streamlit.testing.v1.AppTest` interaction tests
  (6), including the twin/duplicate path and Confirm/Cancel. **Verified to fail on the
  v1.1.1 code and pass on v1.1.2.**
- Six new cb_1.0 logic tests.
- `python -m pytest tests/ -q` → 35 passed.
