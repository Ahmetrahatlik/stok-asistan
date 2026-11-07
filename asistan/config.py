import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Any OpenAI-compatible chat completions endpoint works: Ollama, LM Studio, OpenAI, Gemini.
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "ollama")
    llm_model: str = os.getenv("LLM_MODEL", "qwen2.5:7b")
    stok_api_url: str = os.getenv("STOK_API_URL", "http://localhost:8000")
    # Stok API needs a login for anything that changes data; reading works without it.
    stok_api_username: str = os.getenv("STOK_API_USERNAME", "")
    stok_api_password: str = os.getenv("STOK_API_PASSWORD", "")
    max_steps: int = int(os.getenv("AGENT_MAX_STEPS", "6"))


settings = Settings()
