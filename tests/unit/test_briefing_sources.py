from __future__ import annotations

import hashlib
import json

import pytest

from app.core.errors import LicensePolicyError, NotFoundError
from app.services import briefing_source_service as sources
from app.services.greek_study_service import StudyView

pytestmark = pytest.mark.no_seeded_repo


def seal_map(root, mapping, view):
    """Seal authored map bytes as a fresh mocked snapshot dependency for each scenario."""
    raw = json.dumps(mapping).encode("utf-8")
    (root / "map.json").write_bytes(raw)
    manifest = {
        "kind": "versification",
        "files": [
            {"path": "map.json", "sha256": hashlib.sha256(raw).hexdigest(), "size_bytes": len(raw)}
        ],
    }
    manifest_bytes = json.dumps(manifest).encode("utf-8")
    (root / "package.json").write_bytes(manifest_bytes)
    view.descriptor["packages"] = [
        {"path": "package.json", "sha256": hashlib.sha256(manifest_bytes).hexdigest()}
    ]


@pytest.fixture
def source_view(tmp_path, monkeypatch):
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    unit_id = "lxx.authored.r0001.ps024.v001.a"
    token_id = "lxx.authored.r0001.ps024.v001.t001"
    unit = {
        "unit_id": unit_id,
        "ref": "Greek Psalm 24:1",
        "source_greek": "λόγος",
        "tokens": [{"token_id": token_id, "surface": "λόγος", "position": 1}],
    }
    record = {
        "status": "reviewed",
        "relation": "equivalent",
        "sources": [{"unit_id": "ps025.v001.a", "baseline": "MT", "reference": "Psalm 25:1"}],
        "targets": [{"unit_id": unit_id, "baseline": "LXX", "reference": "Psalm 24:1"}],
    }
    mapping = {"edition_id": "authored", "text_revision_id": "r0001", "records": [record]}
    view = StudyView(
        {
            "study_snapshot_id": "study.test",
            "edition_id": "authored",
            "text_revision_id": "r0001",
            "packages": [{"path": "package.json"}],
        },
        {
            "units": [unit],
            "tokens": [],
            "entries": [{"entry_id": "word", "gloss": "word"}],
            "analyses": [{"token_id": token_id, "entry_ids": ["word"]}],
        },
        "policy.test",
    )
    seal_map(tmp_path, mapping, view)
    monkeypatch.setattr(sources.greek_study_service, "load_view", lambda: view)
    monkeypatch.setattr(sources, "availability", lambda _: True)
    monkeypatch.setattr(sources.source_capability_service, "policy_revision", lambda: "policy.test")
    monkeypatch.setattr(
        sources.registry_service,
        "load_psalm",
        lambda _: {
            "units": [
                {"unit_id": "ps025.v001.a", "ref": "Psalm 25:1"},
                {"unit_id": "ps025.v002.a", "ref": "Psalm 25:2"},
            ]
        },
    )
    return tmp_path, mapping, view


def test_uses_reviewed_edition_mapping_and_dictionary_glosses(source_view):
    evidence = sources.greek_evidence("ps025")
    assert evidence["study_snapshot_id"] == "study.test"
    unit = evidence["by_mt_unit"]["ps025.v001.a"]["units"][0]
    assert unit["ref"] == "Greek Psalm 24:1"
    assert unit["literal_text"] == "word"
    assert "ps025.v002.a" not in evidence["by_mt_unit"]


def test_unreviewed_or_other_revision_maps_never_supply_a_counterpart(source_view):
    root, mapping, view = source_view
    mapping["records"][0]["status"] = "proposed"
    seal_map(root, mapping, view)
    assert sources.greek_evidence("ps025")["by_mt_unit"] == {}
    mapping["records"][0]["status"] = "reviewed"
    mapping["text_revision_id"] = "r0002"
    seal_map(root, mapping, view)
    assert sources.greek_evidence("ps025")["by_mt_unit"] == {}


def test_unavailable_source_is_explicit_and_does_not_fabricate_text(monkeypatch):
    def missing():
        raise NotFoundError("No active study snapshot")

    monkeypatch.setattr(sources.greek_study_service, "load_view", missing)
    result = sources.greek_evidence("ps025")
    assert result["available"] is False and result["by_mt_unit"] == {}
    assert "No active study snapshot" in result["message"]


def test_source_revoked_before_load_returns_no_text_or_glosses(monkeypatch):
    def blocked():
        raise LicensePolicyError("Authored revoked dictionary: secret-gloss")

    monkeypatch.setattr(sources.greek_study_service, "load_view", blocked)
    result = sources.greek_evidence("ps025")
    assert result["available"] is False and result["state"] == "blocked"
    assert result["by_mt_unit"] == {}
    assert "secret-gloss" not in json.dumps(result)


def test_policy_revoked_during_evidence_projection_discards_all_text(source_view, monkeypatch):
    monkeypatch.setattr(
        sources.source_capability_service, "policy_revision", lambda: "policy.revoked"
    )
    result = sources.greek_evidence("ps025")
    assert result["available"] is False and result["by_mt_unit"] == {}
    assert "λόγος" not in json.dumps(result, ensure_ascii=False)
    assert "word" not in json.dumps(result)


def test_modified_map_or_manifest_cannot_supply_unverified_evidence(source_view):
    root, mapping, view = source_view
    mapping["records"][0]["targets"][0]["reference"] = "Tampered source"
    (root / "map.json").write_text(json.dumps(mapping), encoding="utf-8")
    assert sources.greek_evidence("ps025")["available"] is False
    seal_map(root, mapping, view)
    (root / "package.json").write_text('{"kind":"versification","files":[]}', encoding="utf-8")
    assert sources.greek_evidence("ps025")["available"] is False


def test_missing_wrong_revision_endpoint_is_unavailable_not_an_absence_claim(source_view):
    root, mapping, view = source_view
    mapping["records"][0]["targets"][0]["unit_id"] = "lxx.authored.r0002.ps024.v001.a"
    seal_map(root, mapping, view)
    result = sources.greek_evidence("ps025")
    assert result["available"] is False and result["by_mt_unit"] == {}


def test_invalid_partial_boundary_is_unavailable(source_view):
    root, mapping, view = source_view
    mapping["records"][0]["targets"][0]["text_span"] = {"start": 0, "end": 99}
    seal_map(root, mapping, view)
    result = sources.greek_evidence("ps025")
    assert result["available"] is False and result["by_mt_unit"] == {}


def test_release_disabled_during_projection_discards_complete_evidence(source_view, monkeypatch):
    states = iter([True, False])
    monkeypatch.setattr(sources, "availability", lambda _: next(states))
    result = sources.greek_evidence("ps025")
    assert result["available"] is False and result["by_mt_unit"] == {}
    assert "awaiting source release approval" in result["message"]


def test_titles_splits_merges_and_explicit_absence_keep_their_real_references(
    source_view, monkeypatch
):
    from copy import deepcopy

    root, mapping, view = source_view
    base = mapping["records"][0]
    # Deliberately nonnumeric map: MT25 title + v1 share Greek24:1;
    # MT25:2 spans Greek24:1 and Greek26:3, with a subverse boundary.
    title = deepcopy(base)
    title["relation"] = "title"
    title["sources"] = [
        {"unit_id": "ps025.v000.a", "baseline": "MT", "reference": "Psalm 25:title"}
    ]
    split = deepcopy(base)
    split["relation"] = "partial"
    split["sources"] = [{"unit_id": "ps025.v002.a", "baseline": "MT", "reference": "Psalm 25:2"}]
    second_greek = {
        "unit_id": "lxx.authored.r0001.ps026.v003.a",
        "ref": "Greek Psalm 26:3",
        "source_greek": "ῥῆμα",
        "tokens": [
            {"token_id": "lxx.authored.r0001.ps026.v003.t001", "surface": "ῥῆμα", "position": 1}
        ],
    }
    view.payload["units"].append(second_greek)
    split["targets"] = [
        {"unit_id": second_greek["unit_id"], "baseline": "LXX", "reference": "Psalm 26:3"},
        {**base["targets"][0], "text_span": {"start": 0, "end": 2}},
    ]
    absent = deepcopy(base)
    absent["relation"] = "edition_absent"
    absent["sources"] = [{"unit_id": "ps025.v003.a", "baseline": "MT", "reference": "Psalm 25:3"}]
    absent["targets"] = []
    mapping["records"] = [base, title, split, absent]
    seal_map(root, mapping, view)
    monkeypatch.setattr(
        sources.registry_service,
        "load_psalm",
        lambda _: {
            "units": [
                {"unit_id": "ps025.v000.a", "ref": "Psalm 25:title"},
                {"unit_id": "ps025.v001.a", "ref": "Psalm 25:1"},
                {"unit_id": "ps025.v002.a", "ref": "Psalm 25:2"},
                {"unit_id": "ps025.v003.a", "ref": "Psalm 25:3"},
                {"unit_id": "ps025.v004.a", "ref": "Psalm 25:4"},
            ]
        },
    )
    result = sources.greek_evidence("ps025")
    assert result["available"] is True
    by_mt = result["by_mt_unit"]
    assert by_mt["ps025.v000.a"]["relations"] == ["title"]
    assert by_mt["ps025.v000.a"]["units"][0]["ref"] == "Greek Psalm 24:1"
    assert [unit["ref"] for unit in by_mt["ps025.v002.a"]["units"]] == [
        "Greek Psalm 24:1",
        "Greek Psalm 26:3",
    ]
    assert by_mt["ps025.v002.a"]["units"][0]["mapped_spans"] == [{"start": 0, "end": 2}]
    assert all(unit["partial"] for unit in by_mt["ps025.v002.a"]["units"])
    assert by_mt["ps025.v003.a"] == {"units": [], "relations": ["edition_absent"]}
    assert "ps025.v004.a" not in by_mt
