"""统一 HTTP 客户端 — 连接池 + 自动重试"""
import logging
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

_session: Optional[requests.Session] = None


def get_session() -> requests.Session:
    """获取带连接池和自动重试的全局 Session"""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.trust_env = True  # 自动使用系统代理
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
        _session.mount("https://", adapter)
        _session.mount("http://", adapter)
    return _session


def get_json(url: str, headers: Optional[dict] = None, timeout: int = 15) -> dict:
    """GET 请求并返回 JSON"""
    merged = {**_DEFAULT_HEADERS, **(headers or {})}
    session = get_session()
    resp = session.get(url, headers=merged, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def get_text(url: str, headers: Optional[dict] = None, timeout: int = 15) -> str:
    """GET 请求并返回文本"""
    merged = {**_DEFAULT_HEADERS, **(headers or {})}
    session = get_session()
    resp = session.get(url, headers=merged, timeout=timeout)
    resp.raise_for_status()
    return resp.text
