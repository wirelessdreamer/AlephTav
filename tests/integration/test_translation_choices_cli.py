from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from app.cli import app
from tests.integration.test_translation_choices_api import (
    ARRANGEMENT,
    OPENING,
    OPENING_UNIT,
    OTHER_TRANSLATION,
    PSALM,
    REPO,
    _assert_one_history_append,
    _bytes,
    _make_workspace,
    _target,
    _write,
)

pytestmark = pytest.mark.no_seeded_repo
runner = CliRunner()


@pytest.fixture
def choice_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return _make_workspace(tmp_path, monkeypatch)


def _list(*options: str) -> dict[str, Any]:
    result = runner.invoke(app, ["list-translation-choices", PSALM, *options])
    assert result.exit_code == 0, result.exception or result.output
    return json.loads(result.output)


def _record(targets: list[dict[str, Any]], *options: str) -> list[str]:
    args = ["record-translation-choice", PSALM, "--target-kind", targets[0]["kind"]]
    for target in targets:
        args += ["--target-id", target["id"], "--expected-revision", target["revision"]["value"]]
    if targets[0].get("arrangement_id"):
        args += ["--arrangement-id", targets[0]["arrangement_id"]]
    return args + [
        "--decision",
        "Retain this intentional wording",
        "--rationale",
        "Keep the compact image and the intended closing contrast",
        "--context-note",
        "Original supporting context was not recorded",
        "--created-by",
        "fixture-translator",
        *options,
    ]


def test_cli_records_a_listable_unapproved_opening_choice(choice_workspace: Path) -> None:
    target = _target(_list("--unit-id", OPENING_UNIT), OPENING)
    before = _bytes(choice_workspace)

    result = runner.invoke(app, _record([target]))

    assert result.exit_code == 0, result.exception or result.output
    entry = json.loads(result.output)
    assert entry["kind"] == "intentional_choice"
    assert entry["choice"]["context_status"] == "not_established"
    assert entry["choice"]["targets"][0]["text"] == target["text"]
    assert entry["counts_for_publication"] is False
    _assert_one_history_append(choice_workspace, before, entry)
    assert entry["audit_id"] in {
        row["audit_id"] for row in _list("--unit-id", OPENING_UNIT)["choices"]
    }


def test_cli_groups_closing_lines_and_appends_an_explicit_correction(
    choice_workspace: Path,
) -> None:
    listing = _list("--arrangement-id", ARRANGEMENT)
    targets = [_target(listing, identity) for identity in ("ln.0002", "ln.0003")]
    initial = runner.invoke(
        app,
        _record(
            targets,
            "--context-status",
            "provided_by_translator",
            "--context-note",
            "An authored translator claim",
        ),
    )
    assert initial.exit_code == 0, initial.exception or initial.output
    first = json.loads(initial.output)
    assert len(first["choice"]["targets"]) == 2
    before = _bytes(choice_workspace)

    result = runner.invoke(app, _record(targets, "--supersedes-audit-id", first["audit_id"]))

    assert result.exit_code == 0, result.exception or result.output
    correction = json.loads(result.output)
    assert correction["choice"]["supersedes_audit_id"] == first["audit_id"]
    _assert_one_history_append(choice_workspace, before, correction)
    history = {row["audit_id"]: row for row in _list("--arrangement-id", ARRANGEMENT)["choices"]}
    assert history[first["audit_id"]]["choice"] == first["choice"]
    assert history[first["audit_id"]]["superseded_by_audit_id"] == correction["audit_id"]


@pytest.mark.parametrize(
    "case",
    [
        "stale",
        "foreign_translation",
        "unpaired_revisions",
        "missing_creator",
        "forged_authority_option",
    ],
)
def test_cli_refuses_bad_or_unauthorized_arguments_without_writes(
    choice_workspace: Path, case: str
) -> None:
    target = _target(_list("--unit-id", OPENING_UNIT), OPENING)
    args = _record([target])
    if case == "stale":
        args[args.index("--expected-revision") + 1] = "0" * 64
    elif case == "foreign_translation":
        args += ["--translation-id", OTHER_TRANSLATION]
    elif case == "unpaired_revisions":
        args += ["--target-id", "rnd.ps001.v006.a.lyric.alt.0001"]
    elif case == "missing_creator":
        index = args.index("--created-by")
        del args[index : index + 2]
    else:
        args += ["--counts-for-publication", "true"]
    before = _bytes(choice_workspace)

    result = runner.invoke(app, args)

    assert result.exit_code != 0
    assert _bytes(choice_workspace) == before


def test_choice_survives_cache_deletion_and_a_fresh_cli_process(choice_workspace: Path) -> None:
    target = _target(_list("--unit-id", OPENING_UNIT), OPENING)
    recorded = runner.invoke(app, _record([target]))
    assert recorded.exit_code == 0, recorded.exception or recorded.output
    audit_id = json.loads(recorded.output)["audit_id"]
    derived = choice_workspace / "data/derived"
    _write(derived / "caches/authored-cache.json", {"fixture": True})
    assert derived.resolve().is_relative_to(choice_workspace.resolve())
    assert derived.resolve() != choice_workspace.resolve()
    shutil.rmtree(derived)
    env = dict(os.environ, ALEPHTAV_ROOT_DIR=str(choice_workspace), PYTHONDONTWRITEBYTECODE="1")

    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "app.cli",
            "list-translation-choices",
            PSALM,
            "--unit-id",
            OPENING_UNIT,
        ],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    entry = next(
        item for item in json.loads(result.stdout)["choices"] if item["audit_id"] == audit_id
    )
    assert entry["target_state"] == "current"
    assert entry["counts_for_publication"] is False
