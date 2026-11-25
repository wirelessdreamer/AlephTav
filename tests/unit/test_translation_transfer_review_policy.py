from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.errors import ReviewRequiredError
from app.services import (
    collections_service,
    psalm_translations_service,
    registry_service,
    rendering_service,
    review_service,
    translation_transfer_service,
)

pytestmark = pytest.mark.no_seeded_repo
PSALM_ID = "ps001"
UNIT_ID = "ps001.v001.a"


@pytest.fixture
def bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str, str, str]:
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    registry_service.write_json(get_settings().project_file, {"source_manifests": []})
    registry_service.save_unit(
        {
            "unit_id": UNIT_ID,
            "ref": "Authored transfer fixture",
            "tokens": [],
            "renderings": [],
            "alignments": [],
            "canonical_rendering_ids": [],
            "alternate_rendering_ids": [],
            "review_decisions": [],
            "audit_records": [],
            "audit_ids": [],
        }
    )
    registry_service.save_psalm_meta(
        PSALM_ID, {"psalm_id": PSALM_ID, "title": "Psalm 1", "unit_ids": [UNIT_ID]}
    )
    source = collections_service.create_collection("Source")
    target = collections_service.create_collection("Archive")
    translation = psalm_translations_service.create_translation(
        PSALM_ID, "Original", source["collection_id"]
    )
    candidates = [
        rendering_service.create_rendering(
            UNIT_ID,
            "lyric",
            text,
            "proposed",
            "fixture",
            "test",
            translation_id=translation["translation_id"],
        )["rendering_id"]
        for text in ("First draft", "Blessed is the one")
    ]
    return translation["translation_id"], target["collection_id"], *candidates


def _transfer(translation_id: str, target_id: str, rendering_ids: list[str]) -> dict:
    return translation_transfer_service.move_translation_and_replace_bundle(
        PSALM_ID,
        translation_id,
        target_id,
        replacement_title="Replacement",
        rendering_ids=rendering_ids,
        arrangement_ids=[],
        replacement_guidance="Retain source imagery",
        created_by="editor",
    )


def test_canonical_selected_bundle_is_refused_before_any_file_write(
    bundle: tuple[str, str, str, str],
) -> None:
    translation_id, target_id, first_id, second_id = bundle
    for reviewer in ("first", "second"):
        review_service.add_review_decision(second_id, "approve", reviewer, "Hebrew reviewer")
    rendering_service.promote_rendering(second_id, "release", "release reviewer")
    content_dir = get_settings().content_dir
    # Rollback through parsed snapshots must not silently reformat refused requests.
    for path in content_dir.rglob("*.json"):
        path.write_text(json.dumps(registry_service.read_json(path)), encoding="utf-8")
    before = {path: path.read_bytes() for path in content_dir.rglob("*.json")}

    with pytest.raises(ReviewRequiredError, match="canonical"):
        _transfer(translation_id, target_id, [first_id, second_id])

    after = {path: path.read_bytes() for path in content_dir.rglob("*.json")}
    assert after == before


def test_proposed_selected_bundle_still_moves_without_changing_unselected_content(
    bundle: tuple[str, str, str, str],
) -> None:
    translation_id, target_id, first_id, second_id = bundle

    result = _transfer(translation_id, target_id, [second_id])

    replacement_id = result["replacement_translation"]["translation_id"]
    unit = registry_service.load_unit(UNIT_ID)
    renderings = {item["rendering_id"]: item for item in unit["renderings"]}
    assert renderings[first_id]["translation_id"] == translation_id
    assert renderings[second_id]["translation_id"] == replacement_id
    assert renderings[second_id]["status"] == "proposed"
    assert renderings[second_id]["text"] == "Blessed is the one"
    assert result["moved_translation"]["collection_id"] == target_id
    assert any(
        record["entity_id"] == second_id and record["change_type"] == "move"
        for record in unit["audit_records"]
    )
