from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.errors import NotFoundError, ReviewRequiredError
from app.services import registry_service, rendering_service, review_service, verse_notes_service

pytestmark = pytest.mark.no_seeded_repo
UNIT_ID = "ps001.v001.a"


@pytest.fixture
def pending_rebuild(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[str, str, str]:
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    registry_service.write_json(get_settings().project_file, {"source_manifests": []})
    registry_service.save_unit(
        {
            "unit_id": UNIT_ID,
            "ref": "Authored rebuild fixture",
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
    candidates = {
        layer: rendering_service.create_rendering(
            UNIT_ID, layer, "Blessed is the one", "proposed", "rebuild fixture", "test"
        )["rendering_id"]
        for layer in ("literal", "lyric")
    }
    rebuild = verse_notes_service.record_rebuild(
        UNIT_ID,
        "lyric",
        [],
        candidates,
        {},
        [],
        [],
        "test",
    )
    return rebuild["rebuild_id"], candidates["literal"], candidates["lyric"]


def test_promoted_pending_candidate_blocks_discard_before_any_write(
    pending_rebuild: tuple[str, str, str],
) -> None:
    rebuild_id, _, lyric_id = pending_rebuild
    for reviewer in ("first", "second"):
        review_service.add_review_decision(lyric_id, "approve", reviewer, "Hebrew reviewer")
    rendering_service.promote_rendering(lyric_id, "release", "release reviewer")
    path = registry_service.unit_path(UNIT_ID)
    before = path.read_bytes()

    with pytest.raises(ReviewRequiredError, match="canonical"):
        verse_notes_service.discard_rebuild(UNIT_ID, rebuild_id)

    assert path.read_bytes() == before


def test_missing_pending_candidate_blocks_discard_before_any_write(
    pending_rebuild: tuple[str, str, str],
) -> None:
    rebuild_id, _, lyric_id = pending_rebuild
    unit = registry_service.load_unit(UNIT_ID)
    unit["renderings"] = [item for item in unit["renderings"] if item["rendering_id"] != lyric_id]
    path = registry_service.unit_path(UNIT_ID)
    path.write_text(json.dumps(unit), encoding="utf-8")
    before = path.read_bytes()

    with pytest.raises(NotFoundError):
        verse_notes_service.discard_rebuild(UNIT_ID, rebuild_id)

    assert path.read_bytes() == before


def test_valid_pending_rebuild_still_discards_and_audits(
    pending_rebuild: tuple[str, str, str],
) -> None:
    rebuild_id, literal_id, lyric_id = pending_rebuild

    discarded = verse_notes_service.discard_rebuild(UNIT_ID, rebuild_id, created_by="editor")

    assert discarded["status"] == verse_notes_service.REBUILD_DISCARDED
    unit = registry_service.load_unit(UNIT_ID)
    assert {item["rendering_id"]: item["status"] for item in unit["renderings"]} == {
        literal_id: "rejected",
        lyric_id: "rejected",
    }
    discard_audits = [
        record for record in unit["audit_records"] if record["summary"] == "Discard rebuilt verse"
    ]
    assert len(discard_audits) == 1
    assert discard_audits[0]["created_by"] == "editor"
