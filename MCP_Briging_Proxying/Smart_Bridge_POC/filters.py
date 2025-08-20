from __future__ import annotations
import asyncio
import logging
import re
import time
from typing import Any, Callable, Dict, List, Optional

try:
    from .models import FilterInfo
except ImportError:
    from models import FilterInfo

logger = logging.getLogger("stdio-gateway")

FilterFunc = Callable[[str, str, Dict[str, Any]], asyncio.Future]

class FilterChain:
    def __init__(self):
        self.filters: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str, func: Callable[[str, str, Dict[str, Any]], Any], *, enabled: bool = True, description: str = ""):
        self.filters[name] = {"func": func, "enabled": enabled, "description": description}

    def set_enabled(self, name: str, enabled: bool):
        if name not in self.filters:
            raise KeyError(name)
        self.filters[name]["enabled"] = enabled

    def list(self) -> List[FilterInfo]:
        out: List[FilterInfo] = []
        for n, meta in self.filters.items():
            out.append(FilterInfo(name=n, enabled=bool(meta["enabled"]), description=meta.get("description")))
        return out

    async def apply(self, direction: str, session_id: str, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        obj = message
        for n, meta in self.filters.items():
            if not meta["enabled"]:
                continue
            func = meta["func"]
            try:
                res = func(direction, session_id, obj)
                if asyncio.iscoroutine(res):
                    res = await res
                if res is None:  # dropped by filter
                    logger.info("Message dropped by filter %s", n)
                    return None
                obj = res
            except Exception:
                logger.exception("Filter %s failed; passing message through", n)
        return obj

filters = FilterChain()

# Built-in: redact secrets in strings
SECRET_PATTERNS = [
    re.compile(r"(?i)(?:api|secret|access|bearer)[-_ ]?(?:key|token)\s*[:=]\s*[A-Za-z0-9._-]{12,}"),
    re.compile(r"(?i)sk-[A-Za-z0-9]{20,}"),
]

def _walk_strings(value: Any, fn: Callable[[str], str]) -> Any:
    if isinstance(value, str):
        return fn(value)
    if isinstance(value, list):
        return [_walk_strings(v, fn) for v in value]
    if isinstance(value, dict):
        return {k: _walk_strings(v, fn) for k, v in value.items()}
    return value


def redact_secrets(direction: str, session_id: str, msg: Dict[str, Any]) -> Dict[str, Any]:
    def scrub(s: str) -> str:
        out = s
        for pat in SECRET_PATTERNS:
            out = pat.sub("[REDACTED]", out)
        return out
    return _walk_strings(msg, scrub)

filters.register("redact_secrets", redact_secrets, description="Masks common API keys/tokens in all string fields")

# Built-in: add bridge meta (timestamps & direction)

def add_bridge_meta(direction: str, session_id: str, msg: Dict[str, Any]) -> Dict[str, Any]:
    meta = msg.get("bridge_meta", {}) if isinstance(msg, dict) else {}
    meta.update({"ts": time.time(), "direction": direction, "session": session_id})
    if isinstance(msg, dict):
        msg["bridge_meta"] = meta
    return msg

filters.register("add_bridge_meta", add_bridge_meta, enabled=False, description="Attach bridge_meta with ts/direction/session")
