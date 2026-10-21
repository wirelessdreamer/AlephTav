from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from app.services.package_audit_service import record_package_mutation

pytestmark = pytest.mark.no_seeded_repo


@pytest.fixture(autouse=True)
def schemas(tmp_path) -> None:
    shutil.copytree(Path(__file__).resolve().parents[2] / "schemas", tmp_path / "schemas")


def test_repeated_transition_preserves_each_actor_and_event(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    events = [
        record_package_mutation(
            package_id="source_policy",
            before_hash=before * 64,
            after_hash=after * 64,
            summary="Change current policy",
            rationale=f"Decision by {actor}",
            created_by=actor,
            checks=["current_policy"],
        )
        for before, after, actor in [("a", "b", "first"), ("b", "a", "second"), ("a", "b", "third")]
    ]
    assert len({event["audit_id"] for event in events}) == 3
    assert [event["created_by"] for event in events] == ["first", "second", "third"]
    assert len(list((tmp_path / "content/audit/packages").glob("*.json"))) == 3


def test_explicit_retry_key_reuses_original_event_but_rejects_changed_transition(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    arguments = dict(
        package_id="fixture",
        before_hash="a" * 64,
        after_hash="b" * 64,
        summary="Install",
        rationale="Authored fixture",
        created_by="first",
        checks=["hashes"],
        idempotency_key="install-fixture",
    )
    first = record_package_mutation(**arguments)
    retry = record_package_mutation(**{**arguments, "created_by": "retry"})
    assert first == retry
    with pytest.raises(ValueError, match="different mutation"):
        record_package_mutation(**{**arguments, "after_hash": "c" * 64})
