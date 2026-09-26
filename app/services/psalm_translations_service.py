"""The translations of a psalm: separate English settings of the same Hebrew.

A psalm starts with one translation, its main one, whose records carry no
``translation_id``. Each translation added later has an id (``tr.ps023.0001``) that its
English renderings, verse assessments, psalm analyses, song settings, verse notes and
rebuilds carry, and keeps its own guidance. The Hebrew and the literal and gloss layers
are shared: they are the common reference every translation is made and judged against.

Translations live on the psalm meta file. Their audit records are anchored on the
psalm's first unit, as the analyses' and arrangements' are, because an audit id is
patterned to a unit.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.core.errors import NotFoundError, ValidationError
from app.services import audit_service, registry_service

#: Layers every translation of a psalm shares.
SHARED_LAYERS = ("gloss", "literal")
MAIN_TITLE = "Main translation"
CREATED_VIA = ("human", "import")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def list_translations(psalm_id: str) -> list[dict[str, Any]]:
    """The main translation first, then the added ones, oldest first."""
    meta = registry_service.load_psalm_meta(psalm_id)
    main = {"translation_id": None, "psalm_id": psalm_id, "title": MAIN_TITLE}
    return [main, *meta.get("translations", [])]


def require(psalm_id: str, translation_id: str | None) -> None:
    """Refuse an id that is not a translation of this psalm. None is the main one."""
    if translation_id is None:
        return
    meta = registry_service.load_psalm_meta(psalm_id)
    if not any(t["translation_id"] == translation_id for t in meta.get("translations", [])):
        raise NotFoundError(f"{translation_id} is not a translation of {psalm_id}")


def in_translation(record: dict[str, Any], translation_id: str | None) -> bool:
    """Whether a record belongs to the translation. Records without an id are the main one's."""
    return record.get("translation_id") == translation_id


def shows_in(rendering: dict[str, Any], translation_id: str | None) -> bool:
    """Whether a rendering is part of what the translation shows: its own, or a shared layer."""
    return rendering.get("layer") in SHARED_LAYERS or in_translation(rendering, translation_id)


def tag(record: dict[str, Any], translation_id: str | None) -> dict[str, Any]:
    """Mark a record as the translation's; the main translation's records stay unmarked."""
    if translation_id is not None:
        record["translation_id"] = translation_id
    return record


def create_translation(
    psalm_id: str,
    title: str,
    created_by: str = "reviewer",
    created_via: str = "human",
) -> dict[str, Any]:
    cleaned = title.strip()
    if not cleaned:
        raise ValidationError("A translation needs a name")
    if created_via not in CREATED_VIA:
        raise ValidationError(f"Unknown created_via: {created_via}")
    meta = registry_service.load_psalm_meta(psalm_id)
    before = deepcopy(meta)
    translations = meta.setdefault("translations", [])
    numbers = [int(t["translation_id"].rsplit(".", 1)[1]) for t in translations]
    translation: dict[str, Any] = {
        "translation_id": f"tr.{psalm_id}.{max(numbers, default=0) + 1:04d}",
        "psalm_id": psalm_id,
        "title": cleaned,
        "created_by": created_by,
        "created_via": created_via,
        "created_at": _now(),
        "audit_ids": [],
    }
    translations.append(translation)

    anchor = registry_service.load_unit(meta["unit_ids"][0])
    record = audit_service.create_audit_record(
        anchor,
        before_hash=registry_service.file_hash(before),
        after_hash=registry_service.file_hash(meta),
        summary=f"Create translation “{cleaned}”",
        rationale=f"{created_via} translation",
        created_by=created_by,
        entity_type="translation",
        entity_id=translation["translation_id"],
        change_type="create",
    )
    registry_service.save_unit(anchor)
    translation["audit_ids"] = [record["audit_id"]]
    registry_service.save_psalm_meta(psalm_id, meta)
    return translation


def get_guidance(psalm_id: str, translation_id: str | None) -> str:
    """An added translation's own guidance; the main translation's is the psalm's."""
    meta = registry_service.load_psalm_meta(psalm_id)
    if translation_id is None:
        return str(meta.get("translation_guidance", ""))
    for translation in meta.get("translations", []):
        if translation["translation_id"] == translation_id:
            return str(translation.get("guidance", ""))
    raise NotFoundError(f"{translation_id} is not a translation of {psalm_id}")


def set_guidance(psalm_id: str, translation_id: str | None, guidance: str) -> None:
    meta = registry_service.load_psalm_meta(psalm_id)
    holder: dict[str, Any] | None
    if translation_id is None:
        holder = meta
        key = "translation_guidance"
    else:
        holder = next(
            (t for t in meta.get("translations", []) if t["translation_id"] == translation_id),
            None,
        )
        if holder is None:
            raise NotFoundError(f"{translation_id} is not a translation of {psalm_id}")
        key = "guidance"
    if guidance:
        holder[key] = guidance
    else:
        holder.pop(key, None)
    registry_service.save_psalm_meta(psalm_id, meta)
