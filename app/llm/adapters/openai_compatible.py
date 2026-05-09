from __future__ import annotations

import json
from typing import Any

from app.core.errors import GenerationError
from app.llm.base import BaseAdapter, GenerationRequest, GenerationResponse


class OpenAICompatibleAdapter(BaseAdapter):
    name = "openai-compatible"

    def health_check(self) -> dict[str, str]:
        return {
            "status": "ok",
            "adapter": self.name,
            "model": str(self.profile["model"]),
            "base_url": self._base_url(),
        }

    def _base_url(self) -> str:
        return str(self.profile["base_url"]).rstrip("/")

    def _auth_headers(self) -> dict[str, str] | None:
        api_key = str(self.profile.get("api_key", "") or "").strip()
        return {"Authorization": f"Bearer {api_key}"} if api_key else None

    def _messages(self, generation_request: GenerationRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        if generation_request.system_prompt:
            messages.append({"role": "system", "content": generation_request.system_prompt})
        messages.append({"role": "user", "content": generation_request.prompt})
        return messages

    def _response_formats(self, generation_request: GenerationRequest) -> list[dict[str, Any]]:
        return [{"type": "json_object"}]

    def _extra_payload(self, generation_request: GenerationRequest) -> dict[str, Any]:
        return {}

    def _request_payload(
        self,
        generation_request: GenerationRequest,
        response_format: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "model": generation_request.model,
            "messages": self._messages(generation_request),
            "temperature": generation_request.temperature,
            "seed": generation_request.seed,
            "n": generation_request.candidate_count,
            "max_tokens": generation_request.max_tokens,
            "response_format": response_format,
        }
        payload.update(self._extra_payload(generation_request))
        return payload

    def _parse_choice_content(self, choice: dict[str, Any]) -> tuple[dict[str, Any], str]:
        content = choice.get("message", {}).get("content", "")
        if isinstance(content, dict):
            return content, json.dumps(content, ensure_ascii=False)
        if not isinstance(content, str):
            raise GenerationError(f"{self.name} response content was not a string")
        return self._parse_json_text(content), content

    def generate_json(self, generation_request: GenerationRequest) -> GenerationResponse:
        last_error: GenerationError | None = None
        for response_format in self._response_formats(generation_request):
            try:
                response = self._post_json(
                    url=f"{self._base_url()}/chat/completions",
                    payload=self._request_payload(generation_request, response_format),
                    headers=self._auth_headers(),
                    timeout_seconds=generation_request.timeout_seconds,
                )
                choices = response.get("choices", [])
                if not choices:
                    raise GenerationError("No choices returned from local model")
                payload, raw_text = self._parse_choice_content(choices[0])
                return GenerationResponse(
                    payload=payload,
                    raw_text=raw_text,
                    runtime_metadata={
                        "finish_reason": choices[0].get("finish_reason"),
                        "usage": response.get("usage", {}),
                        "response_format": response_format.get("type"),
                    },
                )
            except GenerationError as error:
                last_error = error
        if last_error is None:  # pragma: no cover
            raise GenerationError("Local model request failed")
        raise last_error
