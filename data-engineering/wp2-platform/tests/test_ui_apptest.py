"""
Interface-level tests using streamlit.testing.v1.AppTest.

These tests render the real Streamlit pages in code. They exist because the
logic-level suite (tests/test_wp2.py) cannot see errors raised by Streamlit
while drawing a page: the duplicate-warning crash passed every logic test
while it was live. Run with:  python -m pytest tests/ -q
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(APP_DIR))
from streamlit.testing.v1 import AppTest  # noqa: E402

MAIN = str(APP_DIR / "main.py")
SAVE_INFANT = "💾 Save infant record"
SAVE_SESSION = "💾 Save session"


# ── helpers ───────────────────────────────────────────────────────────────────
@pytest.fixture
def fresh_app(monkeypatch):
    """A running app on a throw-away, already-initialised database."""
    db = tempfile.mktemp(suffix=".db")
    monkeypatch.setenv("WP2_DB_PATH", db)
    # initialise the site directly (bypasses the first-run form)
    import importlib
    import database as db_mod
    importlib.reload(db_mod)
    db_mod.init_db(site_id="TEST-SITE-001")

    at = AppTest.from_file(MAIN, default_timeout=60)
    at.session_state["user_id"] = "USR_TEST"
    at.run()
    assert not at.exception, at.exception
    yield at
    try:
        os.unlink(db)
    except OSError:
        pass


def _submit_infant(at, ga_w=28, ga_d=3, bw=950.0):
    at.number_input(key=None)  # noop to keep API explicit
    at.number_input[0].set_value(ga_w)
    at.number_input[1].set_value(ga_d)
    at.number_input[2].set_value(bw)
    btn = next(b for b in at.button if b.label == SAVE_INFANT)
    btn.click()
    at.run()
    assert not at.exception, at.exception
    return at


# ── tests ─────────────────────────────────────────────────────────────────────
def test_app_renders_without_exception(fresh_app):
    """The main page draws with no Streamlit error."""
    assert fresh_app.sidebar is not None


def test_infant_required_fields_start_blank(fresh_app):
    """Review item 8: required clinical fields must not be pre-filled."""
    assert fresh_app.number_input[0].value is None   # GA weeks
    assert fresh_app.number_input[1].value is None   # GA days
    assert fresh_app.number_input[2].value is None   # birth weight


def test_infant_save_path_renders(fresh_app):
    """Saving a valid infant draws the success message and no exception."""
    at = _submit_infant(fresh_app)
    assert any("saved" in s.value.lower() for s in at.success)


def test_duplicate_infant_warning_does_not_crash(fresh_app):
    """
    Twin scenario: a second infant with the same GA and birth weight must
    show the duplicate warning AND the Confirm/Cancel buttons, and the page
    must render. This is the interaction that crashed with
    'st.button() can't be used in an st.form()' while every logic test passed.
    """
    at = _submit_infant(fresh_app, 28, 3, 950.0)     # first twin
    at = _submit_infant(at, 28, 3, 950.0)            # second twin

    warnings = [w.value for w in at.warning]
    assert any("already exists" in w for w in warnings), warnings

    labels = [b.label for b in at.button]
    assert "✅ Confirm save" in labels, labels
    assert "❌ Cancel" in labels, labels


def test_session_required_fields_start_blank(fresh_app):
    """Session form: intervention type / protocol ID / version must not be pre-filled."""
    at = _submit_infant(fresh_app)           # need an active infant first
    at.session_state["active_tab"] = "Sessions" if "active_tab" in at.session_state else None
    # navigate: the sidebar radio/nav holds tab names
    nav = next((r for r in at.radio if any("Sessions" in str(o) for o in r.options)), None)
    if nav is not None:
        nav.set_value(next(o for o in nav.options if "Sessions" in str(o)))
        at.run()
    assert not at.exception, at.exception
    itype = next((sb for sb in at.selectbox if (sb.label or "").startswith("Intervention type")), None)
    if itype is None:
        pytest.skip("Sessions tab not reachable via nav widget in this harness")
    assert itype.value in ("", None), f"pre-filled: {itype.value}"
    pid = next(ti for ti in at.text_input if (ti.label or "").startswith("Protocol ID"))
    assert not pid.value, f"pre-filled: {pid.value}"


def test_duplicate_confirm_saves_second_twin(fresh_app):
    """Confirming the duplicate warning saves the record and clears the warning."""
    at = _submit_infant(fresh_app, 28, 3, 950.0)
    at = _submit_infant(at, 28, 3, 950.0)
    next(b for b in at.button if b.label == "✅ Confirm save").click()
    at.run()
    assert not at.exception, at.exception
    assert not any("already exists" in w.value for w in at.warning)

    import database as db_mod
    conn = db_mod.get_connection()
    n = conn.execute("SELECT COUNT(*) FROM infants WHERE is_void=0").fetchone()[0]
    conn.close()
    assert n == 2, f"expected both twins saved, found {n}"
