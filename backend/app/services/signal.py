"""Signal generation service based on database scores."""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy.orm import Session

from app.core.constants import SignalStatus, SignalType
from app.models.daily_price import DailyPrice
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.technical_indicator import TechnicalIndicator
from app.models.trade_signal import TradeSignal
from app.services.compliance import sanitize_research_text, signal_display_label


def _data_confidence(score: StockScore) -> float:
    """返回评分数据可信度 (0.0~1.0)，基于评分是否看起来像真实计算值。

    评分=0且max>0 表示该维度数据缺失（被评分引擎标记为无数据）。
    评分>0 表示至少有部分字段可用。
    """
    dims = [
        (score.quality_score or 0, 30),
        (score.valuation_score or 0, 20),
        (score.growth_score or 0, 20),
        (score.trend_score or 0, 20),
        (score.risk_score or 0, 10),
    ]
    # available: dimension contributed something (>0) OR explicitly 0 with data
    # For quality: 0 is suspicious (all data missing), need at least 3 to count
    # For valuation: 0 is very common when PE/PB missing
    available = 0
    for val, weight in dims:
        if val >= 3:
            available += weight
        elif val > 0:
            available += weight * 0.5  # partial credit for very low score (may be genuine or missing)
    total = sum(w for _, w in dims)
    return min(1.0, available / total) if total > 0 else 0.0


def determine_signal_type(score: StockScore) -> tuple[str, int, str]:
    """Determine research-oriented signal label and narrative.

    缺失字段不直接等同于负面判断：当评分偏低但数据覆盖不足时，
    标记为 data_quality_limited（数据质量受限），而非 SELL/REDUCE。
    """
    confidence = _data_confidence(score)

    if (
        score.total_score >= 85
        and score.quality_score >= 24
        and score.valuation_score >= 14
        and score.trend_score >= 14
    ):
        strength = min(5, int((score.total_score - 80) / 4) + 3)
        return SignalType.BUY, strength, "基本面表现较强，估值与趋势匹配，进入高关注研究名单"

    if score.total_score >= 75 and score.trend_score >= 12 and score.risk_score >= 7:
        strength = min(4, int((score.total_score - 70) / 5) + 2)
        return SignalType.ADD, strength, "基本面与趋势继续改善，建议增强关注并跟踪后续数据"

    if score.total_score >= 65:
        strength = min(3, int((score.total_score - 60) / 5) + 1)
        reasons = []
        if score.quality_score >= 20:
            reasons.append("基本面维持良好")
        if score.trend_score < 12:
            reasons.append("趋势仍待确认")
        if score.valuation_score < 14:
            reasons.append("估值吸引力有限")
        logic = "；".join(reasons) if reasons else "综合评分处于中性区间"
        return SignalType.WATCH, strength, f"{logic}，当前维持观察"

    # ── 数据质量 gate：评分偏低但数据覆盖不足 → 不判 SELL/REDUCE ──
    if confidence < 0.50:
        return "DATA_INSUFFICIENT", 0, (
            f"数据覆盖不足（可信度{confidence:.0%}），估值、毛利率或市值等关键字段缺失，暂不形成正式信号"
        )
    if confidence < 0.70:
        return "DATA_INSUFFICIENT", 0, (
            f"数据部分缺失（可信度{confidence:.0%}），当前评估参考价值有限，暂不形成正式信号"
        )

    if score.total_score >= 50:
        reasons = []
        if score.valuation_score < 10:
            reasons.append("估值风险上升")
        if score.trend_score < 10:
            reasons.append("趋势明显转弱")
        if score.risk_score < 5:
            reasons.append("风险因子恶化")
        logic = "；".join(reasons) if reasons else "综合评分明显回落"
        return SignalType.REDUCE, 2, f"{logic}，当前风险升高"

    return SignalType.SELL, 1, "基本面或风险指标明显恶化，建议回避观察"


def calculate_position(
    signal_type: str,
    signal_strength: int,
    existing_sector_pct: float = 0.0,
    total_position_pct: float = 0.0,
) -> float:
    position_map = {
        SignalType.BUY: {5: 8, 4: 6, 3: 5},
        SignalType.ADD: {4: 5, 3: 4, 2: 3},
        SignalType.WATCH: {3: 0, 2: 0, 1: 0},
        SignalType.REDUCE: {2: 0, 1: 0},
        SignalType.SELL: {1: 0},
    }
    base = position_map.get(signal_type, {}).get(signal_strength, 0)
    if base == 0:
        return 0
    if existing_sector_pct > 0.25:
        base = max(1, base // 2)
    if total_position_pct > 0.85:
        base = max(1, base // 2)
    return base


def calculate_prices(
    price: DailyPrice,
    signal_type: str,
    tech: Optional[TechnicalIndicator] = None,
) -> tuple[Optional[float], Optional[float], Optional[float]]:
    if not price.close:
        return None, None, None

    entry = price.close
    vol_pct = 0.10
    if tech and tech.boll_upper and tech.boll_lower and entry > 0:
        boll_width = (tech.boll_upper - tech.boll_lower) / entry
        vol_pct = max(0.05, min(0.25, boll_width))

    if signal_type in (SignalType.BUY, SignalType.ADD):
        target_mult = max(1.10, min(1.30, 1 + 2 * vol_pct))
        stop_mult = max(0.88, min(0.95, 1 - vol_pct))
        target = round(entry * target_mult, 2)
        stop_loss = round(entry * stop_mult, 2)
    elif signal_type == SignalType.REDUCE:
        target = None
        stop_loss = round(entry * max(0.90, min(0.95, 1 - vol_pct * 0.5)), 2)
    else:
        target = None
        stop_loss = None

    return entry, target, stop_loss


def generate_signal_for_stock(db: Session, stock_id: int, signal_date: date, *, commit: bool = True) -> Optional[TradeSignal]:
    score = (
        db.query(StockScore)
        .filter(StockScore.stock_id == stock_id, StockScore.score_date == signal_date)
        .first()
    )
    if not score:
        return None

    price = (
        db.query(DailyPrice)
        .filter(DailyPrice.stock_id == stock_id, DailyPrice.trade_date <= signal_date)
        .order_by(DailyPrice.trade_date.desc())
        .first()
    )
    if not price:
        return None

    tech = (
        db.query(TechnicalIndicator)
        .filter(TechnicalIndicator.stock_id == stock_id, TechnicalIndicator.trade_date <= signal_date)
        .order_by(TechnicalIndicator.trade_date.desc())
        .first()
    )

    signal_type, strength, logic = determine_signal_type(score)

    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    existing_sector_pct = 0.0
    total_position_pct = 0.0
    if stock and stock.industry:
        active_signals = db.query(TradeSignal).filter(
            TradeSignal.signal_date == signal_date,
            TradeSignal.status == "ACTIVE",
            TradeSignal.signal_type.in_(["BUY", "ADD"]),
        ).count()
        if active_signals > 0:
            sector_signal_count = db.query(TradeSignal).join(Stock).filter(
                TradeSignal.signal_date == signal_date,
                TradeSignal.status == "ACTIVE",
                TradeSignal.signal_type.in_(["BUY", "ADD"]),
                Stock.industry == stock.industry,
            ).count()
            existing_sector_pct = sector_signal_count / (active_signals + 5)
            total_position_pct = min(0.9, active_signals * 0.06)

    position = calculate_position(signal_type, strength, existing_sector_pct, total_position_pct)
    entry, target, stop_loss = calculate_prices(price, signal_type, tech)

    if signal_type == "DATA_INSUFFICIENT":
        position = 0
        entry, target, stop_loss = None, None, None

    holding_map = {
        SignalType.BUY: "3-6个月",
        SignalType.ADD: "2-4个月",
        SignalType.WATCH: "-",
        SignalType.REDUCE: "逐步降低关注",
        SignalType.SELL: "尽快复核",
        "DATA_INSUFFICIENT": "-",
    }

    risk_items = []
    if score.risk_score < 5:
        risk_items.append("风险评分较低")
    if score.valuation_score < 10:
        risk_items.append("估值吸引力偏弱")
    if score.trend_score < 10:
        risk_items.append("趋势维度偏弱")

    logic_json = {
        "total_score": score.total_score,
        "quality_score": score.quality_score,
        "valuation_score": score.valuation_score,
        "growth_score": score.growth_score,
        "trend_score": score.trend_score,
        "risk_score": score.risk_score,
        "reason": sanitize_research_text(logic),
        "rating_label": signal_display_label(signal_type),
        "data_source": "数据库评分与信号规则",
    }
    risk_json = {"items": risk_items if risk_items else ["当前未发现重大风险项"]} 

    existing = (
        db.query(TradeSignal)
        .filter(TradeSignal.stock_id == stock_id, TradeSignal.signal_date == signal_date)
        .first()
    )
    if existing:
        existing.signal_type = signal_type
        existing.signal_strength = strength
        existing.suggested_position = position
        existing.entry_price = entry
        existing.target_price = target
        existing.stop_loss_price = stop_loss
        existing.holding_period = holding_map.get(signal_type, "-")
        existing.logic_json = logic_json
        existing.risk_json = risk_json
        signal = existing
    else:
        signal = TradeSignal(
            stock_id=stock_id,
            signal_date=signal_date,
            signal_type=signal_type,
            signal_strength=strength,
            suggested_position=position,
            entry_price=entry,
            target_price=target,
            stop_loss_price=stop_loss,
            holding_period=holding_map.get(signal_type, "-"),
            logic_json=logic_json,
            risk_json=risk_json,
            status=SignalStatus.ACTIVE,
        )
        db.add(signal)

    if commit:
        db.commit()
        db.refresh(signal)
    else:
        db.flush()
    return signal


def generate_all_signals(db: Session, signal_date: date) -> list[TradeSignal]:
    scores = db.query(StockScore).filter(StockScore.score_date == signal_date).all()
    results = []
    for score in scores:
        signal = generate_signal_for_stock(db, score.stock_id, signal_date)
        if signal:
            results.append(signal)
    return results


def get_signal_distribution(db: Session, signal_date: date) -> dict:
    signals = db.query(TradeSignal).filter(TradeSignal.signal_date == signal_date).all()
    distribution = {"BUY": 0, "ADD": 0, "WATCH": 0, "REDUCE": 0, "SELL": 0}
    for signal in signals:
        if signal.signal_type in distribution:
            distribution[signal.signal_type] += 1
    return distribution
