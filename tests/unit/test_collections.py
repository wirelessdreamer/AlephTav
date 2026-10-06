"""Projects (collections): translations gathered across psalms, one per psalm at most.

Every psalm's main translation starts in the built-in default project. A translation is
made in a project and can be moved to another that has none of its psalm yet; the move
is audited on the psalm.
"""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.core.errors import NotFoundError, ValidationError
from app.services import collections_service, registry_service
from app.services import psalm_translations_service as translations

PSALM_ID = "ps001"
UNIT_ID = "ps001.v001.a"
DEFAULT = collections_service.DEFAULT_ID


@pytest.fixture(autouse=True)
def _restore():
    get_settings().collections_file.unlink(missing_ok=True)
    meta = registry_service.load_psalm_meta(PSALM_ID)
    unit = registry_service.load_unit(UNIT_ID)
    yield
    registry_service.save_psalm_meta(PSALM_ID, meta)
    registry_service.save_unit(unit)
    get_settings().collections_file.unlink(missing_ok=True)


def _project(title: str = "Bone and Ash") -> str:
    return collections_service.create_collection(title)["collection_id"]


def _members(collection_id: str) -> list[tuple[str, str | None]]:
    listed = {c["collection_id"]: c for c in translations.list_collections()}
    return [(m["psalm_id"], m["translation_id"]) for m in listed[collection_id]["members"]]


def _last_audit() -> dict:
    return registry_service.load_unit(UNIT_ID)["audit_records"][-1]


def test_the_default_project_holds_every_main_translation_and_a_new_one_starts_empty() -> None:
    project = _project()

    listed = translations.list_collections()

    assert [c["collection_id"] for c in listed] == [DEFAULT, project]
    assert listed[0]["built_in"] is True
    assert (PSALM_ID, None) in _members(DEFAULT)
    assert len(_members(DEFAULT)) == len(registry_service.list_psalm_ids())
    assert _members(project) == []


def test_a_translation_is_made_in_a_project_which_then_has_the_psalm() -> None:
    project = _project()

    created = translations.create_translation(PSALM_ID, "Bone and Ash", project)

    assert created["collection_id"] == project
    assert _members(project) == [(PSALM_ID, created["translation_id"])]
    assert translations.list_translations(PSALM_ID)[1]["collection_id"] == project
    assert "“Bone and Ash”" in _last_audit()["summary"]


def test_a_project_has_at_most_one_translation_of_a_psalm() -> None:
    project = _project()
    translations.create_translation(PSALM_ID, "First", project)

    with pytest.raises(ValidationError, match="already has"):
        translations.create_translation(PSALM_ID, "Second", project)
    # The default project already has the psalm's main translation.
    with pytest.raises(ValidationError, match="already has"):
        translations.create_translation(PSALM_ID, "Third", DEFAULT)


def test_a_translation_needs_a_project_that_exists() -> None:
    with pytest.raises(ValidationError):
        translations.create_translation(PSALM_ID, "Nowhere", "")
    with pytest.raises(NotFoundError):
        translations.create_translation(PSALM_ID, "Nowhere", "col.0042")


def test_a_translation_moves_to_another_project_with_an_audit_record() -> None:
    album = _project("Bone and Ash")
    hymnal = _project("Hymnal")
    added = translations.create_translation(PSALM_ID, "Sung", album)["translation_id"]

    moved = translations.move_translation(PSALM_ID, added, hymnal)

    assert moved["collection_id"] == hymnal
    assert _members(album) == []
    assert _members(hymnal) == [(PSALM_ID, added)]
    record = _last_audit()
    assert (record["entity_type"], record["entity_id"], record["change_type"]) == (
        "translation",
        added,
        "move",
    )
    assert record["summary"] == "Move translation “Sung” to “Hymnal”"
    assert record["rationale"] == "from “Bone and Ash”"
    stored = registry_service.load_psalm_meta(PSALM_ID)["translations"][-1]
    assert stored["audit_ids"][-1] == record["audit_id"]


def test_a_move_into_a_project_that_has_the_psalm_is_refused() -> None:
    album = _project()
    added = translations.create_translation(PSALM_ID, "Sung", album)["translation_id"]
    audits = len(registry_service.load_unit(UNIT_ID)["audit_records"])

    with pytest.raises(ValidationError, match="already has"):
        translations.move_translation(PSALM_ID, added, DEFAULT)

    assert _members(album) == [(PSALM_ID, added)]
    assert len(registry_service.load_unit(UNIT_ID)["audit_records"]) == audits


def test_the_main_translation_moves_out_of_the_default_project_and_back() -> None:
    album = _project()

    translations.move_translation(PSALM_ID, None, album)

    assert registry_service.load_psalm_meta(PSALM_ID)["main_collection_id"] == album
    assert _members(album) == [(PSALM_ID, None)]
    assert (PSALM_ID, None) not in _members(DEFAULT)
    assert _last_audit()["entity_id"] == PSALM_ID

    translations.move_translation(PSALM_ID, None, DEFAULT)

    assert "main_collection_id" not in registry_service.load_psalm_meta(PSALM_ID)
    assert (PSALM_ID, None) in _members(DEFAULT)


def test_moving_a_translation_to_the_project_it_is_in_changes_nothing() -> None:
    audits = len(registry_service.load_unit(UNIT_ID)["audit_records"])

    translations.move_translation(PSALM_ID, None, DEFAULT)

    assert len(registry_service.load_unit(UNIT_ID)["audit_records"]) == audits


def test_a_project_needs_a_name_of_its_own_and_can_be_renamed() -> None:
    project = _project("Bone and Ash")

    with pytest.raises(ValidationError):
        collections_service.create_collection("  ")
    with pytest.raises(ValidationError, match="already a project"):
        collections_service.create_collection("bone and ash")
    renamed = collections_service.rename_collection(project, "Ash and Bone")

    assert renamed["title"] == "Ash and Bone"
    assert collections_service.get_collection(project)["title"] == "Ash and Bone"
    with pytest.raises(ValidationError):
        collections_service.rename_collection(DEFAULT, "Mine")
    with pytest.raises(NotFoundError):
        collections_service.rename_collection("col.0042", "Mine")


def test_a_project_has_its_own_output_text_license() -> None:
    album = _project("Bone and Ash")
    hymnal = _project("Hymnal")

    licensed = collections_service.set_collection_license(album, "CC0 1.0")

    assert licensed["output_text_license"] == "CC0 1.0"
    assert "output_text_license" not in collections_service.get_collection(hymnal)
    with pytest.raises(ValidationError, match="Unknown project license"):
        collections_service.set_collection_license(album, "CC0")
    with pytest.raises(ValidationError, match="workbench text license"):
        collections_service.set_collection_license(DEFAULT, "CC0 1.0")
    with pytest.raises(NotFoundError):
        collections_service.set_collection_license("col.0042", "CC0 1.0")


def test_projects_and_moves_still_validate_and_a_missing_project_is_caught() -> None:
    from scripts.validate_content import validate_all_content

    album = _project()
    added = translations.create_translation(PSALM_ID, "Sung", album)["translation_id"]
    translations.move_translation(PSALM_ID, added, _project("Hymnal"))
    translations.move_translation(PSALM_ID, None, album)
    assert validate_all_content()["errors"] == []

    get_settings().collections_file.unlink()

    errors = validate_all_content()["errors"]
    assert any("unknown project col.0001" in error for error in errors)
    assert any("unknown project col.0002" in error for error in errors)
