"""Redis and in-memory fallback helpers for cache and rate limit."""

from __future__ import annotations

import json
import logging
import time
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client = None
_redis_available = False

_memory_rate_limit_store: dict[str, list[float]] = {}
_memory_cache_store: dict[str, tuple[float, dict]] = {}
_last_cleanup = time.time()
_CLEANUP_INTERVAL = 300


def _get_client():
    global _redis_client, _redis_available
    if _redis_client is not None:
        return _redis_client if _redis_available else None
    if not settings.REDIS_URL:
        return None
    try:
        import redis

        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2)
        _redis_client.ping()
        _redis_available = True
        logger.info("Redis connected: %s", settings.REDIS_URL)
        return _redis_client
    except Exception as exc:
        logger.warning("Redis unavailable, fallback to memory mode: %s", exc)
        _redis_available = False
        return None


def _cleanup_memory(now: float):
    global _last_cleanup
    if now - _last_cleanup < _CLEANUP_INTERVAL:
        return
    _last_cleanup = now

    expired_cache_keys = [key for key, (expires_at, _) in _memory_cache_store.items() if expires_at <= now]
    for key in expired_cache_keys:
        _memory_cache_store.pop(key, None)

    expired_rate_keys = []
    for key, attempts in _memory_rate_limit_store.items():
        active_attempts = [attempt for attempt in attempts if now - attempt < 3600]
        if active_attempts:
            _memory_rate_limit_store[key] = active_attempts
        else:
            expired_rate_keys.append(key)
    for key in expired_rate_keys:
        _memory_rate_limit_store.pop(key, None)


def check_rate_limit(key: str, limit: int, window: int) -> bool:
    client = _get_client()
    now = time.time()

    if client:
        try:
            pipe = client.pipeline()
            redis_key = f"ratelimit:{key}"
            pipe.zremrangebyscore(redis_key, 0, now - window)
            pipe.zcard(redis_key)
            pipe.zadd(redis_key, {str(now): now})
            pipe.expire(redis_key, window)
            results = pipe.execute()
            return results[1] < limit
        except Exception as exc:
            logger.debug("Redis rate limit failed, fallback to memory: %s", exc)

    _cleanup_memory(now)
    attempts = [attempt for attempt in _memory_rate_limit_store.get(key, []) if now - attempt < window]
    if len(attempts) >= limit:
        _memory_rate_limit_store[key] = attempts
        return False
    attempts.append(now)
    _memory_rate_limit_store[key] = attempts
    return True


def cache_get(key: str) -> Optional[dict]:
    client = _get_client()
    if client:
        try:
            data = client.get(f"cache:{key}")
            return json.loads(data) if data else None
        except Exception:
            pass

    now = time.time()
    _cleanup_memory(now)
    cache_item = _memory_cache_store.get(key)
    if not cache_item:
        return None
    expires_at, payload = cache_item
    if expires_at <= now:
        _memory_cache_store.pop(key, None)
        return None
    return payload


def cache_set(key: str, data: dict, ttl: int = 300):
    client = _get_client()
    if client:
        try:
            client.setex(f"cache:{key}", ttl, json.dumps(data, ensure_ascii=False, default=str))
            return
        except Exception:
            pass

    expires_at = time.time() + ttl
    _memory_cache_store[key] = (expires_at, data)


def cache_delete(key: str):
    client = _get_client()
    if client:
        try:
            client.delete(f"cache:{key}")
        except Exception:
            pass
    _memory_cache_store.pop(key, None)


def is_redis_available() -> bool:
    return _get_client() is not None


def cache_backend_mode() -> str:
    return "redis" if is_redis_available() else "memory"
