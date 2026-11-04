"""Ollama transport for the same extraction, tool-planning, and verifier prompts."""

from __future__ import annotations

import asyncio
import json
import os
from typing import TypeVar
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel

from .model import BOUNDARY, LocalModel


T = TypeVar("T", bound=BaseModel)


class OllamaModel(LocalModel):
    """Reuse workflow tasks while replacing only the inference transport."""

    mode = "ollama_local"

    def __init__(self, *, client: httpx.AsyncClient | None = None):
        self.model_id = os.environ.get("OLLAMA_MODEL", "qwen2.5:3b")
        self.base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
        parsed = urlsplit(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("OLLAMA_BASE_URL must be an HTTP(S) server URL without credentials, query, or fragment.")
        self.name = f"{self.model_id} · Ollama"
        self._client = client or httpx.AsyncClient(timeout=httpx.Timeout(600, connect=5))
        self._lock = asyncio.Lock()
        self._ready = False
        self.last_usage = {}
        self.readiness_error = "Ollama has not been checked yet."

    @property
    def available(self) -> bool:
        return self._ready

    async def is_ready(self) -> bool:
        try:
            response = await self._client.get(f"{self.base_url}/api/tags", timeout=3)
            response.raise_for_status()
            names = {
                item.get("name", item.get("model", ""))
                for item in response.json()["models"]
            }
            normalized = self.model_id if ":" in self.model_id else self.model_id + ":latest"
            self._ready = self.model_id in names or normalized in names
            self.readiness_error = "" if self._ready else f"Ollama is running, but the selected model is missing. Run: ollama pull {self.model_id}"
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            self._ready = False
            self.readiness_error = "Ollama is not reachable. Start the Ollama application or run ollama serve, then refresh this connection."
        return self._ready

    async def structured(self, system: str, data: dict, schema: type[T], *, allowed_actions=None, max_tokens=1800) -> T:
        json_schema = schema.model_json_schema()
        if allowed_actions:
            json_schema["properties"]["action"]["enum"] = allowed_actions
        async with self._lock:
            try:
                response = await self._client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model_id,
                        "stream": False,
                        "messages": [
                            {"role": "system", "content": BOUNDARY + "\n" + system + "\nJSON schema: " + json.dumps(json_schema)},
                            {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
                        ],
                        "format": json_schema,
                        "options": {"temperature": 0, "seed": 42, "num_ctx": 8192, "num_predict": max_tokens},
                        "keep_alive": "10m",
                    },
                )
                response.raise_for_status()
            except httpx.TimeoutException as error:
                raise ValueError("Ollama inference timed out. The case checkpoint is retained; check the local model and retry.") from error
            except httpx.HTTPError as error:
                self._ready = False
                raise ValueError(f"Ollama inference is unavailable. Check that Ollama is running and that ollama pull {self.model_id} completed, then retry.") from error
            try:
                result = response.json()
                content = result["message"]["content"]
                if not isinstance(content, str):
                    raise TypeError("Expected model-generated JSON text.")
            except (ValueError, KeyError, TypeError) as error:
                raise ValueError("Ollama returned an invalid response; no model output was accepted.") from error
            if result.get("done_reason") == "length":
                raise ValueError("The model response reached its token limit; incomplete output was rejected.")
            self.last_usage = {
                "prompt_tokens": result.get("prompt_eval_count", 0),
                "completion_tokens": result.get("eval_count", 0),
                "inference_ms": result.get("eval_duration", 0) / 1_000_000,
            }
            return schema.model_validate_json(content)

    async def aclose(self):
        await self._client.aclose()
