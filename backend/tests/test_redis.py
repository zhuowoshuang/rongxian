"""Redis 模块测试（内存回退模式）"""
import pytest
import time


def test_rate_limit_memory_fallback():
    """Redis 不可用时应使用内存回退"""
    from app.core.redis import check_rate_limit

    # 清除可能的 Redis 连接状态
    import app.core.redis as redis_mod
    original = redis_mod._redis_client
    redis_mod._redis_client = None
    redis_mod._available = False

    try:
        # 应该允许前 N 次请求
        for _ in range(5):
            assert check_rate_limit("test:key", 5, 60) is True

        # 第 6 次应该被限制
        assert check_rate_limit("test:key", 5, 60) is False
    finally:
        redis_mod._redis_client = original
        redis_mod._available = original is not None


def test_rate_limit_window_expiry():
    """窗口过期后应重新允许"""
    from app.core.redis import check_rate_limit

    import app.core.redis as redis_mod
    original = redis_mod._redis_client
    redis_mod._redis_client = None
    redis_mod._available = False

    try:
        # 用 1 秒窗口测试
        assert check_rate_limit("test:expiry", 1, 1) is True
        assert check_rate_limit("test:expiry", 1, 1) is False

        # 等待窗口过期
        time.sleep(1.1)
        assert check_rate_limit("test:expiry", 1, 1) is True
    finally:
        redis_mod._redis_client = original
        redis_mod._available = original is not None
