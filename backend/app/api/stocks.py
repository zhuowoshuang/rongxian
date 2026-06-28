"""股票相关 API"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import and_, func
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

router = APIRouter(prefix="/api/stocks", tags=["股票"])


@router.get("")
@router.get("/")
def list_stocks(
    market: str | None = Query(None, description="市场: A_SHARE / HK"),
    rating: str | None = Query(None, description="研究评级: BUY / ADD / WATCH / REDUCE / SELL"),
    keyword: str | None = Query(None, description="代码或名称关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(get_member_user),
):
    """真实个股评分库列表，聚合股票、评分、信号与最新行情。"""
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
            StockScore.score_date,
            StockScore.reason_summary,
            TradeSignal.signal_type,
            TradeSignal.signal_strength,
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

    if market:
        base_query = base_query.filter(Stock.market == market)
    if rating:
        base_query = base_query.filter(StockScore.rating == rating)
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        base_query = base_query.filter(
            (Stock.symbol.like(f"%{escaped}%", escape="\\")) | (Stock.name.like(f"%{escaped}%", escape="\\"))
        )

    total = base_query.count()
    all_rows = base_query.all()

    a_share = sum(1 for row in all_rows if row.market == "A_SHARE")
    hk = sum(1 for row in all_rows if row.market == "HK")
    highest_score = max((row.total_score or 0) for row in all_rows) if all_rows else 0
    risk_elevated_count = sum(1 for row in all_rows if (row.signal_type or row.rating) in ("REDUCE", "SELL"))

    rows = (
        base_query.order_by(
            StockScore.total_score.desc().nullslast(),
            StockScore.score_date.desc().nullslast(),
            Stock.symbol.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

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
                "rating_label": signal_display_label(row.rating) if row.rating else None,
                "signal_type": row.signal_type,
                "signal_label": signal_display_label(row.signal_type) if row.signal_type else None,
                "signal_strength": row.signal_strength,
                "total_score": row.total_score,
                "quality_score": row.quality_score,
                "valuation_score": row.valuation_score,
                "growth_score": row.growth_score,
                "trend_score": row.trend_score,
                "risk_score": row.risk_score,
                "latest_close": row.latest_close,
                "change_pct": price_change,
                "updated_at": str(row.score_date or row.signal_date or row.trade_date) if (row.score_date or row.signal_date or row.trade_date) else None,
                "score_date": str(row.score_date) if row.score_date else None,
                "signal_date": str(row.signal_date) if row.signal_date else None,
                "reason_summary": sanitize_research_text(row.reason_summary),
                "risk_flags": risk_flags[:3],
            }
        )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
        "summary": {
            "rated_stocks": total,
            "a_share": a_share,
            "hk": hk,
            "highest_score": round(highest_score, 1) if highest_score else 0,
            "risk_elevated": risk_elevated_count,
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

            ma20 = np.mean(closes[max(0, i-19):i+1])
            ma60 = np.mean(closes[max(0, i-59):i+1]) if i >= 59 else None
            ma120 = np.mean(closes[max(0, i-119):i+1]) if i >= 119 else None
            vol_ma5 = np.mean(volumes[max(0, i-4):i+1])
            vol_ma20 = np.mean(volumes[max(0, i-19):i+1])

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

            existing_tech = db.query(TechnicalIndicator).filter(
                TechnicalIndicator.stock_id == stock_id,
                TechnicalIndicator.trade_date == last_p.trade_date
            ).first()
            if not existing_tech:
                ti = TechnicalIndicator(
                    stock_id=stock_id,
                    trade_date=last_p.trade_date,
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
                )
                db.add(ti)
                db.commit()
            results["steps"].append("技术指标: 已计算")
        else:
            results["steps"].append("技术指标: 数据不足")
    except Exception as e:
        results["steps"].append(f"技术指标: 计算失败({str(e)[:50]})")

    # 4. 评分
    try:
        price = db.query(DailyPrice).filter(DailyPrice.stock_id == stock_id).order_by(DailyPrice.trade_date.desc()).first()
        financial = db.query(FinancialMetric).filter(FinancialMetric.stock_id == stock_id).order_by(FinancialMetric.report_period.desc()).first()
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
        fields.extend(["ma20", "ma60", "macd", "rsi14"])
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


@router.get("/{symbol}")
def get_stock_detail(symbol: str, db: Session = Depends(get_db)):
    """Return stock detail sourced from current database tables."""
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    latest_price = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id).order_by(DailyPrice.trade_date.desc()).first()
    prices = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id).order_by(DailyPrice.trade_date.desc()).limit(120).all()
    financials = db.query(FinancialMetric).filter(FinancialMetric.stock_id == stock.id).order_by(FinancialMetric.report_period.desc()).limit(8).all()
    latest_financial = financials[0] if financials else None
    previous_financial = financials[1] if len(financials) > 1 else None
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
            "ma20": getattr(tech, "ma20", None),
            "ma60": getattr(tech, "ma60", None),
            "ma120": getattr(tech, "ma120", None),
            "macd": getattr(tech, "macd", None),
            "macd_signal": getattr(tech, "macd_signal", None),
            "rsi14": getattr(tech, "rsi14", None),
        } if tech else None,
        "score": {
            "total": score.total_score,
            "quality": score.quality_score,
            "valuation": score.valuation_score,
            "growth": score.growth_score,
            "trend": score.trend_score,
            "risk": score.risk_score,
            "rating": score.rating,
            "rating_label": signal_display_label(score.rating),
            "reason": sanitize_research_text(score.reason_summary),
            "date": _as_str(score.score_date),
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
    }
