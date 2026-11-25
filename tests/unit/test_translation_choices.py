from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from app.core.config import get_settings
from app.core.errors import NotFoundError, ValidationError
from app.services import audit_service, registry_service, translation_context_service
from app.services import translation_choices_service as choices

pytestmark = pytest.mark.no_seeded_repo
PSALM = "ps001"
UNIT = "ps001.v001.a"
SECOND_UNIT = "ps001.v002.a"
TRANSLATION = "tr.ps001.0001"
ARRANGEMENT = "arr.ps001.0001"
MAIN_ARRANGEMENT = "arr.ps001.0002"
LYRIC = f"rnd.{UNIT}.lyric.alt.0001"
LITERAL = f"rnd.{UNIT}.literal.can.0001"
MAIN_LYRIC = f"rnd.{UNIT}.lyric.can.0001"


def _rendering(target_id: str, layer: str, text: str, translation: str | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "rendering_id": target_id,
        "unit_id": UNIT,
        "layer": layer,
        "text": text,
        "status": "canonical" if ".can." in target_id else "proposed",
        "style_tags": [],
        "target_spans": [],
        "alignment_ids": [],
        "metrics": {"score": 0.1},
        "drift_flags": [{"code": "unresolved"}],
        "rationale": "authored fixture",
        "provenance": {"source_ids": [], "generator": "fixture"},
        "review_signoff": {"reviewer": "historical"},
    }
    if translation:
        result["translation_id"] = translation
    return result


def _line(number: int, text: str) -> dict[str, Any]:
    return {
        "line_id": f"ln.{number:04d}",
        "text": text,
        "anchors": [{"unit_id": UNIT, "token_ids": ["ps001.v001.t001"]}],
        "liberty": "expanded",
        "rationale": "authored departure",
        "approvals": [{"reviewer": "historical", "reviewer_role": "lyric"}],
    }


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    registry_service.write_json(get_settings().project_file, {"source_manifests": []})
    for unit_id in (UNIT, SECOND_UNIT):
        unit = {
            "unit_id": unit_id,
            "psalm_id": PSALM,
            "ref": "Authored choice fixture",
            "tokens": [],
            "renderings": [],
            "alignments": [],
            "canonical_rendering_ids": [],
            "alternate_rendering_ids": [],
            "review_decisions": [{"decision": "approve", "reviewer": "historical"}],
            "verse_assessments": [{"flags": ["unresolved"], "verdict": "needs_work"}],
            "audit_records": [],
            "audit_ids": [],
        }
        if unit_id == UNIT:
            unit["renderings"] = [
                _rendering(LYRIC, "lyric", "God of my salvation", TRANSLATION),
                _rendering(LITERAL, "literal", "God of my deliverance", None),
                _rendering(MAIN_LYRIC, "lyric", "Main translation", None),
            ]
            unit["canonical_rendering_ids"] = [LITERAL, MAIN_LYRIC]
        audit_service.create_audit_record(
            unit,
            "before",
            "after",
            "Existing audit",
            "Preserve this evidence",
            "historical",
            review_signoff={"release": "historical"},
        )
        registry_service.save_unit(unit)
    arrangement = {
        "arrangement_id": ARRANGEMENT,
        "psalm_id": PSALM,
        "translation_id": TRANSLATION,
        "layer": "lyric",
        "title": "Authored song",
        "status": "draft",
        "guidance": "Original guidance",
        "audit_ids": ["existing"],
        "sections": [
            {
                "section_id": "sec.0001",
                "kind": "verse",
                "label": "Opening",
                "repeat_of": None,
                "lines": [_line(1, "God of my salvation")],
            },
            {
                "section_id": "sec.0002",
                "kind": "outro",
                "label": "Ending",
                "repeat_of": None,
                "lines": [_line(2, "Darkness"), _line(3, "My closest friend")],
            },
            {
                "section_id": "sec.0003",
                "kind": "refrain",
                "label": "Again",
                "repeat_of": "sec.0002",
                "lines": [],
            },
        ],
        "omissions": [
            {
                "unit_id": SECOND_UNIT,
                "token_ids": ["ps001.v002.t001"],
                "rationale": "authored omission",
                "approvals": [],
            }
        ],
    }
    main_arrangement = deepcopy(arrangement)
    main_arrangement["arrangement_id"] = MAIN_ARRANGEMENT
    main_arrangement.pop("translation_id")
    registry_service.save_psalm_meta(
        PSALM,
        {
            "psalm_id": PSALM,
            "title": "Psalm fixture",
            "unit_ids": [UNIT, SECOND_UNIT],
            "translation_guidance": "Do not change guidance",
            "translations": [{"translation_id": TRANSLATION, "title": "Authored translation"}],
            "arrangements": [arrangement, main_arrangement],
        },
    )
    return tmp_path


def _bytes() -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in get_settings().content_dir.rglob("*.json")}


def _target(target_id: str = LYRIC, *, translation: str | None = TRANSLATION) -> dict[str, Any]:
    return next(
        t for t in choices.choices_view(PSALM, translation)["targets"] if t["id"] == target_id
    )


def _ref(target: dict[str, Any]) -> dict[str, Any]:
    result = {
        "kind": target["kind"],
        "id": target["id"],
        "expected_revision": target["revision"]["value"],
    }
    if "arrangement_id" in target:
        result["arrangement_id"] = target["arrangement_id"]
    return result


def _record(targets: list[dict[str, Any]] | None = None, **changes: Any) -> dict[str, Any]:
    values = {
        "decision": "Keep the opening and the darkness ending",
        "rationale": "This framing is an intentional translation choice",
        "context_status": "not_established",
        "context_note": "Supporting context is not available; no source support is claimed",
        "created_by": "translator",
        "targets": [_ref(_target())] if targets is None else targets,
    }
    values.update(changes)
    return choices.record_choice(PSALM, TRANSLATION, **values)


def test_records_server_snapshot_in_ordinary_audit_only_and_survives_cache_deletion(
    workspace: Path,
) -> None:
    before = _bytes()
    original = registry_service.read_json(registry_service.unit_path(UNIT))
    target = _target()
    entry = _record()
    assert entry["target_state"] == "current"
    assert entry["counts_for_publication"] is False
    assert entry["superseded_by_audit_id"] is None
    assert entry["created_by"] == "translator"
    assert entry["choice"]["targets"] == [target]
    assert entry["choice"]["context_status"] == "not_established"
    after = registry_service.read_json(registry_service.unit_path(UNIT))
    assert after["audit_records"][:-1] == original["audit_records"]
    assert after["audit_ids"][:-1] == original["audit_ids"]
    audit = after["audit_records"][-1]
    assert audit["entity_type"] == "translation_context"
    assert audit["change_type"] == "create"
    assert audit["review_signoff"] == {} and audit["checks"] == []
    schema = json.loads(
        (Path(__file__).parents[2] / "schemas/audit_record.schema.json").read_text()
    )
    Draft202012Validator(schema).validate(audit)
    snapshot = json.loads(audit["rationale"])
    assert set(snapshot) == {"kind", "translation_id", "choice"}
    assert snapshot["choice"]["targets"][0]["text"] == "God of my salvation"
    for key in ("audit_records", "audit_ids"):
        original.pop(key)
        after.pop(key)
    assert after == original
    assert {p: b for p, b in before.items() if p != registry_service.unit_path(UNIT)} == {
        p: b for p, b in _bytes().items() if p != registry_service.unit_path(UNIT)
    }
    cache = get_settings().caches_dir / "unrelated.json"
    cache.write_text("{}")
    cache.unlink()
    assert choices.choices_view(PSALM, TRANSLATION)["choices"] == [entry]
    assert (
        translation_context_service.current_annotations(
            translation_context_service.history(PSALM, TRANSLATION)
        )
        == []
    )
    assert translation_context_service.briefing_instructions(PSALM, TRANSLATION) == ""


def test_record_does_not_persist_witness_enrichment(
    workspace: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = registry_service.unit_path(UNIT)
    original = registry_service.read_json(path)
    original["ref"] = "Psalm 1:1"
    registry_service.write_json(path, original)
    monkeypatch.setattr(
        registry_service, "_load_public_domain_witness_map", lambda _: {(1, 1): "witness"}
    )
    assert registry_service.load_unit(UNIT)["witnesses"]
    _record()
    after = registry_service.read_json(path)
    assert "witnesses" not in after
    for key in ("audit_records", "audit_ids"):
        original.pop(key)
        after.pop(key)
    assert after == original


def test_scope_shares_literal_but_never_other_translation_lyrics_or_songs(workspace: Path) -> None:
    before = _bytes()
    own = choices.choices_view(PSALM, TRANSLATION)
    main = choices.choices_view(PSALM)
    assert {t["id"] for t in own["targets"] if t["kind"] == "rendering"} == {LYRIC, LITERAL}
    assert {t["id"] for t in main["targets"] if t["kind"] == "rendering"} == {MAIN_LYRIC, LITERAL}
    shared = _target(LITERAL)
    assert shared["shared"] is True and shared["translation_id"] is None
    assert shared == _target(LITERAL, translation=None)
    assert _target()["shared"] is False and _target()["translation_id"] == TRANSLATION
    assert {t.get("arrangement_id") for t in own["targets"] if t["kind"] == "arrangement_line"} == {
        ARRANGEMENT
    }
    _record([_ref(shared)])
    assert choices.choices_view(PSALM)["choices"] == []
    assert set(before) == set(_bytes())


def test_arrangement_snapshot_binds_full_order_repeats_adjacent_text_and_departures(
    workspace: Path,
) -> None:
    target = _target("ln.0003")
    assert target["context_text"] == (
        "God of my salvation\nDarkness\nMy closest friend\nDarkness\nMy closest friend"
    )
    authored = target["authored_snapshot"]["authored"]
    assert authored["sections"][1]["lines"][1]["anchors"][0]["unit_id"] == UNIT
    assert authored["sections"][1]["lines"][1]["liberty"] == "expanded"
    assert "approvals" not in json.dumps(authored)
    assert "audit_ids" not in json.dumps(authored)
    entry = _record([_ref(target)])
    meta = registry_service.load_psalm_meta(PSALM)
    meta["arrangements"][0]["sections"][1]["lines"][0]["text"] = "The dark"
    registry_service.save_psalm_meta(PSALM, meta)
    changed = _target("ln.0003")
    assert changed["text"] == target["text"] and changed["revision"] != target["revision"]
    assert choices.choices_view(PSALM, TRANSLATION)["choices"][0]["target_state"] == "changed"
    assert choices.choices_view(PSALM, TRANSLATION)["choices"][0]["audit_id"] == entry["audit_id"]
    before = _bytes()
    with pytest.raises(ValidationError, match="changed"):
        _record([_ref(target)])
    assert _bytes() == before


@pytest.mark.parametrize("change", ["text", "anchor", "liberty", "order", "repeat", "omission"])
def test_each_authored_arrangement_change_invalidates_revision(
    workspace: Path, change: str
) -> None:
    before = _target("ln.0003")["revision"]
    meta = registry_service.load_psalm_meta(PSALM)
    arrangement = meta["arrangements"][0]
    if change == "text":
        arrangement["sections"][0]["lines"][0]["text"] += "!"
    elif change == "anchor":
        arrangement["sections"][0]["lines"][0]["anchors"] = []
    elif change == "liberty":
        arrangement["sections"][0]["lines"][0]["liberty"] = "added"
    elif change == "order":
        arrangement["sections"][1]["lines"].reverse()
    elif change == "repeat":
        arrangement["sections"].pop()
    else:
        arrangement["omissions"][0]["rationale"] += "!"
    registry_service.save_psalm_meta(PSALM, meta)
    assert _target("ln.0003")["revision"] != before


def test_authored_revision_ignores_runtime_review_and_status_changes_and_key_order(
    workspace: Path,
) -> None:
    before = {t["id"]: t["revision"] for t in choices.choices_view(PSALM, TRANSLATION)["targets"]}
    unit = registry_service.read_json(registry_service.unit_path(UNIT))
    unit["renderings"][0].update(
        {
            "status": "under_review",
            "metrics": {"score": 1},
            "drift_flags": [],
            "review_signoff": {"new": "reviewer"},
        }
    )
    unit["renderings"][0]["provenance"]["run_id"] = "different runtime"
    unit["review_decisions"].append({"contract_version": 2, "decision": "approve"})
    registry_service.write_json(
        registry_service.unit_path(UNIT), dict(reversed(list(unit.items())))
    )
    meta = registry_service.load_psalm_meta(PSALM)
    arrangement = meta["arrangements"][0]
    arrangement.update({"status": "accepted", "updated_at": "later", "audit_ids": ["new"]})
    arrangement["sections"][0]["lines"][0]["approvals"] = []
    arrangement["omissions"][0]["approvals"] = [{"reviewer": "another"}]
    registry_service.save_psalm_meta(PSALM, meta)
    assert {
        t["id"]: t["revision"] for t in choices.choices_view(PSALM, TRANSLATION)["targets"]
    } == before


def test_rendering_revision_binds_authored_alignment_mapping_without_source_lookup(
    workspace: Path,
) -> None:
    before = _target()["revision"]
    unit = registry_service.read_json(registry_service.unit_path(UNIT))
    unit["renderings"][0]["alignment_ids"] = [f"aln.{UNIT}.lyric.0001"]
    unit["alignments"] = [
        {
            "alignment_id": f"aln.{UNIT}.lyric.0001",
            "source_token_ids": ["missing"],
            "target_span_ids": [],
            "alignment_type": "uncertain",
            "notes": "unavailable",
        }
    ]
    registry_service.save_unit(unit)
    target = _target()
    assert target["revision"] != before
    assert _record([_ref(target)])["counts_for_publication"] is False


def test_view_filters_and_preserves_missing_history(workspace: Path) -> None:
    rendering_entry = _record()
    line_entry = _record([_ref(_target("ln.0003"))])
    assert len(choices.choices_view(PSALM, TRANSLATION, unit_id=UNIT)["choices"]) == 2
    song = choices.choices_view(PSALM, TRANSLATION, arrangement_id=ARRANGEMENT)
    assert [e["audit_id"] for e in song["choices"]] == [line_entry["audit_id"]]
    assert all(t["kind"] == "arrangement_line" for t in song["targets"])
    assert choices.choices_view(PSALM, TRANSLATION, unit_id=SECOND_UNIT)["targets"] == []
    unit = registry_service.read_json(registry_service.unit_path(UNIT))
    unit["renderings"] = [r for r in unit["renderings"] if r["rendering_id"] != LYRIC]
    registry_service.save_unit(unit)
    missing = choices.choices_view(PSALM, TRANSLATION)["choices"][0]
    assert (
        missing["audit_id"] == rendering_entry["audit_id"] and missing["target_state"] == "missing"
    )


def test_corrections_append_preserve_original_and_allow_explicit_current_revision(
    workspace: Path,
) -> None:
    original = _record()
    first_audits = deepcopy(
        registry_service.read_json(registry_service.unit_path(UNIT))["audit_records"]
    )
    unit = registry_service.read_json(registry_service.unit_path(UNIT))
    unit["renderings"][0]["text"] += " — revised"
    registry_service.save_unit(unit)
    corrected = _record(supersedes_audit_id=original["audit_id"], decision="Clarify my intention")
    assert corrected["choice"]["supersedes_audit_id"] == original["audit_id"]
    entries = choices.choices_view(PSALM, TRANSLATION)["choices"]
    assert entries[0]["choice"] == original["choice"]
    assert entries[0]["target_state"] == "changed"
    assert entries[0]["superseded_by_audit_id"] == corrected["audit_id"]
    assert entries[1]["target_state"] == "current"
    assert (
        registry_service.read_json(registry_service.unit_path(UNIT))["audit_records"][:-1]
        == first_audits
    )
    before = _bytes()
    with pytest.raises(ValidationError, match="already"):
        _record(supersedes_audit_id=original["audit_id"])
    assert _bytes() == before


@pytest.mark.parametrize(
    "field,limit",
    [("decision", 2000), ("rationale", 8000), ("context_note", 4000), ("created_by", 200)],
)
@pytest.mark.parametrize("invalid", ["empty", "long", "type", "unicode"])
def test_required_text_validation_refuses_without_writes(
    workspace: Path,
    field: str,
    limit: int,
    invalid: str,
) -> None:
    value = {
        "empty": " \n",
        "long": "a" * (limit + 1),
        "type": {"text": "spoof"},
        "unicode": "bad\ud800",
    }[invalid]
    before = _bytes()
    with pytest.raises(ValidationError):
        _record(**{field: value})
    assert _bytes() == before


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown",
        "snapshot",
        "missing",
        "digest",
        "duplicate",
        "kind",
        "foreign_rendering",
        "foreign_line",
        "cross_psalm",
    ],
)
def test_bad_refs_and_scope_refuse_before_any_write(workspace: Path, mutation: str) -> None:
    ref = _ref(_target())
    if mutation == "unknown":
        ref["created_at"] = "1900-01-01T00:00:00Z"
    elif mutation == "snapshot":
        ref["text"] = "Client-supplied words"
    elif mutation == "missing":
        ref.pop("expected_revision")
    elif mutation == "digest":
        ref["expected_revision"] = "A" * 64
    elif mutation == "kind":
        ref["kind"] = "review_approval"
    elif mutation == "foreign_rendering":
        ref["id"] = MAIN_LYRIC
    elif mutation == "foreign_line":
        ref = _ref(_target("ln.0001"))
        ref["arrangement_id"] = MAIN_ARRANGEMENT
    elif mutation == "cross_psalm":
        ref["id"] = ref["id"].replace("ps001", "ps002")
    refs = [ref, deepcopy(ref)] if mutation == "duplicate" else [ref]
    before = _bytes()
    with pytest.raises((ValidationError, NotFoundError)):
        _record(refs)
    assert _bytes() == before


def test_empty_invalid_context_and_excess_targets_refuse_without_writes(workspace: Path) -> None:
    before = _bytes()
    for overrides in (
        {"targets": []},
        {"targets": [_ref(_target())] * 21},
        {"context_status": "source_verified"},
    ):
        with pytest.raises(ValidationError):
            _record(**overrides)
        assert _bytes() == before


def test_twenty_targets_and_self_reported_context_are_supported(workspace: Path) -> None:
    unit = registry_service.read_json(registry_service.unit_path(UNIT))
    unit["renderings"] = [
        _rendering(f"rnd.{UNIT}.lyric.alt.{n:04d}", "lyric", f"Line {n}", TRANSLATION)
        for n in range(1, 21)
    ]
    registry_service.save_unit(unit)
    targets = [
        t for t in choices.choices_view(PSALM, TRANSLATION)["targets"] if t["kind"] == "rendering"
    ]
    entry = _record(
        [_ref(t) for t in targets],
        context_status="provided_by_translator",
        context_note="The translator reports having context; this is not verified",
    )
    assert len(entry["choice"]["targets"]) == 20
    assert entry["counts_for_publication"] is False


@pytest.mark.parametrize("mode", ["unknown", "foreign_scope", "different_targets", "future"])
def test_invalid_corrections_refuse_without_writes(workspace: Path, mode: str) -> None:
    original = _record()
    overrides: dict[str, Any] = {"supersedes_audit_id": original["audit_id"]}
    if mode == "unknown":
        overrides["supersedes_audit_id"] = f"aud.{UNIT}.9999"
    elif mode == "foreign_scope":
        ref = _ref(_target(MAIN_LYRIC, translation=None))
        foreign = choices.record_choice(
            PSALM,
            targets=[ref],
            decision="Main choice",
            rationale="reason",
            context_status="not_established",
            context_note="unknown",
            created_by="main",
        )
        overrides["supersedes_audit_id"] = foreign["audit_id"]
    elif mode == "different_targets":
        overrides["targets"] = [_ref(_target(LITERAL))]
    else:
        unit = registry_service.read_json(registry_service.unit_path(UNIT))
        unit["audit_records"][-1]["created_at"] = "9999-01-01T00:00:00Z"
        registry_service.save_unit(unit)
    before = _bytes()
    with pytest.raises(ValidationError):
        _record(**overrides)
    assert _bytes() == before


@pytest.mark.parametrize(
    "mode", ["duplicate_rendering", "duplicate_line", "wrong_parent", "wrong_psalm"]
)
def test_ambiguous_or_inconsistent_persisted_targets_are_refused(
    workspace: Path, mode: str
) -> None:
    ref = _ref(_target())
    if mode in ("duplicate_rendering", "wrong_parent"):
        unit = registry_service.read_json(registry_service.unit_path(UNIT))
        if mode == "duplicate_rendering":
            unit["renderings"].append(deepcopy(unit["renderings"][0]))
        else:
            unit["renderings"][0]["unit_id"] = SECOND_UNIT
        registry_service.save_unit(unit)
    else:
        meta = registry_service.load_psalm_meta(PSALM)
        if mode == "duplicate_line":
            line = deepcopy(meta["arrangements"][0]["sections"][0]["lines"][0])
            meta["arrangements"][0]["sections"][1]["lines"].append(line)
        else:
            meta["arrangements"][0]["psalm_id"] = "ps002"
        registry_service.save_psalm_meta(PSALM, meta)
    before = _bytes()
    with pytest.raises(ValidationError):
        _record([ref])
    assert _bytes() == before


@pytest.mark.parametrize(
    "filters", [{"arrangement_id": MAIN_ARRANGEMENT}, {"unit_id": "ps002.v001.a"}]
)
def test_foreign_view_filters_refuse_without_writes(
    workspace: Path, filters: dict[str, str]
) -> None:
    before = _bytes()
    with pytest.raises(NotFoundError):
        choices.choices_view(PSALM, TRANSLATION, **filters)
    assert _bytes() == before


def test_deep_malformed_authored_field_refuses_safely_before_append(workspace: Path) -> None:
    ref = _ref(_target())
    unit = registry_service.read_json(registry_service.unit_path(UNIT))
    nested: Any = "private-author-text"
    for _ in range(600):
        nested = {"nested": nested}
    unit["renderings"][0]["source_anchor"] = nested
    registry_service.unit_path(UNIT).write_text(json.dumps(unit), encoding="utf-8")
    before = _bytes()
    with pytest.raises(ValidationError) as error:
        _record([ref])
    assert "private-author-text" not in str(error.value)
    assert _bytes() == before


def test_legacy_provenance_basis_is_archived_as_declaration_and_bound(workspace: Path) -> None:
    unit = registry_service.read_json(registry_service.unit_path(UNIT))
    unit["renderings"][0]["provenance"]["translation_basis"] = {
        "basis_type": "hebrew_to_english",
        "source_ids": ["declared-hebrew"],
        "source_language": "he",
        "source_version": "unknown",
        "basis_note": "authored declaration",
    }
    registry_service.save_unit(unit)
    target = _target()
    entry = _record([_ref(target)])
    declared = entry["choice"]["targets"][0]["authored_snapshot"]["authored"]["declared_provenance"]
    assert declared["translation_basis"]["source_ids"] == ["declared-hebrew"]
    assert entry["choice"]["context_status"] == "not_established"
    unit["renderings"][0]["provenance"]["translation_basis"]["source_version"] = (
        "another declaration"
    )
    registry_service.save_unit(unit)
    assert _target()["revision"] != target["revision"]
