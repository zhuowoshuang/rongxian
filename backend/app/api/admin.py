"""管理员 API"""
import os
from datetime import datetime, date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect, func
from pydantic import BaseModel
from typing import Optional

from app.db.session import get_db
from app.models.user import User
from app.models.api_config import ApiConfig, UserApiQuota, ApiCallLog
from app.api.auth import get_current_admin

router = APIRouter(prefix="/api/admin", tags=["管理"])


class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/stats")
def get_stats(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """系统统计数据"""
    from app.models.stock import Stock
    from app.models.trade_signal import TradeSignal
    from app.models.report import Report
    from app.models.research_report import ResearchReport

    total_stocks = db.query(Stock).count()
    total_signals = db.query(TradeSignal).count()
    total_users = db.query(User).count()
    total_reports = db.query(Report).count()
    total_research = db.query(ResearchReport).count()

    # DB file size
    db_size = "N/A"
    # Try common locations
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    for candidate in ["stock_agent.db", "data/rongxian.db", "data/stock_agent.db"]:
        db_path = os.path.join(backend_dir, candidate)
        if os.path.exists(db_path):
            size_bytes = os.path.getsize(db_path)
            if size_bytes > 1024 * 1024:
                db_size = f"{size_bytes / 1024 / 1024:.1f} MB"
            else:
                db_size = f"{size_bytes / 1024:.1f} KB"
            break
    # db_size remains "N/A" if no candidate file found

    return {
        "total_stocks": total_stocks,
        "total_signals": total_signals,
        "total_users": total_users,
        "total_reports": total_reports,
        "total_research_reports": total_research,
        "db_size": db_size,
    }


@router.get("/users")
def list_users(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """列出所有用户"""
    users = db.query(User).order_by(User.id).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": str(u.created_at) if u.created_at else None,
            "updated_at": str(u.updated_at) if u.updated_at else None,
        }
        for u in users
    ]


@router.put("/users/{user_id}")
def update_user(user_id: int, req: UserUpdateRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """更新用户角色或状态"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if req.role is not None:
        if req.role not in ("admin", "analyst", "user", "guest"):
            raise HTTPException(status_code=400, detail="角色必须是 admin、analyst、user 或 guest")
        user.role = req.role
    if req.is_active is not None:
        user.is_active = req.is_active
    db.commit()
    return {"status": "ok", "message": "用户已更新"}


@router.delete("/users/{user_id}")
def disable_user(user_id: int, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """禁用用户（软删除）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="不能禁用自己")
    user.is_active = False
    db.commit()
    return {"status": "ok", "message": "用户已禁用"}


@router.get("/tables")
def list_tables(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """列出所有数据库表及行数"""
    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    result = []
    for table in sorted(tables):
        try:
            safe_name = table.replace('"', '""')
            count = db.execute(text(f'SELECT COUNT(*) FROM "{safe_name}"')).scalar()
        except Exception:
            count = 0
        result.append({"name": table, "row_count": count})
    return result


@router.get("/tables/{table_name}")
def get_table_data(table_name: str, page: int = 1, page_size: int = 50, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """查看指定表的数据（分页）"""
    inspector = inspect(db.bind)
    # 先验证表名是否存在于数据库中（白名单校验，防止 SQL 注入）
    allowed_tables = set(inspector.get_table_names())
    if table_name not in allowed_tables:
        raise HTTPException(status_code=404, detail=f"表 {table_name} 不存在")

    # Get columns
    columns = [col["name"] for col in inspector.get_columns(table_name)]

    # 敏感字段列表：读取时脱敏
    SENSITIVE_FIELDS = {"password_hash", "api_key", "api_secret", "api_password", "token", "secret"}

    # 使用 SQLAlchemy 的 quoted_name 安全引用标识符（转义表名中的双引号防止注入）
    safe_name = table_name.replace('"', '""')
    total = db.execute(text(f'SELECT COUNT(*) FROM "{safe_name}"')).scalar()

    # Get paginated data
    offset = (page - 1) * page_size
    rows = db.execute(text(f'SELECT * FROM "{safe_name}" LIMIT :limit OFFSET :offset'), {"limit": page_size, "offset": offset}).fetchall()

    # Convert rows to list of dicts（敏感字段脱敏）
    data = []
    for row in rows:
        row_dict = {}
        for i, col in enumerate(columns):
            val = row[i]
            if col in SENSITIVE_FIELDS and val:
                row_dict[col] = "***"
            elif val is None:
                row_dict[col] = None
            elif isinstance(val, (int, float, bool, str)):
                row_dict[col] = val
            else:
                row_dict[col] = str(val)
        data.append(row_dict)

    return {
        "columns": columns,
        "total": total,
        "page": page,
        "page_size": page_size,
        "data": data,
    }


# ==================== API配置管理 ====================

class ApiConfigRequest(BaseModel):
    provider: str
    display_name: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    base_url: Optional[str] = None
    is_enabled: Optional[bool] = None
    daily_limit: Optional[int] = None
    rate_limit: Optional[int] = None
    config_json: Optional[str] = None


class UserQuotaRequest(BaseModel):
    daily_report_limit: Optional[int] = None
    daily_backtest_limit: Optional[int] = None
    daily_search_limit: Optional[int] = None
    daily_pdf_limit: Optional[int] = None
    can_download_pdf: Optional[bool] = None
    can_use_style_report: Optional[bool] = None
    can_use_simulation: Optional[bool] = None


@router.get("/api-configs")
def list_api_configs(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """获取所有API配置"""
    configs = db.query(ApiConfig).order_by(ApiConfig.id).all()
    return [
        {
            "id": c.id,
            "provider": c.provider,
            "display_name": c.display_name,
            "api_key": _mask_key(c.api_key),
            "api_secret": _mask_key(c.api_secret),
            "base_url": c.base_url,
            "is_enabled": c.is_enabled,
            "daily_limit": c.daily_limit,
            "rate_limit": c.rate_limit,
            "config_json": c.config_json,
            "created_at": str(c.created_at) if c.created_at else None,
            "updated_at": str(c.updated_at) if c.updated_at else None,
        }
        for c in configs
    ]


@router.post("/api-configs")
def create_or_update_api_config(req: ApiConfigRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """创建或更新API配置"""
    from app.core.config import encrypt_api_key

    existing = db.query(ApiConfig).filter(ApiConfig.provider == req.provider).first()
    if existing:
        if req.display_name is not None: existing.display_name = req.display_name
        if req.api_key is not None and req.api_key != "***": existing.api_key = encrypt_api_key(req.api_key)
        if req.api_secret is not None and req.api_secret != "***": existing.api_secret = encrypt_api_key(req.api_secret)
        if req.base_url is not None: existing.base_url = req.base_url
        if req.is_enabled is not None: existing.is_enabled = req.is_enabled
        if req.daily_limit is not None: existing.daily_limit = req.daily_limit
        if req.rate_limit is not None: existing.rate_limit = req.rate_limit
        if req.config_json is not None: existing.config_json = req.config_json
        db.commit()
        return {"status": "ok", "message": f"{req.provider} 配置已更新", "id": existing.id}
    else:
        config = ApiConfig(
            provider=req.provider,
            display_name=req.display_name or req.provider,
            api_key=encrypt_api_key(req.api_key) if req.api_key else None,
            api_secret=encrypt_api_key(req.api_secret) if req.api_secret else None,
            base_url=req.base_url,
            is_enabled=req.is_enabled if req.is_enabled is not None else True,
            daily_limit=req.daily_limit or 1000,
            rate_limit=req.rate_limit or 10,
            config_json=req.config_json,
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        return {"status": "ok", "message": f"{req.provider} 配置已创建", "id": config.id}


@router.delete("/api-configs/{config_id}")
def delete_api_config(config_id: int, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """删除API配置"""
    config = db.query(ApiConfig).filter(ApiConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")
    db.delete(config)
    db.commit()
    return {"status": "ok", "message": f"{config.provider} 配置已删除"}


@router.post("/api-configs/{config_id}/test")
def test_api_config(config_id: int, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """测试API连接"""
    config = db.query(ApiConfig).filter(ApiConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="配置不存在")

    # 根据供应商类型测试连接
    if config.provider == "eastmoney":
        try:
            import requests
            resp = requests.get("https://push2.eastmoney.com/api/qt/clist/get", timeout=5,
                                params={"pn": 1, "pz": 1, "fs": "m:1+t:2", "fields": "f12,f14"})
            if resp.status_code == 200:
                return {"status": "ok", "message": "东方财富API连接正常"}
        except Exception as e:
            return {"status": "error", "message": f"连接失败: {str(e)}"}
    elif config.provider == "yahoo":
        try:
            import requests
            resp = requests.get("https://query1.finance.yahoo.com/v8/finance/chart/000001.SS", timeout=5)
            if resp.status_code == 200:
                return {"status": "ok", "message": "Yahoo Finance连接正常"}
        except Exception as e:
            return {"status": "error", "message": f"连接失败: {str(e)}"}
    else:
        return {"status": "ok", "message": f"{config.provider} 暂不支持自动测试"}


def _mask_key(key: str) -> str:
    """掩码显示密钥"""
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return key[:4] + "***" + key[-4:]


# ==================== 用户配额管理 ====================

@router.get("/user-quotas")
def list_user_quotas(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """获取所有用户配额"""
    users = db.query(User).order_by(User.id).all()
    result = []
    for u in users:
        quota = db.query(UserApiQuota).filter(UserApiQuota.user_id == u.id).first()
        # 统计今日调用次数
        today = date.today()
        today_calls = db.query(ApiCallLog).filter(
            ApiCallLog.user_id == u.id,
            func.date(ApiCallLog.called_at) == today,
        ).count()

        today_reports = db.query(ApiCallLog).filter(
            ApiCallLog.user_id == u.id,
            func.date(ApiCallLog.called_at) == today,
            ApiCallLog.endpoint.like("/api/reports/generate%"),
        ).count()

        today_backtests = db.query(ApiCallLog).filter(
            ApiCallLog.user_id == u.id,
            func.date(ApiCallLog.called_at) == today,
            ApiCallLog.endpoint.like("/api/backtest%"),
        ).count()

        result.append({
            "user_id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "is_active": u.is_active,
            "daily_report_limit": quota.daily_report_limit if quota else 5,
            "daily_backtest_limit": quota.daily_backtest_limit if quota else 3,
            "daily_search_limit": quota.daily_search_limit if quota else 100,
            "daily_pdf_limit": quota.daily_pdf_limit if quota else 10,
            "can_download_pdf": quota.can_download_pdf if quota else True,
            "can_use_style_report": quota.can_use_style_report if quota else True,
            "can_use_simulation": quota.can_use_simulation if quota else True,
            "today_calls": today_calls,
            "today_reports": today_reports,
            "today_backtests": today_backtests,
        })
    return result


@router.put("/user-quotas/{user_id}")
def update_user_quota(user_id: int, req: UserQuotaRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """更新用户配额"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    quota = db.query(UserApiQuota).filter(UserApiQuota.user_id == user_id).first()
    if not quota:
        quota = UserApiQuota(user_id=user_id)
        db.add(quota)

    if req.daily_report_limit is not None: quota.daily_report_limit = req.daily_report_limit
    if req.daily_backtest_limit is not None: quota.daily_backtest_limit = req.daily_backtest_limit
    if req.daily_search_limit is not None: quota.daily_search_limit = req.daily_search_limit
    if req.daily_pdf_limit is not None: quota.daily_pdf_limit = req.daily_pdf_limit
    if req.can_download_pdf is not None: quota.can_download_pdf = req.can_download_pdf
    if req.can_use_style_report is not None: quota.can_use_style_report = req.can_use_style_report
    if req.can_use_simulation is not None: quota.can_use_simulation = req.can_use_simulation

    db.commit()
    return {"status": "ok", "message": f"{user.username} 配额已更新"}


# ==================== 调用日志 ====================

@router.get("/api-logs")
def list_api_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None),
    provider: Optional[str] = Query(None),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """获取API调用日志"""
    query = db.query(ApiCallLog)
    if user_id:
        query = query.filter(ApiCallLog.user_id == user_id)
    if provider:
        query = query.filter(ApiCallLog.provider == provider)

    total = query.count()
    logs = query.order_by(ApiCallLog.called_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": l.id,
                "user_id": l.user_id,
                "username": l.username,
                "provider": l.provider,
                "endpoint": l.endpoint,
                "method": l.method,
                "status_code": l.status_code,
                "response_time": l.response_time,
                "error_msg": l.error_msg,
                "called_at": str(l.called_at) if l.called_at else None,
            }
            for l in logs
        ],
    }


@router.get("/api-stats")
def get_api_stats(admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """获取API调用统计"""
    today = date.today()

    # 今日总调用
    today_total = db.query(ApiCallLog).filter(func.date(ApiCallLog.called_at) == today).count()

    # 今日按供应商统计
    by_provider = db.query(
        ApiCallLog.provider, func.count(ApiCallLog.id)
    ).filter(
        func.date(ApiCallLog.called_at) == today
    ).group_by(ApiCallLog.provider).all()

    # 今日按用户统计
    by_user = db.query(
        ApiCallLog.username, func.count(ApiCallLog.id)
    ).filter(
        func.date(ApiCallLog.called_at) == today
    ).group_by(ApiCallLog.username).all()

    # 今日错误数
    today_errors = db.query(ApiCallLog).filter(
        func.date(ApiCallLog.called_at) == today,
        ApiCallLog.status_code >= 400,
    ).count()

    # 平均响应时间
    avg_time = db.query(func.avg(ApiCallLog.response_time)).filter(
        func.date(ApiCallLog.called_at) == today
    ).scalar()

    return {
        "today_total": today_total,
        "today_errors": today_errors,
        "avg_response_time": round(avg_time or 0),
        "by_provider": {p: c for p, c in by_provider},
        "by_user": {u: c for u, c in by_user},
    }


# ==================== 调用记录工具函数 ====================

def log_api_call(db: Session, user_id: int, username: str, provider: str, endpoint: str, method: str, status_code: int, response_time: int = 0, error_msg: str = None):
    """记录API调用（供其他模块调用）"""
    log = ApiCallLog(
        user_id=user_id,
        username=username,
        provider=provider,
        endpoint=endpoint,
        method=method,
        status_code=status_code,
        response_time=response_time,
        error_msg=error_msg,
    )
    db.add(log)
    db.commit()


def check_user_quota(db: Session, user_id: int, quota_type: str) -> tuple[bool, str]:
    """检查用户配额，返回 (allowed, message)"""
    from sqlalchemy import func as sqlfunc

    # admin 和 guest 不限制
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.role in ("admin", "guest"):
        return True, ""

    quota = db.query(UserApiQuota).filter(UserApiQuota.user_id == user_id).first()
    today = date.today()

    if quota_type == "report":
        limit = quota.daily_report_limit if quota else 5
        used = db.query(ApiCallLog).filter(
            ApiCallLog.user_id == user_id,
            func.date(ApiCallLog.called_at) == today,
            ApiCallLog.endpoint.like("/api/reports/generate%"),
        ).count()
        if used >= limit:
            return False, f"今日报告生成次数已达上限（{limit}次）"

    elif quota_type == "backtest":
        limit = quota.daily_backtest_limit if quota else 3
        used = db.query(ApiCallLog).filter(
            ApiCallLog.user_id == user_id,
            func.date(ApiCallLog.called_at) == today,
            ApiCallLog.endpoint.like("/api/backtest%"),
        ).count()
        if used >= limit:
            return False, f"今日回测次数已达上限（{limit}次）"

    elif quota_type == "pdf":
        if quota and not quota.can_download_pdf:
            return False, "无PDF下载权限"
        limit = quota.daily_pdf_limit if quota else 10
        used = db.query(ApiCallLog).filter(
            ApiCallLog.user_id == user_id,
            func.date(ApiCallLog.called_at) == today,
            ApiCallLog.endpoint.like("/api/reports/%/pdf"),
        ).count()
        if used >= limit:
            return False, f"今日PDF下载次数已达上限（{limit}次）"

    elif quota_type == "style_report":
        if quota and not quota.can_use_style_report:
            return False, "无风格报告权限"

    elif quota_type == "simulation":
        if quota and not quota.can_use_simulation:
            return False, "无模拟买入权限"

    return True, ""


# ==================== 股票管理 ====================

class StockUpdateRequest(BaseModel):
    name: Optional[str] = None
    industry: Optional[str] = None
    sector: Optional[str] = None
    status: Optional[str] = None


@router.get("/stocks")
def admin_list_stocks(
    keyword: str = Query("", description="搜索关键词"),
    market: str = Query(None, description="市场筛选"),
    status: str = Query(None, description="状态筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员股票列表"""
    from app.models.stock import Stock
    query = db.query(Stock)
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter((Stock.symbol.like(f"%{escaped}%", escape="\\")) | (Stock.name.like(f"%{escaped}%", escape="\\")))
    if market:
        query = query.filter(Stock.market == market)
    if status:
        query = query.filter(Stock.status == status)
    total = query.count()
    stocks = query.order_by(Stock.id).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": s.id, "symbol": s.symbol, "name": s.name,
                "market": s.market, "exchange": s.exchange,
                "industry": s.industry, "sector": s.sector,
                "status": s.status, "currency": s.currency,
                "created_at": str(s.created_at) if s.created_at else None,
            }
            for s in stocks
        ],
    }


@router.put("/stocks/{stock_id}")
def admin_update_stock(stock_id: int, req: StockUpdateRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """编辑股票信息"""
    from app.models.stock import Stock
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")
    if req.name is not None:
        stock.name = req.name
    if req.industry is not None:
        stock.industry = req.industry
    if req.sector is not None:
        stock.sector = req.sector
    if req.status is not None:
        if req.status not in ("ACTIVE", "DELISTED", "SUSPENDED"):
            raise HTTPException(status_code=400, detail="状态必须是 ACTIVE、DELISTED 或 SUSPENDED")
        stock.status = req.status
    db.commit()
    return {"status": "ok", "message": f"{stock.symbol} 已更新"}


@router.delete("/stocks/{stock_id}")
def admin_delete_stock(stock_id: int, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """删除股票及其关联数据"""
    from app.models.stock import Stock
    from app.models.daily_price import DailyPrice
    from app.models.financial_metric import FinancialMetric
    from app.models.technical_indicator import TechnicalIndicator
    from app.models.stock_score import StockScore
    from app.models.trade_signal import TradeSignal
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="股票不存在")
    symbol = stock.symbol
    for model in [DailyPrice, FinancialMetric, TechnicalIndicator, StockScore, TradeSignal]:
        db.query(model).filter(model.stock_id == stock_id).delete()
    db.delete(stock)
    db.commit()
    return {"status": "ok", "message": f"{symbol} 及关联数据已删除"}


@router.post("/stocks/sync")
def admin_sync_stocks(
    market: str = Query("ALL", description="同步市场: A_SHARE / HK / ALL"),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """从东方财富同步股票列表"""
    from app.services.stock_sync import sync_stock_list
    result = sync_stock_list(db, market=market)
    return {"status": "ok", "message": f"同步完成: 新增{result['added']}，更新{result['updated']}，共{result['total']}", **result}


@router.post("/stocks/fetch")
def admin_fetch_stock(
    symbol: str = Query(..., description="股票代码"),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """添加单只股票并获取全部数据"""
    from app.api.stocks import add_stock_and_fetch
    return add_stock_and_fetch(symbol=symbol, db=db, user=admin)


# ==================== 评分管理 ====================

class ScoreUpdateRequest(BaseModel):
    quality_score: Optional[float] = None
    valuation_score: Optional[float] = None
    growth_score: Optional[float] = None
    trend_score: Optional[float] = None
    risk_score: Optional[float] = None
    rating: Optional[str] = None
    reason_summary: Optional[str] = None


@router.get("/scores")
def admin_list_scores(
    keyword: str = Query("", description="搜索代码/名称"),
    rating: str = Query(None, description="评级筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员评分列表"""
    from app.models.stock_score import StockScore
    from app.models.stock import Stock
    query = db.query(StockScore, Stock).join(Stock, StockScore.stock_id == Stock.id)
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter((Stock.symbol.like(f"%{escaped}%", escape="\\")) | (Stock.name.like(f"%{escaped}%", escape="\\")))
    if rating:
        query = query.filter(StockScore.rating == rating)
    total = query.count()
    results = query.order_by(StockScore.score_date.desc(), StockScore.total_score.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": score.id, "stock_id": stock.id, "symbol": stock.symbol, "name": stock.name,
                "total_score": score.total_score, "quality_score": score.quality_score,
                "valuation_score": score.valuation_score, "growth_score": score.growth_score,
                "trend_score": score.trend_score, "risk_score": score.risk_score,
                "rating": score.rating, "reason_summary": score.reason_summary,
                "score_date": str(score.score_date),
            }
            for score, stock in results
        ],
    }


@router.put("/scores/{score_id}")
def admin_update_score(score_id: int, req: ScoreUpdateRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """手动调整评分"""
    from app.models.stock_score import StockScore
    score = db.query(StockScore).filter(StockScore.id == score_id).first()
    if not score:
        raise HTTPException(status_code=404, detail="评分记录不存在")
    if req.quality_score is not None:
        score.quality_score = req.quality_score
    if req.valuation_score is not None:
        score.valuation_score = req.valuation_score
    if req.growth_score is not None:
        score.growth_score = req.growth_score
    if req.trend_score is not None:
        score.trend_score = req.trend_score
    if req.risk_score is not None:
        score.risk_score = req.risk_score
    if req.rating is not None:
        score.rating = req.rating
    if req.reason_summary is not None:
        score.reason_summary = req.reason_summary
    score.total_score = round((score.quality_score or 0) + (score.valuation_score or 0) + (score.growth_score or 0) + (score.trend_score or 0) + (score.risk_score or 0), 1)
    db.commit()
    return {"status": "ok", "message": "评分已更新", "total_score": score.total_score}


# ==================== 信号管理 ====================

class SignalUpdateRequest(BaseModel):
    signal_type: Optional[str] = None
    signal_strength: Optional[int] = None
    suggested_position: Optional[float] = None
    entry_price: Optional[float] = None
    target_price: Optional[float] = None
    stop_loss_price: Optional[float] = None
    holding_period: Optional[str] = None
    status: Optional[str] = None


@router.get("/signals")
def admin_list_signals(
    keyword: str = Query("", description="搜索代码/名称"),
    signal_type: str = Query(None, description="信号类型"),
    status: str = Query(None, description="状态"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员信号列表"""
    from app.models.trade_signal import TradeSignal
    from app.models.stock import Stock
    query = db.query(TradeSignal, Stock).join(Stock, TradeSignal.stock_id == Stock.id)
    if keyword:
        escaped = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.filter((Stock.symbol.like(f"%{escaped}%", escape="\\")) | (Stock.name.like(f"%{escaped}%", escape="\\")))
    if signal_type:
        query = query.filter(TradeSignal.signal_type == signal_type)
    if status:
        query = query.filter(TradeSignal.status == status)
    total = query.count()
    results = query.order_by(TradeSignal.signal_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": sig.id, "stock_id": stock.id, "symbol": stock.symbol, "name": stock.name,
                "signal_type": sig.signal_type, "signal_strength": sig.signal_strength,
                "suggested_position": sig.suggested_position,
                "entry_price": sig.entry_price, "target_price": sig.target_price,
                "stop_loss_price": sig.stop_loss_price, "holding_period": sig.holding_period,
                "status": sig.status, "signal_date": str(sig.signal_date),
            }
            for sig, stock in results
        ],
    }


@router.put("/signals/{signal_id}")
def admin_update_signal(signal_id: int, req: SignalUpdateRequest, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """编辑信号"""
    from app.models.trade_signal import TradeSignal
    sig = db.query(TradeSignal).filter(TradeSignal.id == signal_id).first()
    if not sig:
        raise HTTPException(status_code=404, detail="信号不存在")
    if req.signal_type is not None:
        sig.signal_type = req.signal_type
    if req.signal_strength is not None:
        sig.signal_strength = req.signal_strength
    if req.suggested_position is not None:
        sig.suggested_position = req.suggested_position
    if req.entry_price is not None:
        sig.entry_price = req.entry_price
    if req.target_price is not None:
        sig.target_price = req.target_price
    if req.stop_loss_price is not None:
        sig.stop_loss_price = req.stop_loss_price
    if req.holding_period is not None:
        sig.holding_period = req.holding_period
    if req.status is not None:
        if req.status not in ("ACTIVE", "EXPIRED", "EXECUTED"):
            raise HTTPException(status_code=400, detail="状态必须是 ACTIVE、EXPIRED 或 EXECUTED")
        sig.status = req.status
    db.commit()
    return {"status": "ok", "message": "信号已更新"}


@router.delete("/signals/{signal_id}")
def admin_delete_signal(signal_id: int, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    """删除信号"""
    from app.models.trade_signal import TradeSignal
    sig = db.query(TradeSignal).filter(TradeSignal.id == signal_id).first()
    if not sig:
        raise HTTPException(status_code=404, detail="信号不存在")
    db.delete(sig)
    db.commit()
    return {"status": "ok", "message": "信号已删除"}
