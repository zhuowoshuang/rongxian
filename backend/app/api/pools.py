"""Stock pool API with rule explanations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.daily_price import DailyPrice
from app.models.stock import Stock
from app.models.stock_score import StockScore

router = APIRouter(prefix="/api/pools", tags=["股票池"])

POOL_DISPLAY_LIMIT = 70

POOL_META = {
    "quality": {
        "name": "优质基本面池",
        "positioning": "以盈利能力、现金流和财务结构为主的基本面筛选池。",
        "rules": ["质量分 >= 10", "按质量分倒序排序"],
        "scenario": "适合研究长期经营质量较稳定的公司。",
        "risks": ["若估值偏高或趋势偏弱，短期表现可能不佳", "部分财务数据可能存在披露滞后"],
    },
    "undervalued": {
        "name": "低估值池",
        "positioning": "优先展示估值相对更低或估值吸引力较高的样本。",
        "rules": ["估值分 >= 5", "按估值分倒序排序"],
        "scenario": "适合寻找估值修复研究样本。",
        "risks": ["低估值不等于低风险", "可能存在基本面走弱导致的价值陷阱"],
    },
    "trend": {
        "name": "趋势确认池",
        "positioning": "优先展示趋势维度较强的样本。",
        "rules": ["趋势分 >= 8", "按趋势分倒序排序"],
        "scenario": "适合研究价格趋势与量价结构是否持续改善。",
        "risks": ["趋势信号可能回撤", "缺少长期基本面支撑时持续性有限"],
    },
    "risk": {
        "name": "风险预警池",
        "positioning": "聚焦风险维度较弱、需要优先复核的样本。",
        "rules": ["风险分 < 5", "按风险分升序排序"],
        "scenario": "适合管理员或研究员优先排查潜在问题样本。",
        "risks": ["池内样本不应视为优选名单", "可能包含高波动或风险警示标的"],
    },
    "steady": {
        "name": "稳健优选",
        "positioning": "偏向质量较高且风险控制较好的研究池。",
        "rules": ["质量分 >= 20", "风险分 >= 6", "展示时额外过滤 PE >= 60"],
        "scenario": "适合偏稳健口径的长期研究。",
        "risks": ["规则偏保守，可能错过高成长样本", "仍需结合行业周期判断"],
    },
    "aggressive": {
        "name": "进取优选",
        "positioning": "偏向成长与趋势共同较强的研究池。",
        "rules": ["成长分 >= 15", "趋势分 >= 15", "按总分倒序排序"],
        "scenario": "适合研究成长弹性和趋势共振样本。",
        "risks": ["高波动概率更高", "估值与回撤风险需单独审视"],
    },
    "conservative": {
        "name": "保守优选",
        "positioning": "偏向估值与质量同时较优的研究池。",
        "rules": ["估值分 >= 15", "质量分 >= 18", "按总分倒序排序"],
        "scenario": "适合寻找安全边际相对更高的研究样本。",
        "risks": ["成长性可能一般", "低估值逻辑可能较慢兑现"],
    },
    "volatile": {
        "name": "周波动 > 2%",
        "positioning": "按最近 5 个交易日波动率筛选的高波动样本池。",
        "rules": ["最近 5 个交易日振幅 >= 2%", "按波动率倒序排序"],
        "scenario": "适合研究波动来源与风险暴露。",
        "risks": ["高波动不代表高质量", "应默认视为风险观察区而非优选区"],
    },
}


def _stock_flags(stock: Stock, item: dict) -> list[str]:
    """生成股票风险标签体系（研究提示维度）"""
    flags = []
    name = stock.name or ""

    # === 结构性风险（确定性较高）===
    if "ST" in name.upper():
        flags.append("ST/风险警示")
    if "退" in name:
        flags.append("退市整理/退市风险")
    if item.get("volatility") and item["volatility"] >= 8:
        flags.append("短期波动偏高")
    if item.get("latest_close") is not None and item["latest_close"] < 2:
        flags.append("流动性风险")

    # === 估值风险 ===
    if item.get("pe") is not None and item["pe"] >= 60:
        flags.append("估值偏高")
    if item.get("pe") is not None and item["pe"] < 0:
        flags.append("亏损状态")
    if item.get("pb") is not None and item["pb"] >= 8:
        flags.append("PB 偏高")

    # === 财务风险（基于评分维度）===
    if item.get("quality_score", 0) < 10:
        flags.append("财务质量偏弱")
    if item.get("risk_score", 0) < 4:
        flags.append("风险评分偏低")
    if item.get("growth_score", 0) < 5:
        flags.append("成长动能不足")

    # === 趋势风险 ===
    if item.get("trend_score", 0) < 5:
        flags.append("趋势走弱")

    # === 数据完整性 ===
    missing = []
    if item.get("pe") is None:
        missing.append("PE")
    if item.get("pb") is None:
        missing.append("PB")
    if not stock.industry:
        missing.append("行业")
    if missing:
        flags.append(f"数据缺失({','.join(missing)})")

    # === 通用研究提示（非实时判断，需结合外部信息）===
    flags.append("宏观/行业变化需关注")

    return flags


def _build_pool_explanation(pool_type: str, stock: Stock, item: dict) -> dict:
    """为股票池标的生成自然语言解释"""
    flags = _stock_flags(stock, item)
    advantages = []
    risks = []

    # 优势维度
    if item.get("quality_score", 0) >= 20:
        advantages.append("基本面质量较好")
    if item.get("valuation_score", 0) >= 15:
        advantages.append("估值具备一定吸引力")
    if item.get("growth_score", 0) >= 15:
        advantages.append("成长维度较强")
    if item.get("trend_score", 0) >= 15:
        advantages.append("技术面趋势结构较好")
    if item.get("total_score", 0) >= 75:
        advantages.append("综合评分较高")

    # 风险维度（基于 flags 生成自然语言）
    if "ST/风险警示" in flags:
        risks.append("存在 ST 或风险警示标记")
    if "退市整理/退市风险" in flags:
        risks.append("存在退市相关风险")
    if "估值偏高" in flags:
        risks.append("当前估值偏高，修复空间不确定")
    if "亏损状态" in flags:
        risks.append("近期处于亏损状态")
    if "财务质量偏弱" in flags:
        risks.append("财务质量维度偏弱")
    if "趋势走弱" in flags:
        risks.append("技术面趋势走弱")
    if "短期波动偏高" in flags:
        risks.append("短期波动率偏高")
    if "流动性风险" in flags:
        risks.append("股价偏低，流动性可能不足")
    if "风险评分偏低" in flags:
        risks.append("综合风险评分偏低")
    if "成长动能不足" in flags:
        risks.append("成长动能不足")
    if "PB 偏高" in flags:
        risks.append("PB 估值偏高")
    if any("数据缺失" in f for f in flags):
        risks.append("部分财务或行情指标暂缺，解释基于现有数据")

    # 观察建议
    if pool_type == "risk":
        observe = "建议优先复核风险来源，结合行业景气和宏观环境判断，不建议作为优选标的。"
    elif pool_type == "volatile":
        observe = "建议放入波动观察区，优先核查波动原因和流动性状况。"
    elif pool_type == "quality":
        observe = "基本面质量较好，但仍需关注宏观环境、行业景气和估值波动。"
    elif pool_type == "undervalued":
        observe = "估值处于较低区间，但低估值不等于低风险，需结合基本面和行业变化判断。"
    elif pool_type == "trend":
        observe = "趋势结构较好，但需关注趋势持续性和成交量配合。"
    elif pool_type in ("steady", "conservative"):
        observe = "适合稳健配置，但仍需定期复核基本面和估值是否维持一致。"
    elif pool_type == "aggressive":
        observe = "成长性较强，但波动可能较大，适合风险承受能力较高的研究场景。"
    else:
        observe = "适合继续跟踪财务、估值和趋势是否维持一致。"

    # 入池原因
    pool_name = POOL_META.get(pool_type, {}).get("name", pool_type)
    entry_reason = f"{stock.name} 进入{pool_name}，主要因为质量/估值/成长/趋势规则中至少一项达到当前池子的筛选阈值。"
    if pool_type == "volatile" and item.get("volatility") is not None:
        entry_reason = f"{stock.name} 最近一周波动率约 {item['volatility']:.2f}%，因此被归入高波动观察池。"
    if pool_type == "risk":
        entry_reason = f"{stock.name} 因风险分偏低，被纳入风险预警池，需优先排查潜在异常。"
    if pool_type == "quality":
        entry_reason = f"{stock.name} 基本面质量维度较强，进入优质基本面池。"
    if pool_type == "undervalued":
        entry_reason = f"{stock.name} 估值维度处于较低区间，进入低估值研究池。"

    return {
        "entry_reason": entry_reason,
        "advantages": advantages or ["当前优势主要来自已披露指标中的相对表现"],
        "risks": risks or ["未发现显著额外风险，但仍需结合宏观环境和行业变化复核"],
        "observation": observe,
        "flags": flags,
        "incomplete": any("数据缺失" in f for f in flags),
    }


def _base_item(stock: Stock, score: StockScore | None, price: DailyPrice | None) -> dict:
    return {
        "symbol": stock.symbol,
        "name": stock.name,
        "market": stock.market,
        "industry": stock.industry,
        "total_score": score.total_score if score else 0,
        "quality_score": score.quality_score if score else 0,
        "valuation_score": score.valuation_score if score else 0,
        "growth_score": score.growth_score if score else 0,
        "trend_score": score.trend_score if score else 0,
        "risk_score": score.risk_score if score else 0,
        "rating": score.rating if score else "N/A",
        "reason": score.reason_summary if score else "",
        "latest_close": price.close if price else None,
        "pe": price.pe if price else None,
        "pb": price.pb if price else None,
    }


@router.get("")
def get_stock_pool(
    type: str = Query("quality", description="pool type"),
    db: Session = Depends(get_db),
):
    latest = db.query(func.max(StockScore.score_date)).scalar()
    if type == "volatile":
        result = _get_volatile_pool(db)
        result["meta"] = {
            **POOL_META["volatile"],
            "data_updated_at": result.get("date"),
            "research_only": True,
        }
        return result

    if not latest:
        return {"type": type, "items": [], "meta": {**POOL_META.get(type, {}), "data_updated_at": None, "research_only": True}}

    query = (
        db.query(StockScore, Stock)
        .join(Stock, StockScore.stock_id == Stock.id)
        .filter(StockScore.score_date == latest, Stock.status == "ACTIVE")
    )
    if type == "quality":
        query = query.filter(StockScore.quality_score >= 10).order_by(StockScore.quality_score.desc())
    elif type == "undervalued":
        query = query.filter(StockScore.valuation_score >= 5).order_by(StockScore.valuation_score.desc())
    elif type == "trend":
        query = query.filter(StockScore.trend_score >= 8).order_by(StockScore.trend_score.desc())
    elif type == "risk":
        query = query.filter(StockScore.risk_score < 5).order_by(StockScore.risk_score.asc())
    elif type == "steady":
        query = query.filter(StockScore.quality_score >= 20, StockScore.risk_score >= 6).order_by(StockScore.total_score.desc())
    elif type == "aggressive":
        query = query.filter(StockScore.growth_score >= 15, StockScore.trend_score >= 15).order_by(StockScore.total_score.desc())
    elif type == "conservative":
        query = query.filter(StockScore.valuation_score >= 15, StockScore.quality_score >= 18).order_by(StockScore.total_score.desc())
    else:
        query = query.order_by(StockScore.total_score.desc())

    results = query.limit(POOL_DISPLAY_LIMIT * 2).all()
    stock_ids = [stock.id for _, stock in results]
    latest_price_sq = (
        db.query(DailyPrice.stock_id, func.max(DailyPrice.trade_date).label("max_date"))
        .filter(DailyPrice.stock_id.in_(stock_ids))
        .group_by(DailyPrice.stock_id)
        .subquery()
    ) if stock_ids else None
    prices = (
        db.query(DailyPrice)
        .join(latest_price_sq, (DailyPrice.stock_id == latest_price_sq.c.stock_id) & (DailyPrice.trade_date == latest_price_sq.c.max_date))
        .all()
    ) if stock_ids else []
    price_map = {price.stock_id: price for price in prices}

    items = []
    for score, stock in results:
        price = price_map.get(stock.id)
        if type == "steady" and price and price.pe and price.pe >= 60:
            continue
        item = _base_item(stock, score, price)
        item["explanation"] = _build_pool_explanation(type, stock, item)
        item["risk_flags"] = item["explanation"]["flags"]
        items.append(item)

    items = items[:POOL_DISPLAY_LIMIT]
    return {
        "type": type,
        "date": str(latest),
        "count": len(items),
        "items": items,
        "has_more": len(items) >= POOL_DISPLAY_LIMIT,
        "meta": {
            **POOL_META.get(type, {"name": type}),
            "data_updated_at": str(latest),
            "research_only": True,
        },
    }


def _get_volatile_pool(db: Session) -> dict:
    latest_date = db.query(func.max(DailyPrice.trade_date)).scalar()
    if not latest_date:
        return {"type": "volatile", "items": [], "date": None, "count": 0}

    recent_dates = db.query(DailyPrice.trade_date).distinct().order_by(DailyPrice.trade_date.desc()).limit(5).all()
    if len(recent_dates) < 2:
        return {"type": "volatile", "items": [], "date": str(latest_date), "count": 0}

    min_date = recent_dates[-1][0]
    stats = (
        db.query(
            DailyPrice.stock_id,
            func.max(DailyPrice.high).label("week_high"),
            func.min(DailyPrice.low).label("week_low"),
            func.max(DailyPrice.close).label("latest_close"),
            func.count().label("day_count"),
        )
        .join(Stock, Stock.id == DailyPrice.stock_id)
        .filter(Stock.status == "ACTIVE", DailyPrice.trade_date >= min_date, DailyPrice.trade_date <= latest_date)
        .group_by(DailyPrice.stock_id)
        .having(func.count() >= 2)
        .all()
    )

    items = []
    stock_ids = []
    for row in stats:
        volatility = (row.week_high - row.week_low) / row.week_low * 100 if row.week_low > 0 else 0
        if volatility >= 2:
            stock_ids.append(row.stock_id)

    stocks = db.query(Stock).filter(Stock.id.in_(stock_ids)).all() if stock_ids else []
    stock_map = {stock.id: stock for stock in stocks}
    latest_price_sq = (
        db.query(DailyPrice.stock_id, func.max(DailyPrice.trade_date).label("max_date"))
        .filter(DailyPrice.stock_id.in_(stock_ids))
        .group_by(DailyPrice.stock_id)
        .subquery()
    ) if stock_ids else None
    latest_prices = (
        db.query(DailyPrice)
        .join(latest_price_sq, (DailyPrice.stock_id == latest_price_sq.c.stock_id) & (DailyPrice.trade_date == latest_price_sq.c.max_date))
        .all()
    ) if stock_ids else []
    price_map = {price.stock_id: price for price in latest_prices}

    first_price_sq = (
        db.query(DailyPrice.stock_id, func.min(DailyPrice.trade_date).label("min_date"))
        .filter(DailyPrice.stock_id.in_(stock_ids), DailyPrice.trade_date >= min_date)
        .group_by(DailyPrice.stock_id)
        .subquery()
    ) if stock_ids else None
    first_prices = (
        db.query(DailyPrice)
        .join(first_price_sq, (DailyPrice.stock_id == first_price_sq.c.stock_id) & (DailyPrice.trade_date == first_price_sq.c.min_date))
        .all()
    ) if stock_ids else []
    first_price_map = {price.stock_id: price.close for price in first_prices}

    latest_score_date = db.query(func.max(StockScore.score_date)).scalar()
    score_records = (
        db.query(StockScore)
        .filter(StockScore.stock_id.in_(stock_ids), StockScore.score_date == latest_score_date)
        .all()
    ) if stock_ids and latest_score_date else []
    score_map = {score.stock_id: score for score in score_records}

    for row in stats:
        if row.stock_id not in stock_ids:
            continue
        stock = stock_map.get(row.stock_id)
        if not stock:
            continue
        volatility = (row.week_high - row.week_low) / row.week_low * 100 if row.week_low > 0 else 0
        first_close = first_price_map.get(row.stock_id, row.latest_close)
        price_change = (row.latest_close - first_close) / first_close * 100 if first_close and first_close > 0 else 0
        score = score_map.get(row.stock_id)
        price = price_map.get(row.stock_id)
        item = _base_item(stock, score, price)
        item["volatility"] = round(volatility, 2)
        item["price_change"] = round(price_change, 2)
        item["reason"] = f"最近一周波动率 {volatility:.1f}% | 区间涨跌幅 {price_change:+.1f}%"
        item["explanation"] = _build_pool_explanation("volatile", stock, item)
        item["risk_flags"] = item["explanation"]["flags"]
        items.append(item)

    items.sort(key=lambda item: item.get("volatility", 0), reverse=True)
    items = items[:POOL_DISPLAY_LIMIT]
    return {
        "type": "volatile",
        "date": str(latest_date),
        "count": len(items),
        "items": items,
        "has_more": len(items) >= POOL_DISPLAY_LIMIT,
    }
