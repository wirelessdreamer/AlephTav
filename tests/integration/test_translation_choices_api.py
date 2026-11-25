from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from app.api.main import app
from app.core.config import get_settings

pytestmark = pytest.mark.no_seeded_repo
PSALM = "ps001"
OPENING_UNIT = "ps001.v001.a"
CLOSING_UNIT = "ps001.v006.a"
OPENING = "rnd.ps001.v001.a.lyric.alt.0001"
OTHER_RENDERING = "rnd.ps001.v001.a.lyric.alt.0002"
ARRANGEMENT = "arr.ps001.0001"
OTHER_ARRANGEMENT = "arr.ps001.0002"
OTHER_TRANSLATION = "tr.ps001.0001"
URL = f"/psalms/{PSALM}/translation-choices"
STAMP = "2026-11-05T12:00:00Z"
REPO = Path(__file__).resolve().parents[2]


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _rendering(identity: str, unit_id: str, text: str, **extra: Any) -> dict[str, Any]:
    return {
        "rendering_id": identity,
        "unit_id": unit_id,
        "layer": "lyric",
        "status": "proposed",
        "text": text,
        "target_spans": [],
        "alignment_ids": [],
        "style_tags": ["lyric"],
        "metrics": {"fixture_metric": 7},
        "rationale": "Authored fixture rationale",
        "provenance": {"source_ids": ["fixture"], "generator": "fixture-author"},
        "review_signoff": {"approval_count": 0, "publication_ready": False},
        "drift_flags": [
            {
                "code": "fixture_concern",
                "severity": "high",
                "confidence": 0.9,
                "message": "Existing concern must not be waived by an intention note",
            }
        ],
        **extra,
    }


def _unit(identity: str, renderings: list[dict[str, Any]]) -> dict[str, Any]:
    psalm_id = identity.split(".")[0]
    return {
        "unit_id": identity,
        "psalm_id": psalm_id,
        "ref": "Authored fixture reference",
        "segmentation_type": "verse",
        "source_hebrew": "Authored source fixture",
        "source_transliteration": "fixture",
        "tokens": [],
        "token_ids": [],
        "concept_ids": [],
        "status": "draft",
        "current_layer_state": {"locked_layers": [], "latest_layer": "lyric"},
        "renderings": renderings,
        "canonical_rendering_ids": [],
        "alternate_rendering_ids": [item["rendering_id"] for item in renderings],
        "alignments": [],
        "audit_records": [],
        "audit_ids": [],
        "review_decisions": [],
        "issue_links": [],
        "pr_links": [],
        "comparison_assessments": [],
        "witnesses": [
            {
                "source_id": source,
                "versionTitle": "Authored fixture witness",
                "language": "en",
                "ref": "Fixture",
                "source_url": "",
                "text": "Fixture",
            }
            for source in ("kjv", "asv", "web")
        ],
    }


def _arrangement(identity: str, **extra: Any) -> dict[str, Any]:
    return {
        "arrangement_id": identity,
        "psalm_id": PSALM,
        "title": "Authored fixture setting",
        "layer": "lyric",
        "status": "draft",
        "guidance": "Fixture guidance",
        "sections": [
            {
                "section_id": "sec.0001",
                "kind": "verse",
                "label": "Opening",
                "repeat_of": None,
                "lines": [
                    {
                        "line_id": "ln.0001",
                        "text": "An authored opening image stays compact",
                        "anchors": [],
                        "liberty": "added",
                        "rationale": "Fixture addition",
                        "approvals": [],
                    }
                ],
            },
            {
                "section_id": "sec.0002",
                "kind": "outro",
                "label": "Closing",
                "repeat_of": None,
                "lines": [
                    {
                        "line_id": "ln.0002",
                        "text": "An authored closing image turns toward light",
                        "anchors": [],
                        "liberty": "added",
                        "rationale": "Fixture addition",
                        "approvals": [],
                    },
                    {
                        "line_id": "ln.0003",
                        "text": "An authored final refrain holds the tension",
                        "anchors": [],
                        "liberty": "added",
                        "rationale": "Fixture addition",
                        "approvals": [],
                    },
                ],
            },
        ],
        "omissions": [],
        "created_by": "fixture-author",
        "created_via": "human",
        "generation_run_id": None,
        "prompt_template_version": None,
        "created_at": STAMP,
        "updated_at": STAMP,
        "audit_ids": [],
        **extra,
    }


def _make_workspace(root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    assert root.resolve() != REPO.resolve()
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(root))
    get_settings()
    _write(
        root / "content/project.json",
        {
            "project_id": "proj.fixture",
            "source_manifests": [],
            "review_policy": {
                "canonical_required_approvals": 2,
                "alternate_required_approvals": 1,
                "release_required_role": "release reviewer",
                "reviewer_roles": ["lyric reviewer", "release reviewer"],
            },
        },
    )
    _write(
        root / "content/psalms/ps001/ps001.meta.json",
        {
            "psalm_id": PSALM,
            "title": "Authored fixture Psalm",
            "unit_ids": [OPENING_UNIT, CLOSING_UNIT],
            "analyses": [],
            "arrangements": [
                _arrangement(ARRANGEMENT),
                _arrangement(OTHER_ARRANGEMENT, translation_id=OTHER_TRANSLATION),
            ],
            "translations": [
                {
                    "translation_id": OTHER_TRANSLATION,
                    "psalm_id": PSALM,
                    "title": "Other authored translation",
                    "collection_id": "col.0001",
                    "created_by": "fixture-author",
                    "created_via": "human",
                    "created_at": STAMP,
                    "audit_ids": [],
                }
            ],
        },
    )
    _write(
        root / "content/psalms/ps001/ps001.v001.a.json",
        _unit(
            OPENING_UNIT,
            [
                _rendering(
                    OPENING, OPENING_UNIT, "An authored opening rendering keeps the compact image"
                ),
                _rendering(
                    OTHER_RENDERING,
                    OPENING_UNIT,
                    "Another translation uses another opening",
                    translation_id=OTHER_TRANSLATION,
                ),
            ],
        ),
    )
    _write(
        root / "content/psalms/ps001/ps001.v006.a.json",
        _unit(
            CLOSING_UNIT,
            [
                _rendering(
                    "rnd.ps001.v006.a.lyric.alt.0001",
                    CLOSING_UNIT,
                    "An authored closing rendering preserves the contrast",
                ),
            ],
        ),
    )
    _write(
        root / "content/psalms/ps002/ps002.meta.json",
        {
            "psalm_id": "ps002",
            "title": "Foreign authored Psalm",
            "unit_ids": ["ps002.v001.a"],
        },
    )
    _write(
        root / "content/psalms/ps002/ps002.v001.a.json",
        _unit(
            "ps002.v001.a",
            [
                _rendering(
                    "rnd.ps002.v001.a.lyric.alt.0001", "ps002.v001.a", "Foreign opening fixture"
                ),
            ],
        ),
    )
    return root


@pytest.fixture
def choice_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return _make_workspace(tmp_path, monkeypatch)


@pytest.fixture
def choice_client() -> TestClient:
    return TestClient(app)


def _bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _list(client: TestClient, **params: Any) -> dict[str, Any]:
    response = client.get(URL, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _target(listing: dict[str, Any], identity: str) -> dict[str, Any]:
    return next(item for item in listing["targets"] if item["id"] == identity)


def _ref(target: dict[str, Any]) -> dict[str, Any]:
    result = {
        "kind": target["kind"],
        "id": target["id"],
        "expected_revision": target["revision"]["value"],
    }
    if "arrangement_id" in target:
        result["arrangement_id"] = target["arrangement_id"]
    return result


def _payload(targets: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "targets": targets,
        "decision": "Retain this intentional wording",
        "rationale": "Keep the compact image and the intended closing contrast",
        "context_status": "not_established",
        "context_note": "Original supporting context was not recorded",
        "created_by": "fixture-translator",
        **extra,
    }


def _assert_one_history_append(root: Path, before: dict[str, bytes], entry: dict[str, Any]) -> None:
    after = _bytes(root)
    assert after.keys() == before.keys()
    changed = [path for path in before if before[path] != after[path]]
    assert len(changed) == 1
    previous, current = (json.loads(data) for data in (before[changed[0]], after[changed[0]]))
    old_records, new_records = previous.pop("audit_records"), current.pop("audit_records")
    old_ids, new_ids = previous.pop("audit_ids"), current.pop("audit_ids")
    assert current == previous  # Text, statuses, reviews, drift and assessments are unchanged.
    assert new_records[:-1] == old_records
    assert new_ids[:-1] == old_ids
    assert len(new_records) == len(old_records) + 1
    audit = new_records[-1]
    assert audit["audit_id"] == new_ids[-1] == entry["audit_id"]
    assert audit["created_by"] == entry["created_by"] == "fixture-translator"
    schema = json.loads((REPO / "schemas/audit_record.schema.json").read_text("utf-8"))
    Draft202012Validator(schema).validate(audit)


def test_rendering_choice_is_audited_without_approving_or_changing_content(
    choice_client: TestClient, choice_workspace: Path
) -> None:
    listing = _list(choice_client, unit_id=OPENING_UNIT)
    target = _target(listing, OPENING)
    assert OTHER_RENDERING not in {item["id"] for item in listing["targets"]}
    before = _bytes(choice_workspace)

    response = choice_client.post(URL, json=_payload([_ref(target)]))

    assert response.status_code == 200, response.text
    entry = response.json()
    assert entry["kind"] == "intentional_choice"
    assert entry["choice"]["version"] == 1
    assert entry["choice"]["targets"][0]["text"] == target["text"]
    assert entry["choice"]["context_status"] == "not_established"
    assert entry["target_state"] == "current"
    assert entry["counts_for_publication"] is False
    _assert_one_history_append(choice_workspace, before, entry)


def test_two_closing_lines_share_one_choice_and_translator_context_remains_a_claim(
    choice_client: TestClient, choice_workspace: Path
) -> None:
    listing = _list(choice_client, arrangement_id=ARRANGEMENT)
    targets = [_target(listing, identity) for identity in ("ln.0002", "ln.0003")]
    before = _bytes(choice_workspace)
    note = "Translator-provided contrast; historical source context remains unverified"

    response = choice_client.post(
        URL,
        json=_payload(
            [_ref(target) for target in targets],
            context_status="provided_by_translator",
            context_note=note,
        ),
    )

    assert response.status_code == 200, response.text
    entry = response.json()
    assert [item["text"] for item in entry["choice"]["targets"]] == [t["text"] for t in targets]
    assert entry["choice"]["context_note"] == note
    assert entry["choice"]["context_status"] == "provided_by_translator"
    assert entry["counts_for_publication"] is False
    _assert_one_history_append(choice_workspace, before, entry)


def test_correcting_a_choice_appends_history_instead_of_rewriting_it(
    choice_client: TestClient, choice_workspace: Path
) -> None:
    ref = _ref(_target(_list(choice_client, unit_id=OPENING_UNIT), OPENING))
    first_response = choice_client.post(URL, json=_payload([ref]))
    assert first_response.status_code == 200, first_response.text
    first = first_response.json()
    before = _bytes(choice_workspace)

    corrected_response = choice_client.post(
        URL,
        json=_payload(
            [ref],
            rationale="Correct the explanation while preserving the earlier record",
            supersedes_audit_id=first["audit_id"],
        ),
    )

    assert corrected_response.status_code == 200, corrected_response.text
    corrected = corrected_response.json()
    _assert_one_history_append(choice_workspace, before, corrected)
    choices = {
        item["audit_id"]: item for item in _list(choice_client, unit_id=OPENING_UNIT)["choices"]
    }
    assert choices[first["audit_id"]]["choice"] == first["choice"]
    assert choices[first["audit_id"]]["superseded_by_audit_id"] == corrected["audit_id"]
    assert corrected["choice"]["supersedes_audit_id"] == first["audit_id"]
    assert all(item["counts_for_publication"] is False for item in choices.values())


@pytest.mark.parametrize("state", ["changed", "missing"])
def test_history_keeps_original_snapshot_after_target_changes_or_disappears(
    choice_client: TestClient, choice_workspace: Path, state: str
) -> None:
    target = _target(_list(choice_client, unit_id=OPENING_UNIT), OPENING)
    response = choice_client.post(URL, json=_payload([_ref(target)]))
    assert response.status_code == 200, response.text
    entry = response.json()
    path = choice_workspace / f"content/psalms/ps001/{OPENING_UNIT}.json"
    unit = json.loads(path.read_text("utf-8"))
    if state == "changed":
        next(item for item in unit["renderings"] if item["rendering_id"] == OPENING)["text"] = (
            "A later authored opening revision"
        )
    else:
        unit["renderings"] = [r for r in unit["renderings"] if r["rendering_id"] != OPENING]
        unit["alternate_rendering_ids"].remove(OPENING)
    _write(path, unit)  # Simulate a later fixture revision without altering the historical audit.

    stored = next(
        item
        for item in _list(choice_client, unit_id=OPENING_UNIT)["choices"]
        if item["audit_id"] == entry["audit_id"]
    )

    assert stored["target_state"] == state
    assert stored["choice"]["targets"][0]["text"] == target["text"]
    assert stored["counts_for_publication"] is False


def test_other_arrangement_line_edits_make_a_stored_closing_context_stale(
    choice_client: TestClient, choice_workspace: Path
) -> None:
    target = _target(_list(choice_client, arrangement_id=ARRANGEMENT), "ln.0002")
    path = choice_workspace / "content/psalms/ps001/ps001.meta.json"
    meta = json.loads(path.read_text("utf-8"))
    meta["arrangements"][0]["sections"][0]["lines"][0]["text"] = (
        "A changed opening performance image"
    )
    _write(path, meta)
    before = _bytes(choice_workspace)

    response = choice_client.post(URL, json=_payload([_ref(target)]))

    assert response.status_code in {400, 409}, response.text
    assert _bytes(choice_workspace) == before


@pytest.mark.parametrize(
    "extra",
    [
        {"audit_id": "aud.ps001.v001.a.9999"},
        {"created_at": "1970-01-01T00:00:00Z"},
        {"before_hash": "0" * 64, "after_hash": "1" * 64},
        {"review_signoff": {"approval_count": 99, "publication_ready": True}},
        {"counts_for_publication": True},
        {"reviewer": "forged", "reviewer_role": "release reviewer"},
    ],
)
def test_api_refuses_forged_audit_and_review_fields_without_writes(
    choice_client: TestClient, choice_workspace: Path, extra: dict[str, Any]
) -> None:
    ref = _ref(_target(_list(choice_client, unit_id=OPENING_UNIT), OPENING))
    before = _bytes(choice_workspace)

    response = choice_client.post(URL, json=_payload([ref], **extra))

    assert response.status_code in {400, 422}, response.text
    assert _bytes(choice_workspace) == before


@pytest.mark.parametrize(
    "case",
    [
        "stale",
        "foreign_psalm",
        "foreign_translation",
        "invalid_kind",
        "unknown_id",
        "missing_parent",
        "duplicate",
        "forged_snapshot",
    ],
)
def test_invalid_target_references_are_refused_without_changing_history(
    choice_client: TestClient, choice_workspace: Path, case: str
) -> None:
    ref = _ref(_target(_list(choice_client, unit_id=OPENING_UNIT), OPENING))
    payload = _payload([ref])
    if case == "stale":
        ref["expected_revision"] = "0" * 64
    elif case == "foreign_psalm":
        ref["id"] = "rnd.ps002.v001.a.lyric.alt.0001"
    elif case == "foreign_translation":
        payload["translation_id"] = OTHER_TRANSLATION
    elif case == "invalid_kind":
        ref["kind"] = "unit"
    elif case == "unknown_id":
        ref["id"] = "rnd.ps001.v001.a.lyric.alt.9999"
    elif case == "missing_parent":
        ref.update(kind="arrangement_line", id="ln.0002")
    elif case == "duplicate":
        payload["targets"] = [ref, deepcopy(ref)]
    else:
        ref["text"] = "A caller-forged source snapshot"
    before = _bytes(choice_workspace)

    response = choice_client.post(URL, json=payload)

    assert response.status_code in {400, 404, 409, 422}, response.text
    assert _bytes(choice_workspace) == before


@pytest.mark.parametrize("field", ["decision", "rationale", "created_by"])
def test_blank_required_choice_information_is_not_recorded(
    choice_client: TestClient, choice_workspace: Path, field: str
) -> None:
    ref = _ref(_target(_list(choice_client, unit_id=OPENING_UNIT), OPENING))
    before = _bytes(choice_workspace)

    response = choice_client.post(URL, json=_payload([ref], **{field: " \n"}))

    assert response.status_code in {400, 422}, response.text
    assert _bytes(choice_workspace) == before


@pytest.mark.parametrize("status", ["not_established", "provided_by_translator"])
@pytest.mark.parametrize("note", ["", " \n"])
def test_blank_context_note_is_refused_for_both_context_statuses(
    choice_client: TestClient, choice_workspace: Path, status: str, note: str
) -> None:
    ref = _ref(_target(_list(choice_client, unit_id=OPENING_UNIT), OPENING))
    before = _bytes(choice_workspace)

    response = choice_client.post(
        URL, json=_payload([ref], context_status=status, context_note=note)
    )

    assert response.status_code in {400, 422}, response.text
    assert _bytes(choice_workspace) == before


def test_corrected_choice_cannot_supersede_another_translation_history(
    choice_client: TestClient, choice_workspace: Path
) -> None:
    main_ref = _ref(_target(_list(choice_client, unit_id=OPENING_UNIT), OPENING))
    first_response = choice_client.post(URL, json=_payload([main_ref]))
    assert first_response.status_code == 200, first_response.text
    other = _list(choice_client, translation_id=OTHER_TRANSLATION, unit_id=OPENING_UNIT)
    other_ref = _ref(_target(other, OTHER_RENDERING))
    before = _bytes(choice_workspace)

    response = choice_client.post(
        URL,
        json=_payload(
            [other_ref],
            translation_id=OTHER_TRANSLATION,
            supersedes_audit_id=first_response.json()["audit_id"],
        ),
    )

    assert response.status_code in {400, 404}, response.text
    assert _bytes(choice_workspace) == before
