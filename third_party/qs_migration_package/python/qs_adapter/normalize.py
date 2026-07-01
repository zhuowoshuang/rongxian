# -*- coding: utf-8 -*-
"""
字段归一化工具

职责：
  1. A股代码格式统一（补齐 6 位，去空格）。
  2. 交易所识别（6 开头 → SH，0/3 开头 → SZ，8/4 开头 → BJ）。
  3. 数字类型统一转换。
  4. 日期统一为 YYYY-MM-DD。
  5. 缺失值统一为 None。
  6. AData 原始字段名 → 清数智算标准字段名映射。
"""

import re
from datetime import datetime
from typing import Optional, Dict, Any, List

from qs_adapter.errors import NormalizationError


# ==================== 代码归一化 ====================

def normalize_symbol(raw: Any) -> str:
    """
    归一化 A 股代码为 6 位字符串。
    例：866 → "000866",  "600519" → "600519",  300866 → "300866"
    """
    if raw is None:
        raise NormalizationError("symbol 为空")
    s = str(raw).strip().replace(" ", "").replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
    # 去掉可能的前缀
    s = re.sub(r'^(sh|sz|bj|SH|SZ|BJ)', '', s)
    if not s.isdigit():
        raise NormalizationError(f"symbol 包含非数字字符: {raw}")
    return s.zfill(6)


def detect_exchange(symbol: str) -> str:
    """
    根据 A 股代码判断交易所。
    - 6 开头 → SH（上海）
    - 0 / 3 开头 → SZ（深圳）
    - 8 / 4 开头 → BJ（北京）
    """
    s = normalize_symbol(symbol)
    if s.startswith('6'):
        return 'SH'
    elif s.startswith(('0', '3')):
        return 'SZ'
    elif s.startswith(('8', '4')):
        return 'BJ'
    return 'UNKNOWN'


def detect_market(symbol: str) -> str:
    """根据代码判断市场，当前仅支持 A 股"""
    return 'A'


# ==================== 数字归一化 ====================

def safe_float(raw: Any) -> Optional[float]:
    """安全转换为 float，失败返回 None"""
    if raw is None:
        return None
    try:
        v = float(raw)
        return v if not (v != v) else None  # NaN check
    except (ValueError, TypeError):
        return None


def safe_int(raw: Any) -> Optional[int]:
    """安全转换为 int（先转 float 再取整），失败返回 None"""
    v = safe_float(raw)
    if v is None:
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


# ==================== 日期归一化 ====================

def normalize_date(raw: Any) -> Optional[str]:
    """
    统一日期为 YYYY-MM-DD 字符串。
    支持：datetime、pandas Timestamp、date、
         20240630, 2024-06-30, 2024/06/30 等字符串格式。
    """
    if raw is None:
        return None

    # datetime / date / pandas Timestamp
    if isinstance(raw, datetime):
        return raw.strftime('%Y-%m-%d')
    if hasattr(raw, 'strftime'):  # pandas Timestamp, datetime.date
        try:
            return raw.strftime('%Y-%m-%d')
        except Exception:
            pass
    if hasattr(raw, 'isoformat'):
        try:
            return raw.isoformat()[:10]
        except Exception:
            pass

    s = str(raw).strip()
    # 去掉时间部分
    s = s.split(' ')[0].split('T')[0]
    patterns = [
        (r'^(\d{4})-(\d{2})-(\d{2})$', '%Y-%m-%d'),
        (r'^(\d{4})(\d{2})(\d{2})$', '%Y%m%d'),
        (r'^(\d{4})/(\d{2})/(\d{2})$', '%Y/%m/%d'),
    ]
    for pattern, fmt in patterns:
        m = re.match(pattern, s)
        if m:
            try:
                dt = datetime.strptime(s, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
    return None


# ==================== 字段映射 ====================

# AData stock.market.get_market() 返回的列名 → 标准字段名
ADATA_KLIST_ORIGIN = [
    'trade_date',  'open',  'close',  'high',  'low',
    'volume',  'amount',  'change_pct',  'change',  'turnover_ratio',
    'pre_close',  'stock_code',  'trade_time',
]


def map_kline_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 AData K 线 DataFrame 行转换为标准化 dict。
    AData 原始字段：
      trade_date, open, close, high, low, volume, amount,
      change_pct, change, turnover_ratio, pre_close
    → 清数智算标准：
      date, open, high, low, close, volume, amount, turnover_rate
    """
    return {
        'date': normalize_date(row.get('trade_date')),
        'open': safe_float(row.get('open')),
        'high': safe_float(row.get('high')),
        'low': safe_float(row.get('low')),
        'close': safe_float(row.get('close')),
        'volume': safe_int(row.get('volume')),
        'amount': safe_float(row.get('amount')),
        'turnover_rate': safe_float(row.get('turnover_ratio')),
    }


def map_quote_row(q: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 AData 实时行情 dict 转换为标准化字段。
    AData list_market_current 返回：
      stock_code, short_name, price, change, change_pct,
      volume, amount, high, low, open, pre_close
    """
    return {
        'name': q.get('short_name') or q.get('name'),
        'trade_date': normalize_date(q.get('trade_time') or q.get('trade_date')),
        'price': safe_float(q.get('price')),
        'change': safe_float(q.get('change')),
        'change_pct': safe_float(q.get('change_pct')),
        'open': safe_float(q.get('open')),
        'high': safe_float(q.get('high')),
        'low': safe_float(q.get('low')),
        'pre_close': safe_float(q.get('pre_close')),
        'volume': safe_int(q.get('volume')),
        'amount': safe_float(q.get('amount')),
        'turnover_rate': safe_float(q.get('turnover_ratio')),
    }


def map_finance_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 AData core_index 财务数据行转换为标准化 dict。
    AData finance.get_core_index() 返回字段（部分）：
      stock_code, short_name, report_date, report_type, notice_date,
      basic_eps, diluted_eps, non_gaap_eps,
      net_asset_ps, cap_reserve_ps, undist_profit_ps, oper_cf_ps,
      total_rev, gross_profit, net_profit_attr_sh, non_gaap_net_profit,
      total_rev_yoy_gr, net_profit_yoy_gr, non_gaap_net_profit_yoy_gr,
      roe_wtd, roe_non_gaap_wtd, roa_wtd,
      gross_margin, net_margin,
      curr_ratio, quick_ratio, cash_flow_ratio,
      asset_liab_ratio, equity_multiplier, equity_ratio,
      ...
    """
    return {
        'period': normalize_date(row.get('report_date')),
        'revenue': safe_float(row.get('total_rev')),
        'revenue_yoy': safe_float(row.get('total_rev_yoy_gr')),
        'net_profit': safe_float(row.get('net_profit_attr_sh')),
        'profit_yoy': safe_float(row.get('net_profit_yoy_gr')),
        'gross_margin': safe_float(row.get('gross_margin')),
        'net_margin': safe_float(row.get('net_margin')),
        'roe': safe_float(row.get('roe_wtd')),
        'debt_ratio': safe_float(row.get('asset_liab_ratio')),
        'eps': safe_float(row.get('basic_eps')),
    }


def collect_missing_fields(data: Dict[str, Any], required_keys: List[str]) -> List[str]:
    """收集值为 None 的必填字段名"""
    return [k for k in required_keys if data.get(k) is None]
