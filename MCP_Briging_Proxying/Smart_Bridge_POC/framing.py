
import asyncio
import json
from typing import Any, Dict

CRLF = b"\r\n"
HEADER_SEP = CRLF + CRLF

async def read_exact(stream: asyncio.StreamReader, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = await stream.read(n - len(buf))
        if not chunk:
            raise EOFError("Unexpected EOF while reading framed body")
        buf.extend(chunk)
    return bytes(buf)

async def read_headers(stream: asyncio.StreamReader) -> Dict[str, str]:
    data = bytearray()
    while True:
        ch = await stream.read(1)
        if not ch:
            raise EOFError("Unexpected EOF while reading headers")
        data.extend(ch)
        if data.endswith(HEADER_SEP):
            break
    header_text = data[:-4].decode("ascii", errors="strict")
    headers: Dict[str, str] = {}
    for line in header_text.split("\r\n"):
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Malformed header line: {line!r}")
        k, v = line.split(":", 1)
        headers[k.strip().lower()] = v.strip()
    return headers

async def read_framed_json(stream: asyncio.StreamReader) -> Dict[str, Any]:
    headers = await read_headers(stream)
    if "content-length" not in headers:
        raise ValueError("Missing Content-Length header")
    try:
        length = int(headers["content-length"])
    except Exception as e:
        raise ValueError("Bad Content-Length") from e
    body = await read_exact(stream, length)
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Bad JSON payload: {e}")

def encode_framed_json(obj: Dict[str, Any]) -> bytes:
    data = json.dumps(obj, separators=( ",", ":"), ensure_ascii=False).encode("utf-8")
    header = f"Content-Length: {len(data)}\r\n\r\n".encode("ascii")
    return header + data
