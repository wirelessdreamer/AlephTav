from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib import error, request

from app.core.errors import GenerationError


@dataclass
class GenerationRequest:
    prompt: str
    contract: dict[str, Any]
    model: str
    seed: int
    temperature: float = 0.0
    max_tokens: int = 512
    system_prompt: str | None = None
    candidate_count: int = 1
    timeout_seconds: int = 30
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationResponse:
    payload: dict[str, Any]
    raw_text: str
    runtime_metadata: dict[str, Any] = field(default_factory=dict)


class BaseAdapter:
    name = "base"

    def __init__(self, profile: dict[str, Any]) -> None:
        self.profile = profile

    def health_check(self) -> dict[str, str]:
        return {"status": "ok", "adapter": self.name, "model": str(self.profile.get("model", ""))}

    def generate_json(self, generation_request: GenerationRequest) -> GenerationResponse:
        raise NotImplementedError

    def estimate_context(self, prompt: str) -> int:
        return len(prompt.split())

    def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        timeout_seconds: int = 30,
    ) -> dict[str, Any]:
        request_headers = {"Content-Type": "application/json"}
        request_headers.update(headers or {})
        http_request = request.Request(
            url=url,
            method="POST",
            headers=request_headers,
            data=json.dumps(payload).encode("utf-8"),
        )
        try:
            with request.urlopen(http_request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:  # pragma: no cover
            detail = exc.read().decode("utf-8", errors="replace")
            raise GenerationError(f"{self.name} request failed: HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:  # pragma: no cover
            raise GenerationError(f"{self.name} request failed: {exc.reason}") from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:  # pragma: no cover
            raise GenerationError(f"{self.name} returned invalid JSON") from exc

    def _parse_json_text(self, text: str) -> dict[str, Any]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start == -1 or end == -1 or end <= start:
                raise GenerationError(f"{self.name} response did not contain a JSON object")
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:  # pragma: no cover
                raise GenerationError(f"{self.name} response JSON could not be parsed") from exc
