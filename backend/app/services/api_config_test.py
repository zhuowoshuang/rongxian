"""Provider-aware API configuration checks."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


LLM_PROVIDERS = {"deepseek", "openai", "custom_llm", "llm"}
DATA_PROVIDERS = {"eastmoney", "akshare", "yahoo", "baostock"}


@dataclass
class ApiConfigTestResult:
    status: str
    message: str


def _valid_url(value: str | None) -> bool:
    if not value:
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def test_provider_config(provider: str, base_url: str | None, model_name: str | None = None, api_key: str | None = None) -> ApiConfigTestResult:
    key = (provider or "").strip().lower()
    if not key:
        return ApiConfigTestResult("failed", "供应商标识不能为空。")

    if key in LLM_PROVIDERS:
        if not _valid_url(base_url):
            return ApiConfigTestResult("failed", "Base URL 格式无效，请填写 http 或 https 开头的完整地址。")
        if not model_name:
            return ApiConfigTestResult("failed", "模型名称不能为空，请填写要调用的模型。")
        if api_key:
            return ApiConfigTestResult("format_valid", "配置格式有效，真实模型连通性待验证。")
        return ApiConfigTestResult("format_valid", "配置格式有效；未填写 API Key，已跳过真实模型连通性验证。")

    if key == "eastmoney":
        return ApiConfigTestResult("unsupported", "东方财富数据源使用系统内置公开接口，该供应商暂未实现自动测试，仅保存配置状态。")
    if key == "akshare":
        return ApiConfigTestResult("unsupported", "AkShare 当前通过本地 Python 包调用，暂未实现自动测试，仅保存配置状态。")
    if key == "yahoo":
        return ApiConfigTestResult("unsupported", "Yahoo 数据源暂未实现自动测试，仅保存配置状态。")
    if key == "baostock":
        return ApiConfigTestResult("unsupported", "Baostock 数据源暂未实现自动测试，仅保存配置状态。")

    if not _valid_url(base_url):
        return ApiConfigTestResult("failed", "自定义供应商必须填写有效 Base URL。")
    return ApiConfigTestResult("format_valid", "自定义供应商格式有效，真实连通性待接入专用测试方法。")
