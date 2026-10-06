from __future__ import annotations

from copy import deepcopy

import pytest

from app.core.config import get_settings
from app.services import (
    arrangement_service,
    collections_service,
    psalm_translations_service,
    registry_service,
    rendering_service,
    translation_transfer_service,
)

PSALM_ID = "ps001"
UNIT_ID = "ps001.v001.a"


@pytest.fixture(autouse=True)
def _restore() -> None:
    settings = get_settings()
    settings.collections_file.unlink(missing_ok=True)
    meta = deepcopy(registry_service.load_psalm_meta(PSALM_ID))
    units = {unit_id: deepcopy(registry_service.load_unit(unit_id)) for unit_id in meta["unit_ids"]}
    yield
    registry_service.save_psalm_meta(PSALM_ID, meta)
    for unit in units.values():
        registry_service.save_unit(unit)
    settings.collections_file.unlink(missing_ok=True)


def _basis() -> dict:
    return {
        "basis_type": "hebrew_to_english",
        "source_ids": ["uxlc"],
        "source_language": "he",
        "source_version": "test",
        "basis_note": "test",
    }


def test_move_translation_and_replace_selected_bundle() -> None:
    source_collection = collections_service.create_collection("Source project")
    target_collection = collections_service.create_collection("Archive project")
    old_translation = psalm_translations_service.create_translation(
        PSALM_ID,
        "Old song",
        source_collection["collection_id"],
    )
    old_id = old_translation["translation_id"]
    psalm_translations_service.set_guidance(PSALM_ID, old_id, "Old guidance")
    old_rendering = rendering_service.create_rendering(
        UNIT_ID,
        "lyric",
        "Old lyric",
        "proposed",
        "old",
        "test",
        translation_basis=_basis(),
        translation_id=old_id,
    )
    fresh_rendering = rendering_service.create_rendering(
        UNIT_ID,
        "lyric",
        "Fresh lyric",
        "proposed",
        "fresh",
        "test",
        translation_basis=_basis(),
        translation_id=old_id,
    )
    arrangement = arrangement_service.create_arrangement(
        PSALM_ID,
        title="Fresh setting",
        status="proposed",
        translation_id=old_id,
    )["arrangement"]

    result = translation_transfer_service.move_translation_and_replace_bundle(
        PSALM_ID,
        old_id,
        target_collection["collection_id"],
        replacement_title="Fresh song",
        rendering_ids=[fresh_rendering["rendering_id"]],
        arrangement_ids=[arrangement["arrangement_id"]],
        replacement_guidance="Fresh guidance",
        created_by="test",
    )

    replacement_id = result["replacement_translation"]["translation_id"]
    listed = psalm_translations_service.list_translations(PSALM_ID)
    assert (
        next(item for item in listed if item["translation_id"] == old_id)["collection_id"]
        == target_collection["collection_id"]
    )
    assert (
        next(item for item in listed if item["translation_id"] == replacement_id)["collection_id"]
        == source_collection["collection_id"]
    )
    unit = registry_service.load_unit(UNIT_ID)
    renderings = {item["rendering_id"]: item for item in unit["renderings"]}
    assert renderings[old_rendering["rendering_id"]]["translation_id"] == old_id
    assert renderings[fresh_rendering["rendering_id"]]["translation_id"] == replacement_id
    moved_setting = arrangement_service.get_arrangement(PSALM_ID, arrangement["arrangement_id"])
    assert moved_setting["translation_id"] == replacement_id
    assert psalm_translations_service.get_guidance(PSALM_ID, old_id) == "Old guidance"
    assert psalm_translations_service.get_guidance(PSALM_ID, replacement_id) == "Fresh guidance"
    rendering_audits = [
        item
        for item in unit["audit_records"]
        if item["entity_id"] == fresh_rendering["rendering_id"]
    ]
    assert rendering_audits[-1]["change_type"] == "move"

    from scripts.validate_content import validate_all_content

    assert validate_all_content()["errors"] == []
