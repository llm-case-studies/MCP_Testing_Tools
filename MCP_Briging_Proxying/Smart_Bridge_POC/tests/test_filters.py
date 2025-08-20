import pytest
import asyncio
import time
from Smart_Bridge_POC.filters import FilterChain, redact_secrets, add_bridge_meta

@pytest.fixture
def filter_chain():
    chain = FilterChain()
    # Clear built-in filters for isolated testing
    chain.filters = {}
    return chain

async def test_filter_chain_register_and_list(filter_chain):
    def dummy_filter(direction, session_id, msg): return msg
    filter_chain.register("test_filter", dummy_filter, enabled=True, description="A test filter")
    filters_info = filter_chain.list()
    assert len(filters_info) == 1
    assert filters_info[0].name == "test_filter"
    assert filters_info[0].enabled is True
    assert filters_info[0].description == "A test filter"

async def test_filter_chain_set_enabled(filter_chain):
    def dummy_filter(direction, session_id, msg): return msg
    filter_chain.register("test_filter", dummy_filter, enabled=True)
    assert filter_chain.filters["test_filter"]["enabled"] is True
    filter_chain.set_enabled("test_filter", False)
    assert filter_chain.filters["test_filter"]["enabled"] is False
    filter_chain.set_enabled("test_filter", True)
    assert filter_chain.filters["test_filter"]["enabled"] is True

    with pytest.raises(KeyError):
        filter_chain.set_enabled("non_existent_filter", True)

@pytest.mark.asyncio
async def test_filter_chain_apply_enabled_filter(filter_chain):
    async def uppercase_filter(direction, session_id, msg):
        return {k: v.upper() if isinstance(v, str) else v for k, v in msg.items()}

    filter_chain.register("uppercase", uppercase_filter, enabled=True)
    message = {"text": "hello", "value": 123}
    result = await filter_chain.apply("test_direction", "test_session", message)
    assert result == {"text": "HELLO", "value": 123}

@pytest.mark.asyncio
async def test_filter_chain_apply_disabled_filter(filter_chain):
    async def uppercase_filter(direction, session_id, msg):
        return {k: v.upper() if isinstance(v, str) else v for k, v in msg.items()}

    filter_chain.register("uppercase", uppercase_filter, enabled=False)
    message = {"text": "hello", "value": 123}
    result = await filter_chain.apply("test_direction", "test_session", message)
    assert result == message  # Should not be modified

@pytest.mark.asyncio
async def test_filter_chain_apply_dropping_filter(filter_chain):
    def dropping_filter(direction, session_id, msg): return None

    filter_chain.register("dropper", dropping_filter, enabled=True)
    message = {"text": "hello"}
    result = await filter_chain.apply("test_direction", "test_session", message)
    assert result is None

@pytest.mark.asyncio
async def test_filter_chain_apply_exception_filter(filter_chain):
    def exception_filter(direction, session_id, msg): raise ValueError("Test error")

    filter_chain.register("exception", exception_filter, enabled=True)
    message = {"text": "hello"}
    result = await filter_chain.apply("test_direction", "test_session", message)
    assert result == message  # Message should pass through if filter fails

@pytest.mark.asyncio
async def test_redact_secrets():
    message = {
        "text": "My API key is sk-1234567890abcdef1234567890abcdef",
        "data": {"token": "bearer_token_xyz"},
        "list": ["secret_key=abc", "no_secret"]
    }
    result = redact_secrets("test", "test_session", message)
    assert result["text"] == "My API key is [REDACTED]"
    assert result["data"]["token"] == "[REDACTED]"
    assert result["list"][0] == "[REDACTED]"
    assert result["list"][1] == "no_secret"

@pytest.mark.asyncio
async def test_add_bridge_meta():
    message = {"data": "some_data"}
    original_time = time.time()
    result = add_bridge_meta("client_to_server", "session123", message)
    assert "bridge_meta" in result
    assert "ts" in result["bridge_meta"]
    assert result["bridge_meta"]["ts"] >= original_time
    assert result["bridge_meta"]["direction"] == "client_to_server"
    assert result["bridge_meta"]["session"] == "session123"

    # Test with existing bridge_meta
    message_with_meta = {"data": "other_data", "bridge_meta": {"existing": "value"}}
    result_with_meta = add_bridge_meta("server_to_client", "session456", message_with_meta)
    assert result_with_meta["bridge_meta"]["existing"] == "value"
    assert result_with_meta["bridge_meta"]["direction"] == "server_to_client"
    assert result_with_meta["bridge_meta"]["session"] == "session456"
