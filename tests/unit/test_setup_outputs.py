from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.setup_rebuild_state import MISSING_OUTPUTS, cmd_check

pytestmark = pytest.mark.no_seeded_repo


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    for relative in (
        "content/project.json",
        "content/psalms/ps001/ps001.meta.json",
        "content/psalms/ps001/ps001.v001.a.json",
        "content/psalms/ps150/ps150.meta.json",
        "data/derived/indexes/workbench.sqlite3",
    ):
        output = tmp_path / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.touch()
    return tmp_path


def test_existing_outputs_are_reused_even_with_stale_rebuild_state(workspace: Path) -> None:
    state = workspace / ".run" / "rebuild-state.json"
    state.parent.mkdir()
    state.write_text('{"states":{"full":{"signature":"old"}}}', encoding="utf-8")

    assert cmd_check("full") == 0
    assert state.read_text(encoding="utf-8") == '{"states":{"full":{"signature":"old"}}}'


def test_active_catalog_file_is_required_when_published(workspace: Path) -> None:
    relative = "data/derived/indexes/catalogs/current.sqlite3"
    pointer = workspace / "data/derived/indexes/active_catalog.json"
    pointer.write_text(json.dumps({"path": relative}), encoding="utf-8")

    assert cmd_check("full") == MISSING_OUTPUTS

    catalog = workspace / relative
    catalog.parent.mkdir()
    catalog.touch()
    (pointer.parent / "workbench.sqlite3").unlink()
    assert cmd_check("full") == 0


def test_missing_corpus_or_fixture_output_requests_rebuild(workspace: Path) -> None:
    assert cmd_check("fixture") == MISSING_OUTPUTS
    vector = workspace / "data/derived/indexes/vector/visual_flow_index.json"
    vector.parent.mkdir()
    vector.touch()
    assert cmd_check("fixture") == 0

    (workspace / "content/psalms/ps150/ps150.meta.json").unlink()
    assert cmd_check("full") == MISSING_OUTPUTS
    assert cmd_check("fixture") == 0

    (workspace / "content/psalms/ps001/ps001.v001.a.json").unlink()
    assert cmd_check("fixture") == MISSING_OUTPUTS


def test_unreadable_catalog_pointer_is_a_check_failure(workspace: Path) -> None:
    pointer = workspace / "data/derived/indexes/active_catalog.json"
    pointer.write_text("{", encoding="utf-8")

    assert cmd_check("full") == 2
