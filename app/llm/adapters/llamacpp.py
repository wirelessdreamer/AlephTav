from __future__ import annotations

from typing import Any

from app.llm.adapters.openai_compatible import OpenAICompatibleAdapter
from app.llm.base import GenerationRequest
from app.services import llama_runtime_service


class LlamaCppAdapter(OpenAICompatibleAdapter):
    name = "llama.cpp"

    def health_check(self) -> dict[str, str]:
        if llama_runtime_service.is_managed_profile(self.profile):
            llama_runtime_service.ensure_runtime(self.profile)
        return super().health_check()

    def _response_formats(self, generation_request: GenerationRequest) -> list[dict[str, Any]]:
        contract = generation_request.contract or {}
        preferred_mode = str(self.profile.get("response_format_mode", "json_schema"))
        fallback_mode = str(self.profile.get("response_format_fallback", "json_object"))

        formats: list[dict[str, Any]] = [self._response_format_for_mode(preferred_mode, contract)]
        if fallback_mode and fallback_mode != preferred_mode:
            formats.append(self._response_format_for_mode(fallback_mode, contract))
        return formats

    def _response_format_for_mode(self, mode: str, contract: dict[str, Any]) -> dict[str, Any]:
        if mode == "json_object":
            payload: dict[str, Any] = {"type": "json_object"}
            if contract:
                payload["schema"] = contract
            return payload
        if mode == "json_schema":
            return {"type": "json_schema", "schema": contract}
        return {"type": "json_object"}

    def _extra_payload(self, generation_request: GenerationRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for field in (
            "top_k",
            "top_p",
            "min_p",
            "repeat_penalty",
            "presence_penalty",
            "frequency_penalty",
            "mirostat",
            "mirostat_tau",
            "mirostat_eta",
            "cache_prompt",
            "ignore_eos",
        ):
            if field in self.profile:
                payload[field] = self.profile[field]

        stop = self.profile.get("stop")
        if stop:
            payload["stop"] = stop

        return payload

    def generate_json(self, generation_request: GenerationRequest):
        if llama_runtime_service.is_managed_profile(self.profile):
            llama_runtime_service.ensure_runtime(self.profile)
        return super().generate_json(generation_request)
