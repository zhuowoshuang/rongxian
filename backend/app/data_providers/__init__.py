"""
数据源工厂 - 根据 MOCK_DATA 环境变量选择数据源
MOCK_DATA=true (Docker 默认): 使用 MockProvider，不依赖外部 API
MOCK_DATA=false: 使用 CompositeProvider (真实 API)
"""
import os

_provider = None


def get_provider():
    global _provider
    if _provider is not None:
        return _provider

    use_mock = os.environ.get("MOCK_DATA", "true").lower() in ("true", "1", "yes")

    if use_mock:
        from app.data_providers.mock_provider import MockProvider
        _provider = MockProvider()
    else:
        from app.data_providers.composite_provider import CompositeProvider
        _provider = CompositeProvider()

    return _provider
