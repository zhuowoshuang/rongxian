"""
Redis 客户端模块
提供速率限制和缓存功能，支持优雅降级（Redis 不可用时回退到内存）
"""
import json
import logging
import time
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_client = None
_available = False


def _get_client():
    """获取 Redis 客户端（懒加载，失败时返回 None）"""
    global _redis_client, _available
    if _redis_client is not None:
        return _redis_client if _available else None
    if not settings.REDIS_URL:
        return None
    try:
        import redis
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=2)
        _redis_client.ping()
        _available = True
        logger.info(f"Redis 连接成功: {settings.REDIS_URL}")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis 不可用，回退到内存模式: {e}")
        _available = False
        return None


# ==================== 速率限制 ====================

# 内存回退存储
_memory_store: dict[str, list[float]] = {}
_last_cleanup: float = time.time()
_CLEANUP_INTERVAL = 300


def _cleanup_memory(now: float):
    """清理过期内存记录"""
    global _last_cleanup
    if now - _last_cleanup < _CLEANUP_INTERVAL:
        return
    _last_cleanup = now
    expired_keys = []
    for k, v in _memory_store.items():
        active = [t for t in v if now - t < 3600]
        if not active:
            expired_keys.append(k)
        else:
            _memory_store[k] = active
    for k in expired_keys:
        del _memory_store[k]


def check_rate_limit(key: str, limit: int, window: int) -> bool:
    """
    检查速率限制
    Args:
        key: 限制键（如 "login:192.168.1.1"）
        limit: 窗口内最大次数
        window: 时间窗口（秒）
    Returns:
        True 表示允许，False 表示超出限制
    """
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
            count = results[1]
            return count < limit
        except Exception as e:
            logger.debug(f"Redis 速率限制失败，回退内存: {e}")

    # 内存回退
    _cleanup_memory(now)
    attempts = _memory_store.get(key, [])
    _memory_store[key] = [t for t in attempts if now - t < window]
    if len(_memory_store[key]) >= limit:
        return False
    _memory_store[key].append(now)
    return True


# ==================== 缓存 ====================

def cache_get(key: str) -> Optional[dict]:
    """从缓存获取 JSON 数据"""
    client = _get_client()
    if not client:
        return None
    try:
        data = client.get(f"cache:{key}")
        return json.loads(data) if data else None
    except Exception:
        return None


def cache_set(key: str, data: dict, ttl: int = 300):
    """设置缓存（默认 5 分钟过期）"""
    client = _get_client()
    if not client:
        return
    try:
        client.setex(f"cache:{key}", ttl, json.dumps(data, ensure_ascii=False, default=str))
    except Exception:
        pass


def cache_delete(key: str):
    """删除缓存"""
    client = _get_client()
    if not client:
        return
    try:
        client.delete(f"cache:{key}")
    except Exception:
        pass


def is_redis_available() -> bool:
    """检查 Redis 是否可用"""
    return _get_client() is not None
