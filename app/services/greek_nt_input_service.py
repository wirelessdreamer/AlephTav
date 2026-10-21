"""Offline, edition-qualified Nestle 1904 lexical evidence; no canonical writes."""

from __future__ import annotations

import re
from typing import Any

from app.services.greek_dictionary_service import normalize_external_id

NT_BOOKS = (
    "Matt",
    "Mark",
    "Luke",
    "John",
    "Acts",
    "Rom",
    "1Cor",
    "2Cor",
    "Gal",
    "Eph",
    "Phil",
    "Col",
    "1Thess",
    "2Thess",
    "1Tim",
    "2Tim",
    "Titus",
    "Phlm",
    "Heb",
    "Jas",
    "1Pet",
    "2Pet",
    "1John",
    "2John",
    "3John",
    "Jude",
    "Rev",
)


def parse_nestle1904(text: str, *, package_id: str) -> list[dict[str, Any]]:
    """Preserve raw Robinson tags, source locators, homonym labels and extra columns."""
    rows = []
    for line_number, line in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split("\t")
        if fields == ["BCV", "text", "func_morph", "form_morph", "strongs", "lemma", "normalized"]:
            continue
        # The upstream export adds a trailing delimiter to ordinary rows. One
        # ambiguous verb also retains two extra morphological alternatives.
        if fields[-1] == "":
            fields.pop()
        extra = fields[7:]
        if len(fields) < 7 or any(not re.fullmatch(r"[A-Z0-9@-]+", f) for f in extra):
            raise ValueError(f"Nestle 1904 line {line_number}: expected seven TSV fields")
        ref, surface, functional, formal, strong, raw_lemma, word = fields[:7]
        match = re.fullmatch(r"(\S+) ([1-9]\d*):([1-9]\d*)", ref)
        if not match or match[1] not in NT_BOOKS or not all((surface, raw_lemma, word)):
            raise ValueError(f"Nestle 1904 line {line_number}: invalid reference or empty word")
        if not re.fullmatch(r"\d+(?:&\d+)?", strong):
            raise ValueError(f"Nestle 1904 line {line_number}: invalid lexical identifier")
        lemma = re.sub(r"\s+\([IVX]+\)$", "", raw_lemma)
        rows.append(
            {
                "row_id": f"{package_id}:row:{line_number}",
                "source_package_id": package_id,
                "source_locator": {"line": line_number, "reference": ref},
                "reference": f"nt:nestle1904:{match[1]}.{match[2]}.{match[3]}",
                "corpus": "nt",
                "book_code": match[1],
                "chapter": int(match[2]),
                "verse": int(match[3]),
                "surface": surface,
                "word": word,
                "normalized_source": word,
                "lemma": lemma,
                "raw_lemma": raw_lemma,
                "scheme": "Robinson",
                "raw_tag": functional,
                "raw_form_tag": formal,
                "morphology_alternatives": extra,
                "features": {},
                "synthetic": False,
                "lexical_identifiers": [
                    normalize_external_id(strong.split("&")[0], default_prefix="G")
                ],
                "raw_strongs": strong,
                "status": "proposed",
                "findings": ["additional_morphology_columns"] if extra else [],
            }
        )
    return rows
