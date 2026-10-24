"""Strict parser for a limited synthetic full blood count demo.

Never infer missing reference ranges or repair damaged units. OCR currently
flattens line breaks, so recognise only known analyte boundaries and reject
anything ambiguous. No identifiers are copied to the output.
"""
from __future__ import annotations

import re
from typing import Any

# Supported demo analytes. Extend only with tests and team agreement.
_ANALYTES = {
    "Haemoglobin": ("g/dL",),
    "White Blood Cells": ("x10^9/L",),
    "Platelets": ("x10^9/L",),
}
_NUM = r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)"
# OCR output is a single string; stop each match at the next analyte.
_ALIASES = "|".join(re.escape(name) for name in sorted(_ANALYTES, key=len, reverse=True))
_TEST = re.compile(rf"(?P<name>{_ALIASES})\s*:?\s*(?P<value>{_NUM})(?=\s|x10|g/dL)", re.I)
_RANGE = re.compile(rf"(?:\s*\(?\s*(?:ref(?:erence)?(?:\s*range)?\s*:?\s*)?\[?\s*({_NUM})\s*[-–]\s*({_NUM})\s*\]?\s*\)?)", re.I)


def to_lab_json(redacted_text: str) -> dict[str, Any]:
    """Return only validated readings, or raise ValueError without partial output."""
    if not isinstance(redacted_text, str) or not redacted_text.strip():
        raise ValueError("Empty redacted report")
    if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", redacted_text):
        raise ValueError("Possible unredacted email in input")
    matches = list(_TEST.finditer(redacted_text))
    if not matches:
        raise ValueError("No supported analytes detected")
    results = []
    seen = set()
    for i, m in enumerate(matches):
        name = next(n for n in _ANALYTES if n.casefold() == m.group("name").casefold())
        if name in seen:
            raise ValueError(f"Duplicate analyte: {name}")
        seen.add(name)
        segment = redacted_text[m.end():matches[i + 1].start() if i + 1 < len(matches) else len(redacted_text)]
        # Only strip surrounding punctuation; never normalise OCR-mangled units.
        unit = next((u for u in _ANALYTES[name] if segment.lstrip(" :").startswith(u)), None)
        if unit is None:
            raise ValueError(f"Missing or ambiguous unit for {name}")
        remainder = segment.lstrip(" :")[len(unit):]
        # Optional reference range: only structured explicit 'ref' or bracketed range.
        reference = None
        range_match = re.search(rf"(?:ref(?:erence)?(?:\s*range)?\s*:?|\[)\s*({_NUM})\s*[-–]\s*({_NUM})\s*\]?", remainder, re.I)
        if range_match:
            low, high = map(float, range_match.groups())
            if not low < high:
                raise ValueError(f"Invalid reference range for {name}")
            reference = {"low": low, "high": high}
        else:
            # Extra numerals after the unit imply an unparsed/malformed range.
            if re.search(r"\d", remainder):
                raise ValueError(f"Ambiguous trailing text for {name}")
        value = float(m.group("value"))
        flag = "unknown" if reference is None else (
            "low" if value < reference["low"] else "high" if value > reference["high"] else "normal"
        )
        results.append({"testName": name, "value": value, "unit": unit,
                        "referenceRange": reference, "flag": flag})
    return {"results": results, "reviewRequired": True}
