"""报告生成工具函数"""
from datetime import date
from sqlalchemy.orm import Session

from app.models.daily_price import DailyPrice


def rating_text(rating: str) -> str:
    return {"BUY": "强烈买入", "ADD": "建议加仓", "WATCH": "观望等待", "REDUCE": "建议减仓", "SELL": "建议卖出"}.get(rating, rating)


def signal_icon(sig_type: str) -> str:
    return {"BUY": "🟢", "ADD": "🔵", "WATCH": "⚪", "REDUCE": "🟡", "SELL": "🔴"}.get(sig_type, "⚪")


def score_bar(score: float, max_score: float) -> str:
    pct = score / max_score * 100 if max_score > 0 else 0
    filled = int(pct / 10)
    return "█" * filled + "░" * (10 - filled) + f" {score:.0f}/{max_score:.0f}"


def spark_line(values: list, width: int = 20) -> str:
    """生成ASCII迷你走势图"""
    if not values or len(values) < 2:
        return "数据不足"
    mn, mx = min(values), max(values)
    rng = mx - mn if mx > mn else 1
    chars = "▁▂▃▄▅▆▇█"
    result = ""
    step = max(1, len(values) // width)
    sampled = values[::step][:width]
    for v in sampled:
        idx = int((v - mn) / rng * (len(chars) - 1))
        result += chars[idx]
    return result


def distribution_bar(counts: dict, total: int) -> str:
    """生成信号分布柱状图"""
    if total == 0:
        return "无数据"
    lines = []
    max_len = 30
    for label, count in [("买入", counts.get("BUY", 0)), ("加仓", counts.get("ADD", 0)),
                          ("观望", counts.get("WATCH", 0)), ("减仓", counts.get("REDUCE", 0)),
                          ("卖出", counts.get("SELL", 0))]:
        bar_len = int(count / total * max_len)
        bar = "█" * bar_len + "░" * (max_len - bar_len)
        lines.append(f"  {label} |{bar}| {count}只 ({count/total*100:.0f}%)")
    return "\n".join(lines)


def market_breadth_chart(buy_add: int, reduce_sell: int, total: int) -> str:
    """生成市场广度图"""
    if total == 0:
        return "数据不足"
    bull_pct = buy_add / total * 100
    bear_pct = reduce_sell / total * 100
    bull_bar = int(bull_pct / 2)
    bear_bar = int(bear_pct / 2)
    return f"""
```
市场多空力量对比
{'─' * 52}
多头 {'▓' * bull_bar}{'░' * (50 - bull_bar)} {bull_pct:.0f}%
空头 {'▒' * bear_bar}{'░' * (50 - bear_bar)} {bear_pct:.0f}%
{'─' * 52}
```"""


def quality_comment(q: float) -> str:
    if q >= 25: return "质地优秀，盈利突出，现金流健康，护城河深厚"
    if q >= 18: return "质地良好，具备一定竞争优势和盈利韧性"
    if q >= 12: return "质地一般，部分财务指标有待改善"
    return "质地偏弱，需密切关注经营风险和现金流状况"


def valuation_comment(v: float) -> str:
    if v >= 16: return "估值极具吸引力，安全边际充足，价值投资者首选"
    if v >= 10: return "估值合理，处于历史中位水平，具备投资价值"
    if v >= 5: return "估值偏高，需警惕回调风险，建议等待更好的买点"
    return "估值较高，当前价位缺乏安全边际，不建议追高"


def growth_comment(g: float) -> str:
    if g >= 16: return "成长性卓越，营收和利润保持高速增长，成长动能强劲"
    if g >= 10: return "成长性良好，业绩稳步增长，增长趋势延续"
    if g >= 5: return "成长性一般，增速有所放缓，需关注增长可持续性"
    return "成长性较弱，业绩面临下滑压力，需谨慎对待"


def trend_comment(t: float) -> str:
    if t >= 16: return "技术面强势，均线多头排列，量价配合良好，趋势明确"
    if t >= 10: return "技术面偏强，整体趋势向好，可关注回调买入机会"
    if t >= 5: return "技术面中性，短期方向不明朗，建议观望等待突破"
    return "技术面偏弱，均线空头排列，需等待企稳信号确认"


def risk_comment(r: float) -> str:
    if r >= 8: return "风险可控，财务结构稳健，业绩确定性强"
    if r >= 5: return "风险适中，需关注部分指标变化，做好仓位管理"
    return "风险偏高，需密切关注财务和经营变化，严格止损"


def suggested_position(buy_add: int, reduce_sell: int, total: int, cfg: dict = None) -> str:
    if total == 0:
        return "暂无建议"
    ratio = buy_add / total
    max_pos = cfg["max_position"] if cfg else 80
    if ratio > 0.6:
        if cfg:
            return f"{max_pos * 0.7:.0f}-{max_pos}%（{cfg['name']}上限配置）"
        return f"{min(70, max_pos)}-{min(80, max_pos)}%（积极做多）"
    if ratio > 0.4:
        return f"{min(50, max_pos)}-{min(70, max_pos)}%（偏多配置）"
    if ratio > 0.2:
        return f"{min(30, max_pos)}-{min(50, max_pos)}%（均衡配置）"
    return f"20-{min(30, max_pos)}%（防御为主）"


def market_index_summary(db: Session, report_date: date) -> str:
    """生成市场指数概览"""
    latest_prices = db.query(DailyPrice).order_by(DailyPrice.trade_date.desc()).limit(50).all()
    if not latest_prices:
        return "> 当前暂无市场行情数据。"

    up_count = sum(1 for p in latest_prices if p.close > (p.pre_close or p.close))
    down_count = sum(1 for p in latest_prices if p.close < (p.pre_close or p.close))
    flat_count = len(latest_prices) - up_count - down_count

    avg_change = 0
    changes = []
    for p in latest_prices:
        if p.pre_close and p.pre_close > 0:
            changes.append((p.close - p.pre_close) / p.pre_close * 100)
    if changes:
        avg_change = sum(changes) / len(changes)

    return f"""**市场温度计:**
```
涨跌家数统计（样本 {len(latest_prices)} 只）
{'─' * 40}
上涨: {'█' * min(up_count, 30)} {up_count}家
下跌: {'▒' * min(down_count, 30)} {down_count}家
平盘: {'░' * min(flat_count, 30)} {flat_count}家
{'─' * 40}
平均涨跌幅: {avg_change:+.2f}%
```"""
