"""Dashboard data aggregation service."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.data_providers import get_provider
from app.models.daily_price import DailyPrice
from app.models.portfolio import Portfolio, PortfolioPosition
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.report import Report
from app.models.trade_signal import TradeSignal
from app.services.compliance import sanitize_research_text
from app.services.data_coverage import get_bulk_data_coverage
from app.services.data_credibility import REAL_SCORE_SOURCE, REAL_SIGNAL_SOURCE
from app.services.research_display_summary import build_research_display_summary


def _fallback_market_indices(market: str) -> list[dict]:
    if market == "A_SHARE":
        return [
            {"name": "上证指数", "code": "000001.SH", "current": 0, "change": 0, "change_pct": 0},
            {"name": "深证成指", "code": "399001.SZ", "current": 0, "change": 0, "change_pct": 0},
            {"name": "创业板指", "code": "399006.SZ", "current": 0, "change": 0, "change_pct": 0},
        ]
    return [
        {"name": "恒生指数", "code": "HSI", "current": 0, "change": 0, "change_pct": 0},
        {"name": "恒生科技", "code": "HSTECH", "current": 0, "change": 0, "change_pct": 0},
    ]


def _market_status_label(status: str) -> str:
    return {
        "bullish": "偏多",
        "mildly_bullish": "中性偏多",
        "neutral": "中性",
        "mildly_bearish": "中性偏谨慎",
        "bearish": "偏空",
    }.get(status, "中性")


def _strategy_summary(dist: dict[str, int]) -> dict:
    buy_add = dist["BUY"] + dist["ADD"]
    reduce_sell = dist["REDUCE"] + dist["SELL"]

    if buy_add > reduce_sell * 2:
        market_status = "bullish"
        suggested_pos = "70-80%"
    elif buy_add > reduce_sell:
        market_status = "mildly_bullish"
        suggested_pos = "50-70%"
    elif reduce_sell > buy_add * 2:
        market_status = "bearish"
        suggested_pos = "20-30%"
    elif reduce_sell > buy_add:
        market_status = "mildly_bearish"
        suggested_pos = "30-45%"
    else:
        market_status = "neutral"
        suggested_pos = "40-60%"

    return {
        "market_status": market_status,
        "market_status_label": _market_status_label(market_status),
        "suggested_position": suggested_pos,
        "core_strategy": "以基本面筛选、估值比较和趋势确认作为研究主线，优先观察评分与信号同步改善的标的。",
        "judgement_basis": [
            f"高关注与增强关注样本合计 {buy_add} 只，风险升高与回避观察样本合计 {reduce_sell} 只。",
            "优先观察五维评分靠前、估值与趋势同步改善的标的。",
            "研究组合表现仅用于模型研究，不代表真实账户收益。",
        ],
        "risk_warning": "研究仓位区间仅用于研究视图，请结合宏观、行业与个股风险独立判断，避免将模型输出视为交易指令。",
    }


def _empty_dashboard(meta: dict | None = None) -> dict:
    return {
        "market_summary": _fallback_market_indices("A_SHARE") + _fallback_market_indices("HK"),
        "strategy_summary": {
            "market_status": "neutral",
            "market_status_label": "待生成",
            "suggested_position": "待生成",
            "core_strategy": "真实行情已接入，真实评分待生成。当前演示评分不会作为正式研究结果展示。",
            "judgement_basis": [
                "当前正式视图不展示 quick_seed_demo 演示评分和演示信号。",
                "待财务数据和技术指标补齐后，再生成真实五维评分与真实研究信号。",
            ],
            "risk_warning": "当前研究结果尚未完成真实评分链路，不应据此形成投资结论。",
        },
        "top_signals": [],
        "signal_distribution": {"BUY": 0, "ADD": 0, "WATCH": 0, "REDUCE": 0, "SELL": 0},
        "portfolio_summary": {
            "monthly_return": 0,
            "benchmark_return": 0,
            "excess_return": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "total_assets": 0,
            "cash_ratio": 0,
            "position_count": 0,
            "name": "研究组合待生成",
        },
        "stock_pools": {"quality": [], "undervalued": [], "trend": [], "risk": []},
        "risk_alerts": [],
        "dashboard_sections": {
            "data_coverage": {},
            "core_ready_samples": [],
            "risk_observation_samples": [],
            "valuation_gap": {},
            "recent_reports": [],
            "backtest_entry": {},
            "demo_entry": {},
        },
        "meta": meta or {},
    }


def _latest_price_map(db: Session, stock_ids: list[int]) -> dict[int, DailyPrice]:
    if not stock_ids:
        return {}
    latest_date_sq = (
        db.query(DailyPrice.stock_id, func.max(DailyPrice.trade_date).label("max_date"))
        .filter(DailyPrice.stock_id.in_(stock_ids))
        .group_by(DailyPrice.stock_id)
        .subquery()
    )
    prices = (
        db.query(DailyPrice)
        .join(latest_date_sq, (DailyPrice.stock_id == latest_date_sq.c.stock_id) & (DailyPrice.trade_date == latest_date_sq.c.max_date))
        .all()
    )
    return {item.stock_id: item for item in prices}


def _primary_low_score_reason(score: StockScore) -> str | None:
    """Return the weakest dimension label for a stock score."""
    if score is None:
        return None
    dimensions = [
        ("质量", score.quality_score, 30),
        ("估值", score.valuation_score, 20),
        ("成长", score.growth_score, 20),
        ("趋势", score.trend_score, 20),
        ("风险", score.risk_score, 10),
    ]
    scored = [(name, val, max_val) for name, val, max_val in dimensions if val is not None and max_val > 0]
    if not scored:
        return None
    weakest = min(scored, key=lambda x: x[1] / x[2])
    return f"{weakest[0]}维度得分偏低"


def get_dashboard_data(db: Session, today: date, include_demo: bool = False) -> dict:
    display_summary = build_research_display_summary(db, include_demo=include_demo, score_date=today)
    system_status = display_summary["system"]
    diagnostics_summary = display_summary["diagnostics"]
    provider = get_provider()

    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut_a = ex.submit(lambda: provider.fetch_market_index("A_SHARE"))
        fut_hk = ex.submit(lambda: provider.fetch_market_index("HK"))
        try: market_a = fut_a.result(timeout=3)
        except Exception: market_a = _fallback_market_indices("A_SHARE")
        try: market_hk = fut_hk.result(timeout=3)
        except Exception: market_hk = _fallback_market_indices("HK")

    latest_date = db.query(func.max(TradeSignal.signal_date)).scalar() or today
    signal_query = db.query(TradeSignal).filter(TradeSignal.signal_date == latest_date)
    score_query = db.query(StockScore, Stock).join(Stock, StockScore.stock_id == Stock.id).filter(StockScore.score_date == latest_date)
    if not include_demo:
        signal_query = signal_query.filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE)
        score_query = score_query.filter(StockScore.score_source == REAL_SCORE_SOURCE)

    signals = signal_query.all()
    if not include_demo and not signals and system_status.get("real_signal_count", 0) == 0:
        payload = _empty_dashboard(
            {
                "signal_date": str(today),
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "data_mode": system_status.get("data_mode"),
                "data_mode_label": system_status.get("data_mode_label"),
                "warning": system_status.get("warning"),
                "real_score_count": system_status.get("real_score_count", 0),
                "demo_score_count": system_status.get("demo_score_count", 0),
                "real_signal_count": system_status.get("real_signal_count", 0),
                "demo_signal_count": system_status.get("demo_signal_count", 0),
                "demo_contaminated": system_status.get("data_mode") == "demo_contaminated",
            }
        )
        payload["market_summary"] = market_a + market_hk
        return payload

    dist = {"BUY": 0, "ADD": 0, "WATCH": 0, "REDUCE": 0, "SELL": 0}
    for signal in signals:
        if signal.signal_type in dist:
            dist[signal.signal_type] += 1

    strategy_summary = _strategy_summary(dist)
    if not include_demo and diagnostics_summary.get("formal_real_count", 0) == 0:
        strategy_summary["market_status"] = "neutral"
        strategy_summary["market_status_label"] = "样本观察中"
        strategy_summary["suggested_position"] = "暂不形成正式区间"
        strategy_summary["core_strategy"] = "当前真实样本已完成基础链路接入，但尚未形成正式高关注信号，首页结论以研究观察、低分解释和风险识别为主。"
        strategy_summary["judgement_basis"] = [
            f"真实评分样本 {diagnostics_summary.get('real_count', 0)} 只，其中正式真实 {diagnostics_summary.get('formal_real_count', 0)} 只、真实观察 {diagnostics_summary.get('real_observation_count', 0)} 只。",
            "当前多数样本在质量、趋势或风险维度得分偏低，因此系统未强行包装为正向信号。",
            "研究组合表现仅用于历史研究视图，不代表实盘账户收益，也不构成投资建议。",
        ]
        strategy_summary["risk_warning"] = "当前页面展示的是偏谨慎的真实研究状态，不代表系统异常，也不应被理解为交易指令。"

    top_signals = (
        db.query(TradeSignal, Stock)
        .join(Stock, TradeSignal.stock_id == Stock.id)
        .filter(TradeSignal.signal_date == today, TradeSignal.signal_type.in_(["BUY", "ADD"]))
    )
    if not include_demo:
        top_signals = top_signals.filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE)
    top_signals = top_signals.order_by(TradeSignal.signal_strength.desc(), TradeSignal.id.desc()).limit(10).all()
    top_stock_ids = [stock.id for _, stock in top_signals]
    top_price_map = _latest_price_map(db, top_stock_ids)

    top_signal_list = []
    for sig, stock in top_signals:
        latest_price = top_price_map.get(stock.id)
        top_signal_list.append(
            {
                "symbol": stock.symbol,
                "name": stock.name,
                "market": stock.market,
                "signal_type": sig.signal_type,
                "signal_strength": sig.signal_strength,
                "suggested_position": sig.suggested_position,
                "logic": sanitize_research_text(sig.logic_json.get("reason", "")) if sig.logic_json else "",
                "risk": [sanitize_research_text(item) for item in (sig.risk_json.get("items", []) if sig.risk_json else [])],
                "latest_close": latest_price.close if latest_price else None,
                "change_pct": round((latest_price.close - latest_price.pre_close) / latest_price.pre_close * 100, 2) if latest_price and latest_price.pre_close and latest_price.pre_close != 0 else None,
            }
        )

    portfolio = db.query(Portfolio).first()
    if portfolio:
        positions = db.query(PortfolioPosition).filter(PortfolioPosition.portfolio_id == portfolio.id).all()
        returns = []
        for position in positions:
            if position.cost_price and position.current_price and position.cost_price > 0:
                returns.append(round((position.current_price - position.cost_price) / position.cost_price * 100, 2))
        avg_return = round(sum(returns) / len(returns), 2) if returns else 0
        portfolio_summary = {
            "monthly_return": avg_return,
            "benchmark_return": 0,
            "excess_return": avg_return,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "total_assets": 1000000,
            "cash_ratio": portfolio.cash_ratio or 35.0,
            "position_count": len(returns),
            "name": portfolio.name,
        }
    else:
        portfolio_summary = {
            "monthly_return": 0,
            "benchmark_return": 0,
            "excess_return": 0,
            "max_drawdown": 0,
            "sharpe_ratio": 0,
            "total_assets": 0,
            "cash_ratio": 0,
            "position_count": 0,
            "name": "暂无研究组合",
        }

    scores = score_query.all()
    pools = {"quality": [], "undervalued": [], "trend": [], "risk": []}
    for score, stock in scores:
        item = {
            "symbol": stock.symbol,
            "name": stock.name,
            "market": stock.market,
            "score": score.total_score,
            "rating": score.rating,
            "latest_close": None,
            "change_pct": None,
        }
        if score.quality_score and score.quality_score >= 22:
            pools["quality"].append(item)
        if score.valuation_score and score.valuation_score >= 15:
            pools["undervalued"].append(item)
        if score.trend_score and score.trend_score >= 15:
            pools["trend"].append(item)
        if score.risk_score and score.risk_score < 5:
            pools["risk"].append(item)

    risk_signals = (
        db.query(TradeSignal, Stock)
        .join(Stock, TradeSignal.stock_id == Stock.id)
        .filter(TradeSignal.signal_date == today, TradeSignal.signal_type.in_(["REDUCE", "SELL"]))
    )
    if not include_demo:
        risk_signals = risk_signals.filter(TradeSignal.signal_source == REAL_SIGNAL_SOURCE)
    risk_signals = risk_signals.order_by(TradeSignal.signal_strength.desc(), TradeSignal.id.desc()).limit(10).all()

    risk_alerts = []
    for sig, stock in risk_signals:
        if sig.risk_json and sig.risk_json.get("items"):
            risk_alerts.append(
                {
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "market": stock.market,
                    "level": "high" if sig.signal_type == "SELL" else "medium",
                    "message": sanitize_research_text("；".join(sig.risk_json["items"])),
                }
            )

    # ── dashboard_sections (7 subsections) ──────────────────────────
    _signal_label_map = {"BUY": "高关注", "ADD": "增强关注", "WATCH": "观察", "REDUCE": "风险升高", "SELL": "回避观察"}
    _risk_signal_label_map = {"SELL": "回避观察", "REDUCE": "风险升高"}

    # --- 1. data_coverage ---
    _ss_counts = system_status.get("counts", {})
    data_coverage = {
        "stocks_count": _ss_counts.get("stocks", db.query(Stock).count()),
        "daily_prices_count": _ss_counts.get("prices", db.query(DailyPrice).count()),
        "daily_prices_stock_count": db.query(DailyPrice.stock_id).distinct().count(),
        "financial_metrics_count": _ss_counts.get("financial_metrics", 0),
        "technical_indicators_count": _ss_counts.get("technical_indicators", 0),
        "real_score_count": system_status.get("real_score_count", 0),
        "real_signal_count": system_status.get("real_signal_count", 0),
        "reports_count": _ss_counts.get("reports", 0),
        "research_reports_count": _ss_counts.get("research_reports", 0),
        "backtest_sample_count": db.query(Stock).filter(Stock.market == "A_SHARE", Stock.status == "ACTIVE").count(),
    }

    # --- 2. core_ready_samples ---
    core_ready_samples: list[dict] = []
    try:
        real_scored_stocks = (
            db.query(Stock)
            .join(StockScore, StockScore.stock_id == Stock.id)
            .filter(StockScore.score_source == REAL_SCORE_SOURCE)
            .distinct()
            .all()
        )
        if real_scored_stocks:
            real_symbols = [s.symbol for s in real_scored_stocks]
            coverage_map = get_bulk_data_coverage(db, real_symbols)

            # latest real scores
            latest_score_map: dict[int, StockScore] = {}
            if real_symbols:
                score_subq = (
                    db.query(StockScore.stock_id, func.max(StockScore.score_date).label("max_date"))
                    .join(Stock, StockScore.stock_id == Stock.id)
                    .filter(Stock.symbol.in_(real_symbols), StockScore.score_source == REAL_SCORE_SOURCE)
                    .group_by(StockScore.stock_id)
                    .subquery()
                )
                latest_scores_rows = (
                    db.query(StockScore)
                    .join(score_subq, (StockScore.stock_id == score_subq.c.stock_id) & (StockScore.score_date == score_subq.c.max_date))
                    .all()
                )
                latest_score_map = {s.stock_id: s for s in latest_scores_rows}

            # latest real signals
            latest_signal_map: dict[int, TradeSignal] = {}
            if real_symbols:
                tssub = (
                    db.query(TradeSignal.stock_id, func.max(TradeSignal.signal_date).label("max_date"))
                    .join(Stock, TradeSignal.stock_id == Stock.id)
                    .filter(Stock.symbol.in_(real_symbols), TradeSignal.signal_source == REAL_SIGNAL_SOURCE)
                    .group_by(TradeSignal.stock_id)
                    .subquery()
                )
                latest_signals_rows = (
                    db.query(TradeSignal)
                    .join(tssub, (TradeSignal.stock_id == tssub.c.stock_id) & (TradeSignal.signal_date == tssub.c.max_date))
                    .all()
                )
                latest_signal_map = {s.stock_id: s for s in latest_signals_rows}

            ready_items = []
            for stock in real_scored_stocks:
                cov = coverage_map.get(stock.symbol, {})
                if cov.get("coverage_level") != "ready_full":
                    continue
                score_obj = latest_score_map.get(stock.id)
                sig_obj = latest_signal_map.get(stock.id)
                signal_label = _signal_label_map.get(sig_obj.signal_type, "") if sig_obj else ""
                ready_items.append({
                    "symbol": stock.symbol,
                    "name": stock.name,
                    "market": stock.market,
                    "exchange": stock.exchange,
                    "readiness": cov.get("readiness_label", ""),
                    "price_count": cov.get("price_count", 0),
                    "financial_count": 1 if cov.get("has_financial") else 0,
                    "technical_count": 1 if cov.get("has_technical") else 0,
                    "score": round(score_obj.total_score, 1) if score_obj and score_obj.total_score is not None else None,
                    "signal_label": signal_label,
                    "primary_low_score_reason": _primary_low_score_reason(score_obj),
                    "detail_url": f"/stocks/{stock.symbol}",
                })
            ready_items.sort(key=lambda x: x.get("score") or 0, reverse=True)
            core_ready_samples = ready_items[:10]
    except Exception:
        core_ready_samples = []

    # --- 3. risk_observation_samples ---
    risk_observation_samples: list[dict] = []
    try:
        risk_signals_rows = (
            db.query(TradeSignal, Stock)
            .join(Stock, TradeSignal.stock_id == Stock.id)
            .filter(
                TradeSignal.signal_source == REAL_SIGNAL_SOURCE,
                TradeSignal.signal_type.in_(["REDUCE", "SELL"]),
            )
            .order_by(TradeSignal.signal_date.desc(), TradeSignal.id.desc())
            .limit(10)
            .all()
        )
        risk_stock_ids = [stock.id for _, stock in risk_signals_rows]
        risk_score_map: dict[int, StockScore] = {}
        if risk_stock_ids:
            rssub = (
                db.query(StockScore.stock_id, func.max(StockScore.score_date).label("max_date"))
                .filter(StockScore.stock_id.in_(risk_stock_ids), StockScore.score_source == REAL_SCORE_SOURCE)
                .group_by(StockScore.stock_id)
                .subquery()
            )
            risk_scores_rows = (
                db.query(StockScore)
                .join(rssub, (StockScore.stock_id == rssub.c.stock_id) & (StockScore.score_date == rssub.c.max_date))
                .all()
            )
            risk_score_map = {s.stock_id: s for s in risk_scores_rows}

        for sig, stock in risk_signals_rows:
            score_obj = risk_score_map.get(stock.id)
            risk_observation_samples.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "market": stock.market,
                "score": round(score_obj.total_score, 1) if score_obj and score_obj.total_score is not None else None,
                "signal_type_label": _risk_signal_label_map.get(sig.signal_type, sig.signal_type),
                "primary_low_score_reason": _primary_low_score_reason(score_obj),
            })
    except Exception:
        risk_observation_samples = []

    # --- 4. valuation_gap ---
    pe_non_null = db.query(DailyPrice).filter(DailyPrice.pe.isnot(None)).count()
    pb_non_null = db.query(DailyPrice).filter(DailyPrice.pb.isnot(None)).count()
    valuation_gap = {
        "pe_non_null": pe_non_null,
        "pb_non_null": pb_non_null,
        "real_score_count": system_status.get("real_score_count", 0),
        "valuation_gap_reason": (
            "部分样本PE/PB估值数据缺失，影响估值维度评分计算"
            if (pe_non_null == 0 or pb_non_null == 0)
            else "PE/PB估值数据覆盖率正常"
        ),
        "next_action": (
            "需检查行情数据源是否包含估值字段"
            if (pe_non_null == 0 and pb_non_null == 0)
            else "估值数据基本可用"
        ),
    }

    # --- 5. recent_reports ---
    recent_reports: list[dict] = []
    try:
        reports_q = db.query(Report).order_by(Report.created_at.desc()).limit(3).all()
        for r in reports_q:
            recent_reports.append({
                "id": r.id,
                "title": r.title,
                "report_type": r.report_type,
                "created_at": str(r.created_at) if r.created_at else None,
            })
    except Exception:
        recent_reports = []

    # --- 6. backtest_entry ---
    trade_day_count = db.query(func.count(func.distinct(DailyPrice.trade_date))).scalar() or 0
    price_count = db.query(DailyPrice).count()
    date_range_row = db.query(func.min(DailyPrice.trade_date), func.max(DailyPrice.trade_date)).first()
    backtest_entry = {
        "sample_count": db.query(Stock).filter(Stock.market == "A_SHARE", Stock.status == "ACTIVE").count(),
        "trade_day_count": trade_day_count,
        "price_count": price_count,
        "date_range": f"{date_range_row[0]} ~ {date_range_row[1]}" if date_range_row and date_range_row[0] else None,
    }

    # --- 7. demo_entry ---
    demo_entry = {
        "demo_score_count": system_status.get("demo_score_count", 0),
        "enabled": True,
        "label": "演示评分数据（quick_seed_demo）",
    }

    dashboard_sections = {
        "data_coverage": data_coverage,
        "core_ready_samples": core_ready_samples,
        "risk_observation_samples": risk_observation_samples,
        "valuation_gap": valuation_gap,
        "recent_reports": recent_reports,
        "backtest_entry": backtest_entry,
        "demo_entry": demo_entry,
    }

    return {
        "market_summary": market_a + market_hk,
        "strategy_summary": strategy_summary,
        "top_signals": top_signal_list,
        "signal_distribution": dist,
        "portfolio_summary": portfolio_summary,
        "stock_pools": pools,
        "risk_alerts": risk_alerts,
        "dashboard_sections": dashboard_sections,
        "meta": {
            "signal_date": str(today),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "data_mode": system_status.get("data_mode"),
            "data_mode_label": system_status.get("data_mode_label"),
            "warning": system_status.get("warning"),
            "real_score_count": system_status.get("real_score_count", 0),
            "demo_score_count": system_status.get("demo_score_count", 0),
            "real_signal_count": system_status.get("real_signal_count", 0),
            "demo_signal_count": system_status.get("demo_signal_count", 0),
            "demo_contaminated": system_status.get("data_mode") == "demo_contaminated",
            "formal_real_count": diagnostics_summary.get("formal_real_count", 0),
            "real_observation_count": diagnostics_summary.get("real_observation_count", 0),
            "data_quality_limited_count": diagnostics_summary.get("data_quality_limited_count", 0),
            "data_insufficient_count": diagnostics_summary.get("data_insufficient_count", 0),
            "core_total": diagnostics_summary.get("core_total", 0),
            "core_ready_full_count": diagnostics_summary.get("core_ready_full_count", 0),
            "latest_real_score_date": diagnostics_summary.get("score_date"),
            "avg_total_score": diagnostics_summary.get("avg_total_score"),
            "avg_quality_score": diagnostics_summary.get("avg_quality_score"),
            "avg_valuation_score": diagnostics_summary.get("avg_valuation_score"),
            "avg_growth_score": diagnostics_summary.get("avg_growth_score"),
            "avg_trend_score": diagnostics_summary.get("avg_trend_score"),
            "avg_risk_score": diagnostics_summary.get("avg_risk_score"),
            "low_score_reasons": diagnostics_summary.get("top_reasons", []),
            "launch_data_status": diagnostics_summary.get("launch_data_status"),
            "data_quality_warning": diagnostics_summary.get("message"),
        },
    }
