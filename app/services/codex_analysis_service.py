"""The analysis pass: auditing existing renderings against the Hebrew.

Deliberately a second pass, separate from translation. It never writes a
rendering, and translation never writes a verdict, so no model grades its own
work. It runs over whatever renderings exist -- including ones a human wrote --
and is re-runnable when they change.

The auditor is blind to the psalm's ``translation_guidance``. That guidance is
injected into translation prompts as instruction that outranks general rules;
feeding it to the auditor would prime it with the intent it is supposed to judge
independently.

Two scopes, N+1 turns per psalm: one turn per verse, and one turn carrying the
sections and the psalm-wide material together, because sections must tile the
psalm and agree with its structural seams.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator

from app.core.errors import NotFoundError, ValidationError
from app.core.ids import psalm_analysis_id as build_psalm_analysis_id
from app.services import (
    audit_service,
    registry_service,
)
from app.services import (
    codex_app_server_service as codex,
)
from app.services import (
    codex_translation_service as translation,
)
from app.services import (
    comparison_assessment_service as comparisons,
)
from app.services import (
    psalm_translations_service as translations,
)

PROMPT_TEMPLATE_VERSION = "codex-analysis-v1"
# The psalm turn's own version: an analysis from an earlier prompt re-runs, not skips.
PSALM_PROMPT_TEMPLATE_VERSION = "codex-psalm-analysis-v2"

ANALYSIS_STATUS_PROPOSED = "proposed"
ANALYSIS_STATUS_SUPERSEDED = "superseded"


def _contract(name: str) -> Draft202012Validator:
    return Draft202012Validator(
        json.loads(resources.files("app.llm.contracts").joinpath(name).read_text(encoding="utf-8"))
    )


VERSE_VALIDATOR = _contract("verse_analysis_output.schema.json")
PSALM_VALIDATOR = _contract("psalm_analysis_output.schema.json")


def _now() -> str:
    return datetime.now(UTC).isoformat()


# -- Fingerprints ----------------------------------------------------------
#
# A rendering's text can change UNDER THE SAME rendering_id: update_rendering
# mutates it in place. Comparing ids therefore cannot detect an edited lyric, so
# staleness is keyed on content. The model never supplies these, which is what
# stops a stale analysis being stamped fresh.


def verse_fingerprint(unit: dict[str, Any], renderings: list[dict[str, Any]]) -> str:
    return registry_service.file_hash(
        {
            "source_hebrew": unit["source_hebrew"],
            "renderings": [
                {"rendering_id": r["rendering_id"], "text": r["text"]}
                for r in renderings
                if r is not None
            ],
        }
    )


def psalm_fingerprint(
    psalm: dict[str, Any], english_layer: str, translation_id: str | None = None
) -> str:
    parts = []
    for unit in psalm["units"]:
        literal = comparisons.select_rendering(unit, comparisons.LITERAL_LAYER, translation_id)
        english = comparisons.select_rendering(unit, english_layer, translation_id)
        parts.append(
            {
                "unit_id": unit["unit_id"],
                "fingerprint": verse_fingerprint(unit, [literal, english]),
            }
        )
    return registry_service.file_hash(parts)


def active_analysis(psalm_id: str, translation_id: str | None = None) -> dict[str, Any] | None:
    """The translation's current psalm-scope analysis, if it has one."""
    meta = registry_service.load_psalm_meta(psalm_id)
    for record in reversed(meta.get("analyses", [])):
        if record["status"] != ANALYSIS_STATUS_SUPERSEDED and translations.in_translation(
            record, translation_id
        ):
            return record
    return None


# -- Prompts ---------------------------------------------------------------


def _evidence_block(
    unit: dict[str, Any],
    english_layer: str,
    chosen: dict[str, dict[str, Any] | None] | None = None,
    translation_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """The audit evidence; ``chosen`` overrides the displayed renderings (a held rebuild)."""
    if chosen is None:
        literal = comparisons.select_rendering(unit, comparisons.LITERAL_LAYER, translation_id)
        english = comparisons.select_rendering(unit, english_layer, translation_id)
    else:
        literal, english = chosen["literal"], chosen["english"]

    token_lines = []
    for token in unit.get("tokens", []):
        bits = [f"{token['token_id']}: {token['surface']}"]
        for key in ("transliteration", "lemma", "strong", "morph_readable", "display_gloss"):
            if token.get(key):
                bits.append(f"{key}={token[key]}")
        token_lines.append("  " + " | ".join(str(b) for b in bits))

    lines = [
        f"Unit: {unit['unit_id']}",
        f"MT reference: {unit['ref']}",
        "",
        "## Hebrew (Masoretic)",
        unit["source_hebrew"],
        "",
        "## Hebrew tokens (use these ids verbatim in word_notes)",
        "\n".join(token_lines) if token_lines else "  (none recorded)",
        "",
        "## Literal rendering under audit",
        f"  {literal['text']}" if literal else "  (none stored)",
        "",
        f"## English used ({english_layer}) under audit",
        f"  {english['text']}" if english else "  (none stored)",
    ]
    return "\n".join(lines), {"literal": literal, "english": english}


def build_verse_analysis_prompt(
    unit_id: str,
    english_layer: str = "lyric",
    chosen: dict[str, dict[str, Any] | None] | None = None,
    translation_id: str | None = None,
) -> str:
    unit = registry_service.load_unit(unit_id)
    evidence, _ = _evidence_block(unit, english_layer, chosen, translation_id)
    return "\n".join(
        [
            "# Translation audit -- one verse",
            "",
            "Judge the English below against the Hebrew. You are auditing work that",
            "already exists; you are not translating and must not propose new",
            "renderings. Say what the English preserves, where it interprets, and",
            "give the compact literal backbone you judged against.",
            "",
            "Comment only on words whose rendering is worth remarking on. An empty",
            "word_notes array is a valid answer.",
            "",
            "Declare any text with no counterpart in the Hebrew -- bracketed meter,",
            "instrumentation, vocal assignments, section labels -- in",
            "non_source_material. A cell mixing such apparatus with genuinely",
            "rendered text takes an ordinary accuracy_rating and declares the extra",
            "material; reserve no_source_basis for a cell that is apparatus alone.",
            "",
            "Claim only what the text supports.",
            "",
            evidence,
        ]
    )


def _compared_translations(psalm_id: str) -> list[str]:
    """The public-domain English of the psalm, each whole and in its own verse numbering.

    Not paired with the Masoretic verses: where a psalm has a heading, English numbering
    runs a verse or two behind, and a mispaired verse would mislead the comparison.
    """
    number = int(psalm_id.removeprefix("ps"))
    lines: list[str] = []
    for source in registry_service.PUBLIC_DOMAIN_WITNESS_SOURCES:
        texts = registry_service._load_public_domain_witness_map(source["source_id"])
        verses = [f"  {v} {text}" for (p, v), text in sorted(texts.items()) if p == number]
        if verses:
            lines += ["", f"### {source['versionTitle']}", *verses]
    return lines


def build_psalm_analysis_prompt(
    psalm_id: str, english_layer: str = "lyric", translation_id: str | None = None
) -> str:
    psalm = registry_service.load_psalm(psalm_id)
    verses = []
    imported = 0
    for unit in psalm["units"]:
        english = comparisons.select_rendering(unit, english_layer, translation_id)
        if english and (english.get("provenance") or {}).get("imported"):
            imported += 1
        verses.append(
            f"  {unit['ref']} [{unit['unit_id']}]: "
            f"{english['text'] if english else '(no English stored)'}"
        )
    provenance = (
        [
            f"{imported} of the {len(psalm['units'])} verses below were imported: pasted in",
            "from an existing translation, not written here. Say plainly whether the English",
            "reproduces or adapts a translation you can identify, and which.",
            "",
        ]
        if imported
        else []
    )
    return "\n".join(
        [
            "# Translation audit -- whole psalm",
            "",
            f"Psalm: {psalm_id} ({psalm.get('title', '')})",
            "",
            "Describe what this English setting does with the psalm as a whole.",
            "Tile the psalm into sections covering every verse in order, using",
            "Masoretic verse numbers, and record structural seams in the received",
            "text (such as Selah), noting whether a section ends at each one.",
            "",
            "Answer both guardrails every time: what the heading does and does not",
            "attribute, and what setting the psalm's own language implies.",
            "",
            "Then draw the epistemic boundary: what the text supports, each with its",
            "basis, and what it does not, each with why not. Do not treat a",
            "traditional ascription as a fact the text establishes.",
            "",
            "Last, name the existing translations this English resembles, closest first:",
            "the public-domain translations below (basis supplied), and any published",
            "translation, metrical psalter or hymn you recognise in it (basis recalled),",
            "quoted by a few words at most. Wording every translation shares is no",
            "resemblance; look for the choices that set a translation apart. Cite verses",
            "by the Masoretic numbers of the English under audit; the translations below",
            "keep their own numbering, a verse or two behind where the psalm has a heading.",
            "",
            *provenance,
            "## English setting under audit",
            "\n".join(verses),
            "",
            "## Public-domain translations for comparison",
            *_compared_translations(psalm_id),
        ]
    )


# -- Verse scope -----------------------------------------------------------


def analyze_verse(
    client: codex.CodexAppServerClient,
    session_id: str,
    unit_id: str,
    english_layer: str = "lyric",
    created_by: str = "codex-analysis",
    force: bool = False,
) -> dict[str, Any]:
    """Audit one verse and record the verdict as a proposed assessment."""
    translation_id = translation.session_translation(session_id)
    unit = registry_service.load_unit(unit_id)
    _, chosen = _evidence_block(unit, english_layer, translation_id=translation_id)
    fingerprint = verse_fingerprint(unit, [chosen["literal"], chosen["english"]])

    result: dict[str, Any] = {
        "unit_id": unit_id,
        "status": translation.RUN_COMPLETED,
        "run_id": None,
        "assessment": None,
        "skipped": False,
        "error": None,
    }

    if not force:
        current = _active_assessment(unit, translation_id)
        if current is not None and current.get("analyzed_text_hash") == fingerprint:
            # Nothing changed since the last audit; writing again would append a
            # superseded record and two audit entries for no new information.
            result["skipped"] = True
            result["assessment"] = current
            return result

    run = translation.run_contract_turn(
        client,
        session_id=session_id,
        prompt=build_verse_analysis_prompt(unit_id, english_layer, translation_id=translation_id),
        validator=VERSE_VALIDATOR,
        kind=translation.KIND_ANALYSIS,
        unit_id=unit_id,
        layer=english_layer,
        prompt_template_version=PROMPT_TEMPLATE_VERSION,
    )
    result["run_id"] = run["run_id"]
    if run["status"] != translation.RUN_COMPLETED:
        result["status"] = run["status"]
        result["error"] = run.get("error")
        return result

    payload = run["payload"]
    _assert_token_ids_exist(unit, payload.get("word_notes", []))

    existing = _active_assessment(unit, translation_id)
    if existing is not None:
        result["assessment"] = comparisons.revise_assessment(
            unit_id=unit_id,
            comparison_id_value=existing["comparison_id"],
            created_by=created_by,
            rationale="codex analysis pass",
            status=ANALYSIS_STATUS_PROPOSED,
            accuracy_rating=payload["accuracy_rating"],
            accuracy_note=payload["accuracy_note"],
            creative_liberties_note=payload["creative_liberties_note"],
        )
        _patch_evidence(unit_id, result["assessment"]["comparison_id"], payload, fingerprint)
        result["assessment"] = _reload_assessment(unit_id, result["assessment"]["comparison_id"])
        return result

    result["assessment"] = comparisons.create_assessment(
        unit_id=unit_id,
        literal_rendering_id=(chosen["literal"] or {}).get("rendering_id"),
        english_rendering_id=(chosen["english"] or {}).get("rendering_id"),
        accuracy_rating=payload["accuracy_rating"],
        accuracy_note=payload["accuracy_note"],
        creative_liberties_note=payload["creative_liberties_note"],
        created_by=created_by,
        created_via="codex",
        generator_provider=codex.PROVIDER_NAME,
        generation_run_id=run["run_id"],
        # Hard-coded, never read from the payload: the pass cannot mark its own
        # verdict reviewed.
        status=ANALYSIS_STATUS_PROPOSED,
        rationale="codex analysis pass",
        literal_backbone=payload["literal_backbone"],
        word_notes=payload["word_notes"],
        non_source_material=payload["non_source_material"],
        analyzed_text_hash=fingerprint,
        translation_id=translation_id,
    )
    return result


def _rebuild_renderings(
    unit: dict[str, Any], rebuild: dict[str, Any]
) -> dict[str, dict[str, Any] | None]:
    """The text a rebuild would show: its own renderings, the current ones elsewhere."""
    by_id = {r["rendering_id"]: r for r in unit.get("renderings", [])}
    english_layer = rebuild["english_layer"]
    held = rebuild["rendering_ids"]
    translation_id = rebuild.get("translation_id")
    return {
        "literal": by_id.get(held.get(comparisons.LITERAL_LAYER, ""))
        or comparisons.select_rendering(unit, comparisons.LITERAL_LAYER, translation_id),
        "english": by_id.get(held.get(english_layer, ""))
        or comparisons.select_rendering(unit, english_layer, translation_id),
    }


def analyze_rebuild(
    client: codex.CodexAppServerClient,
    session_id: str,
    unit_id: str,
    created_by: str = "codex-analysis",
) -> dict[str, Any]:
    """Audit a pending rebuild's text and hold the verdict on the rebuild.

    The auditor sees the rebuilt text exactly as it would appear, and nothing of
    the reviewer's notes: the prompt is the ordinary verse audit.
    """
    from app.services import verse_notes_service

    unit = registry_service.load_unit(unit_id)
    rebuild = verse_notes_service.pending_rebuild(unit, translation.session_translation(session_id))
    if rebuild is None:
        raise ValidationError(f"{unit_id} has no rebuild waiting for a decision")
    chosen = _rebuild_renderings(unit, rebuild)
    result: dict[str, Any] = {
        "unit_id": unit_id,
        "rebuild_id": rebuild["rebuild_id"],
        "status": translation.RUN_COMPLETED,
        "run_id": None,
        "analysis": None,
        "error": None,
    }
    run = translation.run_contract_turn(
        client,
        session_id=session_id,
        prompt=build_verse_analysis_prompt(unit_id, rebuild["english_layer"], chosen),
        validator=VERSE_VALIDATOR,
        kind=translation.KIND_ANALYSIS,
        unit_id=unit_id,
        layer=rebuild["english_layer"],
        prompt_template_version=PROMPT_TEMPLATE_VERSION,
    )
    result["run_id"] = run["run_id"]
    if run["status"] != translation.RUN_COMPLETED:
        result["status"] = run["status"]
        result["error"] = run.get("error")
        return result
    payload = run["payload"]
    _assert_token_ids_exist(unit, payload.get("word_notes", []))
    analysis = {
        **payload,
        "run_id": run["run_id"],
        "analyzed_text_hash": verse_fingerprint(unit, [chosen["literal"], chosen["english"]]),
        "created_at": run.get("completed_at"),
    }
    verse_notes_service.store_rebuild_analysis(unit_id, rebuild["rebuild_id"], analysis, created_by)
    result["analysis"] = analysis
    return result


def adopt_rebuild_analysis(
    unit_id: str, rebuild: dict[str, Any], created_by: str = "codex-analysis"
) -> dict[str, Any] | None:
    """Make an accepted rebuild's held audit the verse's assessment.

    Only when it audited exactly the text now shown; otherwise the verse keeps
    its old assessment, which the table then reports as stale.
    """
    analysis = rebuild["analysis"]
    translation_id = rebuild.get("translation_id")
    unit = registry_service.load_unit(unit_id)
    chosen = {
        "literal": comparisons.select_rendering(unit, comparisons.LITERAL_LAYER, translation_id),
        "english": comparisons.select_rendering(unit, rebuild["english_layer"], translation_id),
    }
    fingerprint = verse_fingerprint(unit, [chosen["literal"], chosen["english"]])
    if fingerprint != analysis["analyzed_text_hash"]:
        return None
    existing = _active_assessment(unit, translation_id)
    literal_id = (chosen["literal"] or {}).get("rendering_id")
    english_id = (chosen["english"] or {}).get("rendering_id")
    if existing is not None:
        successor = comparisons.revise_assessment(
            unit_id=unit_id,
            comparison_id_value=existing["comparison_id"],
            created_by=created_by,
            rationale=f"codex analysis of {rebuild['rebuild_id']}",
            status=ANALYSIS_STATUS_PROPOSED,
            accuracy_rating=analysis["accuracy_rating"],
            accuracy_note=analysis["accuracy_note"],
            creative_liberties_note=analysis["creative_liberties_note"],
            literal_rendering_id=literal_id,
            english_rendering_id=english_id,
        )
        _patch_evidence(unit_id, successor["comparison_id"], analysis, fingerprint)
        return _reload_assessment(unit_id, successor["comparison_id"])
    return comparisons.create_assessment(
        unit_id=unit_id,
        literal_rendering_id=literal_id,
        english_rendering_id=english_id,
        accuracy_rating=analysis["accuracy_rating"],
        accuracy_note=analysis["accuracy_note"],
        creative_liberties_note=analysis["creative_liberties_note"],
        created_by=created_by,
        created_via="codex",
        generator_provider=codex.PROVIDER_NAME,
        generation_run_id=analysis["run_id"],
        status=ANALYSIS_STATUS_PROPOSED,
        rationale=f"codex analysis of {rebuild['rebuild_id']}",
        literal_backbone=analysis["literal_backbone"],
        word_notes=analysis["word_notes"],
        non_source_material=analysis["non_source_material"],
        analyzed_text_hash=fingerprint,
        translation_id=translation_id,
    )


def _active_assessment(
    unit: dict[str, Any], translation_id: str | None = None
) -> dict[str, Any] | None:
    active = [
        item
        for item in unit.get("comparison_assessments", [])
        if item["status"] != ANALYSIS_STATUS_SUPERSEDED
        and translations.in_translation(item, translation_id)
    ]
    return active[-1] if active else None


def _reload_assessment(unit_id: str, comparison_id: str) -> dict[str, Any]:
    unit = registry_service.load_unit(unit_id)
    for item in unit.get("comparison_assessments", []):
        if item["comparison_id"] == comparison_id:
            return item
    raise NotFoundError(f"Comparison assessment not found: {comparison_id}")


def _patch_evidence(
    unit_id: str, comparison_id: str, payload: dict[str, Any], fingerprint: str
) -> None:
    """Attach this run's evidence to the successor a revision just created."""
    unit = registry_service.load_unit(unit_id)
    for item in unit.get("comparison_assessments", []):
        if item["comparison_id"] == comparison_id:
            item["literal_backbone"] = payload["literal_backbone"]
            item["word_notes"] = payload["word_notes"]
            item["non_source_material"] = payload["non_source_material"]
            item["analyzed_text_hash"] = fingerprint
            registry_service.save_unit(unit)
            return
    raise NotFoundError(f"Comparison assessment not found: {comparison_id}")


def _assert_token_ids_exist(unit: dict[str, Any], word_notes: list[dict[str, Any]]) -> None:
    known = {token["token_id"] for token in unit.get("tokens", [])}
    for note in word_notes:
        unknown = [tid for tid in note["token_ids"] if tid not in known]
        if unknown:
            raise ValidationError(
                f"word_notes reference tokens not in {unit['unit_id']}: {sorted(unknown)}"
            )


# -- Psalm scope -----------------------------------------------------------


def analyze_psalm_scope(
    client: codex.CodexAppServerClient,
    session_id: str,
    psalm_id: str,
    english_layer: str = "lyric",
    created_by: str = "codex-analysis",
    force: bool = False,
) -> dict[str, Any]:
    """Audit the psalm as a whole: sections, seams, guardrails, epistemics."""
    translation_id = translation.session_translation(session_id)
    psalm = registry_service.load_psalm(psalm_id)
    fingerprint = psalm_fingerprint(psalm, english_layer, translation_id)

    result: dict[str, Any] = {
        "psalm_id": psalm_id,
        "status": translation.RUN_COMPLETED,
        "run_id": None,
        "analysis": None,
        "skipped": False,
        "error": None,
    }

    current = active_analysis(psalm_id, translation_id)
    if (
        not force
        and current is not None
        and current.get("source_fingerprint") == fingerprint
        and current.get("prompt_template_version") == PSALM_PROMPT_TEMPLATE_VERSION
    ):
        result["skipped"] = True
        result["analysis"] = current
        return result

    run = translation.run_contract_turn(
        client,
        session_id=session_id,
        prompt=build_psalm_analysis_prompt(psalm_id, english_layer, translation_id),
        validator=PSALM_VALIDATOR,
        kind=translation.KIND_ANALYSIS,
        psalm_id=psalm_id,
        prompt_template_version=PSALM_PROMPT_TEMPLATE_VERSION,
    )
    result["run_id"] = run["run_id"]
    if run["status"] != translation.RUN_COMPLETED:
        result["status"] = run["status"]
        result["error"] = run.get("error")
        return result

    payload = run["payload"]
    _assert_sections_tile(psalm, payload["sections"])

    meta = registry_service.load_psalm_meta(psalm_id)
    before_meta = deepcopy(meta)
    analyses = meta.setdefault("analyses", [])
    for record in analyses:
        if translations.in_translation(record, translation_id):
            record["status"] = ANALYSIS_STATUS_SUPERSEDED

    record = {
        "psalm_analysis_id": build_psalm_analysis_id(
            psalm_id, [a["psalm_analysis_id"] for a in analyses]
        ),
        "psalm_id": psalm_id,
        "summary": payload["summary"],
        "sections": payload["sections"],
        "structural_seams": payload["structural_seams"],
        "guardrails": payload["guardrails"],
        "epistemics": payload["epistemics"],
        "non_source_material": payload["non_source_material"],
        "method": payload["method"],
        "citations": payload["citations"],
        "similar_translations": payload["similar_translations"],
        "source_fingerprint": fingerprint,
        "status": ANALYSIS_STATUS_PROPOSED,
        "created_by": created_by,
        "created_via": "codex",
        "generator_provider": codex.PROVIDER_NAME,
        "generation_run_id": run["run_id"],
        "prompt_template_version": PSALM_PROMPT_TEMPLATE_VERSION,
        "created_at": _now(),
        "revision_of": current["psalm_analysis_id"] if current else None,
        "audit_ids": [],
    }
    translations.tag(record, translation_id)
    analyses.append(record)
    registry_service.save_psalm_meta(psalm_id, meta)

    # audit_id is patterned to a unit and validate_content enforces that units
    # mirror their audit records, so a psalm-meta write has no natively lawful
    # audit home. Anchor the record on the psalm's first unit: every field
    # describes the meta payload that actually changed, and only the record's
    # file location is unit-shaped.
    anchor_unit_id = psalm["unit_ids"][0]
    anchor = registry_service.load_unit(anchor_unit_id)
    audit = audit_service.create_audit_record(
        anchor,
        before_hash=registry_service.file_hash(before_meta),
        after_hash=registry_service.file_hash(meta),
        summary="Record psalm analysis",
        rationale="codex analysis pass",
        created_by=created_by,
        entity_type="psalm_analysis",
        entity_id=record["psalm_analysis_id"],
        change_type="update" if current else "create",
    )
    registry_service.save_unit(anchor)

    record["audit_ids"] = [audit["audit_id"]]
    registry_service.save_psalm_meta(psalm_id, meta)
    result["analysis"] = record
    return result


def _assert_sections_tile(psalm: dict[str, Any], sections: list[dict[str, Any]]) -> None:
    """Sections must cover every verse once, in order, with no gap or overlap."""
    verses = sorted(int(unit_id.split(".")[1].lstrip("v")) for unit_id in psalm.get("unit_ids", []))
    if not verses:
        return
    ordered = sorted(sections, key=lambda s: s["first_verse"])
    expected = verses[0]
    for section in ordered:
        if section["first_verse"] != expected:
            raise ValidationError(
                f"sections do not tile {psalm['psalm_id']}: expected a section starting at "
                f"verse {expected}, got {section['first_verse']}"
            )
        if section["last_verse"] < section["first_verse"]:
            raise ValidationError(f"section '{section['title']}' ends before it starts")
        expected = section["last_verse"] + 1
    if expected != verses[-1] + 1:
        raise ValidationError(
            f"sections do not tile {psalm['psalm_id']}: coverage stops at verse {expected - 1} "
            f"but the psalm has {verses[-1]}"
        )
