from typing import Any, Protocol

import httpx


class ChatModel(Protocol):
    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Returns one assistant message: {"role": "assistant", "content": ..., "tool_calls": [...]}."""


class OpenAICompatibleModel:
    """Talks to any server that implements the OpenAI chat completions API."""

    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 60.0):
        self.model = model
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def complete(self, messages, tools):
        response = self.client.post(
            "/chat/completions",
            json={"model": self.model, "messages": messages, "tools": tools, "temperature": 0},
        )
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        return {
            "role": "assistant",
            "content": message.get("content"),
            "tool_calls": message.get("tool_calls") or [],
        }
