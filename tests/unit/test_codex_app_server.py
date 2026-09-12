"""Codex provider tests against a scripted app server.

No live ChatGPT/Codex account is required: every test drives a fake stdio
transport, which is what keeps this suite runnable in CI.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import Callable
from typing import Any

import pytest

from app.core.errors import GenerationError
from app.llm.adapters import ADAPTERS, build_adapter
from app.llm.adapters.codex_app_server import CodexAppServerAdapter
from app.llm.base import GenerationRequest
from app.services import codex_app_server_service as codex

pytestmark = pytest.mark.no_seeded_repo

Handler = Callable[[dict[str, Any], "FakeTransport"], list[dict[str, Any]]]


class FakeTransport:
    def __init__(self, handler: Handler) -> None:
        self.handler = handler
        self.sent: list[dict[str, Any]] = []
        self.closed = False
        self._inbox: deque[str] = deque()

    def send(self, message: dict[str, Any]) -> None:
        self.sent.append(message)
        for outgoing in self.handler(message, self):
            self._inbox.append(json.dumps(outgoing))

    def readline(self) -> str:
        if not self._inbox:
            return ""
        return self._inbox.popleft() + "\n"

    def close(self) -> None:
        self.closed = True

    def sent_methods(self) -> list[str]:
        return [m["method"] for m in self.sent if "method" in m]

    def params_for(self, method: str) -> dict[str, Any]:
        return next(m["params"] for m in self.sent if m.get("method") == method)


def _ok(message: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": message["id"], "result": result}


def _client(handler: Handler) -> codex.CodexAppServerClient:
    return codex.CodexAppServerClient(transport=FakeTransport(handler))


def test_connect_performs_the_initialize_handshake() -> None:
    def handler(message, _transport):
        return [_ok(message, {"userAgent": "codex/0.101.0"})]

    client = _client(handler)
    client.connect()

    assert client.initialized is True
    params = client.transport.params_for("initialize")
    assert params["clientInfo"]["name"] == codex.CLIENT_NAME


def test_start_thread_locks_the_turn_to_read_only_with_routed_approvals() -> None:
    def handler(message, _transport):
        return [_ok(message, {"threadId": "th-1"})]

    client = _client(handler)
    thread_id = client.start_thread(base_instructions="translation policy")

    assert thread_id == "th-1"
    params = client.transport.params_for("thread/start")
    assert params["sandbox"] == {"type": "readOnly"}
    assert params["approvalPolicy"] == "on-request"
    assert params["baseInstructions"] == "translation policy"


def test_run_turn_sends_the_output_schema_and_returns_the_final_message() -> None:
    contract = {"type": "object", "properties": {"candidates": {"type": "array"}}}

    def handler(message, _transport):
        if message.get("method") != "turn/start":
            return [_ok(message, {})]
        return [
            _ok(message, {"turnId": "turn-1"}),
            {
                "jsonrpc": "2.0",
                "method": "item/completed",
                "params": {"item": {"type": "agentMessage", "text": '{"candidates": []}'}},
            },
            {
                "jsonrpc": "2.0",
                "method": "turn/completed",
                "params": {"turnId": "turn-1", "usage": {"input_tokens": 11}},
            },
        ]

    client = _client(handler)
    result = client.run_turn("th-1", "translate", output_schema=contract, model="gpt-5-codex")

    assert result["text"] == '{"candidates": []}'
    assert result["turn_id"] == "turn-1"
    assert result["usage"] == {"input_tokens": 11}

    params = client.transport.params_for("turn/start")
    assert params["outputSchema"] == contract
    assert params["model"] == "gpt-5-codex"
    assert params["sandboxPolicy"] == {"type": "readOnly"}
    assert params["input"] == [{"type": "text", "data": {"text": "translate"}}]


@pytest.mark.parametrize(
    "approval_method",
    [
        "item/commandExecution/requestApproval",
        "item/fileChange/requestApproval",
        "execCommandApproval",
        "applyPatchApproval",
    ],
)
def test_translation_turn_denies_every_system_change_request(approval_method: str) -> None:
    """FR-7: command execution and file modification are denied and recorded."""

    def handler(message, _transport):
        if message.get("method") == "turn/start":
            return [
                _ok(message, {"turnId": "turn-1"}),
                {
                    "jsonrpc": "2.0",
                    "id": 9001,
                    "method": approval_method,
                    "params": {"command": ["rm", "-rf", "content"]},
                },
            ]
        # The client's denial response arrives here; only then does the turn end.
        if "result" in message and message.get("id") == 9001:
            return [
                {
                    "jsonrpc": "2.0",
                    "method": "turn/completed",
                    "params": {"turnId": "turn-1"},
                }
            ]
        return [_ok(message, {})]

    client = _client(handler)
    result = client.run_turn("th-1", "translate")

    denial = next(m for m in client.transport.sent if m.get("id") == 9001)
    assert denial["result"] == {"decision": "denied"}
    assert [event["method"] for event in client.denied_events] == [approval_method]
    assert result["text"] == ""


def test_turn_surfaces_a_server_error_instead_of_returning_partial_text() -> None:
    def handler(message, _transport):
        if message.get("method") != "turn/start":
            return [_ok(message, {})]
        return [
            _ok(message, {"turnId": "turn-1"}),
            {"jsonrpc": "2.0", "method": "error", "params": {"message": "rate limit reached"}},
        ]

    client = _client(handler)
    with pytest.raises(GenerationError, match="rate limit reached"):
        client.run_turn("th-1", "translate")


def test_disconnect_mid_turn_is_reported_as_a_generation_error() -> None:
    def handler(message, _transport):
        return [_ok(message, {"turnId": "turn-1"})] if message.get("method") == "turn/start" else []

    client = _client(handler)
    with pytest.raises(GenerationError, match="disconnected"):
        client.run_turn("th-1", "translate")


def test_status_reports_not_installed_when_codex_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(codex, "codex_executable", lambda: None)
    status = codex.describe_status(None)

    assert status["status"] == codex.STATUS_NOT_INSTALLED
    assert status["local_only"] is True


def test_status_reports_not_signed_in_without_asking_for_an_api_key(monkeypatch) -> None:
    monkeypatch.setattr(codex, "codex_executable", lambda: "/usr/bin/codex")

    def handler(message, _transport):
        return [_ok(message, {"authenticated": False})]

    client = _client(handler)
    client.initialized = True
    status = codex.describe_status(client)

    assert status["status"] == codex.STATUS_NOT_SIGNED_IN
    assert "api key" not in status["detail"].lower()


def test_ready_status_exposes_plan_but_never_credentials(monkeypatch) -> None:
    monkeypatch.setattr(codex, "codex_executable", lambda: "/usr/bin/codex")

    def handler(message, _transport):
        # The shape the live app server actually returns: mode and plan are
        # nested under "account", alongside the signed-in email.
        return [
            _ok(
                message,
                {
                    "account": {
                        "type": "chatgpt",
                        "email": "someone@example.com",
                        "planType": "pro",
                    },
                    "requiresOpenaiAuth": True,
                    "accessToken": "secret-token-value",
                    "refreshToken": "secret-refresh-value",
                },
            )
        ]

    client = _client(handler)
    client.initialized = True
    status = codex.describe_status(client)

    assert status["status"] == codex.STATUS_READY
    assert status["auth_mode"] == "chatgpt"
    assert status["plan_type"] == "pro"
    serialised = json.dumps(status)
    assert "secret-token-value" not in serialised
    assert "secret-refresh-value" not in serialised
    assert "accessToken" not in serialised
    # The email is in the account record but has no business in the panel.
    assert "someone@example.com" not in serialised


def test_signed_out_account_is_not_reported_as_ready(monkeypatch) -> None:
    monkeypatch.setattr(codex, "codex_executable", lambda: "/usr/bin/codex")

    def handler(message, _transport):
        return [_ok(message, {"account": None, "requiresOpenaiAuth": True})]

    client = _client(handler)
    client.initialized = True

    assert codex.describe_status(client)["status"] == codex.STATUS_NOT_SIGNED_IN


def test_transport_resolves_the_executable_through_path(monkeypatch) -> None:
    """Regression: Popen("codex") raises WinError 2 on Windows, where the real
    entry point is codex.CMD. The spawn must use the resolved path."""
    spawned: dict[str, object] = {}

    class FakePopen:
        def __init__(self, argv, **kwargs):
            spawned["argv"] = argv
            self.stdin = None
            self.stdout = None

        def poll(self):
            return 0

    monkeypatch.setattr(codex.shutil, "which", lambda name: r"C:\npm\codex.CMD")
    monkeypatch.setattr(codex.subprocess, "Popen", FakePopen)

    codex.StdioTransport("codex")

    assert spawned["argv"][0] == r"C:\npm\codex.CMD"
    assert spawned["argv"][1:] == ["app-server", "--listen", "stdio://"]


def test_client_reports_a_clear_error_when_codex_is_not_on_path(monkeypatch) -> None:
    monkeypatch.setattr(codex.shutil, "which", lambda name: None)
    client = codex.CodexAppServerClient()

    with pytest.raises(GenerationError, match="not found on PATH"):
        client.connect()


def test_adapter_is_registered_and_normalises_a_turn_into_a_generation_response() -> None:
    assert ADAPTERS["codex-app-server"] is CodexAppServerAdapter

    def handler(message, _transport):
        if message.get("method") == "thread/start":
            return [_ok(message, {"threadId": "th-9"})]
        if message.get("method") == "turn/start":
            return [
                _ok(message, {"turnId": "turn-9"}),
                {
                    "jsonrpc": "2.0",
                    "method": "item/completed",
                    "params": {
                        "item": {"type": "agentMessage", "text": '{"candidates": [{"text": "x"}]}'}
                    },
                },
                {"jsonrpc": "2.0", "method": "turn/completed", "params": {"turnId": "turn-9"}},
            ]
        return [_ok(message, {})]

    adapter = CodexAppServerAdapter({"adapter": "codex-app-server", "model": "gpt-5-codex"},
                                    client=_client(handler))
    response = adapter.generate_json(
        GenerationRequest(
            prompt="translate ps001.v001.a",
            contract={"type": "object"},
            model="gpt-5-codex",
            seed=7,
        )
    )

    assert response.payload == {"candidates": [{"text": "x"}]}
    assert response.runtime_metadata["provider"] == codex.PROVIDER_NAME
    assert response.runtime_metadata["thread_id"] == "th-9"
    assert response.runtime_metadata["turn_id"] == "turn-9"


def test_build_adapter_rejects_an_unknown_adapter_but_accepts_codex() -> None:
    assert isinstance(
        build_adapter({"adapter": "codex-app-server"}),
        CodexAppServerAdapter,
    )
    with pytest.raises(GenerationError):
        build_adapter({"adapter": "not-a-real-adapter"})
