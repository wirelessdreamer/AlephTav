"""Durable briefing and guidance snapshots, carried by the existing unit audit trail.

The rationale holds a JSON snapshot so history survives cache deletion without changing
the content contracts or treating translator notes as review approvals.
"""

from __future__ import annotations

import json
import uuid
from threading import RLock
from typing import Any

from app.core.errors import ValidationError
from app.services import audit_service, registry_service
from app.services import psalm_translations_service as translations

ENTITY = "translation_context"
_decision_lock = RLock()


def history(psalm_id: str, translation_id: str | None = None) -> list[dict[str, Any]]:
    meta = registry_service.load_psalm_meta(psalm_id)
    unit = registry_service.load_unit(meta["unit_ids"][0])
    entries = []
    for record in unit.get("audit_records", []):
        if record.get("entity_type") != ENTITY:
            continue
        snapshot = json.loads(record["rationale"])
        if snapshot.get("translation_id") == translation_id:
            entries.append(
                {
                    **snapshot,
                    **{
                        key: record[key]
                        for key in (
                            "audit_id",
                            "created_at",
                            "created_by",
                            "summary",
                        )
                    },
                }
            )
    return entries


def append(
    psalm_id: str,
    translation_id: str | None,
    *,
    kind: str,
    summary: str,
    snapshot: dict[str, Any],
    previous: Any = None,
    created_by: str = "reviewer",
) -> dict[str, Any]:
    translations.require(psalm_id, translation_id)
    meta = registry_service.load_psalm_meta(psalm_id)
    unit = registry_service.load_unit(meta["unit_ids"][0])
    payload = {"kind": kind, "translation_id": translation_id, **snapshot}
    record = audit_service.create_audit_record(
        unit,
        before_hash=registry_service.file_hash(previous),
        after_hash=registry_service.file_hash(payload),
        summary=summary,
        rationale=json.dumps(payload, ensure_ascii=False),
        created_by=created_by,
        entity_type=ENTITY,
        entity_id=f"ctx.{uuid.uuid4().hex[:12]}",
        change_type="create",
    )
    registry_service.save_unit(unit)
    return {
        **payload,
        **{
            key: record[key]
            for key in (
                "audit_id",
                "created_at",
                "created_by",
                "summary",
            )
        },
    }


def latest_briefing(psalm_id: str, translation_id: str | None = None) -> dict[str, Any] | None:
    return next(
        (
            item["briefing"]
            for item in reversed(history(psalm_id, translation_id))
            if item.get("briefing")
        ),
        None,
    )


def validate_annotations(
    psalm_id: str,
    translation_id: str | None,
    values: list[dict[str, Any]],
    *,
    allow_empty: bool = False,
) -> list[dict[str, Any]]:
    """Bind answers/notes to the exact archived question, never another translation."""
    from app.services.codex_briefing_service import cached_briefing

    if not isinstance(values, list) or any(not isinstance(value, dict) for value in values):
        raise ValidationError("Briefing annotations must be a list of question answers and notes")
    briefings = {
        item["briefing"]["run_id"]: item["briefing"]
        for item in history(psalm_id, translation_id)
        if item.get("briefing")
    }
    cached = cached_briefing(psalm_id, translation_id)
    if cached:
        briefings.setdefault(cached["run_id"], cached)
    result = []
    for value in values:
        briefing = briefings.get(value.get("briefing_run_id"))
        index = value.get("question_index")
        if not briefing or type(index) is not int or not 0 <= index < len(briefing["questions"]):
            raise ValidationError("Briefing question does not belong to this translation")
        answer, notes = value.get("answer", ""), value.get("notes", "")
        if not isinstance(answer, str) or not isinstance(notes, str):
            raise ValidationError("Briefing answers and notes must be text")
        if not allow_empty and not answer.strip() and not notes.strip():
            continue
        result.append(
            {
                "briefing_run_id": briefing["run_id"],
                "question_index": index,
                "question": briefing["questions"][index],
                "answer": answer.strip(),
                "notes": notes.strip(),
            }
        )
    return result


def current_annotations(
    entries: list[dict[str, Any]], *, include_empty: bool = False
) -> list[dict[str, Any]]:
    """Latest answer/notes per archived question; an empty update leaves it open."""
    current = {}
    # Guidance events retain the choices applied at that step, not later edits.
    direct = {}
    for event in entries:
        for note in event.get("annotations", []):
            current[(note["briefing_run_id"], note["question_index"])] = note
            if event["kind"] == "briefing_decision":
                key = (note["briefing_run_id"], note["question_index"])
                direct.pop(key, None)
                direct[key] = note
    for key, note in direct.items():
        current.pop(key, None)
        current[key] = note
    return [note for note in current.values() if include_empty or note["answer"] or note["notes"]]


def save_decision(
    psalm_id: str,
    translation_id: str | None,
    annotation: dict[str, Any],
    *,
    created_by: str = "reviewer",
) -> dict[str, Any]:
    """Record an answer immediately, independently of applying it to guidance."""
    with _decision_lock:
        note = validate_annotations(psalm_id, translation_id, [annotation], allow_empty=True)[0]
        entries = history(psalm_id, translation_id)
        previous = next(
            (
                item
                for item in current_annotations(entries)
                if (item["briefing_run_id"], item["question_index"])
                == (note["briefing_run_id"], note["question_index"])
            ),
            None,
        )
        if note != previous and (previous or note["answer"] or note["notes"]):
            append(
                psalm_id,
                translation_id,
                kind="briefing_decision",
                summary=f"Record briefing decision: {note['question']['topic']}",
                snapshot={
                    "annotations": [note],
                    "guidance": translations.get_guidance(psalm_id, translation_id),
                },
                previous=previous,
                created_by=created_by,
            )
        return note


def capture(psalm_id: str, translation_id: str | None) -> dict[str, Any]:
    from app.services.codex_briefing_service import cached_briefing

    entries = history(psalm_id, translation_id)
    return {
        "guidance": translations.get_guidance(psalm_id, translation_id),
        "briefing": cached_briefing(psalm_id, translation_id),
        "history_ids": [item["audit_id"] for item in entries],
        "annotations": current_annotations(entries),
    }


def briefing_instructions(psalm_id: str, translation_id: str | None = None) -> str:
    """Only recorded answers/notes direct generation; inferred suggestions never do."""
    latest = {}
    for note in current_annotations(history(psalm_id, translation_id), include_empty=True):
        question = note["question"]
        latest[(question["topic"].casefold(), tuple(question["verses"]))] = note
    notes = [note for note in latest.values() if note["answer"] or note["notes"]]
    if not notes:
        return ""
    lines = [
        "## Saved briefing decisions (apply automatically)",
        "Apply the explicit saved answers to the questions they settle; they take precedence "
        "over conflicting general guidance or generic style defaults. Use the general guidance "
        "for other choices. Preserve source meaning and alignment; disclose any "
        "decision the source or required layer cannot support instead of silently ignoring it.",
        "An unanswered question's note supplies context, not a selected answer.",
    ]
    for note in notes:
        question = note["question"]
        verses = ", ".join(str(verse) for verse in question["verses"]) or "whole psalm"
        lines.append(f"- {question['topic']} ({verses}): {question['question']}")
        if note["answer"]:
            lines.append(f"  Decision: {note['answer']}")
        if note["notes"]:
            lines.append(f"  Translator note: {note['notes']}")
    return "\n".join(lines)


def preserve_cached_briefings() -> list[str]:
    """One-time, idempotent preservation of briefings made before durable history existed."""
    from app.services.codex_briefing_service import _read_briefings

    recorded = []
    for briefing in _read_briefings().values():
        psalm_id, translation_id = briefing["psalm_id"], briefing.get("translation_id")
        if any(
            item.get("briefing", {}).get("run_id") == briefing["run_id"]
            for item in history(psalm_id, translation_id)
            if item.get("briefing")
        ):
            continue
        entry = append(
            psalm_id,
            translation_id,
            kind="briefing",
            summary="Preserve earlier translator's briefing",
            snapshot={"briefing": briefing, "guidance": briefing["guidance"]},
            created_by="briefing-history-migration",
        )
        recorded.append(entry["audit_id"])
    return recorded
