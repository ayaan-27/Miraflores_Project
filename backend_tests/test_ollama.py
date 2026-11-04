"""Ollama protocol/error tests use an explicit mocked HTTP transport, not inference."""

import json

import httpx
import pytest
from pydantic import ValidationError

from agent_workspace.api import create_app
from agent_workspace.model import configured_model
from agent_workspace.models import AgentDecision
from agent_workspace.ollama_model import OllamaModel


@pytest.mark.asyncio
async def test_ollama_uses_schema_and_available_actions_and_validates_response(monkeypatch):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:3b")
    captured = []

    def respond(request):
        payload = json.loads(request.content)
        captured.append(payload)
        return httpx.Response(200, json={
            "message": {"content": json.dumps({"action": "lookup_receiving", "purpose": "Check the quantity actually received.", "query": ""})},
            "done_reason": "stop", "prompt_eval_count": 100, "eval_count": 30,
        })

    model = OllamaModel(client=httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    try:
        result = await model.structured("Choose the next tool.", {"invoice": "INV-2048"}, AgentDecision, allowed_actions=["lookup_receiving"], max_tokens=220)
        assert result.action == "lookup_receiving"
        payload = captured[0]
        assert payload["format"]["properties"]["action"]["enum"] == ["lookup_receiving"]
        assert payload["format"]["additionalProperties"] is False
        assert payload["options"]["num_predict"] == 220
        assert payload["stream"] is False
        assert json.loads(payload["messages"][1]["content"])["invoice"] == "INV-2048"
        assert "untrusted data" in payload["messages"][0]["content"]
        assert model.last_usage["completion_tokens"] == 30
    finally:
        await model.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("body,match", [
    ({"message": {"content": "{bad json"}}, "Invalid JSON"),
    ({"message": {"content": '{"action":"approve_payment","purpose":"Skip review"}'}}, "action"),
    ({"message": {"content": "{}"}, "done_reason": "length"}, "token limit"),
    ({"unexpected": True}, "invalid response"),
])
async def test_ollama_rejects_malformed_truncated_and_invalid_actions(body, match):
    model = OllamaModel(client=httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=body))))
    try:
        with pytest.raises((ValueError, ValidationError), match=match):
            await model.structured("Choose a tool.", {}, AgentDecision)
    finally:
        await model.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("status,models,ready", [
    (200, [{"name": "qwen2.5:3b"}], True),
    (200, [{"name": "different-model:latest"}], False),
    (503, [], False),
])
async def test_health_checks_actual_ollama_model_and_blocks_missing_model(tmp_path, monkeypatch, status, models, ready):
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:3b")
    transport = httpx.MockTransport(lambda request: httpx.Response(status, json={"models": models}))
    model = OllamaModel(client=httpx.AsyncClient(transport=transport))
    app = create_app(model=model, data_dir=tmp_path)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            health = (await client.get("/api/health")).json()
            assert health["mode"] == "ollama_local"
            assert health["model_ready"] is ready
            assert health["model_api_key_required"] is False
            if not ready:
                assert health["model_setup_message"]
                response = await client.post("/api/runs", json={"case_id": "partial-delivery"})
                assert response.status_code == 409
                assert (await client.get("/api/runs")).json()["runs"] == []


@pytest.mark.asyncio
async def test_unavailable_ollama_stops_inference_without_fallback():
    def unavailable(request):
        raise httpx.ConnectError("Test-only refused connection.", request=request)

    model = OllamaModel(client=httpx.AsyncClient(transport=httpx.MockTransport(unavailable)))
    try:
        assert await model.is_ready() is False
        assert "Ollama is not reachable" in model.readiness_error
        with pytest.raises(ValueError, match="Ollama inference is unavailable"):
            await model.structured("Choose a tool.", {}, AgentDecision)
    finally:
        await model.aclose()


@pytest.mark.asyncio
async def test_provider_selection_is_explicit(monkeypatch):
    monkeypatch.delenv("LEDGERLENS_MODEL_PROVIDER", raising=False)
    model = configured_model()
    assert isinstance(model, OllamaModel)
    await model.aclose()
    monkeypatch.setenv("LEDGERLENS_MODEL_PROVIDER", "llama_cpp")
    assert configured_model().mode == "local_llm"
    monkeypatch.setenv("LEDGERLENS_MODEL_PROVIDER", "unknown")
    with pytest.raises(ValueError, match="must be ollama or llama_cpp"):
        configured_model()
