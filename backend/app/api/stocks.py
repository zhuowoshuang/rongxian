"""股票相关 API"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import and_, case, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.stock import Stock
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.technical_indicator import TechnicalIndicator
from app.api.auth import get_current_admin, get_member_user
from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal
from app.models.report import Report
from app.models.research_report import ResearchReport
from app.core.constants import ReportType
from app.services.compliance import signal_display_label, sanitize_nested_payload, sanitize_research_text
from app.services.data_coverage import get_bulk_data_coverage, get_stock_data_coverage
from app.services.data_credibility import (
    include_demo_enabled,
    REAL_SCORE_SOURCE,
    REAL_SIGNAL_SOURCE,
    UNKNOWN_SCORE_SOURCE,
    valuation_readiness,
    build_data_readiness,
    score_is_real,
    score_label,
)
from app.services.research_display_summary import build_research_display_summary
from app.services.company_news_service import get_company_news_summary
from app.services.earnings_signal_service import get_earnings_signal
from app.services.industry_news_service import get_industry_support
from app.services.shareholder_signal_service import get_shareholder_signal
from app.services.volatility_signal_service import get_volatility_signal
from app.services.scoring import (
    _latest_financial_for_stock,
    _previous_financial_for_stock,
    calculate_trend_score_v2,
)
from app.services.score_diagnostics import diagnose_real_scores, diagnose_single_stock_score

router = APIRouter(prefix="/api/stocks", tags=["股票"])


@router.get("")
@router.get("/")
def list_stocks(
    market: str | None = Query(None, description="市场: A_SHARE / HK"),
    rating: str | None = Query(None, description="研究评级: BUY / ADD / WATCH / REDUCE / SELL"),
    keyword: str | None = Query(None, description="代码或名称关键词"),
    include_demo: bool = Query(False, description="是否包含演示评分"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(get_member_user),
):
    """真实个股评分库列表，聚合股票、评分、信号与最新行情。"""
    include_demo = include_demo_enabled(include_demo)
    latest_score_subquery = (
        db.query(
            StockScore.stock_id.label("stock_id"),
            func.max(StockScore.score_date).label("latest_score_date"),
        )
        .group_by(StockScore.stock_id)
        .subquery()
    )

    latest_signal_subquery = (
        db.query(
            TradeSignal.stock_id.label("stock_id"),
            func.max(TradeSignal.signal_date).label("latest_signal_date"),
        )
        .group_by(TradeSignal.stock_id)
        .subquery()
    )

    latest_price_subquery = (
        db.query(
            DailyPrice.stock_id.label("stock_id"),
            func.max(DailyPrice.trade_date).label("latest_trade_date"),
        )
        .group_by(DailyPrice.stock_id)
        .subquery()
    )

    base_query = (
        db.query(
            Stock.id.label("stock_id"),
            Stock.symbol,
            Stock.name,
            Stock.market,
            Stock.exchange,
            Stock.industry,
            Stock.status.label("stock_status"),
            StockScore.total_score,
            StockScore.quality_score,
            StockScore.valuation_score,
            StockScore.growth_score,
            StockScore.trend_score,
            StockScore.risk_score,
            StockScore.rating,
            StockScore.score_source,
            StockScore.score_date,
            StockScore.reason_summary,
            TradeSignal.signal_type,
            TradeSignal.signal_strength,
            TradeSignal.signal_source,
            TradeSignal.signal_date,
            TradeSignal.logic_json,
            DailyPrice.close.label("latest_close"),
            DailyPrice.pe.label("pe"),
            DailyPrice.pb.label("pb"),
            DailyPrice.trade_date.label("trade_date"),
            DailyPrice.turnover_rate,
        )
        .select_from(latest_score_subquery)
        .join(Stock, Stock.id == latest_score_subquery.c.stock_id)
        .join(
            StockScore,
            and_(
                StockScore.stock_id == latest_score_subquery.c.stock_id,
                StockScore.score_date == latest_score_subquery.c.latest_score_date,
            ),
        )
        .outerjoin(latest_signal_subquery, latest_signal_subquery.c.stock_id == Stock.id)
        .outerjoin(
            TradeSignal,
            and_(
                TradeSignal.stock_id == latest_signal_subquery.c.stock_id,
                TradeSignal.signal_date == latest_signal_subquery.c.latest_signal_date,
            ),
        )
        .outerjoin(latest_price_subquery, latest_price_subquery.c.stock_id == Stock.id)
        .outerjoin(
            DailyPrice,
            and_(
                DailyPrice.stock_id == latest_price_subquery.c.stock_id,
                DailyPrice.trade_date == latest_price_subquery.c.latest_trade_date,
            ),
        )
        .filter(Stock.status != "DELETED")
    )
    if not include_demo:
        base_query = base_query.filter(StockScore.score_source == REAL_SCORE_SOURCE)

    if market:
        base_query = base_query.filter(Stock.market == market)
    if rating:
        base_query = base_query.filter(StockScore.rating == rating)
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        base_query = base_query.filter(
            (Stock.symbol.like(f"%{escaped}%", escape="\\")) | (Stock.name.like(f"%{escaped}%", escape="\\"))
        )

    summary_payload = build_research_display_summary(db, include_demo=include_demo)
    diagnostics_summary = summary_payload["diagnostics"]

    total = base_query.count()
    all_rows = base_query.all()

    a_share = sum(1 for row in all_rows if row.market == "A_SHARE")
    hk = sum(1 for row in all_rows if row.market == "HK")
    real_rows = [row for row in all_rows if row.score_source == REAL_SCORE_SOURCE]
    highest_score = max((row.total_score or 0) for row in real_rows) if real_rows else 0
    risk_elevated_count = sum(
        1
        for row in all_rows
        if row.score_source == REAL_SCORE_SOURCE and (row.signal_type or row.rating) in ("REDUCE", "SELL")
    )

    rows = (
        base_query.order_by(
            case((StockScore.score_source == REAL_SCORE_SOURCE, 1), else_=0).desc(),
            StockScore.total_score.desc().nullslast(),
            StockScore.score_date.desc().nullslast(),
            Stock.symbol.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    coverage_map = get_bulk_data_coverage(db, [row.symbol for row in rows])

    items = []
    for row in rows:
        price_change = None
        if row.logic_json and isinstance(row.logic_json, dict):
            raw_change = row.logic_json.get("change_pct")
            if isinstance(raw_change, (int, float)):
                price_change = raw_change

        risk_flags = []
        stock_name = row.name or ""
        stock_status = (row.stock_status or "").upper()

        # 结构性风险
        if "ST" in stock_name.upper():
            risk_flags.append("ST/风险警示")
        if "退" in stock_name or stock_status == "DELISTED":
            risk_flags.append("退市风险")
        if isinstance(row.turnover_rate, (int, float)) and row.turnover_rate < 0.2:
            risk_flags.append("流动性风险")

        # 估值风险
        if isinstance(row.pe, (int, float)) and row.pe >= 60:
            risk_flags.append("估值偏高")
        if isinstance(row.pe, (int, float)) and row.pe < 0:
            risk_flags.append("亏损状态")

        # 财务风险
        if isinstance(row.quality_score, (int, float)) and row.quality_score < 10:
            risk_flags.append("财务质量偏弱")
        if isinstance(row.risk_score, (int, float)) and row.risk_score < 4:
            risk_flags.append("风险评分偏低")
        if isinstance(row.growth_score, (int, float)) and row.growth_score < 5:
            risk_flags.append("成长动能不足")

        # 趋势风险
        if isinstance(row.trend_score, (int, float)) and row.trend_score < 5:
            risk_flags.append("趋势走弱")
        if row.signal_type in ("REDUCE", "SELL"):
            risk_flags.append("风险升高")

        # 数据完整性
        missing = []
        if row.total_score is None:
            missing.append("总分")
        if row.quality_score is None:
            missing.append("质量")
        if row.valuation_score is None:
            missing.append("估值")
        if missing:
            risk_flags.append(f"数据缺失({','.join(missing)})")

        # 通用研究提示
        risk_flags.append("宏观/行业变化需关注")

        items.append(
            {
                "stock_id": row.stock_id,
                "symbol": row.symbol,
                "name": sanitize_research_text(row.name),
                "market": row.market,
                "exchange": row.exchange,
                "industry": sanitize_research_text(row.industry) if row.industry else None,
                "rating": row.rating,
                "rating_label": signal_display_label(row.rating) if row.rating and row.score_source == REAL_SCORE_SOURCE else score_label(row.score_source),
                "signal_type": row.signal_type,
                "signal_label": signal_display_label(row.signal_type) if row.signal_type else None,
                "signal_strength": row.signal_strength,
                "total_score": row.total_score if row.score_source == REAL_SCORE_SOURCE else None,
                "quality_score": row.quality_score if row.score_source == REAL_SCORE_SOURCE else None,
                "valuation_score": row.valuation_score if row.score_source == REAL_SCORE_SOURCE else None,
                "growth_score": row.growth_score if row.score_source == REAL_SCORE_SOURCE else None,
                "trend_score": row.trend_score if row.score_source == REAL_SCORE_SOURCE else None,
                "risk_score": row.risk_score if row.score_source == REAL_SCORE_SOURCE else None,
                "latest_close": row.latest_close,
                "change_pct": price_change,
                "updated_at": str(row.score_date or row.signal_date or row.trade_date) if (row.score_date or row.signal_date or row.trade_date) else None,
                "score_date": str(row.score_date) if row.score_date else None,
                "signal_date": str(row.signal_date) if row.signal_date else None,
                "reason_summary": "演示评分已隔离，待真实评分生成" if row.score_source != REAL_SCORE_SOURCE else sanitize_research_text(row.reason_summary),
                "score_source": row.score_source or UNKNOWN_SCORE_SOURCE,
                "score_label": score_label(row.score_source),
                "valuation_status": valuation_readiness(row.pe, row.pb),
                "risk_flags": risk_flags[:3],
                "coverage_level": coverage_map.get(row.symbol, {}).get("coverage_level", "no_data"),
                "readiness_label": coverage_map.get(row.symbol, {}).get("readiness_label", "无可用数据"),
                "display_tier": "demo_only" if row.score_source != REAL_SCORE_SOURCE else (
                    "data_quality_limited"
                    if coverage_map.get(row.symbol, {}).get("blocking_reasons") or (row.pe is None and row.pb is None) or not row.industry
                    else "real_observation" if (row.signal_type or row.rating) in ("REDUCE", "SELL") or (row.total_score or 0) < 55
                    else "formal_real"
                ),
                "display_tier_label": (
                    "仅演示"
                    if row.score_source != REAL_SCORE_SOURCE
                    else "数据质量受限"
                    if coverage_map.get(row.symbol, {}).get("blocking_reasons") or (row.pe is None and row.pb is None) or not row.industry
                    else "真实观察"
                    if (row.signal_type or row.rating) in ("REDUCE", "SELL") or (row.total_score or 0) < 55
                    else "正式真实"
                ),
                "primary_low_score_reason": (
                    (coverage_map.get(row.symbol, {}).get("blocking_reasons") or [None])[0]
                    or ("估值字段缺失" if row.pe is None and row.pb is None else None)
                    or ("行业标签缺失" if not row.industry else None)
                    or ("质量评分偏低" if isinstance(row.quality_score, (int, float)) and row.quality_score < 12 else None)
                    or ("估值性价比不足" if isinstance(row.valuation_score, (int, float)) and row.valuation_score < 8 else None)
                    or ("成长动能偏弱" if isinstance(row.growth_score, (int, float)) and row.growth_score < 8 else None)
                    or ("趋势评分偏低" if isinstance(row.trend_score, (int, float)) and row.trend_score < 8 else None)
                    or ("风险承压" if isinstance(row.risk_score, (int, float)) and row.risk_score < 5 else None)
                    or ("评分结构正常" if row.score_source == REAL_SCORE_SOURCE else "演示评分已隔离")
                ),
                "blocking_reasons": coverage_map.get(row.symbol, {}).get("blocking_reasons", []),
            }
        )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
        "summary": {
            "rated_stocks": total,
            "rated_records_total": total,
            "current_result_count": total,
            "current_page_count": len(items),
            "current_page_items_count": len(items),
            "a_share": a_share,
            "hk": hk,
            "highest_score": round(highest_score, 1) if highest_score else 0,
            "risk_elevated": risk_elevated_count,
            "real_score_count": summary_payload["system"]["real_score_count"],
            "demo_score_count": summary_payload["system"]["demo_score_count"],
            "formal_real_count": diagnostics_summary.get("formal_real_count", 0),
            "real_observation_count": diagnostics_summary.get("real_observation_count", 0),
            "data_quality_limited_count": diagnostics_summary.get("data_quality_limited_count", 0),
            "data_insufficient_count": diagnostics_summary.get("data_insufficient_count", 0),
            "real_highest_score": diagnostics_summary.get("real_highest_score", 0),
            "include_demo": include_demo,
        },
    }


@router.get("/search")
def search_stocks(
    keyword: str = Query(..., description="股票代码/名称/关键词"),
    market: str = Query(None, description="市场: A_SHARE / HK"),
    db: Session = Depends(get_db),
):
    """
    搜索股票（三级降级）
    1. 本地数据库
    2. 预置股票宇宙（268 只）
    3. 东方财富实时 API（任意股票）
    """
    query = db.query(Stock).filter(Stock.status == "ACTIVE")
    if market:
        query = query.filter(Stock.market == market)
    # 转义 LIKE 特殊字符（%、_）防止模式操纵
    escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    query = query.filter(
        (Stock.symbol.like(f"%{escaped}%", escape="\\")) | (Stock.name.like(f"%{escaped}%", escape="\\"))
    )
    stocks = query.limit(20).all()

    # 本地无结果时，从预置股票宇宙中查找并自动入库
    if not stocks:
        from app.stock_universe import search_stocks_local
        candidates = search_stocks_local(keyword, market=market, limit=10)
        for c in candidates:
            existing = db.query(Stock).filter(Stock.symbol == c["symbol"]).first()
            if existing:
                stocks.append(existing)
            else:
                new_stock = Stock(
                    symbol=c["symbol"],
                    name=c["name"],
                    market=c["market"],
                    exchange=c["exchange"],
                    industry=c.get("industry"),
                    sector=c.get("sector"),
                    status="ACTIVE",
                )
                db.add(new_stock)
                db.flush()
                stocks.append(new_stock)
        if stocks:
            db.commit()

    # 仍然无结果时，从东方财富实时 API 搜索
    if not stocks:
        try:
            from app.data_providers.http_client import get_json
            import logging
            logger = logging.getLogger(__name__)
            # 东方财富搜索 API
            url = f"https://searchapi.eastmoney.com/api/suggest/get?input={keyword}&type=14&token=D43BF722C8E33BDC906FB84D85E326E8&count=10"
            data = get_json(url, timeout=5)
            items = data.get("QuotationCodeTable", {}).get("Data", []) or []
            for item in items:
                code = item.get("Code", "")
                name = item.get("Name", "")
                market_type = item.get("MktNum", "")
                if not code or not name:
                    continue
                # 判断市场
                if market_type == "1" or code.startswith(("6", "5", "9")):
                    stk_market, exchange = "A_SHARE", "SH"
                elif market_type == "0" or code.startswith(("0", "3")):
                    stk_market, exchange = "A_SHARE", "SZ"
                elif market_type in ("2", "128"):
                    stk_market, exchange = "HK", "HK"
                else:
                    stk_market, exchange = "A_SHARE", "SZ"
                if market and stk_market != market:
                    continue
                # 检查是否已存在
                existing = db.query(Stock).filter(Stock.symbol == code).first()
                if existing:
                    stocks.append(existing)
                else:
                    new_stock = Stock(
                        symbol=code, name=name, market=stk_market,
                        exchange=exchange, industry="", status="ACTIVE",
                    )
                    db.add(new_stock)
                    db.flush()
                    stocks.append(new_stock)
            if stocks:
                db.commit()
                logger.info(f"东方财富搜索 '{keyword}' 找到 {len(stocks)} 只")
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"东方财富搜索 API 失败: {e}")

    return [
        {
            "id": s.id,
            "symbol": s.symbol,
            "name": s.name,
            "market": s.market,
            "exchange": s.exchange,
            "industry": s.industry,
        }
        for s in stocks
    ]


@router.get("/available-for-backtest")
def get_available_for_backtest(
    market: str = Query("A_SHARE", description="市场: A_SHARE / HK"),
    min_price_count: int = Query(30, ge=1, le=3650),
    min_date_range_days: int = Query(0, ge=0, le=3650),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    limit: int = Query(12, ge=1, le=50),
    db: Session = Depends(get_db),
    user=Depends(get_member_user),
):
    full_threshold = max(120, min_price_count)
    basic_threshold = max(60, min_price_count)
    preview_threshold = max(30, min_price_count)
    price_filters = [DailyPrice.stock_id == Stock.id]
    if start_date:
        price_filters.append(DailyPrice.trade_date >= start_date)
    if end_date:
        price_filters.append(DailyPrice.trade_date <= end_date)

    stock_rows = (
        db.query(
            Stock.id.label("stock_id"),
            Stock.symbol.label("stock_code"),
            Stock.name.label("stock_name"),
            Stock.market,
            Stock.industry,
            func.min(DailyPrice.trade_date).label("available_start_date"),
            func.max(DailyPrice.trade_date).label("available_end_date"),
            func.count(DailyPrice.id).label("price_count"),
        )
        .outerjoin(DailyPrice, and_(*price_filters))
        .filter(Stock.market == market, Stock.status == "ACTIVE")
        .group_by(Stock.id, Stock.symbol, Stock.name, Stock.market, Stock.industry)
        .order_by(func.count(DailyPrice.id).desc(), Stock.symbol.asc())
        .all()
    )

    def classify_support(price_count: int, available_start, available_end):
        if price_count <= 0:
            return (
                "no_price",
                False,
                "当前日期范围内暂无可用行情样本，暂时无法进行回测。",
                "暂无可用行情样本，请调整日期范围或等待数据刷新。",
            )

        range_days = 0
        if available_start and available_end:
            range_days = max((available_end - available_start).days, 0)
        if min_date_range_days and range_days < min_date_range_days:
            return (
                "insufficient",
                False,
                f"已有 {price_count} 条行情，但覆盖天数仅 {range_days} 天，暂不满足回测范围要求。",
                f"样本覆盖天数不足，至少需要 {min_date_range_days} 天。",
            )
        if price_count >= full_threshold:
            return ("full", True, f"已有 {price_count} 条真实行情样本，可进行完整回测观察。", None)
        if price_count >= basic_threshold:
            return ("basic", True, f"已有 {price_count} 条真实行情样本，可进行基础回测观察。", None)
        if price_count >= preview_threshold:
            return ("preview", True, f"已有 {price_count} 条真实行情样本，仅建议做预览回测，不代表完整结论。", None)
        return (
            "insufficient",
            False,
            f"当前仅有 {price_count} 条真实行情样本，暂时无法完成回测。",
            f"真实行情样本不足，至少需要 {preview_threshold} 条。",
        )

    items = []
    for row in stock_rows:
        has_financial = db.query(FinancialMetric.id).filter(FinancialMetric.stock_id == row.stock_id).first() is not None
        has_technical = db.query(TechnicalIndicator.id).filter(TechnicalIndicator.stock_id == row.stock_id).first() is not None
        price_count = int(row.price_count or 0)
        support_level, supports_backtest, reason, missing_reason = classify_support(
            price_count,
            row.available_start_date,
            row.available_end_date,
        )
        items.append(
            {
                "stock_code": row.stock_code,
                "stock_name": sanitize_research_text(row.stock_name),
                "market": row.market,
                "industry": sanitize_research_text(row.industry) if row.industry else None,
                "available_start_date": _as_str(row.available_start_date),
                "available_end_date": _as_str(row.available_end_date),
                "price_count": price_count,
                "supports_backtest": supports_backtest,
                "support_level": support_level,
                "reason": reason,
                "missing_reason": missing_reason,
                "supports_report": bool(price_count > 0),
                "supports_watchlist": True,
                "has_financial_snapshot": has_financial,
                "has_technical_snapshot": has_technical,
            }
        )

    level_order = {"full": 0, "basic": 1, "preview": 2, "insufficient": 3, "no_price": 4}
    items.sort(key=lambda item: (level_order.get(item["support_level"], 9), -item["price_count"], item["stock_code"]))
    full_items = [item for item in items if item["support_level"] == "full"]
    basic_items = [item for item in items if item["support_level"] == "basic"]
    preview_items = [item for item in items if item["support_level"] == "preview"]
    unsupported = [item for item in items if item["support_level"] in {"insufficient", "no_price"}]
    price_stock_count = sum(1 for item in items if item["price_count"] > 0)
    return {
        "market": market,
        "total_price_stocks": price_stock_count,
        "supported_count": len(full_items) + len(basic_items) + len(preview_items),
        "full_count": len(full_items),
        "basic_count": len(basic_items),
        "preview_count": len(preview_items),
        "partial_count": len(preview_items),
        "unsupported_count": len(unsupported),
        "requirements": {
            "full_backtest_min_price_count": full_threshold,
            "basic_backtest_min_price_count": basic_threshold,
            "preview_min_price_count": preview_threshold,
            "min_date_range_days": min_date_range_days,
        },
        "items": items[:limit],
        "unavailable_examples": unsupported[: min(8, len(unsupported))],
        "summary": {
            "market": market,
            "supported_count": len(full_items) + len(basic_items) + len(preview_items),
            "full_count": len(full_items),
            "basic_count": len(basic_items),
            "preview_count": len(preview_items),
            "unsupported_count": len(unsupported),
            "price_stock_count": price_stock_count,
            "financial_coverage_count": sum(1 for item in items if item["has_financial_snapshot"]),
            "technical_coverage_count": sum(1 for item in items if item["has_technical_snapshot"]),
            "diagnosis": "回测可用性按真实行情样本分层判断；财务和技术快照仅用于说明覆盖状态，不再阻断回测入口。",
        },
    }


@router.post("/sync")
def sync_stocks(
    market: str = Query("ALL", description="同步市场: A_SHARE / HK / ALL"),
    db: Session = Depends(get_db),
    user=Depends(get_current_admin),
):
    """从东方财富同步全部股票列表到数据库"""
    from app.services.stock_sync import sync_stock_list
    result = sync_stock_list(db, market=market)
    return {
        "status": "ok",
        "message": f"同步完成: 新增 {result['added']}，更新 {result['updated']}，共 {result['total']}",
        **result,
    }


@router.get("/count")
def stock_count(db: Session = Depends(get_db)):
    """获取数据库中的股票数量"""
    total = db.query(Stock).filter(Stock.status == "ACTIVE").count()
    a_share = db.query(Stock).filter(Stock.status == "ACTIVE", Stock.market == "A_SHARE").count()
    hk = db.query(Stock).filter(Stock.status == "ACTIVE", Stock.market == "HK").count()
    return {"total": total, "a_share": a_share, "hk": hk}


@router.post("/data/fetch")
def add_stock_and_fetch(
    symbol: str = Query(..., description="股票代码，如 600519 或 00700"),
    db: Session = Depends(get_db),
    user=Depends(get_member_user),
):
    """添加股票并获取行情/财务/评分/信号数据（支持任意A股/港股）"""
    import numpy as np
    from app.data_providers import get_provider
    from app.services.scoring import calculate_quality_score, calculate_valuation_score, calculate_growth_score, calculate_trend_score, calculate_risk_score, get_rating
    from app.services.signal import determine_signal_type, calculate_position, calculate_prices

    provider = get_provider()
    today = date.today()

    # 检查股票是否已存在
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        # 判断市场
        if len(symbol) == 5 and symbol.isdigit():
            market, exchange = "HK", "HK"
            currency = "HKD"
        elif symbol.startswith(("6", "5")):
            market, exchange = "A_SHARE", "SH"
            currency = "CNY"
        else:
            market, exchange = "A_SHARE", "SZ"
            currency = "CNY"

        stock = Stock(
            symbol=symbol,
            name=symbol,  # 先用代码作为名称
            market=market,
            exchange=exchange,
            currency=currency,
            status="ACTIVE",
        )
        db.add(stock)
        db.flush()

    stock_id = stock.id
    results = {"symbol": symbol, "steps": []}

    # 1. 获取行情数据
    try:
        start = today - timedelta(days=180)
        df = provider.fetch_daily_prices(symbol, start, today)
        if not df.empty:
            price_count = 0
            for _, row in df.iterrows():
                trade_date = row["trade_date"]
                if hasattr(trade_date, "date"):
                    trade_date = trade_date.date()
                existing = db.query(DailyPrice).filter(
                    DailyPrice.stock_id == stock_id,
                    DailyPrice.trade_date == trade_date
                ).first()
                if not existing:
                    # 安全取值：None 时不 round，避免 TypeError
                    def _safe_round(val, ndigits):
                        return round(val, ndigits) if val is not None else None

                    dp = DailyPrice(
                        stock_id=stock_id,
                        trade_date=trade_date,
                        open=_safe_round(row.get("open"), 2),
                        high=_safe_round(row.get("high"), 2),
                        low=_safe_round(row.get("low"), 2),
                        close=_safe_round(row.get("close"), 2),
                        volume=_safe_round(row.get("volume"), 0) or 0,
                        turnover=_safe_round(row.get("turnover"), 0) or 0,
                    )
                    db.add(dp)
                    price_count += 1
            db.commit()

            # 更新股票名称（从行情数据获取）
            if stock.name == symbol:
                try:
                    quote = provider.fetch_realtime_quote(symbol)
                    # 名称可能在其他地方获取
                except Exception:
                    pass

            results["steps"].append(f"行情数据: {price_count}条")
        else:
            results["steps"].append("行情数据: 无数据")
    except Exception as e:
        results["steps"].append(f"行情数据: 获取失败({str(e)[:50]})")

    # 2. 获取财务数据
    try:
        df = provider.fetch_financial_metrics(symbol)
        if not df.empty:
            fin_count = 0
            for _, row in df.iterrows():
                existing = db.query(FinancialMetric).filter(
                    FinancialMetric.stock_id == stock_id,
                    FinancialMetric.report_period == row.get("report_period", "")
                ).first()
                if not existing:
                    from app.seed import _safe_round
                    fm = FinancialMetric(
                        stock_id=stock_id,
                        report_period=row.get("report_period", ""),
                        revenue=_safe_round(row.get("revenue"), 2),
                        revenue_yoy=_safe_round(row.get("revenue_yoy"), 2),
                        net_profit=_safe_round(row.get("net_profit"), 2),
                        net_profit_yoy=_safe_round(row.get("net_profit_yoy"), 2),
                        gross_margin=_safe_round(row.get("gross_margin"), 2),
                        net_margin=_safe_round(row.get("net_margin"), 2),
                        roe=_safe_round(row.get("roe"), 2),
                        roa=_safe_round(row.get("roa"), 2),
                        debt_ratio=_safe_round(row.get("debt_ratio"), 2),
                        operating_cashflow=_safe_round(row.get("operating_cashflow"), 2),
                        eps=_safe_round(row.get("eps"), 2),
                        book_value_per_share=_safe_round(row.get("book_value_per_share"), 2),
                    )
                    db.add(fm)
                    fin_count += 1
            db.commit()
            results["steps"].append(f"财务数据: {fin_count}条")
        else:
            results["steps"].append("财务数据: 无数据")
    except Exception as e:
        results["steps"].append(f"财务数据: 获取失败({str(e)[:50]})")

    # 3. 计算技术指标
    try:
        prices = db.query(DailyPrice).filter(DailyPrice.stock_id == stock_id).order_by(DailyPrice.trade_date).all()
        if len(prices) >= 20:
            closes = [p.close for p in prices]
            volumes = [p.volume for p in prices]
            last_p = prices[-1]
            i = len(prices) - 1

            ma5 = np.mean(closes[max(0, i-4):i+1]) if i >= 4 else None
            ma10 = np.mean(closes[max(0, i-9):i+1]) if i >= 9 else None
            ma20 = np.mean(closes[max(0, i-19):i+1])
            ma60 = np.mean(closes[max(0, i-59):i+1]) if i >= 59 else None
            ma120 = np.mean(closes[max(0, i-119):i+1]) if i >= 119 else None
            vol_ma5 = np.mean(volumes[max(0, i-4):i+1])
            vol_ma20 = np.mean(volumes[max(0, i-19):i+1])
            volume_ratio_5_20 = (vol_ma5 / vol_ma20) if vol_ma20 else None

            # EMA 计算
            def _ema(data, period):
                ema_vals = [data[0]]
                k = 2 / (period + 1)
                for v in data[1:]:
                    ema_vals.append(v * k + ema_vals[-1] * (1 - k))
                return ema_vals

            ema12_arr = _ema(closes, 12)
            ema26_arr = _ema(closes, 26) if len(closes) >= 26 else ema12_arr
            dif_arr = [ema12_arr[j] - ema26_arr[j] for j in range(len(closes))]
            dea_arr = _ema(dif_arr, 9)
            macd = dif_arr[-1]
            macd_signal = dea_arr[-1]

            # RSI14 计算
            if len(closes) >= 15:
                deltas = [closes[j] - closes[j-1] for j in range(1, len(closes))]
                gains = [d if d > 0 else 0 for d in deltas[-14:]]
                losses = [-d if d < 0 else 0 for d in deltas[-14:]]
                avg_gain = np.mean(gains)
                avg_loss = np.mean(losses)
                rsi14 = round(100 - 100 / (1 + avg_gain / avg_loss), 2) if avg_loss > 0 else (100.0 if avg_gain > 0 else 50.0)
            else:
                rsi14 = None

            # 布林带计算 (MA20 ± 2σ)
            boll_std = np.std(closes[max(0, i-19):i+1], ddof=1)
            boll_upper = ma20 + 2 * boll_std
            boll_lower = ma20 - 2 * boll_std

            weekly_volatility_candidate = None
            monthly_volatility_candidate = None
            if len(closes) >= 6:
                weekly_returns = [(closes[j] - closes[j - 1]) / closes[j - 1] for j in range(max(1, len(closes) - 5), len(closes)) if closes[j - 1] > 0]
                if weekly_returns:
                    weekly_volatility_candidate = float(np.std(weekly_returns, ddof=1) * (252 ** 0.5) * 100) if len(weekly_returns) > 1 else 0.0
            if len(closes) >= 21:
                monthly_returns = [(closes[j] - closes[j - 1]) / closes[j - 1] for j in range(max(1, len(closes) - 20), len(closes)) if closes[j - 1] > 0]
                if monthly_returns:
                    monthly_volatility_candidate = float(np.std(monthly_returns, ddof=1) * (252 ** 0.5) * 100) if len(monthly_returns) > 1 else 0.0

            existing_tech = db.query(TechnicalIndicator).filter(
                TechnicalIndicator.stock_id == stock_id,
                TechnicalIndicator.trade_date == last_p.trade_date
            ).first()
            if not existing_tech:
                ti = TechnicalIndicator(
                    stock_id=stock_id,
                    trade_date=last_p.trade_date,
                    ma5=round(ma5, 2) if ma5 is not None else None,
                    ma10=round(ma10, 2) if ma10 is not None else None,
                    ma20=round(ma20, 2),
                    ma60=round(ma60, 2) if ma60 else None,
                    ma120=round(ma120, 2) if ma120 else None,
                    macd=round(macd, 4),
                    macd_signal=round(macd_signal, 4),
                    macd_hist=round(macd - macd_signal, 4),
                    rsi14=rsi14,
                    boll_upper=round(boll_upper, 2),
                    boll_middle=round(ma20, 2),
                    boll_lower=round(boll_lower, 2),
                    volume_ma5=round(vol_ma5, 0),
                    volume_ma20=round(vol_ma20, 0),
                    volume_ratio_5_20=round(volume_ratio_5_20, 4) if volume_ratio_5_20 is not None else None,
                    weekly_volatility_candidate=round(weekly_volatility_candidate, 4) if weekly_volatility_candidate is not None else None,
                    monthly_volatility_candidate=round(monthly_volatility_candidate, 4) if monthly_volatility_candidate is not None else None,
                )
                db.add(ti)
            else:
                existing_tech.ma5 = round(ma5, 2) if ma5 is not None else None
                existing_tech.ma10 = round(ma10, 2) if ma10 is not None else None
                existing_tech.ma20 = round(ma20, 2)
                existing_tech.ma60 = round(ma60, 2) if ma60 else None
                existing_tech.ma120 = round(ma120, 2) if ma120 else None
                existing_tech.macd = round(macd, 4)
                existing_tech.macd_signal = round(macd_signal, 4)
                existing_tech.macd_hist = round(macd - macd_signal, 4)
                existing_tech.rsi14 = rsi14
                existing_tech.boll_upper = round(boll_upper, 2)
                existing_tech.boll_middle = round(ma20, 2)
                existing_tech.boll_lower = round(boll_lower, 2)
                existing_tech.volume_ma5 = round(vol_ma5, 0)
                existing_tech.volume_ma20 = round(vol_ma20, 0)
                existing_tech.volume_ratio_5_20 = round(volume_ratio_5_20, 4) if volume_ratio_5_20 is not None else None
                existing_tech.weekly_volatility_candidate = round(weekly_volatility_candidate, 4) if weekly_volatility_candidate is not None else None
                existing_tech.monthly_volatility_candidate = round(monthly_volatility_candidate, 4) if monthly_volatility_candidate is not None else None
                db.commit()
            results["steps"].append("技术指标: 已计算")
        else:
            results["steps"].append("技术指标: 数据不足")
    except Exception as e:
        results["steps"].append(f"技术指标: 计算失败({str(e)[:50]})")

    # 4. 评分
    try:
        price = db.query(DailyPrice).filter(DailyPrice.stock_id == stock_id).order_by(DailyPrice.trade_date.desc()).first()
        financial = _latest_financial_for_stock(db, stock_id)
        tech = db.query(TechnicalIndicator).filter(TechnicalIndicator.stock_id == stock_id).order_by(TechnicalIndicator.trade_date.desc()).first()

        if price:
            q_score, _ = calculate_quality_score(financial) if financial else (15, "无财务数据")
            v_score, _ = calculate_valuation_score(price, financial) if financial else (10, "无财务数据")
            g_score, _ = calculate_growth_score(financial) if financial else (10, "无财务数据")
            t_score, _ = calculate_trend_score(price, tech) if tech else (10, "无技术数据")
            r_score, _ = calculate_risk_score(financial, price) if financial else (5, "无财务数据")
            total = q_score + v_score + g_score + t_score + r_score
            rating = get_rating(total)

            existing_score = db.query(StockScore).filter(
                StockScore.stock_id == stock_id, StockScore.score_date == today
            ).first()
            if not existing_score:
                score = StockScore(
                    stock_id=stock_id,
                    score_date=today,
                    total_score=round(total, 1),
                    quality_score=round(q_score, 1),
                    valuation_score=round(v_score, 1),
                    growth_score=round(g_score, 1),
                    trend_score=round(t_score, 1),
                    risk_score=round(r_score, 1),
                    rating=rating,
                    score_source=REAL_SCORE_SOURCE,
                    reason_summary=f"质量{q_score:.0f} 估值{v_score:.0f} 成长{g_score:.0f} 趋势{t_score:.0f} 风险{r_score:.0f}",
                )
                db.add(score)
                db.commit()
            results["steps"].append(f"评分: {total:.0f}分 ({rating})")
        else:
            results["steps"].append("评分: 无行情数据")
    except Exception as e:
        results["steps"].append(f"评分: 失败({str(e)[:50]})")

    # 5. 生成信号
    try:
        score = db.query(StockScore).filter(
            StockScore.stock_id == stock_id, StockScore.score_date == today
        ).first()
        price = db.query(DailyPrice).filter(DailyPrice.stock_id == stock_id).order_by(DailyPrice.trade_date.desc()).first()

        if score and price:
            sig_type, strength, logic = determine_signal_type(score)
            position = calculate_position(sig_type, strength)
            entry, target, stop_loss = calculate_prices(price, sig_type)
            holding_map = {"BUY": "3-6个月", "ADD": "2-4个月", "WATCH": "-", "REDUCE": "逐步减仓", "SELL": "立即"}

            existing_sig = db.query(TradeSignal).filter(
                TradeSignal.stock_id == stock_id, TradeSignal.signal_date == today
            ).first()
            if not existing_sig:
                signal = TradeSignal(
                    stock_id=stock_id,
                    signal_date=today,
                    signal_type=sig_type,
                    signal_strength=strength,
                    suggested_position=position,
                    entry_price=entry,
                    target_price=target,
                    stop_loss_price=stop_loss,
                    holding_period=holding_map.get(sig_type, "-"),
                    signal_source=REAL_SIGNAL_SOURCE,
                    logic_json={"total_score": score.total_score, "reason": logic},
                    status="ACTIVE",
                )
                db.add(signal)
                db.commit()
            results["steps"].append(f"信号: {sig_type}")
        else:
            results["steps"].append("信号: 数据不足")
    except Exception as e:
        results["steps"].append(f"信号: 失败({str(e)[:50]})")

    results["status"] = "ok"
    results["stock_id"] = stock_id
    results["stock_name"] = stock.name
    return results


def _as_str(value):
    return str(value) if value is not None else None


def _missing_fields(latest_price, latest_financial, tech, score, signal):
    fields = []
    if not latest_price:
        fields.extend(["latest_price", "pe", "pb", "market_cap"])
    else:
        for name in ["close", "pe", "pb", "market_cap", "dividend_yield"]:
            if getattr(latest_price, name, None) is None:
                fields.append(name)
    if not latest_financial:
        fields.extend(["revenue_yoy", "net_profit_yoy", "roe", "gross_margin", "debt_ratio", "operating_cashflow"])
    else:
        for name in ["revenue_yoy", "net_profit_yoy", "roe", "gross_margin", "debt_ratio", "operating_cashflow", "free_cashflow", "eps", "book_value_per_share"]:
            if getattr(latest_financial, name, None) is None:
                fields.append(name)
    if not tech:
        fields.extend(["ma5", "ma10", "ma20", "ma60", "macd", "rsi14"])
    if not score:
        fields.extend(["quality_score", "valuation_score", "growth_score", "trend_score", "risk_score"])
    if not signal:
        fields.append("signal")
    return sorted(set(fields))


def _score_trace(score, latest_price, latest_financial, previous_financial, tech, signal, stock_name):
    if not score:
        return None

    signal_risks = []
    if signal and isinstance(signal.risk_json, dict):
        signal_risks = signal.risk_json.get("items") or []

    return {
        "quality": {
            "score": score.quality_score,
            "weight": 0.30,
            "updated_at": _as_str(getattr(score, "score_date", None)),
            "summary": "Focuses on profitability, cashflow quality, and balance-sheet pressure.",
            "indicators": [
                {"label": "ROE", "value": getattr(latest_financial, "roe", None), "unit": "%"},
                {"label": "Gross Margin", "value": getattr(latest_financial, "gross_margin", None), "unit": "%"},
                {"label": "Operating Cashflow", "value": getattr(latest_financial, "operating_cashflow", None), "unit": "bn"},
                {"label": "Debt Ratio", "value": getattr(latest_financial, "debt_ratio", None), "unit": "%"},
            ],
        },
        "valuation": {
            "score": score.valuation_score,
            "weight": 0.20,
            "updated_at": _as_str(getattr(latest_price, "trade_date", None)),
            "summary": "Uses database valuation fields for research comparison, not execution pricing.",
            "indicators": [
                {"label": "PE", "value": getattr(latest_price, "pe", None)},
                {"label": "PB", "value": getattr(latest_price, "pb", None)},
                {"label": "Dividend Yield", "value": getattr(latest_price, "dividend_yield", None), "unit": "%"},
                {"label": "Book Value / Share", "value": getattr(latest_financial, "book_value_per_share", None)},
            ],
        },
        "growth": {
            "score": score.growth_score,
            "weight": 0.20,
            "updated_at": _as_str(getattr(latest_financial, "report_date", None) or getattr(score, "score_date", None)),
            "summary": "Tracks revenue and earnings momentum from the latest stored financial reports.",
            "indicators": [
                {"label": "Revenue YoY", "value": getattr(latest_financial, "revenue_yoy", None), "unit": "%"},
                {"label": "Net Profit YoY", "value": getattr(latest_financial, "net_profit_yoy", None), "unit": "%"},
                {"label": "EPS", "value": getattr(latest_financial, "eps", None)},
                {"label": "Prior ROE", "value": getattr(previous_financial, "roe", None), "unit": "%"},
            ],
        },
        "trend": {
            "score": score.trend_score,
            "weight": 0.20,
            "updated_at": _as_str(getattr(tech, "trade_date", None) or getattr(latest_price, "trade_date", None)),
            "summary": "Built from technical indicators stored in the database and used for research observation only.",
            "indicators": [
                {"label": "MA20", "value": getattr(tech, "ma20", None)},
                {"label": "MA60", "value": getattr(tech, "ma60", None)},
                {"label": "MACD", "value": getattr(tech, "macd", None)},
                {"label": "RSI14", "value": getattr(tech, "rsi14", None)},
            ],
        },
        "risk": {
            "score": score.risk_score,
            "weight": 0.10,
            "updated_at": _as_str(getattr(signal, "signal_date", None) or getattr(score, "score_date", None)),
            "summary": "Flags valuation stretch, stock-status warnings, and stored signal risk items.",
            "indicators": [
                {"label": "Signal Risk Count", "value": len(signal_risks)},
                {"label": "High PE Warning", "value": "yes" if getattr(latest_price, "pe", 0) and latest_price.pe >= 60 else "no"},
                {"label": "ST / Delisting Flag", "value": "yes" if ("ST" in (stock_name or "")) or ("?" in (stock_name or "")) else "no"},
                {"label": "Debt Ratio", "value": getattr(latest_financial, "debt_ratio", None), "unit": "%"},
            ],
        },
    }


@router.get("/diagnostics")
def stock_score_diagnostics(
    score_date: date | None = Query(None, description="可选评分日期"),
    db: Session = Depends(get_db),
    user=Depends(get_member_user),
):
    """Expose score diagnostics for current stored scores without changing model output."""
    return diagnose_real_scores(db, score_date=score_date)


@router.get("/{symbol}")
def get_stock_detail(symbol: str, db: Session = Depends(get_db)):
    """Return stock detail sourced from current database tables."""
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        raise HTTPException(status_code=404, detail="未找到该股票详情，请检查股票代码后重试")

    latest_price = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id).order_by(DailyPrice.trade_date.desc()).first()
    prices = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id).order_by(DailyPrice.trade_date.desc()).limit(120).all()
    all_financials = db.query(FinancialMetric).filter(FinancialMetric.stock_id == stock.id).all()
    financials = sorted(
        all_financials,
        key=lambda item: ((item.report_date or date.min), item.id or 0),
        reverse=True,
    )[:8]
    latest_financial = _latest_financial_for_stock(db, stock.id)
    previous_financial = _previous_financial_for_stock(db, stock.id, latest_financial)
    tech = db.query(TechnicalIndicator).filter(TechnicalIndicator.stock_id == stock.id).order_by(TechnicalIndicator.trade_date.desc()).first()
    score = db.query(StockScore).filter(StockScore.stock_id == stock.id).order_by(StockScore.score_date.desc()).first()
    signal = db.query(TradeSignal).filter(TradeSignal.stock_id == stock.id).order_by(TradeSignal.signal_date.desc()).first()
    research_reports = db.query(ResearchReport).filter(ResearchReport.stock_code == symbol).order_by(ResearchReport.publish_date.desc()).limit(10).all()

    if not research_reports:
        try:
            from app.services.stock_sync import sync_research_reports
            result = sync_research_reports(db, symbol=symbol, max_pages=1)
            if result.get("added", 0) > 0:
                research_reports = db.query(ResearchReport).filter(ResearchReport.stock_code == symbol).order_by(ResearchReport.publish_date.desc()).limit(10).all()
        except Exception:
            pass

    score_trace = _score_trace(score, latest_price, latest_financial, previous_financial, tech, signal, stock.name)
    company_news = get_company_news_summary(stock.symbol)
    industry_support = get_industry_support(stock.symbol, stock.industry)
    shareholder_signal = get_shareholder_signal(db, stock.symbol)
    earnings_signal = get_earnings_signal(latest_financial)
    volatility_signal = get_volatility_signal([p.close for p in reversed(prices) if p.close is not None])
    trend_score_v2, trend_score_v2_details = calculate_trend_score_v2(latest_price, tech, list(reversed(prices)))
    readiness = build_data_readiness(
        has_price=latest_price is not None,
        has_financial=latest_financial is not None,
        has_technical=tech is not None,
        has_score=score is not None,
        score_source=getattr(score, "score_source", None),
    )
    data_coverage = get_stock_data_coverage(db, symbol)
    diagnostics = diagnose_single_stock_score(db, symbol)

    return {
        "stock": {
            "id": stock.id,
            "symbol": stock.symbol,
            "name": stock.name,
            "market": stock.market,
            "exchange": stock.exchange,
            "industry": stock.industry,
            "sector": stock.sector,
        },
        "data_source": {
            "prices": "数据库行情表（daily_prices）",
            "financials": "数据库财务表（financial_metrics）",
            "scores": "数据库评分表（stock_scores）",
            "signals": "数据库信号表（trade_signals）",
            "reports": "数据库研报表（research_reports，可按需同步）",
        },
        "latest_updates": {
            "price": _as_str(getattr(latest_price, "trade_date", None)),
            "financial": _as_str(getattr(latest_financial, "report_date", None) or getattr(latest_financial, "report_period", None)),
            "technical": _as_str(getattr(tech, "trade_date", None)),
            "score": _as_str(getattr(score, "score_date", None)),
            "signal": _as_str(getattr(signal, "signal_date", None)),
            "reports": _as_str(getattr(research_reports[0], "publish_date", None)) if research_reports else None,
        },
        "missing_fields": _missing_fields(latest_price, latest_financial, tech, score, signal),
        "data_readiness": readiness,
        "data_coverage": data_coverage,
        "coverage_level": data_coverage.get("coverage_level"),
        "readiness_label": data_coverage.get("readiness_label"),
        "blocking_reasons": data_coverage.get("blocking_reasons", []),
        "diagnostics": diagnostics,
        "trace": score_trace,
        "latest_price": {
            "trade_date": _as_str(getattr(latest_price, "trade_date", None)),
            "close": getattr(latest_price, "close", None),
            "open": getattr(latest_price, "open", None),
            "high": getattr(latest_price, "high", None),
            "low": getattr(latest_price, "low", None),
            "volume": getattr(latest_price, "volume", None),
            "turnover": getattr(latest_price, "turnover", None),
            "pe": getattr(latest_price, "pe", None),
            "pb": getattr(latest_price, "pb", None),
            "market_cap": getattr(latest_price, "market_cap", None),
            "dividend_yield": getattr(latest_price, "dividend_yield", None),
        } if latest_price else None,
        "price_history": [
            {
                "date": _as_str(p.trade_date),
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "volume": p.volume,
            }
            for p in reversed(prices)
        ],
        "price_data_quality": {
            "has_ohlc": all(p.open is not None and p.high is not None and p.low is not None and p.close is not None for p in prices[:10]) if prices else False,
            "has_volume": any(p.volume is not None and p.volume > 0 for p in prices[:10]) if prices else False,
            "price_count": len(prices),
            "can_render_kline": (all(p.open is not None and p.high is not None and p.low is not None and p.close is not None for p in prices[:10]) and len(prices) >= 5) if prices else False,
            "fallback_reason": None,
        },
        "financial_metrics": [
            {
                "period": f.report_period,
                "report_date": _as_str(f.report_date),
                "revenue": f.revenue,
                "revenue_yoy": f.revenue_yoy,
                "net_profit": f.net_profit,
                "net_profit_yoy": f.net_profit_yoy,
                "gross_margin": f.gross_margin,
                "net_margin": f.net_margin,
                "roe": f.roe,
                "roa": f.roa,
                "debt_ratio": f.debt_ratio,
                "operating_cashflow": f.operating_cashflow,
                "free_cashflow": f.free_cashflow,
                "eps": f.eps,
                "book_value_per_share": f.book_value_per_share,
            }
            for f in financials
        ],
        "technical_indicators": {
            "ma5": getattr(tech, "ma5", None),
            "ma10": getattr(tech, "ma10", None),
            "ma20": getattr(tech, "ma20", None),
            "ma60": getattr(tech, "ma60", None),
            "ma120": getattr(tech, "ma120", None),
            "macd": getattr(tech, "macd", None),
            "macd_signal": getattr(tech, "macd_signal", None),
            "macd_hist": getattr(tech, "macd_hist", None),
            "rsi14": getattr(tech, "rsi14", None),
            "volume_ma5": getattr(tech, "volume_ma5", None),
            "volume_ma20": getattr(tech, "volume_ma20", None),
            "volume_ratio_5_20": getattr(tech, "volume_ratio_5_20", None),
            "weekly_volatility_candidate": getattr(tech, "weekly_volatility_candidate", None),
            "monthly_volatility_candidate": getattr(tech, "monthly_volatility_candidate", None),
            "trend_score_v2": trend_score_v2,
            "trend_score_v2_details": trend_score_v2_details,
        } if tech else None,
        "score": {
            "total": score.total_score,
            "quality": score.quality_score,
            "valuation": score.valuation_score,
            "growth": score.growth_score,
            "trend": score.trend_score,
            "trend_v2": trend_score_v2,
            "risk": score.risk_score,
            "rating": score.rating,
            "rating_label": signal_display_label(score.rating) if score_is_real(score.score_source) else score_label(score.score_source),
            "reason": sanitize_research_text(score.reason_summary) if score_is_real(score.score_source) else "当前评分来源为演示评分，正式结果待真实评分生成。",
            "date": _as_str(score.score_date),
            "score_source": getattr(score, "score_source", UNKNOWN_SCORE_SOURCE),
            "score_label": score_label(getattr(score, "score_source", None)),
            "trace": score_trace,
        } if score else None,
        "signal": {
            "type": signal.signal_type,
            "type_label": signal_display_label(signal.signal_type),
            "strength": signal.signal_strength,
            "position": signal.suggested_position,
            "entry_price": signal.entry_price,
            "target_price": signal.target_price,
            "stop_loss": signal.stop_loss_price,
            "holding_period": signal.holding_period,
            "logic": sanitize_nested_payload(signal.logic_json),
            "risk": sanitize_nested_payload(signal.risk_json),
            "date": _as_str(signal.signal_date),
            "source": "数据库信号表（trade_signals）",
            "signal_source": getattr(signal, "signal_source", UNKNOWN_SCORE_SOURCE),
            "market": stock.market,
        } if signal else None,
        "reports": [
            {
                "title": sanitize_research_text(r.title),
                "org_name": r.org_name,
                "publish_date": _as_str(r.publish_date) or "",
                "rating": sanitize_research_text(r.rating),
                "researcher": r.researcher,
                "url": r.url,
            }
            for r in research_reports
        ],
        "analysis_status": {
            "company_news": company_news,
            "industry_support": industry_support,
            "shareholder_signal": shareholder_signal,
            "earnings_signal": earnings_signal,
            "volatility_signal": volatility_signal,
        },
    }
