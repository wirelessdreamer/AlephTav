from app.llm.adapters.openai_compatible import OpenAICompatibleAdapter


class LlamaCppAdapter(OpenAICompatibleAdapter):
    name = "llama.cpp"
