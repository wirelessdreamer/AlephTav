"""Codex App Server adapter (FR-1, FR-5).

Normalises a Codex turn into the same ``GenerationResponse`` the local-model
adapters return, so Codex output flows through the existing generation and
rendering-creation pipeline unchanged.
"""

from __future__ import annotations

from typing import Any

from app.llm.base import BaseAdapter, GenerationRequest, GenerationResponse
from app.services import codex_app_server_service


class CodexAppServerAdapter(BaseAdapter):
    name = "codex-app-server"

    def __init__(
        self,
        profile: dict[str, Any],
        client: codex_app_server_service.CodexAppServerClient | None = None,
    ) -> None:
        super().__init__(profile)
        self._client = client

    def _ensure_client(self) -> codex_app_server_service.CodexAppServerClient:
        if self._client is None:
            self._client = codex_app_server_service.CodexAppServerClient()
            self._client.connect()
        return self._client

    def health_check(self) -> dict[str, str]:
        status = codex_app_server_service.describe_status(self._client)
        ready = status["status"] == codex_app_server_service.STATUS_READY
        return {
            "status": "ok" if ready else "error",
            "adapter": self.name,
            "model": str(self.profile.get("model", "")),
            "codex_status": status["status"],
        }

    def generate_json(self, generation_request: GenerationRequest) -> GenerationResponse:
        client = self._ensure_client()
        thread_id = self.profile.get("thread_id") or client.start_thread(
            base_instructions=generation_request.system_prompt or None
        )
        result = client.run_turn(
            thread_id=str(thread_id),
            text=generation_request.prompt,
            # The generation contract constrains the final message, so invalid
            # shapes are caught before anything reaches the rendering store.
            output_schema=generation_request.contract,
            model=generation_request.model or None,
        )
        raw_text = result.get("text", "")
        return GenerationResponse(
            payload=self._parse_json_text(raw_text),
            raw_text=raw_text,
            runtime_metadata={
                "provider": codex_app_server_service.PROVIDER_NAME,
                "thread_id": thread_id,
                "turn_id": result.get("turn_id"),
                "usage": result.get("usage") or {},
                "denied_events": list(client.denied_events),
            },
        )
