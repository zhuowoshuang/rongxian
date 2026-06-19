"""统一 HTTP 客户端 — 连接池 + 自动重试"""
import logging
import os
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# 国内数据源域名列表（不走代理）
_CN_DOMAINS = {
    "push2.eastmoney.com",
    "82.push2.eastmoney.com",
    "push2ex.eastmoney.com",
    "emweb.securities.eastmoney.com",
    "reportapi.eastmoney.com",
    "web.ifzq.gtimg.cn",
    "qt.gtimg.cn",
    "stock.xueqiu.com",
}

_session: Optional[requests.Session] = None
_session_cn: Optional[requests.Session] = None


def _is_cn_url(url: str) -> bool:
    """判断是否为国内数据源 URL"""
    for domain in _CN_DOMAINS:
        if domain in url:
            return True
    return False


def _make_session(trust_env: bool) -> requests.Session:
    """创建 Session"""
    session = requests.Session()
    session.trust_env = trust_env
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(
        max_retries=retries,
        pool_connections=10,
        pool_maxsize=20,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_session() -> requests.Session:
    """获取带连接池和自动重试的全局 Session（走代理）"""
    global _session
    if _session is None:
        _session = _make_session(trust_env=True)
    return _session


def get_session_cn() -> requests.Session:
    """获取国内数据源专用 Session（不走代理）"""
    global _session_cn
    if _session_cn is None:
        _session_cn = _make_session(trust_env=False)
    return _session_cn


def get_json(url: str, headers: Optional[dict] = None, timeout: int = 15) -> dict:
    """GET 请求并返回 JSON（国内站自动绕过代理）"""
    merged = {**_DEFAULT_HEADERS, **(headers or {})}
    session = get_session_cn() if _is_cn_url(url) else get_session()
    resp = session.get(url, headers=merged, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def get_text(url: str, headers: Optional[dict] = None, timeout: int = 15) -> str:
    """GET 请求并返回文本（国内站自动绕过代理）"""
    merged = {**_DEFAULT_HEADERS, **(headers or {})}
    session = get_session_cn() if _is_cn_url(url) else get_session()
    resp = session.get(url, headers=merged, timeout=timeout)
    resp.raise_for_status()
    return resp.text
