"""
信号生成服务
根据评分结果生成交易信号
"""
from typing import Optional
from datetime import date
from sqlalchemy.orm import Session

from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.daily_price import DailyPrice
from app.models.technical_indicator import TechnicalIndicator
from app.models.trade_signal import TradeSignal
from app.core.constants import SignalType, SignalStatus


def determine_signal_type(score: StockScore) -> tuple[str, int, str]:
    """
    根据评分确定信号类型、强度和逻辑说明
    Returns: (signal_type, signal_strength, logic_text)
    """
    # BUY: total_score >= 85, quality >= 24, valuation >= 14, trend >= 14
    if (score.total_score >= 85
            and score.quality_score >= 24
            and score.valuation_score >= 14
            and score.trend_score >= 14):
        strength = min(5, int((score.total_score - 80) / 4) + 3)
        return SignalType.BUY, strength, "基本面优秀，估值合理，趋势确认，建议买入"

    # ADD: total_score >= 75, 趋势确认, 风险分 >= 7
    if score.total_score >= 75 and score.trend_score >= 12 and score.risk_score >= 7:
        strength = min(4, int((score.total_score - 70) / 5) + 2)
        return SignalType.ADD, strength, "基本面良好，趋势向好，可适当加仓"

    # WATCH: 基本面好但趋势未确认，或估值合理但信号不完整
    if score.total_score >= 65:
        strength = min(3, int((score.total_score - 60) / 5) + 1)
        reasons = []
        if score.quality_score >= 20:
            reasons.append("基本面良好")
        if score.trend_score < 12:
            reasons.append("趋势待确认")
        if score.valuation_score < 14:
            reasons.append("估值偏高")
        logic = "，".join(reasons) if reasons else "综合评分中等"
        return SignalType.WATCH, strength, f"{logic}，建议观望"

    # REDUCE: 估值过高、趋势转弱、风险升高
    if score.total_score >= 50:
        reasons = []
        if score.valuation_score < 10:
            reasons.append("估值过高")
        if score.trend_score < 10:
            reasons.append("趋势转弱")
        if score.risk_score < 5:
            reasons.append("风险升高")
        logic = "，".join(reasons) if reasons else "综合评分偏低"
        return SignalType.REDUCE, 2, f"{logic}，建议减仓"

    # SELL: 基本面恶化、评分很低
    return SignalType.SELL, 1, "基本面恶化或评分极低，建议卖出"


def calculate_position(
    signal_type: str,
    signal_strength: int,
    existing_sector_pct: float = 0.0,
    total_position_pct: float = 0.0,
) -> float:
    """
    根据信号类型和强度计算建议仓位（含集中度限制）
    Args:
        existing_sector_pct: 同行业已持仓占比（0-1）
        total_position_pct: 当前总仓位占比（0-1）
    """
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

    # 单行业上限 30%：同行业已超 25% 时减半建议仓位
    if existing_sector_pct > 0.25:
        base = max(1, base // 2)

    # 总仓位上限 90%：已超 85% 时减半建议仓位
    if total_position_pct > 0.85:
        base = max(1, base // 2)

    return base


def calculate_prices(price: DailyPrice, signal_type: str, tech: Optional[TechnicalIndicator] = None) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """
    计算入场价、目标价、止损价（波动率自适应）
    使用布林带宽度或 ATR 估算波动率，动态调整目标和止损
    """
    if not price.close:
        return None, None, None

    entry = price.close

    # 基于技术指标估算波动率
    vol_pct = 0.10  # 默认 10% 波动率
    if tech and tech.boll_upper and tech.boll_lower and entry > 0:
        # 布林带宽度作为波动率代理
        boll_width = (tech.boll_upper - tech.boll_lower) / entry
        vol_pct = max(0.05, min(0.25, boll_width))  # 限制在 5%-25%

    if signal_type in (SignalType.BUY, SignalType.ADD):
        # 目标价 = 入场价 * (1 + 2 * 波动率)，至少 10%，最多 30%
        target_mult = max(1.10, min(1.30, 1 + 2 * vol_pct))
        # 止损价 = 入场价 * (1 - 波动率)，至少 5%，最多 12%
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


def generate_signal_for_stock(
    db: Session,
    stock_id: int,
    signal_date: date,
) -> Optional[TradeSignal]:
    """为单只股票生成交易信号"""
    score = (
        db.query(StockScore)
        .filter(StockScore.stock_id == stock_id, StockScore.score_date == signal_date)
        .first()
    )
    if not score:
        return None

    price = (
        db.query(DailyPrice)
        .filter(DailyPrice.stock_id == stock_id)
        .order_by(DailyPrice.trade_date.desc())
        .first()
    )
    if not price:
        return None

    # 获取最新技术指标（用于波动率自适应目标价/止损价）
    tech = (
        db.query(TechnicalIndicator)
        .filter(TechnicalIndicator.stock_id == stock_id)
        .order_by(TechnicalIndicator.trade_date.desc())
        .first()
    )

    signal_type, strength, logic = determine_signal_type(score)

    # 计算持仓集中度（用于仓位限制）
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    existing_sector_pct = 0.0
    total_position_pct = 0.0
    if stock and stock.industry:
        # 同行业已有的活跃信号数量 / 总活跃信号数量
        active_signals = db.query(TradeSignal).filter(
            TradeSignal.signal_date == signal_date,
            TradeSignal.status == "ACTIVE",
            TradeSignal.signal_type.in_(["BUY", "ADD"]),
        ).count()
        if active_signals > 0:
            # 同行业信号数（简化：用信号数近似仓位占比）
            sector_signal_count = db.query(TradeSignal).join(Stock).filter(
                TradeSignal.signal_date == signal_date,
                TradeSignal.status == "ACTIVE",
                TradeSignal.signal_type.in_(["BUY", "ADD"]),
                Stock.industry == stock.industry,
            ).count()
            existing_sector_pct = sector_signal_count / (active_signals + 5)  # +5 避免除零
            total_position_pct = min(0.9, active_signals * 0.06)  # 每只约 6% 仓位

    position = calculate_position(signal_type, strength, existing_sector_pct, total_position_pct)
    entry, target, stop_loss = calculate_prices(price, signal_type, tech)

    # 持有期建议
    holding_map = {
        SignalType.BUY: "3-6个月",
        SignalType.ADD: "2-4个月",
        SignalType.WATCH: "-",
        SignalType.REDUCE: "逐步减仓",
        SignalType.SELL: "立即",
    }

    # 风险提示
    risk_items = []
    if score.risk_score < 5:
        risk_items.append("风险评分较低")
    if score.valuation_score < 10:
        risk_items.append("估值偏高")
    if score.trend_score < 10:
        risk_items.append("趋势偏弱")

    logic_json = {
        "total_score": score.total_score,
        "quality_score": score.quality_score,
        "valuation_score": score.valuation_score,
        "growth_score": score.growth_score,
        "trend_score": score.trend_score,
        "risk_score": score.risk_score,
        "reason": logic,
    }
    risk_json = {"items": risk_items if risk_items else ["暂无重大风险"]}

    # 更新或创建信号
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

    db.commit()
    db.refresh(signal)
    return signal


def generate_all_signals(db: Session, signal_date: date) -> list[TradeSignal]:
    """为所有已评分股票生成信号"""
    scores = db.query(StockScore).filter(StockScore.score_date == signal_date).all()
    results = []
    for s in scores:
        sig = generate_signal_for_stock(db, s.stock_id, signal_date)
        if sig:
            results.append(sig)
    return results


def get_signal_distribution(db: Session, signal_date: date) -> dict:
    """获取信号分布统计"""
    signals = db.query(TradeSignal).filter(TradeSignal.signal_date == signal_date).all()
    dist = {"BUY": 0, "ADD": 0, "WATCH": 0, "REDUCE": 0, "SELL": 0}
    for s in signals:
        if s.signal_type in dist:
            dist[s.signal_type] += 1
    return dist
