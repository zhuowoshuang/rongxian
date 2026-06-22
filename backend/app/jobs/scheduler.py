"""
每日数据更新调度器
使用 APScheduler 定时刷新行情、评分、信号，并推送通知
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import date
import logging

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _sync_top_stock_reports():
    """同步评分较高的股票的研报"""
    from app.db.session import SessionLocal
    from app.models.stock_score import StockScore
    from app.models.stock import Stock
    from app.services.stock_sync import sync_research_reports

    db = SessionLocal()
    try:
        # 获取最近有评分的股票代码
        top_stocks = (
            db.query(Stock.symbol)
            .join(StockScore, StockScore.stock_id == Stock.id)
            .filter(StockScore.total_score >= 70)
            .distinct()
            .limit(20)
            .all()
        )
        symbols = [s[0] for s in top_stocks]
        for symbol in symbols:
            try:
                sync_research_reports(db, symbol=symbol, max_pages=1)
            except Exception as e:
                logger.error(f"Failed to sync reports for {symbol}: {e}")
    finally:
        db.close()


def _push_daily_notification():
    """推送每日通知"""
    from app.db.session import SessionLocal
    from app.services.notification import get_notification_service
    from app.services.dashboard import get_dashboard_data
    from app.models.trade_signal import TradeSignal
    from app.models.stock import Stock

    db = SessionLocal()
    try:
        service = get_notification_service(db)

        # 获取最新数据
        from datetime import date
        today = date.today()
        latest = db.query(TradeSignal.signal_date).order_by(TradeSignal.signal_date.desc()).first()
        if latest:
            today = latest[0]

        data = get_dashboard_data(db, today)

        signals = []
        for s in data.get("top_signals", []):
            signals.append({
                "symbol": s["symbol"],
                "name": s["name"],
                "type": s["signal_type"],
                "score": s.get("logic", ""),
                "position": s.get("suggested_position", 0),
            })

        market_status = data.get("strategy_summary", {}).get("market_status", "中性")
        indices = data.get("market_summary", [])

        # 推送飞书
        if service.config.get("feishu_enabled") == "true":
            service.push_daily_report(market_status, signals, indices, feishu=True)

        # 推送邮件
        recipient = service.config.get("email_recipient", "")
        if recipient and service.config.get("email_password"):
            service.push_daily_report(market_status, signals, indices, to_email=recipient)

    finally:
        db.close()


def daily_refresh_job():
    """每日收盘后刷新数据、同步研报、推送通知"""
    errors = []

    try:
        from app.seed import refresh_daily
        refresh_daily()
    except Exception as e:
        logger.error(f"Daily refresh failed: {e}")
        errors.append(f"数据刷新失败: {e}")

    # 同步研报
    try:
        _sync_top_stock_reports()
    except Exception as e:
        logger.error(f"Research report sync failed: {e}")
        errors.append(f"研报同步失败: {e}")

    # 推送每日通知
    try:
        _push_daily_notification()
    except Exception as e:
        logger.error(f"Daily notification failed: {e}")
        errors.append(f"通知推送失败: {e}")

    # 如果有失败，记录汇总日志
    if errors:
        logger.error(f"每日任务完成但有 {len(errors)} 个错误: {'; '.join(errors)}")
    else:
        logger.info("每日任务全部完成")


def start_scheduler():
    """启动调度器 - 每个交易日 15:30 执行"""
    if scheduler.running:
        return

    # 每天 15:30 (A股收盘后) 执行数据刷新和通知推送
    scheduler.add_job(
        daily_refresh_job,
        CronTrigger(hour=15, minute=30, day_of_week="mon-fri"),
        id="daily_refresh",
        name="每日数据刷新与通知",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: daily refresh at 15:30 (Mon-Fri)")


def stop_scheduler():
    """停止调度器"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
