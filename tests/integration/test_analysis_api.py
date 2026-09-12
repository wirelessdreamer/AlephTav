"""Analysis routes, driven by a scripted app server (no live account)."""

from __future__ import annotations

import json
from collections import deque
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.services import codex_app_server_service as codex
from app.services import codex_translation_service as translation

client = TestClient(app)

UNIT_ID = "ps001.v001.a"
PSALM_ID = "ps001"


def _verse_payload() -> dict[str, Any]:
    return {
        "unit_id": UNIT_ID,
        "accuracy_rating": "adapted",
        "accuracy_note": "Keeps the three-verb progression.",
        "creative_liberties_note": "Compressed for singing.",
        "literal_backbone": ["Blessed is the one who does not walk in the counsel of the wicked"],
        "word_notes": [],
        "non_source_material": [
            {"text": "[6/8]", "kind": "meter", "note": "Arrangement decision, not in the psalm."}
        ],
    }


def _psalm_payload() -> dict[str, Any]:
    return {
        "psalm_id": PSALM_ID,
        "summary": "The two ways.",
        "sections": [
            {
                "title": "Verse 1",
                "first_verse": 1,
                "last_verse": 1,
                "theme": "the blessed life",
                "arc_note": "",
            }
        ],
        "structural_seams": [],
        "guardrails": {
            "heading_attribution": "No heading; no author named.",
            "cultic_setting": "Wisdom framing.",
        },
        "epistemics": {
            "known_from_text": [{"claim": "Two ways contrasted.", "basis": "vv. 1 and 4."}],
            "not_known_from_text": [{"claim": "No author.", "why_not": "No superscription."}],
        },
        "non_source_material": [],
        "method": "Checked against the Masoretic text.",
        "citations": ["BDB"],
    }


class ScriptedTransport:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = list(payloads)
        self.sent: list[dict[str, Any]] = []
        self._inbox: deque[str] = deque()
        self.turn = 0

    def send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)
        method = message.get("method")
        if method == "thread/start":
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {"threadId": "th-1"}})
        elif method == "turn/start":
            self.turn += 1
            turn_id = f"turn-{self.turn}"
            body = self.payloads.pop(0) if self.payloads else {}
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {"turnId": turn_id}})
            self._push(
                {
                    "jsonrpc": "2.0",
                    "method": "item/completed",
                    "params": {"item": {"type": "agentMessage", "text": json.dumps(body)}},
                }
            )
            self._push(
                {"jsonrpc": "2.0", "method": "turn/completed", "params": {"turnId": turn_id}}
            )
        elif "id" in message:
            self._push({"jsonrpc": "2.0", "id": message["id"], "result": {}})

    def _push(self, obj: dict[str, Any]) -> None:
        self._inbox.append(json.dumps(obj))

    def readline(self) -> str:
        return self._inbox.popleft() + "\n" if self._inbox else ""

    def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def _isolate():
    translation._store_path().unlink(missing_ok=True)
    codex.set_active_client(None)
    yield
    codex.set_active_client(None)
    translation._store_path().unlink(missing_ok=True)


def _connect(payloads: list[dict[str, Any]]) -> str:
    codex.set_active_client(codex.CodexAppServerClient(transport=ScriptedTransport(payloads)))
    codex.active_client().initialized = True
    response = client.post("/codex/sessions", json={"psalm_id": PSALM_ID, "purpose": "analysis"})
    assert response.status_code == 200, response.text
    return response.json()["session_id"]


def test_analysis_requires_a_connected_client() -> None:
    response = client.post(
        f"/codex/analysis/verses/{UNIT_ID}", json={"session_id": "cxs.nope"}
    )
    assert response.status_code == 400
    assert "not connected" in response.json()["detail"].lower()


def test_verse_analysis_writes_a_proposed_assessment_and_shows_in_the_table() -> None:
    session_id = _connect([_verse_payload()])

    response = client.post(
        f"/codex/analysis/verses/{UNIT_ID}", json={"session_id": session_id}
    )
    assert response.status_code == 200, response.text
    item = response.json()["assessment"]
    assert item["accuracy_rating"] == "adapted"
    assert item["status"] == "proposed"
    assert item["non_source_material"][0]["kind"] == "meter"

    table = client.get(f"/psalms/{PSALM_ID}/comparison-table").json()
    row = next(r for r in table["rows"] if UNIT_ID in r["unit_ids"])
    assert row["accuracy_rating"] == "adapted"
    assert row["literal_backbone"]
    assert row["stale"] is False


def test_psalm_analysis_endpoint_round_trips() -> None:
    session_id = _connect([_psalm_payload()])

    posted = client.post(
        f"/codex/analysis/psalms/{PSALM_ID}", json={"session_id": session_id}
    )
    assert posted.status_code == 200, posted.text
    assert posted.json()["analysis"]["summary"] == "The two ways."

    fetched = client.get(f"/psalms/{PSALM_ID}/analysis")
    assert fetched.status_code == 200
    record = fetched.json()["analysis"]
    assert record["guardrails"]["heading_attribution"]
    assert record["citations"] == ["BDB"]
    assert record["status"] == "proposed"


def test_analysis_is_absent_until_it_has_been_run() -> None:
    response = client.get(f"/psalms/{PSALM_ID}/analysis")
    assert response.status_code == 200
    assert response.json()["analysis"] is None


def test_invalid_analysis_output_is_rejected_without_writing() -> None:
    session_id = _connect([{"psalm_id": PSALM_ID, "summary": "incomplete"}])

    response = client.post(
        f"/codex/analysis/psalms/{PSALM_ID}", json={"session_id": session_id}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == translation.RUN_INVALID_OUTPUT
    assert body["analysis"] is None
    assert client.get(f"/psalms/{PSALM_ID}/analysis").json()["analysis"] is None


def test_the_comparison_table_reports_canonical_numbering() -> None:
    table = client.get(f"/psalms/{PSALM_ID}/comparison-table").json()

    # Supplied by the committed versification table, not by a model.
    assert table["canonical_numbering"]["mt"] == 1
    assert table["canonical_numbering"]["vulgate"] == [1]
