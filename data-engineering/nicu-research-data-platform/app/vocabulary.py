"""
WP2 Platform - Controlled vocabulary module v1.1
Loads voc_1.1.0.json (authoritative manifest from PI, 13 Aug 2026).
Store records concept codes, never labels. Labels resolve at display time.
"""

import json
from pathlib import Path
from functools import lru_cache

VOC_PATH = Path(__file__).parent.parent / "vocabulary" / "voc_1.1.0.json"
VOC_VERSION = "1.1.0"


@lru_cache(maxsize=1)
def load_vocabulary() -> dict:
    if not VOC_PATH.exists():
        raise FileNotFoundError(f"Vocabulary manifest not found: {VOC_PATH}")
    with open(VOC_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def get_options(field_name: str) -> list[dict]:
    return load_vocabulary()["concepts"].get(field_name, [])


def get_labels(field_name: str) -> list[str]:
    return [opt["label"] for opt in get_options(field_name)]


def get_codes(field_name: str) -> list[str]:
    return [opt["code"] for opt in get_options(field_name)]


def label_to_code(field_name: str, label: str) -> str | None:
    for opt in get_options(field_name):
        if opt["label"] == label:
            return opt["code"]
    return None


def code_to_label(field_name: str, code: str) -> str:
    """Resolve a concept code to its display label. Returns code if not found."""
    for opt in get_options(field_name):
        if opt["code"] == code:
            return opt["label"]
    return code


def get_version() -> str:
    return VOC_VERSION


def selectbox_options(field_name: str, allow_empty: bool = True) -> list[str]:
    """Return labels for st.selectbox. Prepends blank if allow_empty=True."""
    labels = get_labels(field_name)
    if allow_empty:
        return [""] + labels
    return labels


def active_intervention_types() -> list[str]:
    """Return only non-future intervention type labels (for v1 music-only)."""
    return [
        opt["label"] for opt in get_options("l2_intervention_type")
        if "(future)" not in opt["label"].lower()
    ]
