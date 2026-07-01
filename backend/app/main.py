"""
A股 + 港股中长期基本面选股与交易信号报告系统
FastAPI 主入口
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sqlalchemy import text
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine

# 导入所有模型（确保表被创建）
from app.models import stock, daily_price, financial_metric, technical_indicator
from app.models import stock_score, trade_signal, report, portfolio, user, setting
from app.models import research_report, api_config, stock_status_history, watchlist, refresh_job_run

# 导入路由
from app.api.dashboard import router as dashboard_router
from app.api.stocks import router as stocks_router
from app.api.signals import router as signals_router
from app.api.pools import router as pools_router
from app.api.reports import router as reports_router
from app.api.backtest import router as backtest_router
from app.api.auth import router as auth_router
from app.api.adata import router as adata_router
from app.api.settings import router as settings_router
from app.api.admin import router as admin_router
from app.api.profile import router as profile_router
from app.services.data_credibility import mark_existing_scores_as_demo
from app.services.financial_periods import normalize_report_period_to_date


def _audit_action_for_request(path: str, method: str, status_code: int) -> tuple[str, str] | None:
    if path.startswith("/api/admin") and status_code == 403:
        return "permission_denied", "admin"
    if path.startswith("/api/admin/users/") and path.endswith("/reset-password"):
        return "admin_reset_password", "user"
    if path == "/api/admin/users/export":
        return "admin_export_users", "user"
    if path.startswith("/api/admin/api-configs") and method == "POST" and path.endswith("/test"):
        return "admin_api_config_test", "api_config"
    if path.startswith("/api/admin/api-configs") and method == "POST":
        return "admin_api_config_save", "api_config"
    if path.startswith("/api/admin/api-configs") and method == "DELETE":
        return "admin_api_config_delete", "api_config"
    if status_code >= 400 and path.startswith("/api/"):
        return "api_error", "api"
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时创建数据库表、启动调度器；关闭时停止调度器"""
    import os
    import logging
    logger = logging.getLogger(__name__)

    Base.metadata.create_all(bind=engine)
    if settings.DATABASE_URL.startswith("sqlite"):
        with engine.begin() as conn:
            def add_col(table: str, col: str, ddl: str):
                cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()]
                if col not in cols:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
            for col, ddl in {
                "phone": "phone VARCHAR(32)",
                "user_id": "user_id VARCHAR(64)",
                "status": "status VARCHAR(20) DEFAULT 'active'",
                "last_login_at": "last_login_at DATETIME",
            }.items():
                add_col("users", col, ddl)
            for col, ddl in {
                "user_id": "user_id INTEGER",
                "stock_code": "stock_code VARCHAR(20)",
                "stock_name": "stock_name VARCHAR(100)",
                "market": "market VARCHAR(30)",
            }.items():
                add_col("reports", col, ddl)
            for col, ddl in {
                "daily_png_limit": "daily_png_limit INTEGER DEFAULT 30",
                "max_api_configs": "max_api_configs INTEGER DEFAULT 5",
            }.items():
                add_col("user_api_quotas", col, ddl)
            for col, ddl in {
                "strategy_name": "strategy_name VARCHAR(120)",
                "rebalance_frequency": "rebalance_frequency VARCHAR(30)",
            }.items():
                add_col("backtest_tasks", col, ddl)
            for col, ddl in {
                "score_source": "score_source VARCHAR(32) DEFAULT 'unknown_legacy'",
            }.items():
                add_col("stock_scores", col, ddl)
            for col, ddl in {
                "signal_source": "signal_source VARCHAR(32) DEFAULT 'unknown_legacy'",
            }.items():
                add_col("trade_signals", col, ddl)
            for col, ddl in {
                "report_date": "DATE",
            }.items():
                add_col("financial_metrics", col, ddl)
            for col, ddl in {
                "ma5": "ma5 FLOAT",
                "ma10": "ma10 FLOAT",
                "volume_ratio_5_20": "volume_ratio_5_20 FLOAT",
                "weekly_volatility_candidate": "weekly_volatility_candidate FLOAT",
                "monthly_volatility_candidate": "monthly_volatility_candidate FLOAT",
            }.items():
                add_col("technical_indicators", col, ddl)

        from app.db.session import SessionLocal

        credibility_db = SessionLocal()
        try:
            from app.models.financial_metric import FinancialMetric

            missing_dates = credibility_db.query(FinancialMetric).filter(FinancialMetric.report_date.is_(None)).all()
            for row in missing_dates:
                row.report_date = normalize_report_period_to_date(row.report_period)
            credibility_db.commit()
            credibility_result = mark_existing_scores_as_demo(credibility_db)
            logger.info("data credibility bootstrap finished: %s", credibility_result)
        except Exception as exc:
            logger.error("data credibility bootstrap failed: %s", exc)
        finally:
            credibility_db.close()

    # 检查是否使用 Mock 数据
    use_mock = os.environ.get("MOCK_DATA", "true").lower() in ("true", "1", "yes")

    # 生产环境禁止启用 fixture 冒充 live
    app_env = os.environ.get("APP_ENV", "development").lower()
    adata_fixtures = os.environ.get("ADATA_USE_FIXTURES", "false").lower() in ("true", "1", "yes")
    if app_env == "production" and adata_fixtures:
        raise RuntimeError("生产环境禁止启用 ADATA_USE_FIXTURES。fixture 仅用于离线验收，不得在 production 冒充 live 数据。")

    if not use_mock:
        # 仅在非 Mock 模式下尝试从真实 API 同步
        from app.db.session import SessionLocal, get_db
        from app.models.stock import Stock
        from app.models.research_report import ResearchReport
        override_get_db = request.app.dependency_overrides.get(get_db)
        db_gen = override_get_db() if override_get_db else None
        db = next(db_gen) if db_gen else SessionLocal()
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
            if db_gen:
                db_gen.close()
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


# ── 将 Pydantic 校验错误转为中文 400（禁止英文堆栈泄漏到前端）──
_FIELD_LABELS: dict[str, str] = {
    "phone": "手机号",
    "user_id": "用户ID",
    "username": "用户名",
    "password": "密码",
    "confirm_password": "确认密码",
    "display_name": "显示名称",
    "identifier": "手机号或用户ID",
}


def _friendly_validation_detail(errors: list) -> str:
    msgs: list[str] = []
    for err in errors:
        loc = err.get("loc", [])
        raw_msg: str = err.get("msg", "")
        field_name = ""
        for part in reversed(loc):
            if isinstance(part, str) and part not in ("body", "query", "path"):
                field_name = part
                break
        label = _FIELD_LABELS.get(field_name, "")
        if label and ("required" in raw_msg.lower() or "field required" in raw_msg.lower()):
            msgs.append(f"{label}不能为空")
        elif label and raw_msg:
            # Pydantic v2 "Value error, xxx" → "xxx"
            clean = raw_msg
            for prefix in ("Value error, ", "Assertion failed, "):
                if clean.startswith(prefix):
                    clean = clean[len(prefix):]
            if clean:
                msgs.append(clean)
            else:
                msgs.append(f"{label}格式不正确")
        elif raw_msg:
            clean = raw_msg
            for prefix in ("Value error, ", "Assertion failed, "):
                if clean.startswith(prefix):
                    clean = clean[len(prefix):]
            msgs.append(clean if clean else "注册信息格式不正确")
    if not msgs:
        return "注册信息格式不正确，请检查填写信息后重试"
    return "；".join(msgs)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_request: Request, exc: RequestValidationError):
    errors_list = exc.errors() if callable(exc.errors) else []
    return JSONResponse(status_code=400, content={"detail": _friendly_validation_detail(errors_list)})


@app.middleware("http")
async def audit_admin_and_errors(request, call_next):
    response = await call_next(request)
    audit = _audit_action_for_request(request.url.path, request.method, response.status_code)
    if audit:
        from app.api.auth import verify_token
        from app.db.session import SessionLocal, get_db
        from app.models.user import User
        from app.services.audit import log_operation

        action, target_type = audit
        override_get_db = request.app.dependency_overrides.get(get_db)
        db_gen = override_get_db() if override_get_db else None
        db = next(db_gen) if db_gen else SessionLocal()
        try:
            user = None
            authorization = request.headers.get("authorization", "")
            if authorization.startswith("Bearer "):
                payload = verify_token(authorization.split(" ", 1)[1])
                if payload:
                    user = db.query(User).filter(User.username == payload.get("sub")).first()
            log_operation(
                db,
                user=user,
                action=action,
                target_type=target_type,
                target_id=request.path_params.get("user_id") or request.path_params.get("config_id"),
                status="failed" if response.status_code >= 400 else "success",
                message=f"{request.method} {request.url.path} HTTP {response.status_code}",
                request=request,
            )
        finally:
            db.close()
            if db_gen:
                db_gen.close()
    return response

# 注册路由
app.include_router(auth_router)
app.include_router(adata_router)
app.include_router(dashboard_router)
app.include_router(stocks_router)
app.include_router(signals_router)
app.include_router(pools_router)
app.include_router(reports_router)
app.include_router(backtest_router)
app.include_router(settings_router)
app.include_router(admin_router)
app.include_router(profile_router)


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
