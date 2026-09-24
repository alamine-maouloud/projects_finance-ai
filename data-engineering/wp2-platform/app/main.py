"""
WP2 Platform - Streamlit application v1.1
Build review fixes (13 Aug 2026): all 28 items addressed.
Run: streamlit run app/main.py
"""

import streamlit as st
import pandas as pd
import sys
import secrets
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent))

from database import (get_connection, get_site_config, init_db,
                      log_data_audit, SCHEMA_VERSION, VOC_VERSION)
from vocabulary import (selectbox_options, label_to_code, code_to_label,
                        get_version, active_intervention_types, get_labels)
from validation import (validate_infant, validate_session, validate_unit,
                        completeness_breakdown, field_missingness,
                        INFANT_OPTIONAL_SCORED, SESSION_OPTIONAL_SCORED,
                        UNIT_OPTIONAL_SCORED, COMPLETENESS_BASIS)
from export_module import export_data

APP_VERSION = "1.1.2"


def _cov_txt(record: dict, fields: list, **ctx) -> str:
    """'x/y applicable optional fields (n not applicable)' for save messages."""
    b = completeness_breakdown(record, fields, **ctx)
    n_app = b["recorded"] + b["not_recorded"]
    na = f", {b['not_applicable']} not applicable" if b["not_applicable"] else ""
    return f"{b['recorded']}/{n_app} applicable optional fields{na}"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="WP2 Platform",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ── Site init ─────────────────────────────────────────────────────────────────
def ensure_site_init():
    from database import DB_PATH
    if not DB_PATH.exists():
        st.title("WP2 Platform - Site Setup")
        st.info("First run: configure your site identifier.")
        with st.form("site_setup"):
            site_id = st.text_input(
                "Site ID *",
                placeholder="e.g. AE-CUD-001  |  format: {ISO2}-{INST}-{NNN}"
            )
            user_id = st.text_input("Your user ID *", placeholder="e.g. USR_001")
            submitted = st.form_submit_button("Initialise site")
            if submitted:
                if not site_id or not user_id:
                    st.error("Both fields are required.")
                else:
                    init_db(site_id=site_id.strip(), vocab_version=VOC_VERSION)
                    st.session_state["user_id"] = user_id.strip()
                    st.success(f"Site {site_id} initialised.")
                    st.rerun()
        st.stop()


ensure_site_init()
cfg = get_site_config()
SITE_ID = cfg.get("site_id", "UNKNOWN")

for _k, _v in {
    "user_id": "USR_001",
    "active_infant_id": None,
    "active_infant_label": None,
    "active_session_id": None,
    "infant_edit_mode": False,
    "infant_void_mode": False,
    "session_edit_mode": False,
    "session_void_mode": False,
    "export_warning_pending": False,
    "export_warning_message": "",
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── Helpers ───────────────────────────────────────────────────────────────────
def new_infant_id() -> str:
    return f"INF_{SITE_ID}_{secrets.token_hex(4)}"

def new_session_id() -> str:
    return f"SESSION_{SITE_ID}_{secrets.token_hex(4)}"

def new_unit_id() -> str:
    return f"UNIT_{SITE_ID}_{secrets.token_hex(4)}"

def yes_no_select(label: str, key: str = None) -> str | None:
    """Dropdown returning 'Yes', 'No', or None (not recorded)."""
    val = st.selectbox(label, ["", "Yes", "No"], key=key)
    return val if val else None

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏥 WP2 Platform")
    st.caption(f"**App version:** {APP_VERSION}")
    st.caption(f"Site: **{SITE_ID}**")
    st.caption(f"Schema: v{SCHEMA_VERSION}  |  Vocab: voc_{get_version()}")
    st.caption(f"User: {st.session_state['user_id']}")

    # Persistent infant context banner
    if st.session_state["active_infant_id"]:
        st.success(f"📌 Working on:\n{st.session_state['active_infant_label']}")
    else:
        st.info("No infant selected.\nSelect one in the Infants tab.")

    st.divider()
    tab_selection = st.radio(
        "Navigation",
        ["🧒 Infants", "📋 Sessions", "🎵 Intervention Units",
         "📊 Analytics", "📤 Export"],
        label_visibility="collapsed"
    )


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 - INFANTS
# ═════════════════════════════════════════════════════════════════════════════
def _sel_idx(field: str, current_code: str | None) -> int:
    """Return selectbox index for current concept code (0 = blank option)."""
    from vocabulary import get_labels, label_to_code, code_to_label
    if not current_code:
        return 0
    labels = get_labels(field)
    label = code_to_label(field, current_code)
    try:
        return labels.index(label) + 1  # +1 for blank option
    except ValueError:
        return 0


def _bool_idx(current_val: str | None) -> int:
    """Return index in ['', 'Yes', 'No'] for current stored value."""
    if current_val == "Yes":
        return 1
    if current_val == "No":
        return 2
    return 0


def tab_infants():
    st.title("🧒 Infant Profile - Layer 1")
    st.caption("Per-infant variables. Required fields are marked *.")

    conn = get_connection()
    infants = conn.execute(
        "SELECT * FROM infants WHERE is_void = 0 "
        "ORDER BY l8_record_creation_timestamp DESC"
    ).fetchall()
    conn.close()

    col_form, col_list = st.columns([2, 1])

    # ── Infant list + actions (right column) ──────────────────────────────────
    with col_list:
        st.subheader("Registered infants")
        if infants:
            for inf in infants:
                lbl = (f"{inf['l1_infant_id']} - "
                       f"{inf['l1_gestational_age_weeks']}+"
                       f"{inf['l1_gestational_age_days']}wk, "
                       f"{inf['l1_birth_weight_g']}g")
                if st.button(lbl, key=f"sel_{inf['l1_infant_id']}"):
                    st.session_state["active_infant_id"] = inf["l1_infant_id"]
                    st.session_state["active_infant_label"] = (
                        f"{inf['l1_infant_id']} "
                        f"({inf['l1_gestational_age_weeks']}+"
                        f"{inf['l1_gestational_age_days']}wk, "
                        f"{inf['l1_birth_weight_g']}g)"
                    )
                    st.session_state["infant_edit_mode"] = False
                    st.rerun()
        else:
            st.info("No infants registered yet.")

        # ── Edit / Void panel for selected infant ─────────────────────────────
        if st.session_state.get("active_infant_id"):
            aid = st.session_state["active_infant_id"]
            st.divider()

            # Load current values
            conn = get_connection()
            rec = conn.execute(
                "SELECT * FROM infants WHERE l1_infant_id = ?", (aid,)
            ).fetchone()
            conn.close()

            if rec:
                ea, eb = st.columns(2)
                if ea.button("✏️ Edit this infant", key="btn_edit_inf"):
                    st.session_state["infant_edit_mode"] = True
                    st.rerun()
                if eb.button("🗑 Mark as void", key="btn_void_inf"):
                    st.session_state["infant_void_mode"] = True
                    st.rerun()

                # ── Void confirmation ─────────────────────────────────────────
                if st.session_state.get("infant_void_mode"):
                    with st.form("void_infant_form"):
                        st.warning(f"⚠️ Mark {aid} as void?")
                        void_reason = st.text_input(
                            "Reason (required)", placeholder="e.g. Duplicate entry"
                        )
                        c1, c2 = st.columns(2)
                        confirm = c1.form_submit_button("Confirm void", type="primary")
                        cancel  = c2.form_submit_button("Cancel")
                        if confirm:
                            if not void_reason.strip():
                                st.error("Reason is required.")
                            else:
                                conn = get_connection()
                                conn.execute("""
                                    UPDATE infants SET
                                        is_void = 1,
                                        void_reason = ?,
                                        void_timestamp = ?
                                    WHERE l1_infant_id = ?
                                """, (void_reason.strip(), now_iso(), aid))
                                conn.commit()
                                conn.close()
                                log_data_audit(
                                    st.session_state["user_id"],
                                    "infant_voided", aid, aid,
                                    f"Reason: {void_reason.strip()}"
                                )
                                st.session_state["active_infant_id"] = None
                                st.session_state["active_infant_label"] = None
                                st.session_state["infant_void_mode"] = False
                                st.session_state["last_save_msg"] = f"✅ {aid} marked as void."
                                st.rerun()
                        if cancel:
                            st.session_state["infant_void_mode"] = False
                            st.rerun()

                # ── Edit form ─────────────────────────────────────────────────
                elif st.session_state.get("infant_edit_mode"):
                    st.subheader("Edit infant record")
                    with st.form("edit_infant_form"):
                        st.caption(f"Editing: {aid}")

                        c1, c2 = st.columns(2)
                        ga_w = c1.number_input("GA weeks *", 22, 44,
                                               value=int(rec["l1_gestational_age_weeks"]))
                        ga_d = c2.number_input("GA days *", 0, 6,
                                               value=int(rec["l1_gestational_age_days"]))
                        bw = st.number_input("Birth weight (g) *", 300.0, 6000.0,
                                             value=float(rec["l1_birth_weight_g"]), step=10.0)

                        def cur(field): return rec[field] or ""
                        def cur_label(field, vocab):
                            code = rec[field]
                            return code_to_label(vocab, code) if code else ""

                        c3, c4 = st.columns(2)
                        sex  = c3.selectbox("Sex", selectbox_options("l1_sex"),
                                            index=_sel_idx("l1_sex", rec["l1_sex"]))
                        diag = c4.selectbox("Primary diagnosis",
                                            selectbox_options("l1_primary_diagnosis"),
                                            index=_sel_idx("l1_primary_diagnosis", rec["l1_primary_diagnosis"]))

                        c5, c6 = st.columns(2)
                        ivh = c5.selectbox("IVH grade", selectbox_options("l1_brain_injury_ivh"),
                                           index=_sel_idx("l1_brain_injury_ivh", rec["l1_brain_injury_ivh"]))
                        pvl = c6.selectbox("PVL", selectbox_options("l1_brain_injury_pvl"),
                                           index=_sel_idx("l1_brain_injury_pvl", rec["l1_brain_injury_pvl"]))

                        c7, c8 = st.columns(2)
                        bpd    = c7.selectbox("BPD", selectbox_options("l1_cld_bpd"),
                                              index=_sel_idx("l1_cld_bpd", rec["l1_cld_bpd"]))
                        sepsis = c8.selectbox("Sepsis", ["", "Yes", "No"],
                                              index=_bool_idx(rec["l1_sepsis_confirmed"]))

                        c9, c10 = st.columns(2)
                        rop    = c9.selectbox("ROP result", selectbox_options("l1_rop_result"),
                                              index=_sel_idx("l1_rop_result", rec["l1_rop_result"]))
                        hear   = c10.selectbox("Hearing result",
                                               selectbox_options("l1_hearing_result"),
                                               index=_sel_idx("l1_hearing_result", rec["l1_hearing_result"]))

                        st.markdown("**Discharge fields**")
                        c11, c12 = st.columns(2)
                        los  = c11.number_input("LOS (days)", 0, 500,
                                                value=int(rec["l1_discharge_los"] or 0))
                        wt_d = c12.number_input("Weight at discharge (g)", 0.0, 6000.0,
                                                value=float(rec["l1_weight_discharge_g"] or 0), step=10.0)
                        feed = st.selectbox("Feeding at discharge",
                                            selectbox_options("l1_feeding_status_discharge"),
                                            index=_sel_idx("l1_feeding_status_discharge",
                                                           rec["l1_feeding_status_discharge"]))

                        ca, cb = st.columns(2)
                        save_edit = ca.form_submit_button("💾 Save changes", type="primary")
                        cancel_ed = cb.form_submit_button("Cancel")

                        if save_edit:
                            # Build detail string for audit
                            changes = []
                            new_vals = {
                                "l1_gestational_age_weeks": int(ga_w),
                                "l1_gestational_age_days":  int(ga_d),
                                "l1_birth_weight_g":        float(bw),
                                "l1_sex": label_to_code("l1_sex", sex) if sex else None,
                                "l1_primary_diagnosis": label_to_code("l1_primary_diagnosis", diag) if diag else None,
                                "l1_brain_injury_ivh": label_to_code("l1_brain_injury_ivh", ivh) if ivh else None,
                                "l1_brain_injury_pvl": label_to_code("l1_brain_injury_pvl", pvl) if pvl else None,
                                "l1_cld_bpd": label_to_code("l1_cld_bpd", bpd) if bpd else None,
                                "l1_sepsis_confirmed": sepsis if sepsis else None,
                                "l1_rop_result": label_to_code("l1_rop_result", rop) if rop else None,
                                "l1_hearing_result": label_to_code("l1_hearing_result", hear) if hear else None,
                                "l1_discharge_los": los if los > 0 else None,
                                "l1_weight_discharge_g": wt_d if wt_d > 0 else None,
                                "l1_feeding_status_discharge": label_to_code("l1_feeding_status_discharge", feed) if feed else None,
                            }
                            for field, new_val in new_vals.items():
                                old_val = rec[field]
                                if str(old_val) != str(new_val):
                                    changes.append(f"{field}: {old_val!r} → {new_val!r}")

                            conn = get_connection()
                            conn.execute("""
                                UPDATE infants SET
                                    l1_gestational_age_weeks=?, l1_gestational_age_days=?,
                                    l1_birth_weight_g=?, l1_sex=?, l1_primary_diagnosis=?,
                                    l1_brain_injury_ivh=?, l1_brain_injury_pvl=?,
                                    l1_cld_bpd=?, l1_sepsis_confirmed=?,
                                    l1_rop_result=?, l1_hearing_result=?,
                                    l1_discharge_los=?, l1_weight_discharge_g=?,
                                    l1_feeding_status_discharge=?
                                WHERE l1_infant_id=?
                            """, (
                                new_vals["l1_gestational_age_weeks"],
                                new_vals["l1_gestational_age_days"],
                                new_vals["l1_birth_weight_g"],
                                new_vals["l1_sex"],
                                new_vals["l1_primary_diagnosis"],
                                new_vals["l1_brain_injury_ivh"],
                                new_vals["l1_brain_injury_pvl"],
                                new_vals["l1_cld_bpd"],
                                new_vals["l1_sepsis_confirmed"],
                                new_vals["l1_rop_result"],
                                new_vals["l1_hearing_result"],
                                new_vals["l1_discharge_los"],
                                new_vals["l1_weight_discharge_g"],
                                new_vals["l1_feeding_status_discharge"],
                                aid
                            ))
                            conn.commit()
                            conn.close()

                            detail = "; ".join(changes) if changes else "no field changes"
                            log_data_audit(
                                st.session_state["user_id"],
                                "infant_modified", aid, aid, detail
                            )
                            st.session_state["infant_edit_mode"] = False
                            st.session_state["last_save_msg"] = (
                                f"✅ Infant {aid} updated. "
                                f"{'Changes: ' + detail if changes else 'No changes.'}"
                            )
                            st.rerun()

                        if cancel_ed:
                            st.session_state["infant_edit_mode"] = False
                            st.rerun()

    # ── Register new infant (left column) ─────────────────────────────────────
    with col_form:
        st.subheader("Register new infant")
        with st.form("infant_form", clear_on_submit=True):
            new_id = new_infant_id()
            st.text_input("Infant ID (auto-generated)", value=new_id, disabled=True)

            st.markdown("**Gestational age at birth** *")
            c1, c2 = st.columns(2)
            # Start empty - no pre-fill (item 8)
            ga_weeks = c1.number_input("Completed weeks *", min_value=22, max_value=44,
                                        value=None, placeholder="22-44")
            ga_days  = c2.number_input("Remaining days *", min_value=0, max_value=6,
                                        value=None, placeholder="0-6")
            bw = st.number_input("Birth weight (g) *", min_value=300.0, max_value=6000.0,
                                  value=None, placeholder="300-6000 g", step=10.0)

            st.divider()
            st.markdown("**Optional - admission baseline**")
            c3, c4 = st.columns(2)
            sex  = c3.selectbox("Sex", selectbox_options("l1_sex"))
            diag = c4.selectbox("Primary diagnosis", selectbox_options("l1_primary_diagnosis"))

            c5, c6 = st.columns(2)
            length_cm = c5.number_input("Birth length (cm)", min_value=0.0,
                                         max_value=70.0, value=None,
                                         placeholder="cm", step=0.1)
            hc_cm = c6.number_input("Head circumference at birth (cm)", min_value=0.0,
                                     max_value=50.0, value=None,
                                     placeholder="cm", step=0.1)

            c7, c8 = st.columns(2)
            ethnicity = c7.selectbox("Ethnicity", selectbox_options("l1_ethnicity"))
            ethnicity_scheme = c8.text_input("Ethnicity scheme", placeholder="e.g. UK-ONS-2021")

            c9, c10 = st.columns(2)
            acs  = c9.selectbox("Antenatal corticosteroids", selectbox_options("l1_antenatal_corticosteroids"))
            surf = c10.selectbox("Surfactant", selectbox_options("l1_surfactant"))

            c11, c12 = st.columns(2)
            ivh = c11.selectbox("IVH grade", selectbox_options("l1_brain_injury_ivh"))
            pvl = c12.selectbox("PVL", selectbox_options("l1_brain_injury_pvl"))

            c13, c14 = st.columns(2)
            bpd    = c13.selectbox("BPD at 36 wk PMA", selectbox_options("l1_cld_bpd"))
            sepsis = c14.selectbox("Culture-confirmed sepsis", ["", "Yes", "No"])

            c15, c16 = st.columns(2)
            rop     = c15.selectbox("ROP screening result", selectbox_options("l1_rop_result"))
            hearing = c16.selectbox("Hearing screening result", selectbox_options("l1_hearing_result"))

            submitted = st.form_submit_button("💾 Save infant record", type="primary")

            if submitted:
                # Validate required fields are not None
                errors = []
                if ga_weeks is None:
                    errors.append("Gestational age (weeks) is required")
                if ga_days is None:
                    errors.append("Gestational age (days) is required")
                if bw is None:
                    errors.append("Birth weight is required")

                if errors:
                    for e in errors:
                        st.error(e)
                else:
                    record = {
                        "l1_infant_id": new_id,
                        "l1_gestational_age_weeks": int(ga_weeks),
                        "l1_gestational_age_days": int(ga_days),
                        "l1_birth_weight_g": float(bw),
                        "l1_sex": label_to_code("l1_sex", sex) if sex else None,
                        "l1_primary_diagnosis": label_to_code("l1_primary_diagnosis", diag) if diag else None,
                        "l1_birth_length_cm": float(length_cm) if length_cm is not None else None,
                        "l1_birth_hc_cm": float(hc_cm) if hc_cm is not None else None,
                        "l1_ethnicity": label_to_code("l1_ethnicity", ethnicity) if ethnicity else None,
                        "l1_ethnicity_scheme": ethnicity_scheme.strip() if ethnicity_scheme else None,
                        "l1_antenatal_corticosteroids": label_to_code("l1_antenatal_corticosteroids", acs) if acs else None,
                        "l1_surfactant": label_to_code("l1_surfactant", surf) if surf else None,
                        "l1_brain_injury_ivh": label_to_code("l1_brain_injury_ivh", ivh) if ivh else None,
                        "l1_brain_injury_pvl": label_to_code("l1_brain_injury_pvl", pvl) if pvl else None,
                        "l1_cld_bpd": label_to_code("l1_cld_bpd", bpd) if bpd else None,
                        "l1_sepsis_confirmed": sepsis if sepsis else None,
                        "l1_rop_result": label_to_code("l1_rop_result", rop) if rop else None,
                        "l1_hearing_result": label_to_code("l1_hearing_result", hearing) if hearing else None,
                    }

                    passed, issues, score = validate_infant(record)
                    if not passed:
                        for issue in issues:
                            st.error(issue)
                    else:
                        # Store in session_state for post-form duplicate check
                        st.session_state["pending_infant_record"] = record
                        st.session_state["pending_infant_score"] = score
                        st.session_state["pending_infant_needs_dup_check"] = True
                        st.rerun()

        # ── Post-form duplicate check (OUTSIDE st.form, Streamlit compatible) ──
        if st.session_state.get("pending_infant_needs_dup_check"):
            record = st.session_state.get("pending_infant_record", {})
            score  = st.session_state.get("pending_infant_score", 0)

            conn = get_connection()
            dup = conn.execute(
                "SELECT l1_infant_id FROM infants WHERE "
                "l1_gestational_age_weeks = ? AND l1_gestational_age_days = ? "
                "AND l1_birth_weight_g = ? AND is_void = 0",
                (record["l1_gestational_age_weeks"],
                 record["l1_gestational_age_days"],
                 record["l1_birth_weight_g"])
            ).fetchone()
            conn.close()

            if dup and not st.session_state.get("confirm_duplicate"):
                st.warning(
                    f"⚠️ A record with the same GA and birth weight already exists "
                    f"({dup['l1_infant_id']}). "
                    "Twins share the same GA and birth weight. Confirm to save anyway."
                )
                c_yes, c_no = st.columns(2)
                if c_yes.button("✅ Confirm save", key="confirm_dup_btn", type="primary"):
                    st.session_state["confirm_duplicate"] = True
                    st.rerun()
                if c_no.button("❌ Cancel", key="cancel_dup_btn"):
                    for k in ["pending_infant_record", "pending_infant_score",
                              "pending_infant_needs_dup_check", "confirm_duplicate"]:
                        st.session_state.pop(k, None)
                    st.rerun()
                st.stop()

            # Clear check flags
            for k in ["pending_infant_needs_dup_check", "confirm_duplicate"]:
                st.session_state.pop(k, None)

            conn = get_connection()
            conn.execute("""
                INSERT INTO infants (
                    l1_infant_id, l1_gestational_age_weeks, l1_gestational_age_days,
                    l1_birth_weight_g, l1_sex, l1_primary_diagnosis,
                    l1_birth_length_cm, l1_birth_hc_cm,
                    l1_ethnicity, l1_ethnicity_scheme,
                    l1_antenatal_corticosteroids, l1_surfactant,
                    l1_brain_injury_ivh, l1_brain_injury_pvl,
                    l1_cld_bpd, l1_sepsis_confirmed,
                    l1_rop_result, l1_hearing_result,
                    l8_site_id, l8_schema_version, l8_vocabulary_version,
                    l8_created_by, l8_record_creation_timestamp
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                record["l1_infant_id"],
                record["l1_gestational_age_weeks"],
                record["l1_gestational_age_days"],
                record["l1_birth_weight_g"],
                record["l1_sex"], record["l1_primary_diagnosis"],
                record["l1_birth_length_cm"], record["l1_birth_hc_cm"],
                record["l1_ethnicity"], record["l1_ethnicity_scheme"],
                record["l1_antenatal_corticosteroids"], record["l1_surfactant"],
                record["l1_brain_injury_ivh"], record["l1_brain_injury_pvl"],
                record["l1_cld_bpd"], record["l1_sepsis_confirmed"],
                record["l1_rop_result"], record["l1_hearing_result"],
                SITE_ID, SCHEMA_VERSION, VOC_VERSION,
                st.session_state["user_id"], now_iso()
            ))
            conn.commit()
            conn.close()
            new_id = record["l1_infant_id"]
            log_data_audit(st.session_state["user_id"], "infant_created", new_id, new_id)

            st.session_state["active_infant_id"] = new_id
            st.session_state["active_infant_label"] = (
                f"{new_id} ({record['l1_gestational_age_weeks']}+"
                f"{record['l1_gestational_age_days']}wk, "
                f"{record['l1_birth_weight_g']}g)"
            )
            st.session_state["last_save_msg"] = (
                f"✅ Infant {new_id} saved. "
                f"Optional-field coverage: {score}% "
                f"({_cov_txt(record, INFANT_OPTIONAL_SCORED)})"
                + (" - consider completing optional fields." if score < 60 else "")
            )
            for k in ["pending_infant_record", "pending_infant_score"]:
                st.session_state.pop(k, None)
            st.rerun()

    # Show persisted success message
    if "last_save_msg" in st.session_state:
        st.success(st.session_state.pop("last_save_msg"))


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 - SESSIONS
# ═════════════════════════════════════════════════════════════════════════════
def tab_sessions():
    st.title("📋 Session - Layers 2, 4, 5, 6, 7, 8")

    conn = get_connection()
    infants = conn.execute(
        "SELECT l1_infant_id, l1_gestational_age_weeks, l1_gestational_age_days "
        "FROM infants WHERE is_void = 0"
    ).fetchall()
    conn.close()

    if not infants:
        st.warning("No infants registered. Please register an infant first.")
        return

    infant_options = {
        f"{inf['l1_infant_id']} ({inf['l1_gestational_age_weeks']}+"
        f"{inf['l1_gestational_age_days']}wk)": inf["l1_infant_id"]
        for inf in infants
    }

    # Default to active infant if set
    default_idx = 0
    if st.session_state["active_infant_id"]:
        keys = list(infant_options.keys())
        for i, k in enumerate(keys):
            if infant_options[k] == st.session_state["active_infant_id"]:
                default_idx = i
                break

    selected_label = st.selectbox("Select infant *", list(infant_options.keys()),
                                   index=default_idx)
    selected_infant_id = infant_options[selected_label]

    # Update active infant on selection
    if selected_infant_id != st.session_state["active_infant_id"]:
        st.session_state["active_infant_id"] = selected_infant_id

    conn = get_connection()
    sessions = conn.execute(
        "SELECT session_id, l2_session_datetime, l2_session_number, "
        "l2_intervention_type, l5_overall_outcome "
        "FROM sessions WHERE l1_infant_id = ? AND is_void = 0 "
        "ORDER BY l2_session_number",
        (selected_infant_id,)
    ).fetchall()
    conn.close()

    col_form, col_list = st.columns([2, 1])

    with col_list:
        st.subheader(f"Sessions ({len(sessions)})")
        if sessions:
            for s in sessions:
                itype_label   = code_to_label("l2_intervention_type", s["l2_intervention_type"])
                outcome_label = code_to_label("l5_overall_outcome", s["l5_overall_outcome"] or "")
                lbl = (f"#{s['l2_session_number']} - "
                       f"{str(s['l2_session_datetime'])[:10]} - "
                       f"{itype_label} - {outcome_label}")
                if st.button(lbl, key=f"sesssel_{s['session_id']}"):
                    st.session_state["active_session_id"] = s["session_id"]
                    st.session_state["session_edit_mode"] = False
                    st.session_state["session_void_mode"] = False
                    st.rerun()
        else:
            st.info("No sessions yet.")

        # ── Edit / Void for selected session ──────────────────────────────────
        if st.session_state.get("active_session_id"):
            asid = st.session_state["active_session_id"]
            # Check it belongs to current infant
            conn = get_connection()
            srec = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ? AND is_void = 0", (asid,)
            ).fetchone()
            conn.close()

            if srec and srec["l1_infant_id"] == selected_infant_id:
                st.divider()
                st.caption(f"Selected: session #{srec['l2_session_number']}")
                sa, sb = st.columns(2)
                if sa.button("✏️ Edit session", key="btn_edit_sess"):
                    st.session_state["session_edit_mode"] = True
                    st.rerun()
                if sb.button("🗑 Void session", key="btn_void_sess"):
                    st.session_state["session_void_mode"] = True
                    st.rerun()

                # ── Void confirmation ─────────────────────────────────────────
                if st.session_state.get("session_void_mode"):
                    with st.form("void_session_form"):
                        st.warning(f"⚠️ Mark session #{srec['l2_session_number']} as void?")
                        void_reason = st.text_input("Reason (required)")
                        vc1, vc2 = st.columns(2)
                        confirm = vc1.form_submit_button("Confirm void", type="primary")
                        cancel  = vc2.form_submit_button("Cancel")
                        if confirm:
                            if not void_reason.strip():
                                st.error("Reason is required.")
                            else:
                                conn = get_connection()
                                conn.execute("""
                                    UPDATE sessions SET is_void=1, void_reason=?
                                    WHERE session_id=?
                                """, (void_reason.strip(), asid))
                                conn.commit()
                                conn.close()
                                log_data_audit(
                                    st.session_state["user_id"],
                                    "session_voided", asid, selected_infant_id,
                                    f"Reason: {void_reason.strip()}"
                                )
                                st.session_state["active_session_id"] = None
                                st.session_state["session_void_mode"] = False
                                st.session_state["last_save_msg"] = "✅ Session marked as void."
                                st.rerun()
                        if cancel:
                            st.session_state["session_void_mode"] = False
                            st.rerun()

                # ── Session edit form ─────────────────────────────────────────
                elif st.session_state.get("session_edit_mode") and srec:
                    st.subheader(f"Edit session #{srec['l2_session_number']}")
                    with st.form("edit_session_form"):
                        new_outcome = st.selectbox(
                            "Overall session outcome *",
                            selectbox_options("l5_overall_outcome", allow_empty=False),
                            index=max(0, _sel_idx("l5_overall_outcome",
                                                  srec["l5_overall_outcome"]) - 1)
                        )
                        new_impression = st.selectbox(
                            "Clinician impression",
                            selectbox_options("l5_clinician_impression"),
                            index=_sel_idx("l5_clinician_impression",
                                           srec["l5_clinician_impression"])
                        )
                        new_notes = st.text_area(
                            "Free-text notes (max 500 chars)",
                            value=srec["l5_free_text_notes"] or "",
                            max_chars=500
                        )
                        new_adverse = st.selectbox(
                            "Adverse event",
                            ["No", "Yes"],
                            index=1 if srec["l5_adverse_event"] == "Yes" else 0
                        )
                        new_anxiety_str = st.text_input(
                            "Parental anxiety (0-10)",
                            value=str(srec["l6_parental_anxiety"])
                            if srec["l6_parental_anxiety"] is not None else ""
                        )
                        new_tolerated = st.selectbox(
                            "Session tolerated *",
                            ["Yes", "No"],
                            index=1 if srec["l4_session_tolerated"] == "No" else 0
                        )

                        ec1, ec2 = st.columns(2)
                        save_sess = ec1.form_submit_button("💾 Save changes", type="primary")
                        cancel_s  = ec2.form_submit_button("Cancel")

                        if save_sess:
                            new_anxiety = None
                            if new_anxiety_str.strip():
                                try:
                                    new_anxiety = int(new_anxiety_str.strip())
                                except ValueError:
                                    st.error("Anxiety score must be 0-10")
                                    st.stop()

                            new_outcome_code = label_to_code("l5_overall_outcome", new_outcome)
                            new_imp_code = label_to_code("l5_clinician_impression",
                                                          new_impression) if new_impression else None

                            # Build audit detail
                            changes = []
                            checks = {
                                "l5_overall_outcome": (srec["l5_overall_outcome"], new_outcome_code),
                                "l5_clinician_impression": (srec["l5_clinician_impression"], new_imp_code),
                                "l5_free_text_notes": (srec["l5_free_text_notes"], new_notes or None),
                                "l5_adverse_event": (srec["l5_adverse_event"], new_adverse),
                                "l4_session_tolerated": (srec["l4_session_tolerated"], new_tolerated),
                                "l6_parental_anxiety": (srec["l6_parental_anxiety"], new_anxiety),
                            }
                            for field, (old, new) in checks.items():
                                if str(old) != str(new):
                                    changes.append(f"{field}: {old!r} → {new!r}")

                            conn = get_connection()
                            conn.execute("""
                                UPDATE sessions SET
                                    l5_overall_outcome=?, l5_clinician_impression=?,
                                    l5_free_text_notes=?, l5_adverse_event=?,
                                    l4_session_tolerated=?, l6_parental_anxiety=?
                                WHERE session_id=?
                            """, (
                                new_outcome_code, new_imp_code,
                                new_notes if new_notes else None,
                                new_adverse, new_tolerated, new_anxiety,
                                asid
                            ))
                            conn.commit()
                            conn.close()

                            detail = "; ".join(changes) if changes else "no field changes"
                            log_data_audit(
                                st.session_state["user_id"],
                                "session_modified", asid, selected_infant_id, detail
                            )
                            st.session_state["session_edit_mode"] = False
                            st.session_state["last_save_msg"] = (
                                f"✅ Session #{srec['l2_session_number']} updated. "
                                f"{'Changes: ' + detail if changes else 'No changes.'}"
                            )
                            st.rerun()

                        if cancel_s:
                            st.session_state["session_edit_mode"] = False
                            st.rerun()

    with col_form:
        st.subheader("New session")
        with st.form("session_form", clear_on_submit=True):
            sess_id  = new_session_id()
            sess_num = len(sessions) + 1
            st.text_input("Session ID", value=sess_id, disabled=True)
            st.text_input("Session number", value=str(sess_num), disabled=True)

            st.markdown("**Layer 2 - Session context (Required)**")
            session_dt = st.text_input(
                "Session date & time (ISO 8601) *",
                value=datetime.now().strftime("%Y-%m-%dT%H:%M")
            )
            clinician_id = st.text_input(
                "Clinician / therapist ID *",
                placeholder="e.g. CLIN_001 - letters, digits, underscores only, no spaces"
            )

            c1, c2 = st.columns(2)
            # Only active intervention types (item 19).
            # Required fields start blank so that a value is consciously chosen
            # rather than silently accepted (same rule as the infant form).
            active_types = active_intervention_types()
            itype_label  = c1.selectbox("Intervention type *", [""] + active_types)
            itype_code   = label_to_code("l2_intervention_type", itype_label) if itype_label else None
            protocol_id  = c2.text_input("Protocol ID *", placeholder="e.g. MUSIC_V1")
            protocol_ver = st.text_input("Protocol version *", placeholder="e.g. 1.0")

            st.divider()
            st.markdown("**Layer 2 - Clinical context (Optional)**")
            c3, c4 = st.columns(2)
            corr_ga   = c3.number_input("Corrected GA at session (weeks)",
                                         min_value=0.0, max_value=50.0,
                                         value=None, placeholder="weeks", step=0.1)
            resp_supp = c4.selectbox("Respiratory support", selectbox_options("l2_respiratory_support"))

            c5, c6 = st.columns(2)
            # FiO2: value=None so 21 (room air) is a valid entered value
            fio2      = c5.number_input("FiO₂ (%)", min_value=21.0, max_value=100.0,
                                         value=None, placeholder="21-100 %", step=1.0)
            nutrition = c6.selectbox("Nutrition", selectbox_options("l2_nutrition"))

            c7, c8 = st.columns(2)
            ambient_noise  = c7.selectbox("Ambient noise level", selectbox_options("l2_ambient_noise"))
            lighting       = c8.selectbox("Lighting conditions", selectbox_options("l2_lighting"))

            c9, c10 = st.columns(2)
            rand_seed = c9.text_input("Randomization seed", placeholder="optional")
            recent_surg = c10.selectbox("Recent surgery", selectbox_options("l2_recent_surgery"))

            # Yes/No/None dropdowns for booleans (item 3)
            c11, c12 = st.columns(2)
            skin_to_skin    = c11.selectbox("Skin-to-skin phase included", ["", "Yes", "No"])
            parent_present  = c12.selectbox("Parent present", ["", "Yes", "No"])

            st.divider()
            st.markdown("**Layer 4 - Behavioural (session level, Optional)**")
            c13, c14 = st.columns(2)
            state_start = c13.selectbox("Behavioural state at session start",
                                         selectbox_options("l4_behavioural_state_start"))
            state_end   = c14.selectbox("Behavioural state at session end",
                                         selectbox_options("l4_behavioural_state_end"))
            session_tolerated = st.selectbox("Session tolerated to completion *",
                                              ["Yes", "No"])

            st.divider()
            st.markdown("**Layer 5 - Session Outcome**")
            c15, c16 = st.columns(2)
            outcome    = c15.selectbox("Overall session outcome *",
                                        selectbox_options("l5_overall_outcome", allow_empty=False))
            impression = c16.selectbox("Clinician global impression",
                                        selectbox_options("l5_clinician_impression"))
            free_text     = st.text_area("Free-text session notes (max 500 chars)",
                                          max_chars=500)
            adverse_event = st.selectbox("Adverse event", ["No", "Yes"])

            st.divider()
            st.markdown("**Layer 6 - Family Context (Optional)**")
            c17, c18 = st.columns(2)
            # Parental anxiety: None means not recorded; 0 is valid (calm parent)
            anxiety_str   = c17.text_input("Parental anxiety score (VAS 0-10)",
                                            placeholder="0-10 or leave blank")
            participation = c18.selectbox("Parent participation level",
                                           selectbox_options("l6_parent_participation"))
            musical_pref  = st.selectbox("Family musical preference documented",
                                          ["", "Yes", "No"])

            st.divider()
            st.markdown("**Layer 7 - EEG Linkage (Optional)**")
            c19, c20 = st.columns(2)
            eeg_linked  = c19.selectbox("EEG recording linked", ["", "Yes", "No"])
            eeg_quality = c20.selectbox("EEG quality flag",
                                         selectbox_options("l7_eeg_quality_flag"))

            submitted = st.form_submit_button("💾 Save session", type="primary")

            if submitted:
                # Parse parental anxiety safely (0 is valid)
                anxiety_val = None
                if anxiety_str.strip():
                    try:
                        anxiety_val = int(anxiety_str.strip())
                    except ValueError:
                        st.error("Parental anxiety score must be a number 0-10")
                        st.stop()

                record = {
                    "l2_session_datetime": session_dt,
                    "l2_session_number": sess_num,
                    "l2_clinician_id": clinician_id.strip(),
                    "l2_intervention_type": itype_code,
                    "l2_protocol_id": protocol_id.strip(),
                    "l2_protocol_version": protocol_ver.strip(),
                    "l2_randomization_seed": rand_seed.strip() if rand_seed else None,
                    "l2_skin_to_skin": skin_to_skin if skin_to_skin else None,
                    "l2_parent_present": parent_present if parent_present else None,
                    "l2_ambient_noise": label_to_code("l2_ambient_noise", ambient_noise) if ambient_noise else None,
                    "l2_lighting": label_to_code("l2_lighting", lighting) if lighting else None,
                    "l2_corrected_gestational_age": float(corr_ga) if corr_ga is not None else None,
                    "l2_respiratory_support": label_to_code("l2_respiratory_support", resp_supp) if resp_supp else None,
                    "l2_fio2": float(fio2) if fio2 is not None else None,
                    "l2_nutrition": label_to_code("l2_nutrition", nutrition) if nutrition else None,
                    "l2_recent_surgery": label_to_code("l2_recent_surgery", recent_surg) if recent_surg else None,
                    "l4_behavioural_state_start": label_to_code("l4_behavioural_state_start", state_start) if state_start else None,
                    "l4_behavioural_state_end": label_to_code("l4_behavioural_state_end", state_end) if state_end else None,
                    "l4_session_tolerated": session_tolerated,
                    "l5_overall_outcome": label_to_code("l5_overall_outcome", outcome) if outcome else None,
                    "l5_clinician_impression": label_to_code("l5_clinician_impression", impression) if impression else None,
                    "l5_free_text_notes": free_text if free_text else None,
                    "l5_adverse_event": adverse_event,
                    "l6_parental_anxiety": anxiety_val,
                    "l6_parent_participation": label_to_code("l6_parent_participation", participation) if participation else None,
                    "l6_family_musical_preference": musical_pref if musical_pref else None,
                    "l7_eeg_recording_linked": eeg_linked if eeg_linked else None,
                    "l7_eeg_quality_flag": label_to_code("l7_eeg_quality_flag", eeg_quality) if eeg_quality else None,
                }

                passed, issues, score = validate_session(record)

                if not passed:
                    for issue in issues:
                        if issue.startswith("FORMAT"):
                            st.error(f"🚫 {issue}")
                        else:
                            st.error(issue)
                else:
                    plaus_warns = [i for i in issues if i.startswith("PLAUSIBILITY")]
                    consistency = "passed" if not plaus_warns else f"warning:{';'.join(plaus_warns)}"

                    conn = get_connection()
                    conn.execute("""
                        INSERT INTO sessions (
                            session_id, l1_infant_id,
                            l2_session_datetime, l2_session_number, l2_clinician_id,
                            l2_intervention_type, l2_protocol_id, l2_protocol_version,
                            l2_randomization_seed,
                            l2_skin_to_skin, l2_parent_present,
                            l2_ambient_noise, l2_lighting,
                            l2_corrected_gestational_age, l2_respiratory_support,
                            l2_fio2, l2_nutrition, l2_recent_surgery,
                            l4_behavioural_state_start, l4_behavioural_state_end,
                            l4_session_tolerated,
                            l5_overall_outcome, l5_clinician_impression,
                            l5_free_text_notes, l5_adverse_event,
                            l6_parental_anxiety, l6_parent_participation,
                            l6_family_musical_preference,
                            l7_eeg_recording_linked, l7_eeg_quality_flag,
                            l8_completeness_score, l8_consistency_check,
                            l8_site_id, l8_schema_version, l8_vocabulary_version,
                            l8_created_by, l8_record_creation_timestamp
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        sess_id, selected_infant_id,
                        record["l2_session_datetime"], record["l2_session_number"],
                        record["l2_clinician_id"],
                        record["l2_intervention_type"], record["l2_protocol_id"],
                        record["l2_protocol_version"],
                        record["l2_randomization_seed"],
                        record["l2_skin_to_skin"], record["l2_parent_present"],
                        record["l2_ambient_noise"], record["l2_lighting"],
                        record["l2_corrected_gestational_age"],
                        record["l2_respiratory_support"],
                        record["l2_fio2"], record["l2_nutrition"],
                        record["l2_recent_surgery"],
                        record["l4_behavioural_state_start"],
                        record["l4_behavioural_state_end"],
                        record["l4_session_tolerated"],
                        record["l5_overall_outcome"],
                        record["l5_clinician_impression"],
                        record["l5_free_text_notes"],
                        record["l5_adverse_event"],
                        record["l6_parental_anxiety"],
                        record["l6_parent_participation"],
                        record["l6_family_musical_preference"],
                        record["l7_eeg_recording_linked"],
                        record["l7_eeg_quality_flag"],
                        score, consistency,
                        SITE_ID, SCHEMA_VERSION, VOC_VERSION,
                        st.session_state["user_id"], now_iso()
                    ))
                    conn.commit()
                    conn.close()
                    log_data_audit(st.session_state["user_id"], "session_created",
                                   sess_id, selected_infant_id)

                    for w in plaus_warns:
                        st.warning(w)

                    st.session_state["last_save_msg"] = (
                        f"✅ Session {sess_id} saved. Optional-field coverage: {score}% "
                        f"({_cov_txt(record, SESSION_OPTIONAL_SCORED)})"
                    )
                    st.rerun()

    if "last_save_msg" in st.session_state:
        st.success(st.session_state.pop("last_save_msg"))


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 - INTERVENTION UNITS
# ═════════════════════════════════════════════════════════════════════════════
def tab_units():
    st.title("🎵 Intervention Unit - Layers 3, 4, 7")

    conn = get_connection()
    infants = conn.execute(
        "SELECT l1_infant_id FROM infants WHERE is_void = 0"
    ).fetchall()
    conn.close()

    if not infants:
        st.warning("No infants registered.")
        return

    infant_ids = [inf["l1_infant_id"] for inf in infants]
    default_idx = 0
    if st.session_state["active_infant_id"] in infant_ids:
        default_idx = infant_ids.index(st.session_state["active_infant_id"])

    selected_infant = st.selectbox("Select infant", infant_ids, index=default_idx)

    conn = get_connection()
    sessions = conn.execute(
        "SELECT session_id, l2_session_number, l2_session_datetime, l2_intervention_type, "
        "l7_eeg_recording_linked "
        "FROM sessions WHERE l1_infant_id = ? AND is_void = 0 ORDER BY l2_session_number",
        (selected_infant,)
    ).fetchall()
    conn.close()

    if not sessions:
        st.warning("No sessions for this infant. Record a session first.")
        return

    sess_options = {
        f"#{s['l2_session_number']} - "
        f"{str(s['l2_session_datetime'])[:10]} - "
        f"{code_to_label('l2_intervention_type', s['l2_intervention_type'])}": s["session_id"]
        for s in sessions
    }
    selected_sess_label = st.selectbox("Select session", list(sess_options.keys()))
    selected_sess_id    = sess_options[selected_sess_label]
    selected_sess       = next(s for s in sessions if s["session_id"] == selected_sess_id)
    is_music            = selected_sess["l2_intervention_type"] == "ITYPE_MUSIC"

    conn = get_connection()
    units = conn.execute(
        "SELECT unit_id, unit_order, l3_unit_condition, l3_unit_duration "
        "FROM intervention_units WHERE session_id = ? ORDER BY unit_order",
        (selected_sess_id,)
    ).fetchall()
    conn.close()

    col_form, col_list = st.columns([2, 1])

    with col_list:
        st.subheader("Units in this session")
        if units:
            for u in units:
                cond_label = code_to_label("l3_unit_condition", u["l3_unit_condition"])
                st.text(f"Unit {u['unit_order']}: {cond_label} - {u['l3_unit_duration']}s")
        else:
            st.info("No units yet.")

    with col_form:
        st.subheader(f"Add unit #{len(units)+1}")
        with st.form("unit_form", clear_on_submit=True):
            unit_id    = new_unit_id()
            unit_order = len(units) + 1

            st.markdown("**Layer 3 - Required**")
            condition = st.selectbox(
                "Condition *",
                selectbox_options("l3_unit_condition", allow_empty=False)
            )

            # Capture start time for l3_unit_start_end (item 12)
            c1, c2 = st.columns(2)
            unit_start = c1.text_input(
                "Unit start time (ISO 8601) *",
                value=datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            )
            duration = c2.number_input(
                "Actual duration (seconds) *",
                min_value=1.0, max_value=3600.0, value=None,
                placeholder="seconds", step=10.0
            )

            st.markdown("**Layer 3 - Optional**")
            c3, c4 = st.columns(2)
            delivery_mode = c3.selectbox("Delivery mode",
                                          selectbox_options("l3_unit_delivery_mode"))
            spl = c4.number_input(
                "SPL at incubator (dB) [music only]",
                min_value=0.0, max_value=100.0,
                value=None, placeholder="dB", step=0.5,
                disabled=not is_music
            )
            interruptions = st.text_input("Interruptions / deviations")

            st.divider()
            st.markdown("**Layer 4 - Physiological (Optional)**")
            c5, c6, c7 = st.columns(3)
            hr_pre    = c5.number_input("HR pre (bpm)",    min_value=0.0,
                                         max_value=300.0, value=None, placeholder="bpm")
            hr_during = c6.number_input("HR during (bpm)", min_value=0.0,
                                         max_value=300.0, value=None, placeholder="bpm")
            hr_post   = c7.number_input("HR post (bpm)",   min_value=0.0,
                                         max_value=300.0, value=None, placeholder="bpm")

            c8, c9, c10 = st.columns(3)
            spo2_pre    = c8.number_input("SpO₂ pre (%)",    min_value=0.0,
                                           max_value=100.0, value=None, placeholder="%")
            spo2_during = c9.number_input("SpO₂ during (%)", min_value=0.0,
                                           max_value=100.0, value=None, placeholder="%")
            spo2_post   = c10.number_input("SpO₂ post (%)",  min_value=0.0,
                                            max_value=100.0, value=None, placeholder="%")

            c11, c12 = st.columns(2)
            stress_signs     = c11.selectbox("Stress signs observed",     ["", "Yes", "No"])
            engagement_signs = c12.selectbox("Engagement signs observed", ["", "Yes", "No"])

            st.divider()
            st.markdown("**Layer 7 - EEG marker (Optional)**")
            eeg_timestamp = st.text_input(
                "EEG marker timestamp (triple beep, ISO 8601)",
                placeholder="2026-06-01T10:15:30Z"
            )

            submitted = st.form_submit_button("💾 Save unit", type="primary")

            if submitted:
                if duration is None:
                    st.error("Unit duration is required")
                    st.stop()

                # Derive end time from start + duration
                unit_start_end = None
                if unit_start:
                    try:
                        from datetime import timedelta
                        start_dt = datetime.fromisoformat(unit_start.replace("Z", "+00:00"))
                        end_dt   = start_dt + timedelta(seconds=float(duration))
                        unit_start_end = json.dumps({
                            "start": unit_start,
                            "end": end_dt.isoformat()
                        })
                    except Exception:
                        unit_start_end = unit_start

                record = {
                    "l3_unit_condition": label_to_code("l3_unit_condition", condition),
                    "l3_unit_duration": float(duration),
                    "l3_unit_delivery_mode": label_to_code("l3_unit_delivery_mode", delivery_mode) if delivery_mode else None,
                    "l3music_spl_at_incubator": float(spl) if (is_music and spl is not None) else None,
                    "l3_unit_interruptions": interruptions if interruptions else None,
                    "l4_heart_rate_pre_bpm": float(hr_pre) if hr_pre is not None else None,
                    "l4_heart_rate_during_bpm": float(hr_during) if hr_during is not None else None,
                    "l4_heart_rate_post_bpm": float(hr_post) if hr_post is not None else None,
                    "l4_spo2_pre_pct": float(spo2_pre) if spo2_pre is not None else None,
                    "l4_spo2_during_pct": float(spo2_during) if spo2_during is not None else None,
                    "l4_spo2_post_pct": float(spo2_post) if spo2_post is not None else None,
                    "l4_stress_signs": stress_signs if stress_signs else None,
                    "l4_engagement_signs": engagement_signs if engagement_signs else None,
                    "l7_eeg_marker_timestamps": eeg_timestamp if eeg_timestamp else None,
                }

                passed, issues, score = validate_unit(
                    record,
                    intervention_type=selected_sess["l2_intervention_type"],
                    eeg_linked=(selected_sess["l7_eeg_recording_linked"] == "Yes"),
                )

                if not passed:
                    for issue in issues:
                        st.error(issue)
                else:
                    for w in [i for i in issues if i.startswith("PLAUSIBILITY")]:
                        st.warning(w)

                    conn = get_connection()
                    conn.execute("""
                        INSERT INTO intervention_units (
                            unit_id, session_id, l1_infant_id, unit_order,
                            l3_unit_condition, l3_unit_start_end, l3_unit_duration,
                            l3_unit_delivery_mode, l3_unit_interruptions,
                            l3music_spl_at_incubator,
                            l4_heart_rate_pre_bpm, l4_heart_rate_during_bpm,
                            l4_heart_rate_post_bpm,
                            l4_spo2_pre_pct, l4_spo2_during_pct, l4_spo2_post_pct,
                            l4_stress_signs, l4_engagement_signs,
                            l7_eeg_marker_timestamps,
                            l8_site_id, l8_schema_version, l8_vocabulary_version,
                            l8_created_by, l8_record_creation_timestamp
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        unit_id, selected_sess_id, selected_infant, unit_order,
                        record["l3_unit_condition"], unit_start_end,
                        record["l3_unit_duration"],
                        record["l3_unit_delivery_mode"],
                        record["l3_unit_interruptions"],
                        record["l3music_spl_at_incubator"],
                        record["l4_heart_rate_pre_bpm"],
                        record["l4_heart_rate_during_bpm"],
                        record["l4_heart_rate_post_bpm"],
                        record["l4_spo2_pre_pct"],
                        record["l4_spo2_during_pct"],
                        record["l4_spo2_post_pct"],
                        record["l4_stress_signs"],
                        record["l4_engagement_signs"],
                        record["l7_eeg_marker_timestamps"],
                        SITE_ID, SCHEMA_VERSION, VOC_VERSION,
                        st.session_state["user_id"], now_iso()
                    ))
                    conn.commit()
                    conn.close()
                    log_data_audit(st.session_state["user_id"], "unit_created",
                                   unit_id, selected_infant)
                    st.session_state["last_save_msg"] = f"✅ Unit {unit_id} saved."
                    st.rerun()

    if "last_save_msg" in st.session_state:
        st.success(st.session_state.pop("last_save_msg"))


# Need json for unit_start_end serialization
import json


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 - ANALYTICS
# ═════════════════════════════════════════════════════════════════════════════
def tab_analytics():
    st.title("📊 Analytics Dashboard")
    st.caption("Read-only - queries run via DuckDB.")

    try:
        import duckdb
        from database import DB_PATH
        db_path = str(DB_PATH)
        dc = duckdb.connect(":memory:")
        dc.execute(f"ATTACH '{db_path}' AS wp2 (TYPE SQLITE, READ_ONLY TRUE)")

        col1, col2, col3 = st.columns(3)
        n_inf  = dc.execute("SELECT COUNT(*) FROM wp2.infants WHERE is_void=0").fetchone()[0]
        n_sess = dc.execute("SELECT COUNT(*) FROM wp2.sessions WHERE is_void=0").fetchone()[0]
        n_unit = dc.execute("SELECT COUNT(*) FROM wp2.intervention_units").fetchone()[0]
        col1.metric("Infants", n_inf)
        col2.metric("Sessions", n_sess)
        col3.metric("Units", n_unit)

        if n_sess > 0:
            st.subheader("Session completeness")
            scores = dc.execute(
                "SELECT l8_completeness_score FROM wp2.sessions "
                "WHERE l8_completeness_score IS NOT NULL AND is_void=0"
            ).fetchdf()
            if not scores.empty:
                st.bar_chart(scores)

            # ── Per-field missingness (cb_1.0) ────────────────────────────
            # not_recorded / applicable, per field, across the cohort.
            # Always shown with N applicable: 40 % of 5 and 40 % of 500 are
            # not the same fact.
            st.subheader("Per-field missingness")
            st.caption(f"Basis {COMPLETENESS_BASIS} - % of applicable records "
                       "in which the field was left blank. Not-applicable "
                       "records are excluded from N.")
            infants_df  = dc.execute("SELECT * FROM wp2.infants WHERE is_void=0").fetchdf()
            sessions_df = dc.execute("SELECT * FROM wp2.sessions WHERE is_void=0").fetchdf()
            units_df    = dc.execute(
                "SELECT u.*, s.l2_intervention_type, s.l7_eeg_recording_linked "
                "FROM wp2.intervention_units u "
                "JOIN wp2.sessions s ON s.session_id = u.session_id "
                "WHERE s.is_void=0").fetchdf()

            def _recs(df):
                return [{k: (None if pd.isna(v) else v) for k, v in r.items()}
                        for r in df.to_dict("records")]

            def _unit_ctx(r):
                return {"intervention_type": r.get("l2_intervention_type"),
                        "eeg_linked": r.get("l7_eeg_recording_linked") == "Yes"}

            def _miss_table(rows):
                t = pd.DataFrame(rows)
                t["% missing"] = t["pct_missing"].map(
                    lambda v: "n/a" if v is None else f"{v:.1f} %")
                t = t.rename(columns={"field": "Field",
                                      "n_applicable": "N applicable",
                                      "n_missing": "N missing"})
                return t[["Field", "N applicable", "N missing", "% missing"]]

            tab_i, tab_s, tab_u = st.tabs(["Infant fields", "Session fields",
                                           "Unit fields"])
            with tab_i:
                st.dataframe(_miss_table(field_missingness(
                    _recs(infants_df), INFANT_OPTIONAL_SCORED)),
                    use_container_width=True, hide_index=True)
            with tab_s:
                st.dataframe(_miss_table(field_missingness(
                    _recs(sessions_df), SESSION_OPTIONAL_SCORED)),
                    use_container_width=True, hide_index=True)
            with tab_u:
                st.dataframe(_miss_table(field_missingness(
                    _recs(units_df), UNIT_OPTIONAL_SCORED, ctx_fn=_unit_ctx)),
                    use_container_width=True, hide_index=True)

            st.subheader("Outcome distribution")
            outcomes = dc.execute(
                "SELECT l5_overall_outcome, COUNT(*) as n FROM wp2.sessions "
                "WHERE is_void=0 GROUP BY l5_overall_outcome"
            ).fetchdf()
            if not outcomes.empty:
                outcomes["label"] = outcomes["l5_overall_outcome"].apply(
                    lambda c: code_to_label("l5_overall_outcome", c) if c else c
                )
                st.dataframe(outcomes[["label", "n"]], use_container_width=True)

        dc.close()
    except ImportError:
        st.warning("DuckDB not installed. Run: pip install duckdb")
    except Exception as e:
        st.info(f"Analytics: {e}")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5 - EXPORT
# ═════════════════════════════════════════════════════════════════════════════
def tab_export():
    st.title("📤 Export")
    st.caption("De-identification scan runs before any file is written.")

    cfg = get_site_config()
    conn = get_connection()
    n_inf  = conn.execute("SELECT COUNT(*) FROM infants WHERE is_void=0").fetchone()[0]
    n_sess = conn.execute("SELECT COUNT(*) FROM sessions WHERE is_void=0").fetchone()[0]
    n_unit = conn.execute("SELECT COUNT(*) FROM intervention_units").fetchone()[0]
    conn.close()

    col1, col2, col3 = st.columns(3)
    col1.metric("Infants", n_inf)
    col2.metric("Sessions", n_sess)
    col3.metric("Units", n_unit)

    st.markdown(f"""
**Export produces two files:**
- `export_{cfg['site_id'].replace('-','_')}_[timestamp].csv`
- `export_{cfg['site_id'].replace('-','_')}_[timestamp]_metadata.json`

Every record carries: `l8_site_id = {cfg['site_id']}` · 
`l8_schema_version = {cfg.get('schema_version','1.1')}` · 
`l8_vocabulary_version = voc_{cfg.get('vocabulary_version','1.1.0')}`
    """)

    st.info(
        "**De-id check:** unambiguous identifiers (ID numbers, phone numbers, "
        "dates of birth) **block** the export. Possible names (two capitalised words) "
        "**warn** and ask for confirmation."
    )

    # Handle warning confirmation flow
    if st.session_state.get("export_warning_pending"):
        st.warning(st.session_state["export_warning_message"])
        c1, c2 = st.columns(2)
        if c1.button("✅ Confirm - no patient names present, proceed with export"):
            st.session_state["export_warning_pending"] = False
            status, message, file_paths = export_data(
                st.session_state["user_id"], force_despite_warning=True
            )
            if status == "success":
                st.success(message)
                for fp in file_paths:
                    fname = Path(fp).name
                    with open(fp, "rb") as f:
                        st.download_button(
                            label=f"⬇️ Download {fname}",
                            data=f,
                            file_name=fname,
                            mime="text/csv" if fname.endswith(".csv") else "application/json"
                        )
            else:
                st.error(message)
        if c2.button("❌ Cancel - I will review the notes first"):
            st.session_state["export_warning_pending"] = False
            st.rerun()
        return

    if st.button("🚀 Run export", type="primary"):
        with st.spinner("Running de-identification check..."):
            status, message, file_paths = export_data(st.session_state["user_id"])

        if status == "success":
            st.success(message)
            for fp in file_paths:
                fname = Path(fp).name
                with open(fp, "rb") as f:
                    st.download_button(
                        label=f"⬇️ Download {fname}",
                        data=f,
                        file_name=fname,
                        mime="text/csv" if fname.endswith(".csv") else "application/json"
                    )
        elif status == "warning":
            st.session_state["export_warning_pending"] = True
            st.session_state["export_warning_message"] = message
            st.rerun()
        else:
            st.error(message)

    st.divider()
    st.subheader("Export audit trail")
    conn = get_connection()
    audit = conn.execute(
        "SELECT timestamp, exported_by, record_count, export_filename, "
        "deidentification_check, block_reason "
        "FROM sys_export_audit ORDER BY timestamp DESC LIMIT 20"
    ).fetchall()
    conn.close()

    if audit:
        import pandas as pd
        df = pd.DataFrame([dict(r) for r in audit])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No export attempts yet.")


# ═════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═════════════════════════════════════════════════════════════════════════════
if tab_selection == "🧒 Infants":
    tab_infants()
elif tab_selection == "📋 Sessions":
    tab_sessions()
elif tab_selection == "🎵 Intervention Units":
    tab_units()
elif tab_selection == "📊 Analytics":
    tab_analytics()
elif tab_selection == "📤 Export":
    tab_export()
