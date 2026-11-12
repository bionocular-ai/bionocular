import json

import httpx
import pytest
from pydantic import BaseModel, ValidationError
from tenacity import wait_none

from src.infrastructure import openrouter_structured_service as mod
from src.infrastructure.cost_calculator import CostCalculator
from src.infrastructure.openrouter_structured_service import (
    OpenRouterStructuredService,
    to_strict_schema,
)

MODEL = "deepseek/deepseek-v4.1-flash-1017"


class Inner(BaseModel):
    a: int
    b: str | None = None


class M(BaseModel):
    x: str
    inner: Inner
    items: list[Inner] = []


VALID = M(x="hi", inner=Inner(a=1)).model_dump_json()


@pytest.fixture(autouse=True)
def _no_wait(monkeypatch):
    monkeypatch.setattr(mod, "_WAIT", wait_none())


def _resp(content, status=200, **extra):
    body = {"choices": [{"message": {"content": content}}], **extra}
    return httpx.Response(status, json=body)


def _svc(responses, tmp_path=None, posted=None):
    seq = list(responses)

    def handler(request):
        if posted is not None:
            posted.append(json.loads(request.content))
        r = seq.pop(0)
        return r if isinstance(r, httpx.Response) else _resp(r)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenRouterStructuredService(
        MODEL,
        CostCalculator(),
        api_key="k",
        call_log_path=(tmp_path / "log.jsonl") if tmp_path else None,
        http=http,
    )


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def test_strict_schema_requires_all_and_closes_objects():
    objs = [n for n in _walk(to_strict_schema(M)) if "properties" in n]
    assert len(objs) >= 3  # M plus Inner twice
    for o in objs:
        assert o["required"] == sorted(o["properties"])
        assert o["additionalProperties"] is False


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError):
        OpenRouterStructuredService(MODEL, CostCalculator())


@pytest.mark.asyncio
async def test_request_body_and_parse():
    posted: list = []
    out = await _svc([VALID], posted=posted).generate_structured(
        "p", M, temperature=0.3, max_tokens=123
    )
    assert out == M(x="hi", inner=Inner(a=1))
    b = posted[0]
    assert b["model"] == MODEL
    assert b["response_format"]["type"] == "json_schema"
    assert b["response_format"]["json_schema"]["strict"] is True
    assert b["provider"] == {
        "order": ["deepinfra/fp8"],
        "quantizations": ["fp8"],
        "require_parameters": True,
    }
    assert b["reasoning"] == {"enabled": False}
    assert b["temperature"] == 0.3 and b["max_tokens"] == 123


@pytest.mark.asyncio
async def test_retries_empty_then_succeeds():
    posted: list = []
    await _svc(["", "  ", VALID], posted=posted).generate_structured("p", M)
    assert len(posted) == 3


@pytest.mark.asyncio
async def test_retries_429_and_5xx():
    posted: list = []
    svc = _svc([httpx.Response(429), httpx.Response(503), _resp(VALID)], posted=posted)
    await svc.generate_structured("p", M)
    assert len(posted) == 3


@pytest.mark.asyncio
async def test_raises_after_max_retries():
    posted: list = []
    svc = _svc(["{"] * 3, posted=posted)
    with pytest.raises(ValidationError):
        await svc.generate_structured("p", M, max_retries=3)
    assert len(posted) == 3


@pytest.mark.asyncio
async def test_call_log_records_provider_tokens_cost(tmp_path):
    usage = {
        "prompt_tokens": 1000,
        "completion_tokens": 500,
        "prompt_tokens_details": {"cached_tokens": 200},
    }
    svc = _svc([_resp(VALID, provider="DeepInfra", usage=usage)], tmp_path)
    await svc.generate_structured("p", M, operation="op")
    line = json.loads((tmp_path / "log.jsonl").read_text().splitlines()[0])
    assert line["provider"] == "DeepInfra"
    assert line["status"] == "ok"
    assert line["operation"] == "op" and line["model"] == MODEL
    assert (
        line["prompt_tokens"],
        line["completion_tokens"],
        line["cached_tokens"],
    ) == (
        1000,
        500,
        200,
    )
    assert line["cost_usd"] == CostCalculator().calculate_cost(1000, 500, MODEL)
    assert line["cost_usd"] == pytest.approx(0.000245)
    assert set(line) == {
        "ts", "operation", "model", "provider", "status",
        "prompt_tokens", "completion_tokens", "cached_tokens", "cost_usd", "error",
    }  # fmt: skip


@pytest.mark.asyncio
async def test_cache_methods():
    posted: list = []
    svc = _svc([VALID], posted=posted)
    assert await svc.create_context_cache("d", "s") is None
    assert await svc.delete_cache("x") is None
    await svc.cached_or_inline_generate(None, "DOC", "P", M)
    assert posted[0]["messages"] == [{"role": "user", "content": "DOC\n\nP"}]
