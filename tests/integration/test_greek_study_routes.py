from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import greek_study
from app.core.errors import LicensePolicyError, NotFoundError
from app.services import greek_study_export_service, greek_study_service
from tests.unit.test_greek_study_service import view

pytestmark = pytest.mark.no_seeded_repo


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    study = view(3)

    def load(snapshot: str | None = None, policy: str | None = None):
        if snapshot is not None:
            study.require_identity(snapshot, policy or "")
        return study

    monkeypatch.setattr(greek_study_service, "load_view", load)
    monkeypatch.setattr(greek_study_export_service, "availability", lambda _: True)
    app = FastAPI()
    app.include_router(greek_study.router)
    return TestClient(app)


def test_route_card_then_first_page_requires_same_snapshot(client: TestClient) -> None:
    identity = {"study_snapshot_id": "snapshot-1", "policy_revision_id": "policy-1"}
    card = client.get("/greek/tokens/token-0000/card", params=identity).json()
    first = client.get("/greek/concordance", params=card["query"])
    assert first.status_code == 200
    assert first.json()["total_matches"] == card["counts"]["total_matches"] == 3
    stale = client.get(
        "/greek/concordance", params={**card["query"], "policy_revision_id": "policy-2"}
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "study_stale"
    assert (
        client.get("/greek/concordance", params={**card["query"], "bogus": "x"}).status_code == 422
    )
    assert (
        client.get(
            "/greek/concordance", params={**card["query"], "query_kind": "bogus"}
        ).status_code
        == 422
    )


def test_unavailable_snapshots_and_revocation_return_no_content(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(*args):
        raise NotFoundError("Retired snapshot")

    monkeypatch.setattr(greek_study_service, "load_view", missing)
    params = {"study_snapshot_id": "snapshot-1", "policy_revision_id": "policy-1"}
    assert client.get("/greek/tokens/token-0000/card", params=params).status_code == 409

    def revoked(*args):
        raise LicensePolicyError("Revoked")

    monkeypatch.setattr(greek_study_service, "load_view", revoked)
    response = client.get("/greek/tokens/token-0000/card", params=params)
    assert response.status_code == 403
    assert "λόγος" not in response.text
    assert client.get("/lxx/editions").json()["editions"] == []


def test_release_disabled_blocks_every_direct_read_without_source_leak(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(greek_study_export_service, "availability", lambda _: False)
    identity = {"study_snapshot_id": "snapshot-1", "policy_revision_id": "policy-1"}
    requests = [
        ("/lxx/psalms", identity),
        ("/lxx/reader", {**identity, "psalm": 1}),
        ("/lxx/units/any-unit", identity),
        ("/greek/tokens/token-0000/card", identity),
        ("/greek/lexicon/entries/any-entry", identity),
        ("/greek/lexicon/identifiers", {**identity, "scheme": "strong", "value": "G1"}),
        ("/greek/concordance", {**identity, "query_kind": "surface", "value": "λόγος"}),
    ]
    for path, params in requests:
        response = client.get(path, params=params)
        assert response.status_code == 403, path
        assert "λόγος" not in response.text
        assert "total_matches" not in response.text
    assert client.get("/lxx/editions").json()["editions"] == []


def test_unverified_catalog_diagnostics_do_not_expose_source_text(client, monkeypatch) -> None:
    from app.core.errors import ValidationError

    def corrupt(*args):
        raise ValidationError("Unpublished catalog contains κρυπτός")

    monkeypatch.setattr(greek_study_service, "load_view", corrupt)
    response = client.get("/greek/tokens/token-0000/card", params={
        "study_snapshot_id": "snapshot-1", "policy_revision_id": "policy-1",
    })
    assert response.status_code == 403
    assert "κρυπτός" not in response.text
