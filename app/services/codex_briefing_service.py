"""A briefing for the translator, before a psalm is translated.

One Codex turn gives the background a translator needs (authorship, setting, form,
themes, reception) and the decisions the psalm leaves to them, each with the answers
translations and traditions give. It never writes a rendering and never decides: the
translator's answers go into the guidance, which the translation passes follow.

Retained in the translation's audit history; a derived cache also serves the latest view.
"""

from __future__ import annotations

import json
from typing import Any

from jsonschema import Draft202012Validator

from app.core.config import get_settings
from app.services import codex_analysis_service as analysis
from app.services import codex_app_server_service as codex
from app.services import codex_translation_service as translation
from app.services import comparison_assessment_service as comparisons
from app.services import registry_service, translation_context_service

BRIEFING_TEMPLATE_VERSION = "codex-briefing-v1"
KIND_BRIEFING = "briefing"

BACKGROUND_PARTS = ("authorship", "setting", "form", "themes", "reception")

BRIEFING_VALIDATOR = Draft202012Validator(
    {
        "type": "object",
        "required": ["background", "questions"],
        "additionalProperties": False,
        "properties": {
            "background": {
                "type": "object",
                "required": list(BACKGROUND_PARTS),
                "additionalProperties": False,
                "properties": {
                    part: {"type": "string", "minLength": 1} for part in BACKGROUND_PARTS
                },
            },
            "questions": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["topic", "verses", "question", "background", "options"],
                    "additionalProperties": False,
                    "properties": {
                        "topic": {"type": "string", "minLength": 1},
                        "verses": {"type": "array", "items": {"type": "integer", "minimum": 1}},
                        "question": {"type": "string", "minLength": 1},
                        "background": {"type": "string", "minLength": 1},
                        "options": {
                            "type": "array",
                            "minItems": 2,
                            "items": {
                                "type": "object",
                                "required": ["choice", "held_by", "effect"],
                                "additionalProperties": False,
                                "properties": {
                                    "choice": {"type": "string", "minLength": 1},
                                    "held_by": {"type": "string", "minLength": 1},
                                    "effect": {"type": "string", "minLength": 1},
                                },
                            },
                        },
                    },
                },
            },
        },
    }
)


def _briefings_path():
    return get_settings().caches_dir / "psalm_briefings.json"


def _key(psalm_id: str, translation_id: str | None) -> str:
    return f"{psalm_id}|{translation_id}" if translation_id else psalm_id


def _read_briefings() -> dict[str, Any]:
    path = _briefings_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:  # pragma: no cover - a cache, rebuildable
        return {}


def cached_briefing(psalm_id: str, translation_id: str | None = None) -> dict[str, Any] | None:
    return translation_context_service.latest_briefing(
        psalm_id, translation_id
    ) or _read_briefings().get(_key(psalm_id, translation_id))


def build_briefing_prompt(psalm_id: str, translation_id: str | None = None) -> str:
    psalm = registry_service.load_psalm(psalm_id)
    guidance = translation.generation_guidance(psalm_id, translation_id)
    sections = [
        "# Translator's briefing -- before translating",
        "",
        f"Psalm: {psalm_id} ({psalm.get('title', '')})",
        "",
        "A translator is about to put this psalm into English. Prepare them: first the",
        "background they need, then the decisions the psalm leaves to them. You are not",
        "translating, and you must not decide for them.",
        "Offer Hebrew and Greek choices where the evidence supports them; distinguish readings "
        "and identify the source edition. Saved choices guide the translation automatically.",
        "",
        "## Background",
        "Write each part plainly, for a translator rather than a specialist. Keep apart what",
        "the text itself says, what tradition holds, and what scholars reconstruct, and name",
        "who holds a view where it matters. Do not treat a traditional ascription as a fact",
        "the text establishes.",
        "  authorship: what the heading attributes and the ways its wording can be read, then",
        "    the traditional and critical views of who wrote the psalm;",
        "  setting: the occasions, dates and settings proposed for it, each with its basis;",
        "  form: its genre, and the literary features a translation can keep or lose (an",
        "    acrostic, refrains, parallelism, wordplay, Selah and other markers);",
        "  themes: its themes, and how the psalm moves from its first verse to its last;",
        "  reception: how Jewish and Christian tradition have read and used it, including any",
        "    quotation in the New Testament, as far as that bears on translating it.",
        "",
        "## Questions for the translator",
        "List the decisions this psalm puts to a translator: where the Hebrew can be read more",
        "than one way, where translations or traditions divide, and where English forces a",
        "choice the Hebrew does not. Include the psalm-wide questions that arise here, such as",
        "how to render each divine name the psalm uses (YHWH, Elohim, Adonai, Elyon and the",
        "like), whether to keep the heading and Selah, gendered language, and the time of the",
        "verbs; and the verse-level ones, such as a disputed word, a phrase open to two",
        "readings, or a place where the Masoretic text and the Septuagint differ. Ask every",
        "question that shapes the translation, greatest first, and none that does not. For each:",
        "  topic: a short name;",
        "  verses: the Masoretic verse numbers it touches, empty when it runs through the psalm;",
        "  question: the decision, put to the translator as a question;",
        "  background: why it is open -- the Hebrew in question, the evidence, and where the",
        "    readings divide;",
        "  options: at least two answers a translator could reasonably give, each with",
        "    choice: the answer, worded as an instruction the translator could adopt;",
        "    held_by: who takes it -- translations, traditions or scholars, by name;",
        "    effect: what it gains and what it loses in English.",
        "Present the options even-handedly: do not rank them or say which is right. The",
        "decision is the translator's.",
        "",
        "## The translator's guidance so far",
        "Do not ask what it already decides. Do ask what it leaves open, including the choices",
        "its own aims force (a set meter, say, makes the translator choose what to compress).",
        guidance or "(none yet)",
        "",
        "## The psalm (Masoretic numbering: where the psalm has a heading, it is verse 1)",
    ]
    for unit in psalm["units"]:
        sections.append(f"  {unit['ref']} [{unit['unit_id']}]")
        sections.append(f"    Hebrew: {unit['source_hebrew']}")
        literal = comparisons.select_rendering(unit, comparisons.LITERAL_LAYER, translation_id)
        if literal is not None:
            sections.append(f"    Literal: {literal['text']}")
    sections += [
        "",
        "## Public-domain translations, to show where translations divide",
        "They keep their own verse numbering, a verse or two behind where the psalm has a",
        "heading; cite verses by the Masoretic numbers above.",
        *analysis._compared_translations(psalm_id),
    ]
    from app.services import greek_generation_service

    sections.append(
        greek_generation_service.prompt_evidence(
            psalm_id, [unit["unit_id"] for unit in psalm["units"]]
        )
    )
    return "\n".join(sections)


def prepare_briefing(
    client: codex.CodexAppServerClient, session_id: str, psalm_id: str
) -> dict[str, Any]:
    """Brief the translator on the psalm; a failed turn keeps the briefing there was."""
    translation_id = translation.session_translation(session_id)
    run = translation.run_contract_turn(
        client,
        session_id=session_id,
        prompt=build_briefing_prompt(psalm_id, translation_id),
        validator=BRIEFING_VALIDATOR,
        kind=KIND_BRIEFING,
        psalm_id=psalm_id,
        prompt_template_version=BRIEFING_TEMPLATE_VERSION,
    )
    result: dict[str, Any] = {
        "psalm_id": psalm_id,
        "translation_id": translation_id,
        "status": run["status"],
        "error": run.get("error"),
        "run_id": run["run_id"],
        "briefing": cached_briefing(psalm_id, translation_id),
    }
    if run["status"] != translation.RUN_COMPLETED:
        return result
    briefing = {
        "psalm_id": psalm_id,
        "translation_id": translation_id,
        **run["payload"],
        "run_id": run["run_id"],
        "created_at": run.get("completed_at"),
        # The guidance it was made under: questions that guidance settled were left out.
        "guidance": (run.get("translation_context") or {}).get(
            "guidance",
            translation.get_guidance(psalm_id, translation_id),
        ),
        "template_version": BRIEFING_TEMPLATE_VERSION,
    }
    translation_context_service.append(
        psalm_id,
        translation_id,
        kind="briefing",
        summary="Prepare translator's briefing",
        snapshot={"briefing": briefing, "guidance": briefing["guidance"]},
        previous=result["briefing"],
        created_by="codex",
    )
    cache = _read_briefings()
    cache[_key(psalm_id, translation_id)] = briefing
    path = _briefings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    result["briefing"] = briefing
    return result
