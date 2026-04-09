from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class GenerationResponse:
    payload: dict[str, Any]


class BaseAdapter:
    name = "base"

    def health_check(self) -> dict[str, str]:
        return {"status": "ok", "adapter": self.name}

    def generate_json(self, prompt: str, contract: dict[str, Any]) -> GenerationResponse:
        return GenerationResponse(payload={"prompt": prompt, "contract": contract, "adapter": self.name})

    def estimate_context(self, prompt: str) -> int:
        return len(prompt.split())
