"""Compact attributed English translation spans from the pinned Perseus LSJ.

The documentary DTD is never loaded. Each entry is parsed independently with no
DTD/entity declarations, so external resources cannot be resolved by the adapter.
"""

from __future__ import annotations

import re
import unicodedata
import xml.etree.ElementTree as ET
from typing import Any

_LETTERS = dict(zip("abgdezhqiklmncoprstufxywv", "αβγδεζηθικλμνξοπρστυφχψωϝ", strict=True))
_MARKS = {
    "(": "\u0314",
    ")": "\u0313",
    "/": "\u0301",
    "\\": "\u0300",
    "=": "\u0342",
    "+": "\u0308",
    "|": "\u0345",
}
_ENTRY = re.compile(r"<entryFree\b.*?</entryFree>", re.S)


def beta_headword(value: str) -> str:
    """Convert source Beta Code keys; omit quantity notation in lookup keys only."""
    value = re.sub(r"\d+$", "", value)
    result = []
    base = ""
    marks = ""
    capital = False
    for char in value:
        if char == "*":
            if base:
                result.append(base + marks)
                base = marks = ""
            capital = True
        elif char.lower() in _LETTERS:
            if base:
                result.append(base + marks)
                marks = ""
            base = _LETTERS[char.lower()]
            if capital:
                base = base.upper()
            capital = False
        elif char in _MARKS:
            marks += _MARKS[char]
        elif char in "_^":
            continue
        elif char in "-' ":
            if base:
                result.append(base + marks)
            result.append(char)
            base = marks = ""
        else:
            raise ValueError(f"Unsupported Beta Code key character: {char!r}")
    if base:
        result.append(base + marks)
    text = "".join(result)
    text = re.sub(r"σ(?=$|[-' ])", "ς", text)
    return unicodedata.normalize("NFC", text)


def parse_lsj_spans(
    text: str, *, source_file: str, attribution: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Retain source keys/IDs and explicit English <tr> spans, never Greek quotations."""
    entries = []
    counts = {
        "entries": 0,
        "with_translation_spans": 0,
        "cross_references": 0,
        "without_translation_spans": 0,
        "unsupported_keys": 0,
    }
    for match in _ENTRY.finditer(text):
        fragment = match[0]
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", fragment, re.I):
            raise ValueError("DTD/entity declarations inside LSJ entries are forbidden")
        element = ET.fromstring(fragment)
        counts["entries"] += 1
        key = element.get("key") or ""
        try:
            headword = beta_headword(key)
        except ValueError:
            counts["unsupported_keys"] += 1
            continue
        if not headword:
            counts["unsupported_keys"] += 1
            continue
        translations = list(
            dict.fromkeys(
                " ".join("".join(node.itertext()).split()).strip(" ,;.")
                for node in element.iter("tr")
                if "".join(node.itertext()).strip()
            )
        )
        translations = [t for t in translations if t and re.search(r"[a-zA-Z]", t)]
        references = []
        if not translations:
            for xr in element.iter("xr"):
                for ref in xr.iter("ref"):
                    if ref.get("lang") == "greek":
                        try:
                            references.append(beta_headword("".join(ref.itertext()).strip()))
                        except ValueError:
                            pass
        entry = {
            "entry_id": f"perseus.lsj:{source_file}:{element.get('id')}",
            "headword": headword,
            "gloss": " / ".join(translations[:4]) or None,
            "source_key": key,
            "source_locator": {"file": source_file, "id": element.get("id")},
            "attribution": dict(attribution),
            "fallback_dictionary": True,
            "dictionary_cross_references": references,
        }
        if translations:
            counts["with_translation_spans"] += 1
            entries.append(entry)
        elif references:
            counts["cross_references"] += 1
            entries.append(entry)
        else:
            counts["without_translation_spans"] += 1
    if counts["entries"] != len(re.findall(r"<entryFree\b", text)):
        raise ValueError(f"LSJ entry accounting mismatch: {source_file}")
    return entries, counts


def resolve_lsj_cross_references(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy context only from an explicitly referenced defined dictionary headword."""
    from app.services.greek_analysis_service import normalize_greek

    by_headword: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        if entry["gloss"]:
            by_headword.setdefault(normalize_greek(entry["headword"]), []).append(entry)
    resolved = []
    for entry in entries:
        if entry["gloss"]:
            resolved.append(entry)
            continue
        targets = [
            target
            for ref in entry["dictionary_cross_references"]
            for target in by_headword.get(normalize_greek(ref), [])
        ]
        if targets:
            resolved.append(
                {
                    **entry,
                    "gloss": "see "
                    + " / ".join(
                        dict.fromkeys(
                            f"{target['headword']}: {target['gloss']}" for target in targets
                        )
                    ),
                    "cross_reference_entry_ids": [t["entry_id"] for t in targets],
                }
            )
    return resolved
