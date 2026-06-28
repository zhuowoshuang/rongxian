"""Helpers for Chinese research report generation."""

from datetime import date

from sqlalchemy.orm import Session

from app.models.daily_price import DailyPrice


def rating_text(rating: str) -> str:
    return {
        "BUY": "高关注",
        "ADD": "增强关注",
        "WATCH": "观察",
        "REDUCE": "风险升高",
        "SELL": "回避观察",
    }.get(rating, rating)


def signal_icon(sig_type: str) -> str:
    return {"BUY": "●", "ADD": "◆", "WATCH": "○", "REDUCE": "▲", "SELL": "■"}.get(sig_type, "○")


def score_bar(score: float, max_score: float) -> str:
    pct = score / max_score * 100 if max_score > 0 else 0
    filled = int(pct / 10)
    return "■" * filled + "□" * (10 - filled) + f" {score:.0f}/{max_score:.0f}"


def spark_line(values: list, width: int = 20) -> str:
    if not values or len(values) < 2:
        return "数据不足"
    minimum, maximum = min(values), max(values)
    spread = maximum - minimum if maximum > minimum else 1
    chars = "▁▂▃▄▅▆▇█"
    result = ""
    step = max(1, len(values) // width)
    for value in values[::step][:width]:
        idx = int((value - minimum) / spread * (len(chars) - 1))
        result += chars[idx]
    return result


def distribution_bar(counts: dict, total: int) -> str:
    if total == 0:
        return "暂无数据"
    lines = []
    max_len = 30
    for label, count in [
        ("高关注", counts.get("BUY", 0)),
        ("增强关注", counts.get("ADD", 0)),
        ("观察", counts.get("WATCH", 0)),
        ("风险升高", counts.get("REDUCE", 0)),
        ("回避观察", counts.get("SELL", 0)),
    ]:
        bar_len = int(count / total * max_len)
        bar = "■" * bar_len + "·" * (max_len - bar_len)
        lines.append(f"  {label} |{bar}| {count}只 ({count / total * 100:.0f}%)")
    return "\n".join(lines)


def market_breadth_chart(buy_add: int, reduce_sell: int, total: int) -> str:
    if total == 0:
        return "数据不足"
    bull_pct = buy_add / total * 100
    bear_pct = reduce_sell / total * 100
    bull_bar = int(bull_pct / 2)
    bear_bar = int(bear_pct / 2)
    return f"""
```
市场研究热度对比
{'─' * 52}
积极信号 {'■' * bull_bar}{'·' * (50 - bull_bar)} {bull_pct:.0f}%
风险信号 {'■' * bear_bar}{'·' * (50 - bear_bar)} {bear_pct:.0f}%
{'─' * 52}
```"""


def quality_comment(score: float) -> str:
    if score >= 25:
        return "盈利质量、现金流和经营稳定性表现较强。"
    if score >= 18:
        return "经营质量整体良好，但仍需持续跟踪。"
    if score >= 12:
        return "部分财务指标尚可，稳健性一般。"
    return "经营质量偏弱，需重点关注基本面风险。"


def valuation_comment(score: float) -> str:
    if score >= 16:
        return "估值相对有吸引力，具备一定安全边际。"
    if score >= 10:
        return "估值处于合理区间，需结合成长性判断。"
    if score >= 5:
        return "估值偏高，回撤压力需要额外关注。"
    return "估值约束明显，当前观察性价比不足。"


def growth_comment(score: float) -> str:
    if score >= 16:
        return "收入与利润扩张动能较强。"
    if score >= 10:
        return "成长性稳健，但弹性一般。"
    if score >= 5:
        return "增长延续性有待验证。"
    return "成长性偏弱，需谨慎看待后续扩张。"


def trend_comment(score: float) -> str:
    if score >= 16:
        return "价格趋势较强，技术面配合度较高。"
    if score >= 10:
        return "趋势温和偏强，适合观察回调节奏。"
    if score >= 5:
        return "趋势中性，方向仍待确认。"
    return "趋势偏弱，需等待修复信号。"


def risk_comment(score: float) -> str:
    if score >= 8:
        return "风险维度相对可控。"
    if score >= 5:
        return "风险适中，需持续跟踪。"
    return "风险偏高，需重点关注异常状态。"


def suggested_position(buy_add: int, reduce_sell: int, total: int, cfg: dict | None = None) -> str:
    if total == 0:
        return "暂无研究仓位区间"
    ratio = buy_add / total
    max_pos = cfg["max_position"] if cfg else 80
    if ratio > 0.6:
        if cfg:
            return f"{max_pos * 0.7:.0f}-{max_pos:.0f}%（接近 {cfg['name']} 研究上限）"
        return f"{min(70, max_pos)}-{min(80, max_pos)}%（研究视角偏积极）"
    if ratio > 0.4:
        return f"{min(50, max_pos)}-{min(70, max_pos)}%（研究视角偏均衡）"
    if ratio > 0.2:
        return f"{min(30, max_pos)}-{min(50, max_pos)}%（研究视角中性）"
    return f"20-{min(30, max_pos)}%（研究视角偏谨慎）"


def market_index_summary(db: Session, report_date: date) -> str:
    latest_prices = db.query(DailyPrice).order_by(DailyPrice.trade_date.desc()).limit(50).all()
    if not latest_prices:
        return "> 当前暂无市场行情数据。"

    up_count = sum(1 for price in latest_prices if price.close > (price.pre_close or price.close))
    down_count = sum(1 for price in latest_prices if price.close < (price.pre_close or price.close))
    flat_count = len(latest_prices) - up_count - down_count

    changes = []
    for price in latest_prices:
        if price.pre_close and price.pre_close > 0:
            changes.append((price.close - price.pre_close) / price.pre_close * 100)
    avg_change = sum(changes) / len(changes) if changes else 0

    return f"""**市场温度观察**
```
涨跌样本统计（最近 {len(latest_prices)} 条价格记录）
{'─' * 40}
上涨: {'■' * min(up_count, 30)} {up_count}条
下跌: {'■' * min(down_count, 30)} {down_count}条
平盘: {'■' * min(flat_count, 30)} {flat_count}条
{'─' * 40}
平均涨跌幅: {avg_change:+.2f}%
```"""
