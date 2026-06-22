"""
A股 + 港股中长期基本面选股与交易信号报告系统
FastAPI 主入口
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

# 导入所有模型（确保表被创建）
from app.models import stock, daily_price, financial_metric, technical_indicator
from app.models import stock_score, trade_signal, report, portfolio, user, setting
from app.models import research_report, api_config, stock_status_history

# 导入路由
from app.api.dashboard import router as dashboard_router
from app.api.stocks import router as stocks_router
from app.api.signals import router as signals_router
from app.api.pools import router as pools_router
from app.api.reports import router as reports_router
from app.api.backtest import router as backtest_router
from app.api.auth import router as auth_router
from app.api.settings import router as settings_router
from app.api.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时创建数据库表、启动调度器；关闭时停止调度器"""
    import os
    import logging
    logger = logging.getLogger(__name__)

    Base.metadata.create_all(bind=engine)

    # 检查是否使用 Mock 数据
    use_mock = os.environ.get("MOCK_DATA", "true").lower() in ("true", "1", "yes")

    if not use_mock:
        # 仅在非 Mock 模式下尝试从真实 API 同步
        from app.db.session import SessionLocal
        from app.models.stock import Stock
        from app.models.research_report import ResearchReport
        db = SessionLocal()
        try:
            count = db.query(Stock).count()
            if count == 0:
                logger.info("数据库无股票数据，开始同步...")
                from app.services.stock_sync import sync_stock_list
                result = sync_stock_list(db, market="ALL")
                logger.info(f"股票同步完成: 新增 {result['added']}，共 {result['total']}")

            report_count = db.query(ResearchReport).count()
            if report_count == 0:
                logger.info("开始同步热门股票研报...")
                from app.services.stock_sync import sync_research_reports
                from app.models.stock_score import StockScore
                top_stocks = (
                    db.query(Stock.symbol)
                    .join(StockScore, StockScore.stock_id == Stock.id)
                    .filter(StockScore.total_score >= 70)
                    .distinct()
                    .limit(10)
                    .all()
                )
                if top_stocks:
                    for s in top_stocks:
                        try:
                            sync_research_reports(db, symbol=s[0], max_pages=1)
                        except Exception:
                            pass
                    logger.info("研报同步完成")
        except Exception as e:
            logger.error(f"启动同步失败: {e}")
        finally:
            db.close()
    else:
        logger.info("Mock 模式: 跳过真实 API 同步，请确保已运行 seed 脚本")

    # 启动调度器（Mock 模式下跳过，模拟数据不需要每日刷新）
    from app.jobs.scheduler import start_scheduler, stop_scheduler
    if not use_mock:
        try:
            start_scheduler()
            logger.info("Scheduler started successfully")
        except Exception as e:
            logger.warning(f"Scheduler failed to start: {e}")
    else:
        logger.info("Mock 模式: 跳过调度器")

    yield

    # 关闭时停止调度器
    if not use_mock:
        stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="A股 + 港股中长期基本面选股与交易信号报告系统 API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(stocks_router)
app.include_router(signals_router)
app.include_router(pools_router)
app.include_router(reports_router)
app.include_router(backtest_router)
app.include_router(settings_router)
app.include_router(admin_router)


@app.get("/")
def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "disclaimer": "本系统仅用于研究和辅助分析，不构成任何投资建议。",
    }


@app.get("/api/health")
def health():
    """健康检查（含数据库和 Redis 连通性）"""
    from app.db.session import SessionLocal
    from app.core.redis import is_redis_available
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        db.close()
    redis_ok = is_redis_available()
    status = "ok" if db_ok and redis_ok else ("degraded" if db_ok else "error")
    return {"status": status, "database": "ok" if db_ok else "error", "redis": "ok" if redis_ok else "unavailable"}
