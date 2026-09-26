"""Importing an existing translation of a psalm.

A translation pasted in from elsewhere (a songbook, a hymnal, another version) is read
by Codex in one turn, which only says where each part belongs: guidance it carries (a
meter, a tune, notes to singers) goes to the translation's guidance, and each verse's
text goes to that verse as a proposed rendering on the chosen layer. The pasted words
are kept exactly: everything Codex quotes back must be found in the paste, or nothing
is stored.

The paste lands in the translation the Codex session works on. When the reviewer does
not know which psalm a paste translates, Codex can identify it first.
"""

from __future__ import annotations

import re
from typing import Any

from jsonschema import Draft202012Validator

from app.core.errors import ValidationError
from app.services import codex_app_server_service as codex
from app.services import codex_translation_service as translation
from app.services import comparison_assessment_service as comparisons
from app.services import psalm_translations_service as translations
from app.services import registry_service, rendering_service

IMPORT_TEMPLATE_VERSION = "codex-import-v1"
KIND_IMPORT = "import"
LAYERS = ("gloss", "literal", "phrase", "concept", "lyric", "metered_lyric", "parallelism_lyric")
GUIDANCE_HEADING = "From the imported translation:"

IMPORT_VALIDATOR = Draft202012Validator(
    {
        "type": "object",
        "required": ["title", "guidance", "verses", "unplaced"],
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string"},
            "guidance": {"type": "array", "items": {"type": "string"}},
            "verses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["unit_id", "text"],
                    "additionalProperties": False,
                    "properties": {
                        "unit_id": {"type": "string"},
                        "text": {"type": "string", "minLength": 1},
                    },
                },
            },
            "unplaced": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["text", "reason"],
                    "additionalProperties": False,
                    "properties": {"text": {"type": "string"}, "reason": {"type": "string"}},
                },
            },
        },
    }
)

_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def fold(text: str) -> str:
    """Text as compared for "copied exactly": quotes, dashes and spacing evened out."""
    return re.sub(r"\s+", " ", text.translate(_QUOTES)).strip()


def not_in_paste(pasted: str, quoted: str) -> list[str]:
    """The lines of ``quoted`` that cannot be found in the paste."""
    haystack = fold(pasted)
    return [
        line.strip() for line in quoted.splitlines() if line.strip() and fold(line) not in haystack
    ]


def build_import_prompt(psalm_id: str, text: str, layer: str) -> str:
    psalm = registry_service.load_psalm(psalm_id)
    sections = [
        f"# Import task: an existing translation of {psalm.get('title', psalm_id)}",
        "",
        "The reviewer pasted the translation below. Say where each part of it belongs. Do",
        "not translate, correct or rewrite anything: every piece of text you return must be",
        "copied exactly from the paste. You may leave out verse numbers, section headings",
        "and repeat marks.",
        "",
        "## The Hebrew, verse by verse",
    ]
    for unit in psalm["units"]:
        sections += ["", f"### {unit['ref']} ({unit['unit_id']})", unit["source_hebrew"]]
        literal = comparisons.select_rendering(unit, comparisons.LITERAL_LAYER)
        if literal is not None:
            sections.append("  literal: " + " / ".join(literal["text"].splitlines()))
    sections += [
        "",
        "## The pasted translation",
        "<<<",
        text.strip(),
        ">>>",
        "",
        "## What to return",
        "title: the setting's title if the paste gives one, else an empty string.",
        "guidance: passages that direct how the psalm is translated or sung rather than",
        "  translating it (a meter, a tune, a key or tempo, notes to singers or translators),",
        '  each copied exactly. Headings such as "Verse 1" or "Chorus" are structure, not',
        "  guidance.",
        "verses: for each verse the paste translates, its unit_id and the text that renders",
        f"  it, copied exactly, lines joined with a newline. It becomes that verse's {layer}.",
        "  When the paste sings a verse more than once (a chorus), give its text once. When",
        "  one line carries two verses, give it with the verse it mostly renders.",
        "unplaced: text that renders no verse (a title, a line the translator added, a",
        "  heading you could not place), each with a short reason.",
    ]
    return "\n".join(sections)


def _imported_basis() -> dict[str, Any]:
    return {
        "basis_type": "hebrew_to_english",
        "source_ids": ["import"],
        "source_language": "en",
        "source_version": "imported",
        "basis_note": "Imported from an existing translation; its source basis is not recorded.",
    }


def _add_guidance(psalm_id: str, excerpts: list[str], translation_id: str | None) -> str:
    """Append the paste's guidance below any guidance already set. Returns what was added."""
    block = "\n".join(excerpts)
    existing = translation.get_guidance(psalm_id, translation_id)
    if not block or fold(block) in fold(existing):
        return ""
    heading = f"{GUIDANCE_HEADING}\n{block}"
    translation.set_guidance(
        psalm_id, f"{existing}\n\n{heading}" if existing else heading, translation_id
    )
    return block


def import_translation(
    client: codex.CodexAppServerClient,
    session_id: str,
    psalm_id: str,
    text: str,
    layer: str = "lyric",
    created_by: str = "import",
) -> dict[str, Any]:
    """Place a pasted translation: its guidance, and each verse's text on the verse."""
    if layer not in LAYERS:
        raise ValidationError(f"Unknown layer: {layer}")
    if not text.strip():
        raise ValidationError("Paste the translation to import")
    translation_id = translation.session_translation(session_id)
    psalm = registry_service.load_psalm(psalm_id)
    units = {unit["unit_id"]: unit for unit in psalm["units"]}

    run = translation.run_contract_turn(
        client,
        session_id=session_id,
        prompt=build_import_prompt(psalm_id, text, layer),
        validator=IMPORT_VALIDATOR,
        kind=KIND_IMPORT,
        psalm_id=psalm_id,
        layer=layer,
        prompt_template_version=IMPORT_TEMPLATE_VERSION,
    )
    result: dict[str, Any] = {
        "psalm_id": psalm_id,
        "translation_id": translation_id,
        "layer": layer,
        "status": run["status"],
        "error": run.get("error"),
        "run_id": run["run_id"],
        "title": "",
        "guidance_added": "",
        "renderings": [],
        "unplaced": [],
        "missing": [],
    }
    if run["status"] != translation.RUN_COMPLETED:
        return result
    payload = run["payload"]

    # One verse can come back in pieces; gather them in order.
    by_unit: dict[str, list[str]] = {}
    for verse in payload["verses"]:
        by_unit.setdefault(verse["unit_id"], []).append(verse["text"].strip())
    problems = [
        f"{unit_id} is not a verse of {psalm_id}" for unit_id in by_unit if unit_id not in units
    ]
    quoted = [*payload["guidance"], *(t for texts in by_unit.values() for t in texts)]
    problems += [f"“{line}” is not in the paste" for q in quoted for line in not_in_paste(text, q)]
    if problems:
        result["status"] = translation.RUN_INVALID_OUTPUT
        result["error"] = "Codex's reading did not keep to the pasted words: " + "; ".join(
            problems[:4]
        )
        return result

    result["title"] = payload["title"].strip()
    result["unplaced"] = payload["unplaced"]
    result["guidance_added"] = _add_guidance(
        psalm_id, [g.strip() for g in payload["guidance"] if g.strip()], translation_id
    )
    for unit_id in psalm["unit_ids"]:
        if unit_id not in by_unit:
            result["missing"].append(units[unit_id]["ref"])
            continue
        verse_text = "\n".join(by_unit[unit_id])
        unit = units[unit_id]
        same = next(
            (
                r
                for r in unit.get("renderings", [])
                if r.get("layer") == layer
                and r.get("status") != "rejected"
                and translations.shows_in(r, translation_id)
                and fold(r.get("text", "")) == fold(verse_text)
            ),
            None,
        )
        rendering = same or rendering_service.create_rendering(
            unit_id=unit_id,
            layer=layer,
            text=verse_text,
            status="proposed",
            rationale="Imported from an existing translation",
            created_by=created_by,
            translation_basis=_imported_basis(),
            translation_id=translation_id,
            provenance={
                "imported": True,
                "provider": codex.PROVIDER_NAME,
                "run_id": run["run_id"],
                "prompt_template_version": IMPORT_TEMPLATE_VERSION,
            },
        )
        shown = comparisons.select_rendering(
            registry_service.load_unit(unit_id), layer, translation_id
        )
        result["renderings"].append(
            {
                "unit_id": unit_id,
                "ref": unit["ref"],
                "rendering_id": rendering["rendering_id"],
                "unchanged": same is not None,
                # A verse with reviewed text keeps showing it; the import waits as a proposal.
                "shown": shown is not None and shown["rendering_id"] == rendering["rendering_id"],
            }
        )
    return result


# -- Which psalm a paste translates ----------------------------------------------

IDENTIFY_TEMPLATE_VERSION = "codex-identify-v1"
KIND_IDENTIFY = "identify"
#: How many of a psalm's opening word glosses the prompt lists, to check a guess against.
OPENING_GLOSSES = 20

IDENTIFY_VALIDATOR = Draft202012Validator(
    {
        "type": "object",
        "required": ["psalm_number", "confidence", "reason", "alternatives", "title"],
        "additionalProperties": False,
        "properties": {
            "psalm_number": {"type": ["integer", "null"]},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "reason": {"type": "string"},
            "alternatives": {"type": "array", "items": {"type": "integer"}},
            "title": {"type": "string"},
        },
    }
)


def _opening(psalm_id: str) -> str:
    """A psalm's first words, as the corpus glosses them word by word."""
    glosses: list[str] = []
    for unit_id in registry_service.load_psalm_meta(psalm_id).get("unit_ids", []):
        for token in registry_service.load_unit(unit_id).get("tokens", []):
            gloss = token.get("display_gloss") or token.get("gloss")
            if gloss:
                glosses.append(gloss)
        if len(glosses) >= OPENING_GLOSSES:
            break
    return " ".join(glosses[:OPENING_GLOSSES])


def build_identify_prompt(text: str, psalms: list[dict[str, Any]]) -> str:
    sections = [
        "# Which psalm is this?",
        "",
        "The reviewer pasted the translation below without saying which psalm it translates.",
        "Name the psalm. Number it as the Hebrew (Masoretic) text does, as English Bibles do,",
        "not as the Septuagint or Vulgate do (their Psalm 22 is the Hebrew Psalm 23).",
        "",
        "## The pasted translation",
        "<<<",
        text.strip(),
        ">>>",
        "",
        "## The opening of each psalm, as word-by-word glosses of the Hebrew",
    ]
    sections += [f"  {psalm['title']}: {_opening(psalm['psalm_id'])}" for psalm in psalms]
    sections += [
        "",
        "## What to return",
        "psalm_number: the psalm it translates, or null when it translates none of them.",
        "confidence: high, medium or low.",
        "reason: one sentence naming the words or images that identify it.",
        "alternatives: other psalms it could be, most likely first; empty when there are none.",
        "title: the translation's own title if the paste gives one, else an empty string.",
    ]
    return "\n".join(sections)


def identify_psalm(client: codex.CodexAppServerClient, text: str) -> dict[str, Any]:
    """Ask Codex which psalm a paste translates, in a thread of its own."""
    if not text.strip():
        raise ValidationError("Paste the translation to identify")
    psalms = {psalm["psalm_id"]: psalm for psalm in registry_service.list_psalm_summaries()}
    session = translation.create_session(client, psalm_id=None, purpose=KIND_IDENTIFY)
    run = translation.run_contract_turn(
        client,
        session_id=session["session_id"],
        prompt=build_identify_prompt(text, list(psalms.values())),
        validator=IDENTIFY_VALIDATOR,
        kind=KIND_IDENTIFY,
        prompt_template_version=IDENTIFY_TEMPLATE_VERSION,
    )
    result: dict[str, Any] = {
        "status": run["status"],
        "error": run.get("error"),
        "run_id": run["run_id"],
        "psalm_id": None,
        "confidence": None,
        "reason": "",
        "title": "",
        "alternatives": [],
    }
    if run["status"] != translation.RUN_COMPLETED:
        return result
    payload = run["payload"]

    def known(number: int | None) -> str | None:
        psalm_id = f"ps{number:03d}" if number is not None else None
        return psalm_id if psalm_id in psalms else None

    psalm_id = known(payload["psalm_number"])
    if payload["psalm_number"] is not None and psalm_id is None:
        result["status"] = translation.RUN_INVALID_OUTPUT
        result["error"] = f"Codex named Psalm {payload['psalm_number']}, which this workspace lacks"
        return result
    others = [known(number) for number in payload["alternatives"]]
    result.update(
        psalm_id=psalm_id,
        confidence=payload["confidence"],
        reason=payload["reason"].strip(),
        title=payload["title"].strip(),
        alternatives=list(dict.fromkeys(o for o in others if o and o != psalm_id)),
    )
    return result
