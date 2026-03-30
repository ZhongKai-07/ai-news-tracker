import pytest
from unittest.mock import AsyncMock, patch
from app.services.llm_service import LLMService


@pytest.fixture
def llm_service():
    return LLMService(
        base_url="http://fake.api/v1",
        api_key="test-key",
        tier1_model="tier1",
        tier2_model="tier2",
        tier3_model="tier3",
        timeout=5,
        max_retries=1,
        circuit_breaker_threshold=3,
    )


def test_tier_to_model_mapping(llm_service):
    assert llm_service._get_model("tier1") == "tier1"
    assert llm_service._get_model("tier2") == "tier2"
    assert llm_service._get_model("tier3") == "tier3"


def test_circuit_breaker_initial_state(llm_service):
    assert llm_service._circuit_open is False
    assert llm_service._consecutive_failures == 0


@pytest.mark.asyncio
async def test_call_success(llm_service):
    mock_response = {"choices": [{"message": {"content": '{"result": "ok"}'}}]}
    with patch.object(llm_service, '_raw_call', new_callable=AsyncMock, return_value=mock_response):
        result = await llm_service.call("tier1", "test prompt")
        assert result == '{"result": "ok"}'


@pytest.mark.asyncio
async def test_call_retry_then_succeed(llm_service):
    call_count = 0

    async def fake_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Timeout")
        return {"choices": [{"message": {"content": "ok"}}]}

    with patch.object(llm_service, '_raw_call', side_effect=fake_call), \
         patch('app.services.llm_service.asyncio.sleep', new_callable=AsyncMock):
        result = await llm_service.call("tier1", "test")
        assert result == "ok"
        assert call_count == 2


@pytest.mark.asyncio
async def test_circuit_breaker_opens(llm_service):
    llm_service._circuit_breaker_threshold = 3

    async def always_fail(*args, **kwargs):
        raise Exception("API down")

    with patch.object(llm_service, '_raw_call', side_effect=always_fail), \
         patch('app.services.llm_service.asyncio.sleep', new_callable=AsyncMock):
        for _ in range(3):
            try:
                await llm_service.call("tier1", "test")
            except Exception:
                pass
    assert llm_service._circuit_open is True


@pytest.mark.asyncio
async def test_tier_degradation(llm_service):
    calls = []

    async def track_calls(model, messages, **kwargs):
        calls.append(model)
        if model == "tier2":
            raise Exception("Tier 2 down")
        return {"choices": [{"message": {"content": "degraded"}}]}

    with patch.object(llm_service, '_raw_call', side_effect=track_calls), \
         patch('app.services.llm_service.asyncio.sleep', new_callable=AsyncMock):
        result = await llm_service.call("tier2", "test")
        assert result == "degraded"
        assert "tier1" in calls
