"""The local model, over llama.cpp's OpenAI-compatible API, with thinking off.

Thinking is switched off for every call: with it on, one small check took
nearly two minutes, which is no use in a chat. Qwen under --jinja otherwise
spends its token budget in `reasoning_content` and returns empty content.
"""

from __future__ import annotations

import base64

import httpx


class TutorUnavailable(RuntimeError):
    """The model did not answer: down, too slow, or an empty reply."""


class LLM:
    def __init__(self, url: str, model: str = "local", timeout: float = 240.0):
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def chat(self, system: str, messages: list[dict], max_tokens: int = 900, temperature: float = 0.4) -> str:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "max_tokens": max_tokens,
            "temperature": temperature,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.url}/chat/completions", json=body)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"].get("content") or ""
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise TutorUnavailable(str(exc) or type(exc).__name__) from exc
        if not content.strip():
            raise TutorUnavailable("empty reply")
        return content.strip()


def image_part(data: bytes, mime: str = "image/jpeg") -> dict:
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(data).decode()}"}}
