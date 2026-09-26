"""Drafting a song setting of a whole psalm with Codex.

One turn writes the setting: sections, lines anchored to the Hebrew tokens they
render, the kind of liberty each line takes, and any Hebrew left out with the
reason. The draft is checked against the psalm's real tokens before anything is
stored, and is stored as a proposed arrangement for review.
"""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from app.core.errors import ValidationError
from app.services import arrangement_service as arrangements
from app.services import codex_app_server_service as codex
from app.services import codex_translation_service as translation
from app.services import comparison_assessment_service as comparisons
from app.services import registry_service
from app.services.codex_import_service import not_in_paste

ARRANGE_TEMPLATE_VERSION = "codex-arrangement-v1"
IMPORT_ARRANGE_TEMPLATE_VERSION = "codex-arrangement-import-v1"
KIND_ARRANGEMENT = "arrangement"

ARRANGE_VALIDATOR = Draft202012Validator(
    {
        "type": "object",
        "required": ["title", "sections", "omissions"],
        "additionalProperties": False,
        "properties": {
            "title": {"type": "string", "minLength": 1},
            "sections": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["key", "kind", "label", "repeat_of", "lines"],
                    "additionalProperties": False,
                    "properties": {
                        "key": {"type": "string", "minLength": 1},
                        "kind": {"type": "string", "enum": list(arrangements.SECTION_KINDS)},
                        "label": {"type": "string"},
                        "repeat_of": {"type": ["string", "null"]},
                        "lines": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["text", "token_ids", "liberty", "rationale"],
                                "additionalProperties": False,
                                "properties": {
                                    "text": {"type": "string", "minLength": 1},
                                    "token_ids": {"type": "array", "items": {"type": "string"}},
                                    "liberty": {
                                        "type": "string",
                                        "enum": list(arrangements.LINE_LIBERTIES),
                                    },
                                    "rationale": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
            "omissions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["token_ids", "rationale"],
                    "additionalProperties": False,
                    "properties": {
                        "token_ids": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "string"},
                        },
                        "rationale": {"type": "string"},
                    },
                },
            },
        },
    }
)


def _verse_block(unit: dict[str, Any], layer: str, translation_id: str | None = None) -> list[str]:
    lines = [f"### {unit['ref']} ({unit['unit_id']})", unit["source_hebrew"]]
    for token in unit.get("tokens", []):
        gloss = token.get("display_gloss") or token.get("gloss") or ""
        lines.append(f"  {token['token_id']} {token['surface']}  {gloss}".rstrip())
    for shown in ("literal", layer):
        rendering = comparisons.select_rendering(unit, shown, translation_id)
        if rendering is not None:
            text = " / ".join(rendering["text"].splitlines())
            lines.append(f"  {shown}: {text}")
    return lines


def build_arrangement_prompt(psalm_id: str, layer: str, translation_id: str | None = None) -> str:
    psalm = registry_service.load_psalm(psalm_id)
    guidance = translation.get_guidance(psalm_id, translation_id)
    sections = [
        "# Song setting task",
        f"Psalm: {psalm.get('title', psalm_id)} ({psalm_id})",
        f"English register: {layer}",
        "",
        "## Translator guidance for this psalm (the setting must work within it)",
        guidance or "(none set)",
        "",
        "## The Hebrew, verse by verse, with every token's id",
    ]
    for unit in psalm["units"]:
        sections += ["", *_verse_block(unit, layer, translation_id)]
    refrains = arrangements.find_refrains(psalm["units"])
    if refrains:
        sections += ["", "## Words the Hebrew itself repeats"]
        for refrain in refrains:
            places = ", ".join(instance["ref"] for instance in refrain["instances"])
            sections.append(f"  {refrain['text']} — in {places}")
    sections += [
        "",
        "## Task",
        "Write a singable setting of the whole psalm in sections (verse, chorus, refrain,",
        "bridge, intro, outro, other). You are free to:",
        "  - let a line carry words from more than one verse, or spread a verse over lines;",
        "  - sing a section again: give the repeat its own key and set repeat_of to the key",
        "    of the section it repeats; its lines are only what that time adds, usually none;",
        "  - compress, expand, reorder or add, where the guidance or the song calls for it.",
        "Every departure is declared, never hidden. For each line give:",
        "  text: the line as sung;",
        "  token_ids: the Hebrew tokens the line renders, exact ids from above, or none",
        "    when the line renders nothing in the Hebrew;",
        "  liberty: tracks (renders its tokens closely), compressed (folds them together or",
        "    leaves part out), expanded (adds to them), reordered (changes their order), or",
        "    added (not in the Hebrew there);",
        "  rationale: one sentence for any liberty but tracks; empty for tracks.",
        "Carry every Hebrew token in some line at least once. List any you leave out in",
        "omissions, with the reason. Words the Hebrew repeats are sung the same way each",
        "time unless there is a reason to vary them. Keys are short names you choose",
        '("V1", "C"); labels are what a singer reads ("Verse 1", "Chorus").',
    ]
    return "\n".join(sections)


def build_import_arrangement_prompt(
    psalm_id: str, text: str, layer: str, translation_id: str | None = None
) -> str:
    """Describe an existing translation as a setting, without writing a word of it."""
    psalm = registry_service.load_psalm(psalm_id)
    sections = [
        f"# Song setting analysis: an existing translation of {psalm.get('title', psalm_id)}",
        f"English register: {layer}",
        "",
        "## Translator guidance for this psalm",
        translation.get_guidance(psalm_id, translation_id) or "(none set)",
        "",
        "## The Hebrew, verse by verse, with every token's id",
    ]
    for unit in psalm["units"]:
        sections += ["", *_verse_block(unit, "literal")]
    sections += [
        "",
        "## The translation",
        "<<<",
        text.strip(),
        ">>>",
        "",
        "## Task",
        "Describe this translation as a song setting of the psalm. Do not write new lines or",
        "change any: every line's text is one line of the translation, copied exactly.",
        "  - sections: the translation's own sections in its order. A heading such as",
        '    "Chorus" starts one; without headings, each stanza or verse is a section.',
        "    When a section comes back word for word, give it its own key and set repeat_of",
        "    to the key of its first appearance, with no lines. When it comes back with lines",
        "    added, give only the added lines. When it comes back changed otherwise, write it",
        "    out as a section of its own.",
        "  - for each line: token_ids, the exact ids of the Hebrew tokens it renders, or none;",
        "    liberty: tracks (renders them closely), compressed (folds them together or leaves",
        "    part out), expanded (adds to them), reordered (changes their order), or added (not",
        "    in the Hebrew there); rationale: one sentence for any liberty but tracks.",
        "  - omissions: Hebrew tokens no line carries, with the reason as far as the",
        "    translation shows it.",
        "  - title: the translation's title, or a short one.",
    ]
    return "\n".join(sections)


def _store(
    run: dict[str, Any],
    psalm_id: str,
    layer: str,
    created_by: str,
    created_via: str,
    template_version: str,
    pasted: str | None = None,
) -> dict[str, Any]:
    """Store a completed run's setting as a proposal; nothing when it does not hold."""
    result: dict[str, Any] = {
        "psalm_id": psalm_id,
        "status": run["status"],
        "error": run.get("error"),
        "run_id": run["run_id"],
        "view": None,
    }
    if run["status"] != translation.RUN_COMPLETED:
        return result
    payload = run["payload"]
    if pasted is not None:
        rewritten = [
            line
            for section in payload["sections"]
            for item in section["lines"]
            for line in not_in_paste(pasted, item["text"])
        ]
        if rewritten:
            result["status"] = translation.RUN_INVALID_OUTPUT
            result["error"] = "Codex changed the translation's lines: " + "; ".join(
                f"“{line}”" for line in rewritten[:4]
            )
            return result
    try:
        result["view"] = arrangements.create_arrangement(
            psalm_id,
            layer=layer,
            title=payload["title"],
            created_by=created_by,
            sections=payload["sections"],
            omissions=payload["omissions"],
            created_via=created_via,
            generation_run_id=run["run_id"],
            prompt_template_version=template_version,
            status="proposed",
            guidance=translation.get_guidance(psalm_id, run.get("translation_id")),
            translation_id=run.get("translation_id"),
        )
    except ValidationError as error:
        # The setting named tokens or sections that do not exist: nothing is stored.
        result["status"] = translation.RUN_INVALID_OUTPUT
        result["error"] = f"Codex's setting did not hold together: {error}"
    return result


def draft_arrangement(
    client: codex.CodexAppServerClient,
    session_id: str,
    psalm_id: str,
    layer: str = "lyric",
    created_by: str = "codex",
) -> dict[str, Any]:
    """Draft a setting and store it as a proposed arrangement."""
    run = translation.run_contract_turn(
        client,
        session_id=session_id,
        prompt=build_arrangement_prompt(
            psalm_id, layer, translation.session_translation(session_id)
        ),
        validator=ARRANGE_VALIDATOR,
        kind=KIND_ARRANGEMENT,
        psalm_id=psalm_id,
        layer=layer,
        prompt_template_version=ARRANGE_TEMPLATE_VERSION,
    )
    return _store(run, psalm_id, layer, created_by, "codex", ARRANGE_TEMPLATE_VERSION)


def arrange_import(
    client: codex.CodexAppServerClient,
    session_id: str,
    psalm_id: str,
    text: str,
    layer: str = "lyric",
    created_by: str = "import",
) -> dict[str, Any]:
    """Analyse a pasted translation as a setting, its lines kept exactly as pasted."""
    if not text.strip():
        raise ValidationError("Paste the translation to analyse")
    run = translation.run_contract_turn(
        client,
        session_id=session_id,
        prompt=build_import_arrangement_prompt(
            psalm_id, text, layer, translation.session_translation(session_id)
        ),
        validator=ARRANGE_VALIDATOR,
        kind=KIND_ARRANGEMENT,
        psalm_id=psalm_id,
        layer=layer,
        prompt_template_version=IMPORT_ARRANGE_TEMPLATE_VERSION,
    )
    return _store(
        run, psalm_id, layer, created_by, "import", IMPORT_ARRANGE_TEMPLATE_VERSION, pasted=text
    )
