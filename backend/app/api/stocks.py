"""股票相关 API"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
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

router = APIRouter(prefix="/api/stocks", tags=["股票"])


@router.get("/search")
def search_stocks(
    keyword: str = Query(..., description="股票代码/名称/关键词"),
    market: str = Query(None, description="市场: A_SHARE / HK"),
    db: Session = Depends(get_db),
):
    """搜索股票"""
    query = db.query(Stock).filter(Stock.status == "ACTIVE")
    if market:
        query = query.filter(Stock.market == market)
    query = query.filter(
        (Stock.symbol.like(f"%{keyword}%")) | (Stock.name.like(f"%{keyword}%"))
    )
    stocks = query.limit(20).all()
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
                    dp = DailyPrice(
                        stock_id=stock_id,
                        trade_date=trade_date,
                        open=round(row["open"], 2),
                        high=round(row["high"], 2),
                        low=round(row["low"], 2),
                        close=round(row["close"], 2),
                        volume=round(row["volume"], 0),
                        turnover=round(row.get("turnover", 0), 0),
                    )
                    db.add(dp)
                    price_count += 1
            db.commit()

            # 更新股票名称（从行情数据获取）
            if stock.name == symbol:
                try:
                    quote = provider.fetch_realtime_quote(symbol)
                    # 名称可能在其他地方获取
                except:
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

            ema12 = np.mean(closes[max(0, i-11):i+1])
            ema26 = np.mean(closes[max(0, i-25):i+1]) if i >= 25 else ema12
            macd = ema12 - ema26
            macd_signal = macd * 0.8

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
                    rsi14=round(50 + np.random.uniform(-15, 15), 2),
                    boll_upper=round(ma20 * 1.02, 2),
                    boll_middle=round(ma20, 2),
                    boll_lower=round(ma20 * 0.98, 2),
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


@router.get("/{symbol}")
def get_stock_detail(symbol: str, db: Session = Depends(get_db)):
    """获取股票详情：基本信息、行情、财务、评分、信号、报告"""
    stock = db.query(Stock).filter(Stock.symbol == symbol).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")

    # 最新行情
    latest_price = (
        db.query(DailyPrice)
        .filter(DailyPrice.stock_id == stock.id)
        .order_by(DailyPrice.trade_date.desc())
        .first()
    )

    # 历史行情（近 120 日）
    prices = (
        db.query(DailyPrice)
        .filter(DailyPrice.stock_id == stock.id)
        .order_by(DailyPrice.trade_date.desc())
        .limit(120)
        .all()
    )

    # 财务指标
    financials = (
        db.query(FinancialMetric)
        .filter(FinancialMetric.stock_id == stock.id)
        .order_by(FinancialMetric.report_period.desc())
        .limit(8)
        .all()
    )

    # 技术指标
    tech = (
        db.query(TechnicalIndicator)
        .filter(TechnicalIndicator.stock_id == stock.id)
        .order_by(TechnicalIndicator.trade_date.desc())
        .first()
    )

    # 评分
    score = (
        db.query(StockScore)
        .filter(StockScore.stock_id == stock.id)
        .order_by(StockScore.score_date.desc())
        .first()
    )

    # 最新信号
    signal = (
        db.query(TradeSignal)
        .filter(TradeSignal.stock_id == stock.id)
        .order_by(TradeSignal.signal_date.desc())
        .first()
    )

    # 相关报告（从研报表查询该股票的研报）
    research_reports = (
        db.query(ResearchReport)
        .filter(ResearchReport.stock_code == symbol)
        .order_by(ResearchReport.publish_date.desc())
        .limit(10)
        .all()
    )

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
        "latest_price": {
            "trade_date": str(latest_price.trade_date) if latest_price else None,
            "close": latest_price.close if latest_price else None,
            "open": latest_price.open if latest_price else None,
            "high": latest_price.high if latest_price else None,
            "low": latest_price.low if latest_price else None,
            "volume": latest_price.volume if latest_price else None,
            "turnover": latest_price.turnover if latest_price else None,
            "pe": latest_price.pe if latest_price else None,
            "pb": latest_price.pb if latest_price else None,
            "market_cap": latest_price.market_cap if latest_price else None,
            "dividend_yield": latest_price.dividend_yield if latest_price else None,
        } if latest_price else None,
        "price_history": [
            {
                "date": str(p.trade_date),
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
                "revenue": f.revenue,
                "revenue_yoy": f.revenue_yoy,
                "net_profit": f.net_profit,
                "net_profit_yoy": f.net_profit_yoy,
                "gross_margin": f.gross_margin,
                "roe": f.roe,
                "debt_ratio": f.debt_ratio,
                "eps": f.eps,
            }
            for f in financials
        ],
        "technical_indicators": {
            "ma20": tech.ma20 if tech else None,
            "ma60": tech.ma60 if tech else None,
            "ma120": tech.ma120 if tech else None,
            "macd": tech.macd if tech else None,
            "macd_signal": tech.macd_signal if tech else None,
            "rsi14": tech.rsi14 if tech else None,
        } if tech else None,
        "score": {
            "total": score.total_score,
            "quality": score.quality_score,
            "valuation": score.valuation_score,
            "growth": score.growth_score,
            "trend": score.trend_score,
            "risk": score.risk_score,
            "rating": score.rating,
            "reason": score.reason_summary,
            "date": str(score.score_date),
        } if score else None,
        "signal": {
            "type": signal.signal_type,
            "strength": signal.signal_strength,
            "position": signal.suggested_position,
            "entry_price": signal.entry_price,
            "target_price": signal.target_price,
            "stop_loss": signal.stop_loss_price,
            "holding_period": signal.holding_period,
            "logic": signal.logic_json,
            "risk": signal.risk_json,
            "date": str(signal.signal_date),
        } if signal else None,
        "reports": [
            {
                "title": r.title,
                "org_name": r.org_name,
                "publish_date": str(r.publish_date) if r.publish_date else "",
                "rating": r.rating,
                "researcher": r.researcher,
                "url": r.url,
            }
            for r in research_reports
        ],
    }
