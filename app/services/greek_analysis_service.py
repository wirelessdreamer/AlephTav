"""Offline Greek analysis adapters. Matching creates proposals, never reviewed facts."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from typing import Any

NORMALIZER_VERSION = "greek-search-v1"
_ELISIONS = str.maketrans({"’": "'", "ʼ": "'", "᾿": "'", "᾽": "'"})


def normalize_greek(
    text: str, *, mark_insensitive: bool = False, normalize_elision: bool = False
) -> str:
    """Return a derived search key; callers must retain the original source spelling.

    Case folding preserves iota subscript as a full iota. Removing accent/breathing
    marks therefore does not conflate eta and eta-with-iota.
    """
    result = unicodedata.normalize("NFC", text).casefold()
    if normalize_elision:
        result = result.translate(_ELISIONS)
    if mark_insensitive:
        result = "".join(
            char
            for char in unicodedata.normalize("NFD", result)
            if unicodedata.category(char) != "Mn"
        )
    return unicodedata.normalize("NFC", result)


def unicode_findings(text: str) -> list[dict[str, Any]]:
    """Flag foreign-script letters without silently correcting a transcription."""
    findings = []
    for offset, char in enumerate(text):
        name = unicodedata.name(char, "")
        if char.isalpha() and ("LATIN" in name or "CYRILLIC" in name):
            findings.append(
                {"code": "foreign_script_letter", "offset": offset, "character": char, "name": name}
            )
    return findings


_FEATURES = (
    ("person", {"1": "first", "2": "second", "3": "third"}),
    (
        "tense",
        {
            "P": "present",
            "I": "imperfect",
            "F": "future",
            "A": "aorist",
            "X": "perfect",
            "Y": "pluperfect",
        },
    ),
    ("voice", {"A": "active", "M": "middle", "P": "passive"}),
    (
        "mood",
        {
            "I": "indicative",
            "D": "imperative",
            "S": "subjunctive",
            "O": "optative",
            "N": "infinitive",
            "P": "participle",
        },
    ),
    (
        "case",
        {"N": "nominative", "G": "genitive", "D": "dative", "A": "accusative", "V": "vocative"},
    ),
    ("number", {"S": "singular", "P": "plural", "D": "dual"}),
    ("gender", {"M": "masculine", "F": "feminine", "N": "neuter"}),
    ("degree", {"C": "comparative", "S": "superlative"}),
)
_POS = {
    "N-": "noun",
    "NP": "proper_noun",
    "V-": "verb",
    "A-": "adjective",
    "D-": "adverb",
    "P-": "preposition",
    "C-": "conjunction",
    "X-": "particle",
    "I-": "interjection",
    "RA": "article",
    "RD": "demonstrative_pronoun",
    "RI": "interrogative_pronoun",
    "RP": "personal_pronoun",
    "RR": "relative_pronoun",
}


def parse_morphgnt(pos: str, raw_tag: str) -> dict[str, Any]:
    if len(pos) != 2 or len(raw_tag) != 8:
        raise ValueError("MorphGNT requires a two-character POS and eight-character parsing")
    features = {"part_of_speech": _POS.get(pos)}
    unknowns = []
    if pos not in _POS:
        unknowns.append({"field": "part_of_speech", "value": pos})
    for char, (field, values) in zip(raw_tag, _FEATURES, strict=True):
        features[field] = values.get(char)
        if char != "-" and char not in values:
            unknowns.append({"field": field, "value": char})
    return {
        "scheme": "MorphGNT",
        "raw_pos": pos,
        "raw_tag": raw_tag,
        "features": features,
        "unknowns": unknowns,
    }


def parse_quantforge(text: str, *, package_id: str, book_code: int = 24) -> list[dict[str, Any]]:
    """Read all nine columns. No external Strong identifier is inferred."""
    if not 1 <= book_code <= 55:
        raise ValueError("QuantForge book code must be in the pinned catalog (1–55)")
    rows = []
    for line_number, line in enumerate(text.lstrip("\ufeff").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        # Four upstream rows have whitespace inside their lemma. Retain the
        # original field and a finding; join only that field for dictionary lookup.
        raw_lemma = " ".join(fields[6:-2])
        split_lemma = len(fields) > 9 and all(
            "GREEK" in unicodedata.name(c, "") or unicodedata.category(c) == "Mn"
            for c in "".join(fields[6:-2])
        )
        if len(fields) != 9 and not split_lemma:
            raise ValueError(f"QuantForge line {line_number}: expected nine fields")
        if split_lemma:
            fields = [*fields[:6], "".join(fields[6:-2]), *fields[-2:]]
        reference, pos, tag, surface, word, normalized, lemma, language, method = fields
        if not re.fullmatch(rf"{book_code:03}\d{{6}}", reference) or language != "grc":
            raise ValueError(f"QuantForge line {line_number}: invalid book reference/language")
        if book_code == 24 and not 1 <= int(reference[3:6]) <= 151:
            raise ValueError(f"QuantForge line {line_number}: psalm outside 1–151")
        # Esther's additions and the Odes include chapter-zero material in this
        # source. Preserve those locators instead of dropping or renumbering it.
        parsing = parse_morphgnt(pos, tag)
        rows.append(
            {
                "row_id": f"{package_id}:row:{line_number}",
                "source_package_id": package_id,
                "source_locator": {"line": line_number},
                "reference": reference,
                "book_code": book_code,
                "chapter": int(reference[3:6]),
                **({"psalm": int(reference[3:6])} if book_code == 24 else {}),
                "verse": int(reference[6:9]),
                "surface": surface,
                "word": word,
                "normalized_source": normalized,
                "lemma": lemma,
                "raw_lemma": raw_lemma,
                "findings": ["lemma_whitespace"] if split_lemma else [],
                "language": language,
                "method": method,
                "synthetic": method == "morpheus-proper",
                "status": "proposed",
                "identifiers": [],
                **parsing,
            }
        )
    return rows


def _span_key(words: list[str]) -> str:
    return "".join(normalize_greek(word, normalize_elision=True) for word in words)


def propose_analyses(
    units: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    *,
    verse_map: dict[str, list[str]],
    analysis_set_id: str,
    max_span: int = 3,
) -> dict[str, Any]:
    """Compare explicitly mapped verses and source surfaces, including split/joined spans.

    Repeated spellings retain all candidates. Positions constrain contiguous spans,
    never identify a source word by its ordinal in a different edition.
    """
    if not 1 <= max_span <= 4:
        raise ValueError("max_span must be between 1 and 4")
    unit_map = {unit["unit_id"]: unit for unit in units}
    if len(unit_map) != len(units):
        raise ValueError("Duplicate source unit ID")
    token_ids = [token["token_id"] for unit in units for token in unit["tokens"]]
    if len(token_ids) != len(set(token_ids)):
        raise ValueError("Duplicate source token ID")
    annotations = {
        token_id: {
            "token_id": token_id,
            "status": "unresolved",
            "analyses": [],
            "selected_analysis_id": None,
        }
        for token_id in token_ids
    }
    by_reference: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_reference[row["reference"]].append(row)
    spans = []
    matched_rows: set[str] = set()
    for reference, targets in verse_map.items():
        if any(target not in unit_map for target in targets):
            raise ValueError(f"Unknown source unit in verse map: {reference}")
        source_rows = by_reference.get(reference, [])
        row_spans: dict[str, list[list[dict[str, Any]]]] = defaultdict(list)
        for start in range(len(source_rows)):
            for size in range(1, min(max_span, len(source_rows) - start) + 1):
                span_rows = source_rows[start : start + size]
                row_spans[_span_key([row["word"] for row in span_rows])].append(span_rows)
        for target in targets:
            tokens = unit_map[target]["tokens"]
            for start in range(len(tokens)):
                for size in range(1, min(max_span, len(tokens) - start) + 1):
                    members = tokens[start : start + size]
                    key = _span_key([token["surface"] for token in members])
                    for span_rows in row_spans.get(key, []):
                        # Multiword matches add evidence only for actual split/joined forms.
                        if size > 1 and len(span_rows) > 1:
                            continue
                        row_ids = [row["row_id"] for row in span_rows]
                        member_ids = [token["token_id"] for token in members]
                        digest = hashlib.sha256(
                            (analysis_set_id + "|" + "|".join(member_ids + row_ids)).encode()
                        ).hexdigest()[:20]
                        evidence = {
                            "normalizer": NORMALIZER_VERSION,
                            "reference": reference,
                            "method": "verse_surface_span",
                            "token_ids": member_ids,
                            "source_row_ids": row_ids,
                        }
                        span_id = f"{analysis_set_id}:span:{digest}"
                        spans.append({"span_id": span_id, "status": "proposed", **evidence})
                        matched_rows.update(row_ids)
                        for member in members:
                            annotation = annotations[member["token_id"]]
                            annotation["status"] = "proposed"
                            for row in span_rows:
                                candidate_id = f"{span_id}:{row['row_id']}:{member['token_id']}"
                                annotation["analyses"].append(
                                    {
                                        "analysis_id": candidate_id,
                                        "analysis_set_id": analysis_set_id,
                                        "token_id": member["token_id"],
                                        "lexeme_id": None,
                                        "lemma": row["lemma"],
                                        "identifiers": [],
                                        "status": "proposed",
                                        "scheme": row["scheme"],
                                        "raw_tag": row["raw_tag"],
                                        "raw_pos": row["raw_pos"],
                                        "features": row["features"],
                                        "unknowns": row["unknowns"],
                                        "synthetic": row["synthetic"],
                                        "confidence": None,
                                        "source_package_id": row["source_package_id"],
                                        "evidence": evidence,
                                    }
                                )
    for annotation in annotations.values():
        annotation["ambiguous"] = len(annotation["analyses"]) > 1
    return {
        "analysis_set_id": analysis_set_id,
        "status": "proposed",
        "spans": spans,
        "annotations": list(annotations.values()),
        "unmatched_source_row_ids": [
            row["row_id"] for row in rows if row["row_id"] not in matched_rows
        ],
        "coverage": {
            "total_tokens": len(token_ids),
            "proposed_tokens": sum(a["status"] == "proposed" for a in annotations.values()),
            "unresolved_tokens": sum(a["status"] == "unresolved" for a in annotations.values()),
            "reviewed_tokens": 0,
        },
    }


def expression_matches(
    occurrences: list[dict[str, Any]], *, scheme: str, value: str, expand_components: bool = False
) -> dict[str, Any]:
    """Count authored expression occurrences without inventing printed component tokens."""
    matches = []
    seen = set()
    for occurrence in occurrences:
        identifiers = list(occurrence.get("identifiers", []))
        if expand_components:
            identifiers += occurrence.get("component_identifiers", [])
        if not any(item["scheme"] == scheme and item["value"] == value for item in identifiers):
            continue
        occurrence_id = occurrence["occurrence_id"]
        members = occurrence["token_ids"]
        if not members or len(members) != len(set(members)):
            raise ValueError("An expression requires distinct ordered physical token members")
        if occurrence_id not in seen:
            seen.add(occurrence_id)
            matches.append(occurrence)
    return {
        "match_unit": "expression",
        "total_matches": len(matches),
        "total_tokens": len({token for match in matches for token in match["token_ids"]}),
        "total_verses": len({match["unit_id"] for match in matches}),
        "component_expansion": expand_components,
        "matches": matches,
    }


def validate_lexical_graph(
    lexeme_set: dict[str, Any],
    crosswalk_set: dict[str, Any],
    *,
    source_entry_ids: set[str],
    previous_lexeme_ids: set[str] | None = None,
) -> dict[str, int]:
    """Validate authored identities without merging homographs or repeated external IDs."""
    from app.services.foundation_contract_service import validate_contract

    validate_contract("greek_lexeme_set.schema.json", lexeme_set)
    validate_contract("greek_crosswalk_set.schema.json", crosswalk_set)
    if crosswalk_set["lexeme_set_id"] != lexeme_set["lexeme_set_id"]:
        raise ValueError("Crosswalk is bound to a different immutable lexeme set")
    ids = [item["lexeme_id"] for item in lexeme_set["lexemes"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate local lexeme identity")
    prior = previous_lexeme_ids or set()
    for lexeme in lexeme_set["lexemes"]:
        if set(lexeme["replaces"]) - prior or lexeme["lexeme_id"] in lexeme["replaces"]:
            raise ValueError("Lexeme split/merge requires explicit retained predecessor IDs")
    assignments = crosswalk_set["assignments"]
    if len({item["assignment_id"] for item in assignments}) != len(assignments):
        raise ValueError("Duplicate crosswalk assignment identity")
    for item in assignments:
        if item["lexeme_id"] not in ids or item["source_entry_id"] not in source_entry_ids:
            raise ValueError("Crosswalk references a missing local lexeme or source entry")
    return {"lexemes": len(ids), "assignments": len(assignments)}
