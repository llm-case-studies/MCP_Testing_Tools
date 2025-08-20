import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from Smart_Bridge_POC.broker import Broker, Session
from Smart_Bridge_POC.process import StdioProcess
from Smart_Bridge_POC.filters import filters

@pytest.fixture
def mock_stdio_process():
    proc = AsyncMock(spec=StdioProcess)
    proc.start = AsyncMock()
    proc.write_json = AsyncMock()
    proc.read_json = AsyncMock()
    return proc

@pytest.fixture
def broker(mock_stdio_process):
    b = Broker(mock_stdio_process)
    # Patch filters.apply to control its behavior in tests
    b.filters = MagicMock()
    b.filters.apply = AsyncMock(side_effect=lambda d, s, m: m) # Default: pass message through
    return b

@pytest.mark.asyncio
async def test_broker_start(broker, mock_stdio_process):
    await broker.start()
    mock_stdio_process.start.assert_awaited_once()
    assert len(asyncio.all_tasks()) > 0 # Reader loop and pump tasks should be running

@pytest.mark.asyncio
async def test_broker_create_session(broker):
    session_id = broker.create_session()
    assert session_id in broker.sessions
    assert isinstance(broker.sessions[session_id], Session)

@pytest.mark.asyncio
async def test_broker_get_session(broker):
    session_id = broker.create_session()
    session = broker.get_session(session_id)
    assert session.session_id == session_id

    with pytest.raises(KeyError):
        broker.get_session("non_existent_session")

@pytest.mark.asyncio
async def test_broker_route_from_client_with_id(broker, mock_stdio_process):
    session_id = broker.create_session()
    payload = {"jsonrpc": "2.0", "method": "test", "id": 1}
    await broker.route_from_client(session_id, payload)

    broker.filters.apply.assert_awaited_once_with("client_to_server", session_id, payload)
    mock_stdio_process.write_json.assert_awaited_once_with(payload)
    assert broker.id_to_session[1] == session_id

@pytest.mark.asyncio
async def test_broker_route_from_client_filter_drops_message(broker, mock_stdio_process):
    broker.filters.apply.return_value = None # Simulate filter dropping message
    session_id = broker.create_session()
    payload = {"jsonrpc": "2.0", "method": "test", "id": 1}
    await broker.route_from_client(session_id, payload)

    broker.filters.apply.assert_awaited_once_with("client_to_server", session_id, payload)
    mock_stdio_process.write_json.assert_not_awaited()
    assert 1 not in broker.id_to_session

@pytest.mark.asyncio
async def test_broker_pump_response_to_correct_session(broker):
    session1_id = broker.create_session()
    session2_id = broker.create_session()

    # Simulate a request from session1
    req_payload = {"jsonrpc": "2.0", "method": "req", "id": 1}
    broker.id_to_session[1] = session1_id

    # Simulate a response from stdio process
    res_payload = {"jsonrpc": "2.0", "result": "ok", "id": 1}
    await broker.inbox.put(res_payload)

    # Allow pump to run
    await asyncio.sleep(0.01)

    # Verify session1 received the message, session2 did not
    assert not broker.sessions[session1_id].queue.empty()
    assert broker.sessions[session2_id].queue.empty()
    received_data = await broker.sessions[session1_id].queue.get()
    assert json.loads(received_data.decode().split("data: ")[1]) == res_payload
    assert 1 not in broker.id_to_session # ID should be popped

@pytest.mark.asyncio
async def test_broker_pump_notification_broadcast(broker):
    session1_id = broker.create_session()
    session2_id = broker.create_session()

    # Simulate a notification from stdio process
    notif_payload = {"jsonrpc": "2.0", "method": "notif"}
    await broker.inbox.put(notif_payload)

    # Allow pump to run
    await asyncio.sleep(0.01)

    # Verify both sessions received the message
    assert not broker.sessions[session1_id].queue.empty()
    assert not broker.sessions[session2_id].queue.empty()
    received_data1 = await broker.sessions[session1_id].queue.get()
    received_data2 = await broker.sessions[session2_id].queue.get()
    assert json.loads(received_data1.decode().split("data: ")[1]) == notif_payload
    assert json.loads(received_data2.decode().split("data: ")[1]) == notif_payload

@pytest.mark.asyncio
async def test_broker_send_sse(broker):
    session_id = broker.create_session()
    test_obj = {"message": "hello"}
    await broker._send(session_id, test_obj)

    assert not broker.sessions[session_id].queue.empty()
    data = await broker.sessions[session_id].queue.get()
    assert data == f"data: {json.dumps(test_obj, ensure_ascii=False)}\n\n".encode("utf-8")

@pytest.mark.asyncio
async def test_broker_send_websocket(broker):
    session_id = broker.create_session()
    mock_websocket = AsyncMock()
    broker.sessions[session_id].websockets.add(mock_websocket)

    test_obj = {"message": "ws_hello"}
    await broker._send(session_id, test_obj)

    mock_websocket.send_text.assert_awaited_once_with(json.dumps(test_obj, ensure_ascii=False))

@pytest.mark.asyncio
async def test_broker_send_websocket_disconnect(broker):
    session_id = broker.create_session()
    mock_websocket = AsyncMock()
    mock_websocket.send_text.side_effect = Exception("Simulated WS disconnect")
    broker.sessions[session_id].websockets.add(mock_websocket)

    test_obj = {"message": "ws_disconnect"}
    await broker._send(session_id, test_obj)

    assert mock_websocket not in broker.sessions[session_id].websockets

@pytest.mark.asyncio
async def test_broker_broadcast(broker):
    session1_id = broker.create_session()
    session2_id = broker.create_session()

    test_obj = {"broadcast": "message"}
    await broker.broadcast(test_obj)

    assert not broker.sessions[session1_id].queue.empty()
    assert not broker.sessions[session2_id].queue.empty()
    data1 = await broker.sessions[session1_id].queue.get()
    data2 = await broker.sessions[session2_id].queue.get()
    expected_data = f"data: {json.dumps(test_obj, ensure_ascii=False)}\n\n".encode("utf-8")
    assert data1 == expected_data
    assert data2 == expected_data
