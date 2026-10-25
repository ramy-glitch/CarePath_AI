"""Read known blood-test rows from redacted OCR text.

A clean unit and a hyphenated range are kept. A damaged unit or a range that
is not clearly low-high is returned as read, with needsCheck set, so the
person can correct it. Units are never rewritten. No identifiers are copied.
"""
from __future__ import annotations

import re
from typing import Any

# Longer aliases are tried first. Canonical names stay stable for the client.
_ROWS = (
    ("Haemoglobin", ("haemoglobin (hb)", "haemoglobin", "hemoglobin", "hb"), ("g/dL", "g/L")),
    ("White Blood Cells", ("white blood cells", "white cell count", "wbc"), ("x10^9/L",)),
    ("Neutrophils", ("neutrophil count", "neutrophils"), ("x10^9/L",)),
    ("Lymphocytes", ("lymphocyte count", "lymphocytes"), ("x10^9/L",)),
    ("Platelets", ("platelet count", "platelets"), ("x10^9/L",)),
    ("MCV", ("mean cell volume", "mcv"), ("fL",)),
)
_CANONICAL = {alias.casefold(): name for name, aliases, _units in _ROWS for alias in aliases}
_CLEAN_UNITS = {name: units for name, _aliases, units in _ROWS}
_NUM = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
_ALIASES = "|".join(re.escape(alias) for alias in sorted(_CANONICAL, key=len, reverse=True))
_TEST = re.compile(
    rf"(?<![A-Za-z])(?P<name>{_ALIASES})(?![A-Za-z])\s*(?:\([^)]{{0,16}}\))?\s*:?\s*(?P<value>{_NUM})",
    re.I,
)
_RANGE = re.compile(rf"({_NUM})\s*[-–]\s*({_NUM})")
_EMAIL = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")


def _looks_like_unit(token: str) -> bool:
    cleaned = token.strip(".,;:")
    return bool(cleaned) and len(cleaned) <= 24 and bool(re.search(r"\d|/", cleaned))


def _read_unit(segment: str, clean_units: tuple[str, ...]) -> tuple[str, str, bool]:
    text = segment.lstrip(" :")
    for unit in clean_units:
        if text.casefold().startswith(unit.casefold()):
            return unit, text[len(unit):], False
    token = re.match(r"\S+", text)
    if token and _looks_like_unit(token.group(0)):
        raw = token.group(0).strip(".,;:")
        return raw, text[token.end():], True
    return "", text, True


def to_lab_json(redacted_text: str) -> dict[str, Any]:
    """Return the rows that were read. Raise only when nothing safe can be shown."""
    if not isinstance(redacted_text, str) or not redacted_text.strip():
        raise ValueError("Empty redacted report")
    if _EMAIL.search(redacted_text):
        raise ValueError("Possible unredacted email in input")
    matches = list(_TEST.finditer(redacted_text))
    if not matches:
        raise ValueError("No supported analytes detected")
    results = []
    seen = set()
    for i, match in enumerate(matches):
        name = _CANONICAL[match.group("name").casefold()]
        if name in seen:
            raise ValueError(f"Duplicate analyte: {name}")
        seen.add(name)
        segment = redacted_text[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(redacted_text)]
        unit, rest, unit_unsure = _read_unit(segment, _CLEAN_UNITS[name])
        reference = None
        range_match = _RANGE.search(rest)
        if range_match:
            low, high = map(float, range_match.groups())
            if low < high:
                reference = {"low": low, "high": high}
                rest = rest[:range_match.start()] + rest[range_match.end():]
        needs_check = unit_unsure or reference is None and bool(re.search(r"\d", rest))
        value = float(match.group("value"))
        flag = "unknown" if reference is None else (
            "low" if value < reference["low"] else "high" if value > reference["high"] else "normal"
        )
        results.append({
            "testName": name,
            "value": value,
            "unit": unit,
            "referenceRange": reference,
            "flag": flag,
            "needsCheck": needs_check,
        })
    return {"results": results, "reviewRequired": True}
