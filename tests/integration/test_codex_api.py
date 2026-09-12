"""Codex route tests driven by a scripted app server (no live account)."""

from __future__ import annotations

import json
from collections import deque
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.services import codex_app_server_service as codex
from app.services import codex_translation_service as translation
from app.services import registry_service

client = TestClient(app)
UNIT_ID = "ps001.v001.a"


class ScriptedTransport:
    def __init__(self, agent_text: str, approval_method: str | None = None) -> None:
        self.agent_text = agent_text
        self.approval_method = approval_method
        self.sent: list[dict[str, Any]] = []
        self._inbox: deque[str] = deque()

    def send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)
        method = message.get("method")
        if method == "initialize":
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {}})
        elif method == "account/read":
            self._push(
                {
                    "jsonrpc": "2.0",
                    "id": message["id"],
                    "result": {"authenticated": True, "authMode": "chatgpt", "planType": "pro"},
                }
            )
        elif method == "thread/start":
            self._push(
                {"jsonrpc": "2.0", "id": message["id"], "result": {"thread": {"id": "th-1"}}}
            )
        elif method == "turn/start":
            self._push(
                {"jsonrpc": "2.0", "id": message["id"], "result": {"turn": {"id": "turn-1"}}}
            )
            if self.approval_method:
                self._push(
                    {
                        "jsonrpc": "2.0",
                        "id": 555,
                        "method": self.approval_method,
                        "params": {"command": ["rm", "-rf", "/"]},
                    }
                )
            self._push(
                {
                    "jsonrpc": "2.0",
                    "method": "item/completed",
                    "params": {"item": {"type": "agentMessage", "text": self.agent_text}},
                }
            )
            self._push(
                {"jsonrpc": "2.0", "method": "turn/completed", "params": {"turn": {"id": "turn-1"}}}
            )
        elif "id" in message:
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {}})

    def _push(self, obj: dict[str, Any]) -> None:
        self._inbox.append(json.dumps(obj))

    def readline(self) -> str:
        return self._inbox.popleft() + "\n" if self._inbox else ""

    def close(self) -> None:
        pass


def _payload() -> dict[str, Any]:
    return {
        "unit_id": UNIT_ID,
        "layer": "lyric",
        "candidates": [
            {
                "text": "Blessed is the one",
                "rationale": "tracks the Hebrew",
                "alignment_hints": [],
                "drift_flags": [],
                "metrics": {},
                "variation_basis": ["hebrew_source"],
                "preserved_source_images": [],
                "differentiator": "literal-leaning",
                "grounding_confidence": 0.9,
                "translation_basis": {
                    "basis_type": "hebrew_to_english",
                    "source_ids": ["oshb"],
                    "source_language": "he",
                    "source_version": "1.0",
                    "basis_note": "Hebrew source",
                },
                "delivery_profile": "spoken",
                "source_anchor": {
                    "anchor_text": "a",
                    "source_language": "he",
                    "source_text": "b",
                    "basis_note": "c",
                },
                "accuracy_note": "Close to the Hebrew.",
                "creative_liberties_note": "Contracted.",
                "literalness": "very_close",
            }
        ],
    }


@pytest.fixture(autouse=True)
def _isolate():
    translation._store_path().unlink(missing_ok=True)
    codex.set_active_client(None)
    yield
    codex.set_active_client(None)
    translation._store_path().unlink(missing_ok=True)


def _connect(agent_text: str, approval_method: str | None = None) -> None:
    codex.set_active_client(
        codex.CodexAppServerClient(transport=ScriptedTransport(agent_text, approval_method))
    )
    codex.active_client().initialized = True


def test_status_reports_not_installed_without_codex(monkeypatch) -> None:
    monkeypatch.setattr(codex, "codex_executable", lambda: None)
    response = client.get("/codex/status")

    assert response.status_code == 200
    assert response.json()["status"] == codex.STATUS_NOT_INSTALLED
    assert response.json()["local_only"] is True


def test_turn_endpoints_require_a_connected_client() -> None:
    response = client.post("/codex/sessions", json={"psalm_id": "ps001"})
    assert response.status_code == 400
    assert "not connected" in response.json()["detail"].lower()


def test_status_never_leaks_credentials(monkeypatch) -> None:
    monkeypatch.setattr(codex, "codex_executable", lambda: "/usr/bin/codex")
    _connect("{}")
    body = client.get("/codex/status").json()

    assert body["status"] == codex.STATUS_READY
    assert body["plan_type"] == "pro"
    assert "accessToken" not in json.dumps(body)


def test_session_turn_and_save_candidates_flow() -> None:
    _connect(json.dumps(_payload()))

    session = client.post(
        "/codex/sessions", json={"psalm_id": "ps001", "unit_id": UNIT_ID, "model": "gpt-5"}
    )
    assert session.status_code == 200, session.text
    session_id = session.json()["session_id"]
    assert session.json()["thread_id"] == "th-1"

    turn = client.post(
        f"/codex/sessions/{session_id}/turns", json={"unit_id": UNIT_ID, "layer": "lyric"}
    )
    assert turn.status_code == 200, turn.text
    run = turn.json()
    assert run["status"] == translation.RUN_COMPLETED

    events = client.get(f"/codex/runs/{run['run_id']}/events")
    assert events.status_code == 200
    assert events.json()["status"] == translation.RUN_COMPLETED

    saved = client.post(f"/codex/runs/{run['run_id']}/save-candidates", json={})
    assert saved.status_code == 200, saved.text
    renderings = saved.json()
    assert renderings[0]["status"] == "proposed"

    unit = registry_service.load_unit(UNIT_ID)
    assert renderings[0]["rendering_id"] not in unit["canonical_rendering_ids"]


def test_invalid_output_is_not_saved_and_exposes_validation_errors() -> None:
    _connect(json.dumps({"unit_id": UNIT_ID, "layer": "lyric", "candidates": [{"text": "x"}]}))

    session_id = client.post("/codex/sessions", json={"psalm_id": "ps001"}).json()["session_id"]
    run = client.post(
        f"/codex/sessions/{session_id}/turns", json={"unit_id": UNIT_ID, "layer": "lyric"}
    ).json()

    assert run["status"] == translation.RUN_INVALID_OUTPUT

    events = client.get(f"/codex/runs/{run['run_id']}/events").json()
    assert events["validation"], "the retry action needs the validation detail"

    saved = client.post(f"/codex/runs/{run['run_id']}/save-candidates", json={})
    assert saved.status_code == 400


def test_a_turn_requesting_command_execution_is_denied_and_logged() -> None:
    _connect(json.dumps(_payload()), approval_method="item/commandExecution/requestApproval")

    session_id = client.post("/codex/sessions", json={"psalm_id": "ps001"}).json()["session_id"]
    run = client.post(
        f"/codex/sessions/{session_id}/turns", json={"unit_id": UNIT_ID, "layer": "lyric"}
    ).json()

    events = client.get(f"/codex/runs/{run['run_id']}/events").json()
    assert [e["method"] for e in events["denied_events"]] == [
        "item/commandExecution/requestApproval"
    ]

    denial = next(m for m in codex.active_client().transport.sent if m.get("id") == 555)
    assert denial["result"] == {"decision": "decline"}


def test_cancel_marks_the_run_cancelled() -> None:
    _connect(json.dumps(_payload()))
    session_id = client.post("/codex/sessions", json={"psalm_id": "ps001"}).json()["session_id"]
    run = client.post(
        f"/codex/sessions/{session_id}/turns", json={"unit_id": UNIT_ID, "layer": "lyric"}
    ).json()

    cancelled = client.post(f"/codex/runs/{run['run_id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == translation.RUN_CANCELLED


def test_unknown_run_is_not_found() -> None:
    _connect("{}")
    assert client.get("/codex/runs/cxr.doesnotexist/events").status_code == 404
