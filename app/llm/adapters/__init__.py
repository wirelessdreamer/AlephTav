from __future__ import annotations

from app.core.errors import GenerationError
from app.llm.adapters.llamacpp import LlamaCppAdapter
from app.llm.adapters.ollama import OllamaAdapter
from app.llm.adapters.openai_compatible import OpenAICompatibleAdapter
from app.llm.adapters.vllm import VllmAdapter

ADAPTERS = {
    "llama.cpp": LlamaCppAdapter,
    "ollama": OllamaAdapter,
    "openai-compatible": OpenAICompatibleAdapter,
    "vllm": VllmAdapter,
}


def build_adapter(profile: dict[str, object]):
    adapter_name = str(profile.get("adapter", ""))
    adapter_cls = ADAPTERS.get(adapter_name)
    if adapter_cls is None:
        raise GenerationError(f"Unknown local model adapter: {adapter_name}")
    return adapter_cls(profile)
