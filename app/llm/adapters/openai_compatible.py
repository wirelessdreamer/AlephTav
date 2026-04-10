from __future__ import annotations

from app.core.errors import GenerationError
from app.llm.base import BaseAdapter, GenerationRequest, GenerationResponse

class OpenAICompatibleAdapter(BaseAdapter):
    name = "openai-compatible"

    def health_check(self) -> dict[str, str]:
        return {
            "status": "ok",
            "adapter": self.name,
            "model": self.profile["model"],
            "base_url": self.profile["base_url"].rstrip("/"),
        }

    def generate_json(self, generation_request: GenerationRequest) -> GenerationResponse:
        base_url = self.profile["base_url"].rstrip("/")
        api_key = self.profile.get("api_key", "")
        messages = []
        if generation_request.system_prompt:
            messages.append({"role": "system", "content": generation_request.system_prompt})
        messages.append({"role": "user", "content": generation_request.prompt})
        response = self._post_json(
            url=f"{base_url}/chat/completions",
            payload={
                "model": generation_request.model,
                "messages": messages,
                "temperature": generation_request.temperature,
                "seed": generation_request.seed,
                "n": generation_request.candidate_count,
                "max_tokens": generation_request.max_tokens,
                "response_format": {"type": "json_object"},
            },
            headers={"Authorization": f"Bearer {api_key}"} if api_key else None,
            timeout_seconds=generation_request.timeout_seconds,
        )
        choices = response.get("choices", [])
        if not choices:
            raise GenerationError("No choices returned from local model")
        content = choices[0]["message"]["content"]
        return GenerationResponse(
            payload=self._parse_json_text(content),
            raw_text=content,
            runtime_metadata={
                "finish_reason": choices[0].get("finish_reason"),
                "usage": response.get("usage", {}),
            },
        )
