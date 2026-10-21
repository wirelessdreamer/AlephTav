"""Read-only phrase attribution from recorded arrangement notes and exact verse anchors."""

from __future__ import annotations

import re
from typing import Any

from app.services import comparison_assessment_service as comparisons

_ADOPTS_GREEK = re.compile(
    r"^\s*(?:follows?|adopts?|uses?|based on)\s+(?:the\s+)?(?:Greek|Septuagint|LXX)\b", re.I
)
_GREEK_REFERENCE = re.compile(r"(?:Greek|Septuagint|LXX)\s+Psalm\s+(\d+:\d+)", re.I)
_GREEK_DECISION = re.compile(r"\b(?:Greek|Septuagint|LXX)\b", re.I)
_WORD = re.compile(r"[\w]+(?:['’][\w]+)?")
_TOKEN = re.compile(
    r"\b(ps\d{3}\.v\d{3}\.t\d{3}|t\d{3})(?:\s*[–—-]\s*(ps\d{3}\.v\d{3}\.t\d{3}|t\d{3}))?\b"
)


def _phrase_range(text: str, phrase: str) -> tuple[int, int] | None:
    """Match explicit English hints, allowing punctuation and possessive inflection only."""
    words = list(_WORD.finditer(text))

    def key(value: str) -> str:
        return re.sub(r"['’]s$", "", value.casefold())

    wanted = [key(word[0]) for word in _WORD.finditer(phrase)]
    if not wanted:
        return None
    found = [
        (words[index].start(), words[index + len(wanted) - 1].end())
        for index in range(len(words) - len(wanted) + 1)
        if [key(word[0]) for word in words[index : index + len(wanted)]] == wanted
    ]
    return found[0] if len(found) == 1 else None


def _hebrew_phrases(
    unit: dict[str, Any], rendering: dict[str, Any], line: dict[str, Any], anchor: dict[str, Any]
) -> list[dict[str, Any]]:
    """Project explicit token → English hints; replacement/correspondence notes are not links."""
    valid = {token["token_id"] for token in unit.get("tokens", [])}
    anchored = set(anchor["token_ids"])
    prefix = unit["unit_id"].rsplit(".", 1)[0] + "."
    phrases = []
    for hint in (rendering.get("provenance") or {}).get("alignment_hints", []):
        if not re.match(r"^(?:Hebrew\s+)?ps\d{3}\.v\d{3}\.t\d{3}\b", hint):
            continue
        if "→" not in hint:
            continue
        source, target = hint.split("→", 1)
        # Explanatory prose after a comma/semicolon is not part of the quoted phrase.
        target = re.split(r"[,;]", target, maxsplit=1)[0].strip()
        span = _phrase_range(line["text"], target)
        if span is None or _phrase_range(rendering["text"], target) is None:
            continue
        ids: list[str] = []
        for match in _TOKEN.finditer(source):
            first, last = match.groups()
            first = first if first.startswith("ps") else prefix + first
            last = last if last and last.startswith("ps") else prefix + last if last else first
            if not first.startswith(prefix) or not last.startswith(prefix):
                ids = []
                break
            ids.extend(
                f"{prefix}t{number:03d}" for number in range(int(first[-3:]), int(last[-3:]) + 1)
            )
        if not ids or not set(ids).issubset(valid & anchored):
            continue
        phrase = {
            "start": span[0],
            "end": span[1],
            "text": line["text"][slice(*span)],
            "token_ids": list(dict.fromkeys(ids)),
        }
        if phrase not in phrases:
            phrases.append(phrase)
    return phrases


def arrangement_choices(
    psalm: dict[str, Any], arrangement: dict[str, Any], greek: dict[str, Any]
) -> list[dict[str, Any]]:
    """Expose recorded claims only when their verse's Greek anchor resolves to this edition.

    A line's saved rationale supplies phrase scope; lexical resemblance never assigns a source.
    Existing choices remain proposed, not new word-level alignment or review approval.
    """
    if not greek.get("available"):
        return []
    units = {unit["unit_id"]: unit for unit in psalm["units"]}
    choices = []
    for section in arrangement["sections"]:
        for line in section["lines"]:
            note = line.get("rationale", "")
            if not _ADOPTS_GREEK.search(note):
                continue
            claim = _GREEK_REFERENCE.search(note)
            anchors = line.get("anchors", [])
            if not claim and len(anchors) != 1:
                continue
            for anchor in anchors:
                unit = units.get(anchor["unit_id"])
                if unit is None:
                    continue
                rendering = comparisons.select_rendering(
                    unit, arrangement["layer"], arrangement.get("translation_id")
                )
                if not rendering:
                    continue
                basis = rendering.get("translation_basis") or {}
                source = rendering.get("source_anchor") or {}
                if (
                    rendering.get("status") in {"rejected", "superseded"}
                    or basis.get("basis_type") != "septuagint_greek_to_english"
                    or basis.get("source_language") != "grc"
                    or not {"lxx", greek["edition_id"]}.issubset(basis.get("source_ids", []))
                ):
                    continue
                mapped = greek.get("by_mt_unit", {}).get(unit["unit_id"], {}).get("units", [])
                resolved = next(
                    (
                        candidate
                        for candidate in mapped
                        if source.get("source_language") == "grc"
                        and source.get("source_text") == candidate["source_greek"]
                        and source.get("token_ids")
                        == [token["token_id"] for token in candidate["tokens"]]
                        and str(basis.get("source_version", "")).startswith(
                            f"{greek['edition_id']}:{greek['text_revision_id']}:"
                        )
                        and (not claim or candidate["ref"].endswith(f" {claim[1]}"))
                    ),
                    None,
                )
                if resolved is None:
                    continue
                context = (rendering.get("provenance") or {}).get("translation_context") or {}
                decisions = [
                    annotation
                    for annotation in context.get("annotations", [])
                    if int(unit["unit_id"].split(".")[1][1:])
                    in annotation["question"].get("verses", [])
                    and _GREEK_DECISION.search(annotation.get("answer", ""))
                ]
                choices.append(
                    {
                        "choice_id": f"{line['line_id']}:{unit['unit_id']}",
                        "line_id": line["line_id"],
                        "unit_id": unit["unit_id"],
                        "mt_reference": unit["ref"],
                        "greek_reference": resolved["ref"],
                        "edition_id": greek["edition_id"],
                        "text_revision_id": greek["text_revision_id"],
                        "source_version": basis["source_version"],
                        "rendering_id": rendering["rendering_id"],
                        "text": line["text"],
                        "rationale": note,
                        "decisions": decisions,
                        "decision_scope": "verse_translation",
                        "status": "proposed",
                        "hebrew_phrases": _hebrew_phrases(unit, rendering, line, anchor),
                    }
                )
    return choices
