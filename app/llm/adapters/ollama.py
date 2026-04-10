from __future__ import annotations

from app.llm.base import BaseAdapter, GenerationRequest, GenerationResponse

class OllamaAdapter(BaseAdapter):
    name = "ollama"

    def generate_json(self, generation_request: GenerationRequest) -> GenerationResponse:
        base_url = self.profile["base_url"].rstrip("/")
        response = self._post_json(
            url=f"{base_url}/api/generate",
            payload={
                "model": generation_request.model,
                "prompt": generation_request.prompt,
                "system": generation_request.system_prompt or "",
                "stream": False,
                "format": generation_request.contract,
                "options": {
                    "seed": generation_request.seed,
                    "temperature": generation_request.temperature,
                    "num_predict": generation_request.max_tokens,
                },
            },
            timeout_seconds=generation_request.timeout_seconds,
        )
        raw_text = response.get("response", "")
        return GenerationResponse(
            payload=self._parse_json_text(raw_text),
            raw_text=raw_text,
            runtime_metadata={
                "eval_count": response.get("eval_count"),
                "prompt_eval_count": response.get("prompt_eval_count"),
            },
        )
