from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes import assistant, project, units

pytestmark = pytest.mark.no_seeded_repo


@pytest.fixture
def raw_mutation_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))
    project_payload = {
        "project_id": "proj.test",
        "title": "Unchanged project",
        "review_policy": {
            "canonical_required_approvals": 2,
            "alternate_required_approvals": 1,
            "release_required_role": "release reviewer",
            "reviewer_roles": ["Hebrew reviewer", "release reviewer"],
        },
        "source_manifests": [],
    }
    unit_payload = {
        "unit_id": "ps001.v001.a",
        "psalm_id": "ps001",
        "ref": "Psalm 1:1",
        "source_hebrew": "source text",
        "token_ids": ["ps001.v001.t001"],
        "tokens": [{"token_id": "ps001.v001.t001", "surface": "source text"}],
        "renderings": [
            {
                "rendering_id": "rnd.ps001.v001.a.literal.can.0001",
                "layer": "literal",
                "status": "canonical",
                "text": "Original canonical text",
                "target_spans": [],
            }
        ],
        "canonical_rendering_ids": ["rnd.ps001.v001.a.literal.can.0001"],
        "review_decisions": [
            {
                "target_id": "rnd.ps001.v001.a.literal.can.0001",
                "decision": "approve",
                "reviewer": "fixture-reviewer",
                "reviewer_role": "Hebrew reviewer",
                "timestamp": "2026-01-01T00:00:00+00:00",
            }
        ],
        "audit_records": [{"audit_id": "aud.ps001.v001.a.0001", "summary": "Existing history"}],
        "audit_ids": ["aud.ps001.v001.a.0001"],
        "alignments": [],
        "witnesses": [{"source_id": source} for source in ("kjv", "asv", "web")],
    }
    for relative, payload in (
        ("content/project.json", project_payload),
        ("content/psalms/ps001/ps001.v001.a.json", unit_payload),
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    return tmp_path


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(project.router)
    app.include_router(units.router)
    app.include_router(assistant.router)
    return TestClient(app)


def _persisted_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"source_hebrew": "replacement source"},
        {"tokens": [], "token_ids": []},
        {"renderings": []},
        {"review_decisions": [{"decision": "approve", "reviewer": "forged"}]},
        {"review_decisions": []},
        {"audit_records": [], "audit_ids": []},
        {"canonical_rendering_ids": []},
        {"unit_id": "ps002.v001.a", "psalm_id": "ps002"},
        {"rationale": "An unsupported metadata edit"},
        {},
    ],
)
def test_raw_unit_patch_refuses_without_writing(
    client: TestClient, raw_mutation_workspace: Path, payload: dict
) -> None:
    before = _persisted_bytes(raw_mutation_workspace)

    response = client.patch("/units/ps001.v001.a", json=payload)

    assert response.status_code == 400, response.text
    assert "Raw unit updates are disabled" in response.json()["detail"]
    assert _persisted_bytes(raw_mutation_workspace) == before


@pytest.mark.parametrize(
    "payload",
    [
        {"review_policy": {"canonical_required_approvals": 0}},
        {"source_manifests": [{"source_id": "restricted", "allowed_for_export": True}]},
        {"allowed_sources": ["restricted"]},
        {"output_text_license": "unapproved license"},
        {"title": "An unsupported metadata edit"},
        {},
    ],
)
def test_raw_project_patch_refuses_without_writing(
    client: TestClient, raw_mutation_workspace: Path, payload: dict
) -> None:
    before = _persisted_bytes(raw_mutation_workspace)

    response = client.patch("/project", json=payload)

    assert response.status_code == 400, response.text
    assert "Raw project updates are disabled" in response.json()["detail"]
    assert _persisted_bytes(raw_mutation_workspace) == before


@pytest.mark.parametrize(
    "patch",
    [{"review_policy": {"canonical_required_approvals": 0}}, {"title": "New title"}],
)
def test_confirmation_cannot_enable_raw_assistant_project_patch(
    client: TestClient, raw_mutation_workspace: Path, patch: dict
) -> None:
    before = _persisted_bytes(raw_mutation_workspace)
    request = {"action_id": "project.patch", "input": {"patch": patch}}
    preview = client.post("/assistant/actions/preview", json=request)
    assert preview.status_code == 200, preview.text

    response = client.post(
        "/assistant/actions/execute",
        json={**request, "confirmation_token": preview.json()["confirmation_token"]},
    )

    assert response.status_code == 400, response.text
    assert "Raw project updates are disabled" in response.json()["detail"]
    assert _persisted_bytes(raw_mutation_workspace) == before


def test_read_endpoints_remain_available_without_content_changes(
    client: TestClient, raw_mutation_workspace: Path
) -> None:
    before = _persisted_bytes(raw_mutation_workspace)

    project_response = client.get("/project")
    unit_response = client.get("/units/ps001.v001.a")

    assert project_response.status_code == 200, project_response.text
    assert project_response.json()["title"] == "Unchanged project"
    assert unit_response.status_code == 200, unit_response.text
    assert unit_response.json()["renderings"][0]["text"] == "Original canonical text"
    assert _persisted_bytes(raw_mutation_workspace) == before


@pytest.mark.parametrize("endpoint", ["/project", "/units/ps001.v001.a"])
def test_raw_patch_does_not_bootstrap_an_empty_workspace(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    monkeypatch.setenv("ALEPHTAV_ROOT_DIR", str(tmp_path))

    response = client.patch(endpoint, json={"title": "Unsupported update"})

    assert response.status_code == 400, response.text
    assert _persisted_bytes(tmp_path) == {}
