"""Shared Redis-backed sliding-window rate limiting with bounded fallback."""

from __future__ import annotations

import hashlib
import logging
import secrets
import threading
import time
from collections import OrderedDict, deque
from typing import Any

_MAX_FALLBACK_KEYS = 20_000
_FALLBACK_LOCK = threading.Lock()
_FALLBACK_WINDOWS: OrderedDict[str, deque[float]] = OrderedDict()
_LOGGER = logging.getLogger(__name__)
_REDIS_FALLBACK_WARNING_EMITTED = False

_SLIDING_WINDOW_SCRIPT = """
local now_parts = redis.call('TIME')
local now_ms = tonumber(now_parts[1]) * 1000 + math.floor(tonumber(now_parts[2]) / 1000)
local window_ms = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now_ms - window_ms)
local count = redis.call('ZCARD', KEYS[1])
if count >= limit then
  local first = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  local retry_ms = window_ms
  if first[2] then retry_ms = tonumber(first[2]) + window_ms - now_ms end
  return {0, math.max(1, math.ceil(retry_ms / 1000))}
end
redis.call('ZADD', KEYS[1], now_ms, tostring(now_ms) .. ':' .. ARGV[3])
redis.call('PEXPIRE', KEYS[1], window_ms)
return {1, 0}
"""


def _digest_key(key: str) -> str:
    return hashlib.sha256(str(key).encode("utf-8", "replace")).hexdigest()


def _fallback_consume(key_digest: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    now = time.monotonic()
    cutoff = now - window_seconds
    with _FALLBACK_LOCK:
        stamps = _FALLBACK_WINDOWS.get(key_digest)
        if stamps is not None:
            while stamps and stamps[0] <= cutoff:
                stamps.popleft()
            if not stamps:
                _FALLBACK_WINDOWS.pop(key_digest, None)
                stamps = None
        if stamps is None:
            if len(_FALLBACK_WINDOWS) >= _MAX_FALLBACK_KEYS:
                for old_key in list(_FALLBACK_WINDOWS.keys()):
                    old_stamps = _FALLBACK_WINDOWS[old_key]
                    while old_stamps and old_stamps[0] <= cutoff:
                        old_stamps.popleft()
                    if not old_stamps:
                        _FALLBACK_WINDOWS.pop(old_key, None)
                    if len(_FALLBACK_WINDOWS) < _MAX_FALLBACK_KEYS:
                        break
            if len(_FALLBACK_WINDOWS) >= _MAX_FALLBACK_KEYS:
                _FALLBACK_WINDOWS.popitem(last=False)
            stamps = deque()
            _FALLBACK_WINDOWS[key_digest] = stamps
        else:
            _FALLBACK_WINDOWS.move_to_end(key_digest)
        if len(stamps) >= limit:
            retry_after = max(1, int(stamps[0] + window_seconds - now + 0.999))
            return False, retry_after
        stamps.append(now)
        return True, 0


def consume_rate_limit(
    redis_client: Any,
    key: str,
    *,
    limit: int,
    window_seconds: int,
) -> tuple[bool, int]:
    """Consume one request from a shared sliding window.

    Redis makes the policy consistent across workers. If Redis is unavailable,
    a bounded per-process fallback preserves a reduced level of protection
    without taking the endpoint offline.
    """
    safe_limit = max(1, int(limit))
    safe_window = max(1, int(window_seconds))
    digest = _digest_key(key)
    redis_key = f"security:rate-limit:{digest}"
    global _REDIS_FALLBACK_WARNING_EMITTED
    if redis_client is not None:
        try:
            result = redis_client.eval(
                _SLIDING_WINDOW_SCRIPT,
                1,
                redis_key,
                safe_window * 1000,
                safe_limit,
                secrets.token_urlsafe(12),
            )
            allowed = bool(int(result[0]))
            retry_after = max(1, int(result[1] or 1)) if not allowed else 0
            return allowed, retry_after
        except Exception:
            if not _REDIS_FALLBACK_WARNING_EMITTED:
                _LOGGER.warning(
                    "Redis rate-limit store is unavailable; using process-local fallback"
                )
                _REDIS_FALLBACK_WARNING_EMITTED = True
    return _fallback_consume(digest, safe_limit, safe_window)
