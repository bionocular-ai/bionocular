"""Structured LLM backend that calls DeepSeek V4.1 Flash through OpenRouter.

Implements ``StructuredLLMService`` plus the context-cache methods the harness
expects. OpenRouter has no explicit cache handle, so the cache methods are
no-ops and the document is re-sent inline on every call.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from src.domain.structured_llm_interfaces import StructuredLLMService, T
from src.infrastructure.cost_calculator import CostCalculator
from src.infrastructure.gemini_service import _inline_pydantic_schema

URL = "https://openrouter.ai/api/v1/chat/completions"
PROVIDER = {
    "order": ["deepinfra/fp8"],
    "quantizations": ["fp8"],
    "require_parameters": True,
}
_WAIT = wait_random_exponential(max=60)  # module-level so tests can zero it


class _Retryable(Exception):
    """429, 5xx or empty content."""


def to_strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Inline refs, then make every object closed with all properties required."""
    schema = _inline_pydantic_schema(model)

    def _fix(node: Any) -> None:
        if isinstance(node, dict):
            if "properties" in node:
                node["required"] = sorted(node["properties"])
                node["additionalProperties"] = False
            for v in node.values():
                _fix(v)
        elif isinstance(node, list):
            for v in node:
                _fix(v)

    _fix(schema)
    return schema


class OpenRouterStructuredService(StructuredLLMService):
    def __init__(
        self,
        model: str,
        cost_calculator: CostCalculator,
        api_key: str | None = None,
        call_log_path: Path | None = None,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        self._key = key
        self.model = model
        self.cost_calculator = cost_calculator
        self.call_log_path = call_log_path
        self._http = http or httpx.AsyncClient(timeout=300)

    def _log(self, **fields: Any) -> None:
        if self.call_log_path is None:
            return
        row = {"ts": datetime.now(timezone.utc).isoformat(), **fields}
        with self.call_log_path.open("a") as f:
            f.write(json.dumps(row) + "\n")

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type[T],
        temperature: float = 0.0,
        max_tokens: int = 4096,
        model_name: str | None = None,
        operation: str = "structured_extraction",
        attribute_type: str | None = None,
        max_retries: int = 6,
        cache_id: str | None = None,
    ) -> T:
        model = model_name or self.model
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_schema.__name__,
                    "strict": True,
                    "schema": to_strict_schema(response_schema),
                },
            },
            "provider": PROVIDER,
            "reasoning": {"enabled": False},
        }

        async def _attempt() -> T:
            prompt_tokens = completion_tokens = cached = 0
            provider = None
            status, error = "ok", None
            try:
                resp = await self._http.post(
                    URL, json=body, headers={"Authorization": f"Bearer {self._key}"}
                )
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise _Retryable(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                data = resp.json()
                provider = data.get("provider")
                usage = data.get("usage") or {}
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                cached = (usage.get("prompt_tokens_details") or {}).get(
                    "cached_tokens", 0
                )
                content = (data["choices"][0]["message"].get("content") or "").strip()
                if not content:
                    raise _Retryable("empty content")
                return response_schema.model_validate_json(content)
            except Exception as e:
                status, error = "error", f"{type(e).__name__}: {e}"
                raise
            finally:
                cost = self.cost_calculator.calculate_cost(
                    prompt_tokens, completion_tokens, model
                )
                self._log(
                    operation=operation,
                    model=model,
                    provider=provider,
                    status=status,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    cached_tokens=cached,
                    cost_usd=cost,
                    error=error,
                )
                if prompt_tokens or completion_tokens:
                    self.cost_calculator.record_api_call(
                        prompt_tokens,
                        completion_tokens,
                        model,
                        operation,
                        attribute_type,
                        success=status == "ok",
                        error_message=error,
                    )

        async for attempt in AsyncRetrying(
            wait=_WAIT,
            stop=stop_after_attempt(max_retries),
            retry=retry_if_exception_type(
                (_Retryable, httpx.TransportError, ValidationError)
            ),
            reraise=True,
        ):
            with attempt:
                return await _attempt()
        raise AssertionError("unreachable")

    async def create_context_cache(
        self, doc_text: str, system_instruction: str, ttl_seconds: int = 3600
    ) -> None:
        return None

    async def cached_or_inline_generate(
        self,
        cache_id: str | None,
        doc_text: str,
        prompt: str,
        response_schema: type[T],
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> T:
        return await self.generate_structured(
            f"{doc_text}\n\n{prompt}",
            response_schema,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def delete_cache(self, cache_id: str | None) -> None:
        return None
