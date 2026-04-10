from app.llm.adapters.openai_compatible import OpenAICompatibleAdapter


class VllmAdapter(OpenAICompatibleAdapter):
    name = "vllm"
