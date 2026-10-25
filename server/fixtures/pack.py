"""Safe view of the synthetic test pack.

The scenario file contains names and NHS numbers. This module never returns those fields.
"""

from __future__ import annotations

import json
import re

from config import settings

_ID = re.compile(r"^([SF]\d{2})", re.IGNORECASE)
_RANGE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*$")

_NAMES = {
    "haemoglobin": "Haemoglobin",
    "wbc": "White blood cells",
    "neutrophils": "Neutrophils",
    "lymphocytes": "Lymphocytes",
    "platelets": "Platelets",
    "mcv": "MCV",
    "sodium": "Sodium",
    "potassium": "Potassium",
    "urea": "Urea",
    "creatinine": "Creatinine",
    "egfr": "eGFR",
    "hba1c": "HbA1c",
    "ferritin": "Ferritin",
    "tsh": "TSH",
    "free_t4": "Free T4",
}

_AGE = {
    "10-19": "under-18",
    "20-29": "18-29",
    "30-39": "30-39",
    "40-49": "40-49",
    "50-59": "50-59",
    "60-69": "60-plus",
    "70-79": "60-plus",
}


def fixture_id_from_name(name: str) -> str | None:
    match = _ID.match(name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1])
    return match.group(1).upper() if match else None


def load_pack(path=None) -> list[dict]:
    pack_path = path or settings.FIXTURE_PACK
    raw = json.loads(pack_path.read_text(encoding="utf-8"))
    scenarios = raw.get("scenarios")
    if not isinstance(scenarios, list):
        raise ValueError("Fixture pack has no scenarios")
    return scenarios


def catalog(scenarios: list[dict] | None = None) -> list[dict]:
    return [_card(scenario) for scenario in scenarios or load_pack()]


def lookup(fixture_id: str, scenarios: list[dict] | None = None) -> dict | None:
    wanted = fixture_id.upper()
    for scenario in scenarios or load_pack():
        if str(scenario.get("id", "")).upper() == wanted:
            return scenario
    return None


def is_unreadable(scenario: dict) -> bool:
    return scenario.get("photo") == "blurry" or str(scenario.get("id")) == "F03"


def public_fixture(scenario: dict) -> dict:
    """Printed results, age band, and declared context. No identifiers."""
    rows = []
    for printed in scenario.get("printed_rows") or []:
        row = _row(printed)
        if row is not None:
            rows.append(row)
    if not rows:
        raise ValueError("Fixture has no printed results")
    context = scenario.get("declared_context") or {}
    return {
        "id": scenario["id"],
        "lab": {"results": rows, "reviewRequired": True},
        "ageBand": _AGE.get(str((scenario.get("derived") or {}).get("age_band")), "unset"),
        "context": {
            "pregnant": "yes" if context.get("pregnant") else "unset",
            "hormones": "yes" if context.get("gender_affirming_hormones") else "unset",
            "duffy": "yes" if context.get("duffy_null") else "unset",
        },
    }


def _card(scenario: dict) -> dict:
    rows = [row for row in scenario.get("printed_rows") or [] if row.get("analyte") in _NAMES]
    flagged = [row for row in rows if row.get("lab_flag")] or rows[:1]
    parts = [
        f"{_NAMES[row['analyte']]} {row['printed_value']}"
        for row in flagged[:2]
    ]
    label = f"{scenario['id']} · {', '.join(parts)}" if parts else str(scenario["id"])
    return {"id": scenario["id"], "label": label, "detail": _detail(scenario), "fileName": f"{scenario['id']}.pdf"}


def _detail(scenario: dict) -> str:
    if is_unreadable(scenario):
        return "Blurry photo. CarePath should refuse to guess."
    context = scenario.get("declared_context") or {}
    notes = []
    if context.get("duffy_null"):
        notes.append("Duffy-null declared")
    if context.get("pregnant"):
        notes.append("Pregnancy declared")
    if context.get("gender_affirming_hormones"):
        notes.append("Gender-affirming hormones declared")
    if (scenario.get("derived") or {}).get("age_band") == "10-19":
        notes.append("Under 18")
    if scenario.get("id") == "S14":
        notes.append("Critical potassium")
    if scenario.get("id") == "F02":
        notes.append("Implausible haemoglobin")
    if scenario.get("id") == "F01":
        notes.append("Missing unit")
    if not notes:
        action = str((scenario.get("expected") or {}).get("action") or "").replace("_", " ")
        notes.append(action or "Synthetic report")
    return ". ".join(notes)


def _row(printed: dict) -> dict | None:
    analyte = printed.get("analyte")
    if analyte not in _NAMES:
        return None
    try:
        value = float(printed["printed_value"])
    except (TypeError, ValueError):
        return None
    reference = _range(str(printed.get("printed_range") or ""))
    return {
        "testName": _NAMES[analyte],
        "value": value,
        "unit": str(printed.get("printed_unit") or ""),
        "referenceRange": reference,
        "flag": _flag(str(printed.get("lab_flag") or ""), value, reference),
    }


def _range(text: str) -> dict | None:
    match = _RANGE.match(text)
    if not match:
        return None
    low, high = float(match.group(1)), float(match.group(2))
    if not low < high:
        return None
    return {"low": low, "high": high}


def _flag(lab_flag: str, value: float, reference: dict | None) -> str:
    token = lab_flag.upper()
    if token == "L":
        return "low"
    if token in {"H", "HH"}:
        return "high"
    if reference is not None:
        if value < reference["low"]:
            return "low"
        if value > reference["high"]:
            return "high"
        return "normal"
    return "normal" if token == "" else "unknown"
