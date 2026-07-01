"""Stock pool API with rule explanations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.daily_price import DailyPrice
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.services.data_credibility import REAL_SCORE_SOURCE, include_demo_enabled
from app.services.research_display_summary import build_research_display_summary
from app.services.score_diagnostics import diagnose_real_scores
from app.services.system_status import build_system_status

router = APIRouter(prefix="/api/pools", tags=["股票池"])

POOL_DISPLAY_LIMIT = 30

POOL_META = {
    "quality": {
        "name": "优质基本面池",
        "positioning": "以盈利能力、现金流和财务结构为主的基本面筛选池。",
        "rules": ["质量分 >= 10", "按质量分倒序排序"],
        "scenario": "适合研究长期经营质量较稳健的公司。",
        "risks": ["若估值偏高或趋势偏弱，短期表现可能不稳", "部分财务数据可能存在披露滞后"],
    },
    "undervalued": {
        "name": "低估值池",
        "positioning": "优先展示估值相对更低或估值吸引力更高的样本。",
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


def _score_query_for_mode(db: Session, include_demo: bool):
    query = db.query(StockScore)
    if not include_demo:
        query = query.filter(StockScore.score_source == REAL_SCORE_SOURCE)
    return query


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
        "score_source": getattr(score, "score_source", None),
    }


def _stock_flags(stock: Stock, item: dict) -> list[str]:
    flags = []
    name = stock.name or ""
    if "ST" in name.upper():
        flags.append("ST/风险警示")
    if "退" in name:
        flags.append("退市风险")
    if item.get("volatility") and item["volatility"] >= 8:
        flags.append("短期波动偏高")
    if item.get("latest_close") is not None and item["latest_close"] < 2:
        flags.append("流动性风险")
    if item.get("pe") is not None and item["pe"] >= 60:
        flags.append("估值偏高")
    if item.get("quality_score", 0) < 10:
        flags.append("财务质量偏弱")
    if item.get("risk_score", 0) < 4:
        flags.append("风险评分偏低")
    missing = []
    if item.get("pe") is None:
        missing.append("PE")
    if item.get("pb") is None:
        missing.append("PB")
    if not stock.industry:
        missing.append("行业")
    if missing:
        flags.append(f"数据缺失({','.join(missing)})")
    return flags


def _build_pool_explanation(pool_type: str, stock: Stock, item: dict) -> dict:
    flags = _stock_flags(stock, item)
    risks = []
    if "ST/风险警示" in flags:
        risks.append("存在 ST 或风险警示标记")
    if "退市风险" in flags:
        risks.append("存在退市相关风险")
    if "估值偏高" in flags:
        risks.append("当前估值偏高，修复空间不确定")
    if any(flag.startswith("数据缺失") for flag in flags):
        risks.append("部分指标缺失，解释基于现有数据生成")
    if "短期波动偏高" in flags:
        risks.append("短期波动率偏高")

    observation = "适合继续跟踪财务、估值和趋势是否维持一致。"
    if pool_type == "risk":
        observation = "建议优先复核风险来源，不应作为优选研究样本。"
    elif pool_type == "volatile":
        observation = "建议放入波动观察区，优先核查波动原因和流动性情况。"

    pool_name = POOL_META.get(pool_type, {}).get("name", pool_type)
    return {
        "entry_reason": f"{stock.name} 进入{pool_name}，主要因为现有评分满足该池规则。",
        "advantages": ["当前解释仅基于数据库中已存在的评分与价格字段生成。"] if not item.get("reason") else [item.get("reason")],
        "risks": risks or ["未发现额外显著风险，但仍需结合宏观和行业变化复核。"],
        "observation": observation,
        "flags": flags,
        "incomplete": any(flag.startswith("数据缺失") for flag in flags),
    }


def _empty_pool(pool_type: str, system_status: dict, diagnostics: dict | None = None) -> dict:
    diagnostics_summary = diagnostics or {}
    return {
        "type": pool_type,
        "date": None,
        "count": 0,
        "items": [],
        "has_more": False,
        "message": _empty_pool_message(system_status, diagnostics_summary),
        "meta": {
            **POOL_META.get(pool_type, {"name": pool_type}),
            "data_updated_at": None,
            "research_only": True,
            "display_limit": POOL_DISPLAY_LIMIT,
            "warning": system_status.get("warning"),
            "data_mode": system_status.get("data_mode"),
        },
        "diagnostics": {
            "real_score_count": diagnostics_summary.get("real_count", 0),
            "demo_score_count": diagnostics_summary.get("demo_count", 0),
            "formal_real_count": diagnostics_summary.get("formal_real_count", 0),
            "real_observation_count": diagnostics_summary.get("real_observation_count", 0),
            "risk_observation_count": diagnostics_summary.get("risk_observation_count", 0),
            "data_quality_limited_count": diagnostics_summary.get("data_quality_limited_count", 0),
            "reason_code": _empty_pool_reason_code(system_status, diagnostics_summary),
            "top_reasons": diagnostics_summary.get("top_reasons", []),
            "launch_data_status": diagnostics_summary.get("launch_data_status"),
        },
    }


def _empty_pool_reason_code(system_status: dict, diagnostics_summary: dict | None = None) -> str:
    diagnostics_summary = diagnostics_summary or {}
    counts = system_status.get("counts") or {}
    financial_count = system_status.get("financial_metrics_count", 0) or counts.get("financial_metrics", 0) or 0
    technical_count = system_status.get("technical_indicators_count", 0) or counts.get("technical_indicators", 0) or 0
    if financial_count > 0 and technical_count > 0 and diagnostics_summary.get("real_count", 0) > 0:
        return "NO_REAL_SAMPLE_MATCH_POOL_RULE"
    return "DATA_NOT_READY"


def _empty_pool_message(system_status: dict, diagnostics_summary: dict | None = None) -> str:
    diagnostics_summary = diagnostics_summary or {}
    real_count = diagnostics_summary.get("real_count", 0)
    if _empty_pool_reason_code(system_status, diagnostics_summary) == "NO_REAL_SAMPLE_MATCH_POOL_RULE":
        return f"当前暂无可正式展示的股票池。真实评分样本已接入({real_count}只)，但当前样本多处于风险观察或数据质量受限状态，尚未达到该股票池筛选门槛。"
    return f"当前暂无可正式展示的股票池。真实评分样本已接入({real_count}只)，但当前样本多处于风险观察或数据质量受限状态，尚未达到该股票池筛选门槛。"


@router.get("")
def get_stock_pool(
    type: str = Query("quality", description="pool type"),
    limit: int = Query(30, ge=1, le=30, description="max items"),
    include_demo: bool = Query(False, description="是否包含演示评分"),
    db: Session = Depends(get_db),
):
    include_demo = include_demo_enabled(include_demo)
    system_status = build_system_status(db)
    summary = build_research_display_summary(db, include_demo=include_demo)
    diagnostics = summary["diagnostics"]
    diagnostics_summary = diagnostics
    detail_rows = diagnose_real_scores(db)
    diagnostic_map = {item.get("stock_code"): item for item in detail_rows.get("items", [])}
    effective_limit = min(limit, POOL_DISPLAY_LIMIT)

    latest_query = _score_query_for_mode(db, include_demo)
    latest = latest_query.with_entities(func.max(StockScore.score_date)).scalar()
    if not latest:
        return _empty_pool(type, system_status, diagnostics=diagnostics)

    if type == "volatile":
        result = _get_volatile_pool(db, include_demo=include_demo)
        result["meta"] = {
            **POOL_META["volatile"],
            "data_updated_at": result.get("date"),
            "research_only": True,
            "display_limit": effective_limit,
            "warning": system_status.get("warning"),
            "data_mode": system_status.get("data_mode"),
        }
        if not result.get("items") and not include_demo:
            result["message"] = _empty_pool_message(system_status, diagnostics_summary)
            result["diagnostics"] = {
                "real_score_count": diagnostics_summary.get("real_count", 0),
                "demo_score_count": diagnostics_summary.get("demo_count", 0),
                "formal_real_count": diagnostics_summary.get("formal_real_count", 0),
                "real_observation_count": diagnostics_summary.get("real_observation_count", 0),
                "risk_observation_count": diagnostics_summary.get("risk_observation_count", 0),
                "data_quality_limited_count": diagnostics_summary.get("data_quality_limited_count", 0),
                "reason_code": _empty_pool_reason_code(system_status, diagnostics_summary),
                "top_reasons": diagnostics_summary.get("top_reasons", []),
                "launch_data_status": diagnostics_summary.get("launch_data_status"),
            }
        return result

    query = (
        db.query(StockScore, Stock)
        .join(Stock, StockScore.stock_id == Stock.id)
        .filter(StockScore.score_date == latest, Stock.status == "ACTIVE")
    )
    if not include_demo:
        query = query.filter(StockScore.score_source == REAL_SCORE_SOURCE)

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

    results = query.limit(effective_limit * 2).all()
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
        if not include_demo:
            diagnostic = diagnostic_map.get(stock.symbol, {})
            if diagnostic.get("display_tier") != "formal_real":
                continue
        price = price_map.get(stock.id)
        if type == "steady" and price and price.pe and price.pe >= 60:
            continue
        item = _base_item(stock, score, price)
        item["explanation"] = _build_pool_explanation(type, stock, item)
        item["risk_flags"] = item["explanation"]["flags"]
        items.append(item)

    items = items[:effective_limit]
    payload = {
        "type": type,
        "date": str(latest),
        "count": len(items),
        "items": items,
        "has_more": len(items) >= effective_limit,
        "meta": {
            **POOL_META.get(type, {"name": type}),
            "data_updated_at": str(latest),
            "research_only": True,
            "display_limit": effective_limit,
            "warning": system_status.get("warning"),
            "data_mode": system_status.get("data_mode"),
        },
    }
    if not include_demo and not items:
        payload["message"] = _empty_pool_message(system_status, diagnostics_summary)
        payload["diagnostics"] = {
            "real_score_count": diagnostics_summary.get("real_count", 0),
            "demo_score_count": diagnostics_summary.get("demo_count", 0),
            "formal_real_count": diagnostics_summary.get("formal_real_count", 0),
            "real_observation_count": diagnostics_summary.get("real_observation_count", 0),
            "risk_observation_count": diagnostics_summary.get("risk_observation_count", 0),
            "data_quality_limited_count": diagnostics_summary.get("data_quality_limited_count", 0),
            "reason_code": _empty_pool_reason_code(system_status, diagnostics_summary),
            "top_reasons": diagnostics_summary.get("top_reasons", []),
            "launch_data_status": diagnostics_summary.get("launch_data_status"),
        }
    return payload


def _get_volatile_pool(db: Session, include_demo: bool = False) -> dict:
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

    latest_score_date = db.query(func.max(StockScore.score_date)).filter(StockScore.stock_id.in_(stock_ids)).scalar()
    score_records_query = db.query(StockScore).filter(StockScore.stock_id.in_(stock_ids), StockScore.score_date == latest_score_date)
    if not include_demo:
        score_records_query = score_records_query.filter(StockScore.score_source == REAL_SCORE_SOURCE)
    score_records = score_records_query.all() if stock_ids and latest_score_date else []
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
