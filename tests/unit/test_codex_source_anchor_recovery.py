from __future__ import annotations

from copy import deepcopy

import pytest

from app.services import codex_source_anchor_recovery_service as recovery
from app.services import codex_translation_service, registry_service, rendering_service

UNIT_ID = "ps001.v001.a"


def _proposal(monkeypatch: pytest.MonkeyPatch) -> tuple[dict, dict, dict]:
    unit = registry_service.load_unit(UNIT_ID)
    basis = {
        "basis_type": "hebrew_to_english",
        "source_ids": ["uxlc"],
        "source_language": "he",
        "source_version": "fixture",
        "basis_note": "Fixture source",
    }
    rendering = rendering_service.create_rendering(
        UNIT_ID,
        "lyric",
        "Blessed is the man.",
        status="proposed",
        rationale="Recovery fixture",
        created_by="test",
        translation_basis=basis,
        provenance={"provider": "codex-app-server", "run_id": "cxr.recovery"},
    )
    anchor = {
        "anchor_text": "Blessed",
        "source_language": "he",
        "source_text": unit["source_hebrew"],
        "token_ids": unit["token_ids"],
        "basis_note": "Original source evidence",
    }
    run = {
        "run_id": "cxr.recovery",
        "kind": "translation",
        "status": "completed",
        "layer": "lyric",
        "payload": {
            "unit_id": UNIT_ID,
            "layer": "lyric",
            "candidates": [
                {"text": rendering["text"], "source_anchor": anchor, "translation_basis": basis}
            ],
        },
    }
    monkeypatch.setattr(
        codex_translation_service, "_read_store", lambda: {"runs": {run["run_id"]: run}}
    )
    saved_unit = registry_service.load_unit(UNIT_ID)
    monkeypatch.setattr(registry_service, "list_units", lambda: [saved_unit])
    return rendering, run, saved_unit


def _saved(rendering_id: str) -> dict:
    return next(
        rendering
        for rendering in registry_service.load_unit(UNIT_ID)["renderings"]
        if rendering["rendering_id"] == rendering_id
    )


def test_inventory_does_not_modify_a_recoverable_proposal(monkeypatch: pytest.MonkeyPatch) -> None:
    rendering, _, _ = _proposal(monkeypatch)
    report = recovery.recover_source_anchors()
    assert report["counts"] == {"recoverable": 1}
    saved = _saved(rendering["rendering_id"])
    assert saved["source_anchor"] is None


def test_recovery_preserves_evidence_and_writes_an_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    rendering, run, _ = _proposal(monkeypatch)
    report = recovery.recover_source_anchors(apply=True)
    assert report["counts"] == {"recovered": 1}
    saved = _saved(rendering["rendering_id"])
    assert saved["source_anchor"] == run["payload"]["candidates"][0]["source_anchor"]
    assert saved["status"] == "proposed"
    assert saved["rationale"] == rendering["rationale"]
    audit = registry_service.load_unit(UNIT_ID)["audit_records"][-1]
    assert audit["created_by"] == "codex-source-anchor-recovery"
    assert audit["entity_id"] == rendering["rendering_id"]
    assert run["run_id"] in audit["rationale"]


def test_recovery_leaves_reviewed_content_for_qualified_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rendering, _, unit = _proposal(monkeypatch)
    next(r for r in unit["renderings"] if r["rendering_id"] == rendering["rendering_id"])[
        "status"
    ] = "canonical"
    report = recovery.recover_source_anchors(apply=True)
    assert report["counts"] == {"review_required": 1}
    assert _saved(rendering["rendering_id"])["source_anchor"] is None


@pytest.mark.parametrize(
    "mismatch",
    [
        "duplicate",
        "unit",
        "layer",
        "text",
        "status",
        "translation",
        "run_id",
        "source_version",
        "source_language",
        "source_ids",
    ],
)
def test_recovery_requires_unique_matching_completed_evidence(
    monkeypatch: pytest.MonkeyPatch, mismatch: str
) -> None:
    rendering, run, _ = _proposal(monkeypatch)
    if mismatch == "duplicate":
        run["payload"]["candidates"] *= 2
    elif mismatch == "unit":
        run["payload"]["unit_id"] = "ps002.v001.a"
    elif mismatch == "layer":
        run["payload"]["layer"] = "literal"
    elif mismatch == "text":
        run["payload"]["candidates"][0]["text"] = "A later revision."
    elif mismatch == "status":
        run["status"] = "invalid_output"
    elif mismatch == "translation":
        run["translation_id"] = "trn.other"
    elif mismatch == "run_id":
        run["run_id"] = "cxr.other"
    else:
        basis = run["payload"]["candidates"][0]["translation_basis"]
        basis[mismatch] = ["macula"] if mismatch == "source_ids" else "another value"
    report = recovery.recover_source_anchors(apply=True)
    assert report["counts"] == {"unresolved": 1}
    assert _saved(rendering["rendering_id"])["source_anchor"] is None


@pytest.mark.parametrize(
    "invalid", ["missing", "script", "tokens", "anchor_text", "basis_note", "wrong_type", "extra"]
)
def test_recovery_rejects_missing_or_invalid_anchors(
    monkeypatch: pytest.MonkeyPatch, invalid: str
) -> None:
    rendering, run, _ = _proposal(monkeypatch)
    candidate = run["payload"]["candidates"][0]
    if invalid == "missing":
        candidate.pop("source_anchor")
    elif invalid == "script":
        candidate["source_anchor"]["source_text"] = "English is not source evidence."
    elif invalid == "tokens":
        candidate["source_anchor"]["token_ids"] = ["ps002.v001.t001"]
    elif invalid in {"anchor_text", "basis_note"}:
        candidate["source_anchor"].pop(invalid)
    elif invalid == "wrong_type":
        candidate["source_anchor"]["anchor_text"] = 123
    else:
        candidate["source_anchor"]["unvalidated"] = True
    report = recovery.recover_source_anchors(apply=True)
    assert report["counts"] == {"unresolved": 1}
    assert _saved(rendering["rendering_id"])["source_anchor"] is None


def test_passage_evidence_is_recovered(monkeypatch: pytest.MonkeyPatch) -> None:
    _, run, _ = _proposal(monkeypatch)
    entry = deepcopy(run["payload"])
    run["payload"] = {"units": [entry]}
    assert recovery.recover_source_anchors(apply=True)["counts"] == {"recovered": 1}
