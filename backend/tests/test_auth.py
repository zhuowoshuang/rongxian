"""认证服务测试"""
import pytest
from app.api.auth import hash_password, verify_password, create_token, verify_token


class TestPassword:
    """密码哈希测试"""

    def test_hash_and_verify(self):
        """哈希后应能正确验证"""
        password = "TestPass123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password(self):
        """错误密码应验证失败"""
        hashed = hash_password("CorrectPass1")
        assert verify_password("WrongPass1", hashed) is False

    def test_different_hashes(self):
        """相同密码应产生不同哈希（salt）"""
        h1 = hash_password("SamePass1")
        h2 = hash_password("SamePass1")
        assert h1 != h2


class TestToken:
    """JWT Token 测试"""

    def test_create_and_verify(self):
        """创建后应能正确验证"""
        token = create_token("testuser", "user")
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "testuser"
        assert payload["role"] == "user"

    def test_invalid_token(self):
        """无效 token 应返回 None"""
        payload = verify_token("invalid.token.here")
        assert payload is None

    def test_expired_token(self):
        """过期 token 应返回 None"""
        from datetime import datetime, timedelta, timezone
        from jose import jwt
        from app.core.config import settings

        expire = datetime.now(timezone.utc) - timedelta(hours=1)
        token = jwt.encode(
            {"sub": "user", "role": "user", "exp": expire},
            settings.JWT_SECRET_KEY,
            algorithm="HS256",
        )
        payload = verify_token(token)
        assert payload is None
