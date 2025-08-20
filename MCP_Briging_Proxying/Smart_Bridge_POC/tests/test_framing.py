import pytest
import asyncio
import json
from io import BytesIO
from Smart_Bridge_POC.framing import read_exact, read_headers, read_framed_json, encode_framed_json

@pytest.mark.asyncio
async def test_read_exact():
    stream = asyncio.StreamReader()
    stream.feed_data(b"hello")
    stream.feed_eof()
    data = await read_exact(stream, 5)
    assert data == b"hello"

    stream = asyncio.StreamReader()
    stream.feed_data(b"hello world")
    stream.feed_eof()
    data = await read_exact(stream, 5)
    assert data == b"hello"

    stream = asyncio.StreamReader()
    stream.feed_data(b"hi")
    stream.feed_eof()
    with pytest.raises(EOFError):
        await read_exact(stream, 5)

@pytest.mark.asyncio
async def test_read_headers():
    stream = asyncio.StreamReader()
    stream.feed_data(b"Content-Length: 5\r\n\r\n")
    stream.feed_eof()
    headers = await read_headers(stream)
    assert headers == {"content-length": "5"}

    stream = asyncio.StreamReader()
    stream.feed_data(b"Content-Type: application/json\r\nContent-Length: 10\r\n\r\n")
    stream.feed_eof()
    headers = await read_headers(stream)
    assert headers == {"content-type": "application/json", "content-length": "10"}

    stream = asyncio.StreamReader()
    stream.feed_data(b"Content-Length: 5\r\n")
    stream.feed_eof()
    with pytest.raises(EOFError):
        await read_headers(stream)

    stream = asyncio.StreamReader()
    stream.feed_data(b"Invalid-Header\r\n\r\n")
    stream.feed_eof()
    with pytest.raises(ValueError, match="Malformed header line"):
        await read_headers(stream)

@pytest.mark.asyncio
async def test_read_framed_json():
    stream = asyncio.StreamReader()
    stream.feed_data(b"Content-Length: 15\r\n\r\n{\"key\":\"value\"}")
    stream.feed_eof()
    data = await read_framed_json(stream)
    assert data == {"key": "value"}

    stream = asyncio.StreamReader()
    stream.feed_data(b"Content-Length: 5\r\n\r\nhello")
    stream.feed_eof()
    with pytest.raises(ValueError, match="Bad JSON payload"):
        await read_framed_json(stream)

    stream = asyncio.StreamReader()
    stream.feed_data(b"Invalid-Header: 10\r\n\r\n{}")
    stream.feed_eof()
    with pytest.raises(ValueError, match="Missing Content-Length header"):
        await read_framed_json(stream)

def test_encode_framed_json():
    obj = {"test": "data"}
    encoded = encode_framed_json(obj)
    expected_data = json.dumps(obj, separators=( ",", ":"), ensure_ascii=False).encode("utf-8")
    expected_header = f"Content-Length: {len(expected_data)}\r\n\r\n".encode("ascii")
    assert encoded == expected_header + expected_data

    obj_unicode = {"key": "你好"}
    encoded_unicode = encode_framed_json(obj_unicode)
    expected_data_unicode = json.dumps(obj_unicode, separators=( ",", ":"), ensure_ascii=False).encode("utf-8")
    expected_header_unicode = f"Content-Length: {len(expected_data_unicode)}\r\n\r\n".encode("ascii")
    assert encoded_unicode == expected_header_unicode + expected_data_unicode
