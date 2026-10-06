"""Audited transfer of one saved translation bundle between projects."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.errors import ValidationError
from app.services import (
    arrangement_service,
    audit_service,
    collections_service,
    psalm_translations_service,
    registry_service,
    rendering_service,
)


def _set_guidance_audited(
    psalm_id: str,
    translation_id: str,
    guidance: str,
    *,
    created_by: str,
) -> str:
    """Set an added translation's guidance and append a translation audit."""
    meta = registry_service.load_psalm_meta(psalm_id)
    holder = next(
        (item for item in meta.get("translations", []) if item["translation_id"] == translation_id),
        None,
    )
    if holder is None:
        raise ValidationError(f"{translation_id} is not a translation of {psalm_id}")
    cleaned = guidance.strip()
    if str(holder.get("guidance", "")) == cleaned:
        return ""
    before = deepcopy(meta)
    if cleaned:
        holder["guidance"] = cleaned
    else:
        holder.pop("guidance", None)
    anchor = registry_service.load_unit(meta["unit_ids"][0])
    record = audit_service.create_audit_record(
        anchor,
        before_hash=registry_service.file_hash(before),
        after_hash=registry_service.file_hash(meta),
        summary=f"Set guidance for translation {translation_id}",
        rationale="Carry the transferred candidate's generation guidance with it",
        created_by=created_by,
        entity_type="translation",
        entity_id=translation_id,
        change_type="update",
    )
    registry_service.save_unit(anchor)
    holder.setdefault("audit_ids", []).append(record["audit_id"])
    registry_service.save_psalm_meta(psalm_id, meta)
    return record["audit_id"]


def move_translation_and_replace_bundle(
    psalm_id: str,
    source_translation_id: str,
    target_collection_id: str,
    *,
    replacement_title: str,
    rendering_ids: list[str],
    arrangement_ids: list[str],
    replacement_guidance: str,
    created_by: str = "reviewer",
) -> dict[str, Any]:
    """Move a mixed translation out, then retain a selected bundle in its old project.

    The existing translation keeps its identity and all unselected records. A new
    translation is created in the vacated collection, and the selected renderings and
    song settings are reassigned to it without changing their text, ids, or provenance.
    All written records receive audits. If any step fails, every affected psalm file is
    restored to its pre-transfer state.
    """
    translations = psalm_translations_service.list_translations(psalm_id)
    source = next(
        (item for item in translations if item["translation_id"] == source_translation_id),
        None,
    )
    if source is None:
        raise ValidationError(f"{source_translation_id} is not a translation of {psalm_id}")
    source_collection_id = source["collection_id"]
    if source_collection_id == target_collection_id:
        raise ValidationError("The destination must be a different project")
    collections_service.get_collection(target_collection_id)
    occupied = next(
        (item for item in translations if item["collection_id"] == target_collection_id),
        None,
    )
    if occupied is not None:
        raise ValidationError(f"The destination already has {psalm_id}")

    meta_snapshot = deepcopy(registry_service.load_psalm_meta(psalm_id))
    unit_snapshots = {
        unit_id: deepcopy(registry_service.load_unit(unit_id))
        for unit_id in meta_snapshot["unit_ids"]
    }
    selected_renderings: dict[str, dict[str, Any]] = {}
    for unit in unit_snapshots.values():
        for rendering in unit.get("renderings", []):
            if rendering["rendering_id"] in rendering_ids:
                selected_renderings[rendering["rendering_id"]] = rendering
    missing_renderings = sorted(set(rendering_ids) - selected_renderings.keys())
    if missing_renderings:
        raise ValidationError(f"Unknown rendering ids: {', '.join(missing_renderings)}")
    wrong_renderings = [
        rendering_id
        for rendering_id, rendering in selected_renderings.items()
        if rendering.get("translation_id") != source_translation_id
    ]
    if wrong_renderings:
        raise ValidationError(
            f"Renderings do not belong to {source_translation_id}: {', '.join(wrong_renderings)}"
        )

    arrangements = {item["arrangement_id"]: item for item in meta_snapshot.get("arrangements", [])}
    missing_arrangements = sorted(set(arrangement_ids) - arrangements.keys())
    if missing_arrangements:
        raise ValidationError(f"Unknown arrangement ids: {', '.join(missing_arrangements)}")
    wrong_arrangements = [
        arrangement_id
        for arrangement_id in arrangement_ids
        if arrangements[arrangement_id].get("translation_id") != source_translation_id
    ]
    if wrong_arrangements:
        raise ValidationError(
            f"Arrangements do not belong to {source_translation_id}: "
            + ", ".join(wrong_arrangements)
        )

    try:
        moved = psalm_translations_service.move_translation(
            psalm_id,
            source_translation_id,
            target_collection_id,
            created_by=created_by,
        )
        replacement = psalm_translations_service.create_translation(
            psalm_id,
            replacement_title,
            source_collection_id,
            created_by=created_by,
            created_via="import",
        )
        replacement_id = replacement["translation_id"]
        moved_renderings = [
            rendering_service.move_rendering_to_translation(
                rendering_id,
                replacement_id,
                created_by=created_by,
            )["rendering_id"]
            for rendering_id in rendering_ids
        ]
        moved_arrangements = [
            arrangement_service.move_arrangement_to_translation(
                psalm_id,
                arrangement_id,
                replacement_id,
                created_by=created_by,
            )["arrangement"]["arrangement_id"]
            for arrangement_id in arrangement_ids
        ]
        guidance_audit_id = _set_guidance_audited(
            psalm_id,
            replacement_id,
            replacement_guidance,
            created_by=created_by,
        )
    except Exception:
        registry_service.save_psalm_meta(psalm_id, meta_snapshot)
        for snapshot in unit_snapshots.values():
            registry_service.save_unit(snapshot)
        raise

    return {
        "psalm_id": psalm_id,
        "moved_translation": moved,
        "replacement_translation": psalm_translations_service.list_translations(psalm_id)[-1],
        "rendering_ids": moved_renderings,
        "arrangement_ids": moved_arrangements,
        "guidance_audit_id": guidance_audit_id,
    }
