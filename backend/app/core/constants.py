"""系统常量定义"""

# 市场类型
class Market:
    A_SHARE = "A_SHARE"
    HK = "HK"

# 交易所
class Exchange:
    SH = "SH"  # 上海证券交易所
    SZ = "SZ"  # 深圳证券交易所
    HK = "HK"  # 香港交易所

# 信号类型
class SignalType:
    BUY = "BUY"
    ADD = "ADD"
    WATCH = "WATCH"
    REDUCE = "REDUCE"
    SELL = "SELL"

# 信号状态
class SignalStatus:
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    EXECUTED = "EXECUTED"

# 报告类型
class ReportType:
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    STOCK = "STOCK"

# 评级映射
RATING_MAP = {
    (85, 100): "BUY",
    (75, 84): "ADD",
    (65, 74): "WATCH",
    (50, 64): "REDUCE",
    (0, 49): "SELL",
}

# 市场状态
class MarketStatus:
    BULLISH = "偏多"
    NEUTRAL = "中性"
    BEARISH = "偏空"

# 股票池类型
class PoolType:
    QUALITY = "quality"
    UNDERVALUED = "undervalued"
    TREND = "trend"
    RISK = "risk"
