"""报告中心 API"""
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db.session import get_db
from app.models.report import Report
from app.models.research_report import ResearchReport
from app.services.report import generate_daily_report, generate_stock_report, generate_style_report
from app.api.auth import get_member_user

router = APIRouter(prefix="/api/reports", tags=["报告"])


@router.get("")
def list_reports(
    report_type: str = Query(None, description="报告类型: DAILY/WEEKLY/STOCK"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """获取报告列表"""
    query = db.query(Report)
    if report_type:
        query = query.filter(Report.report_type == report_type)

    total = query.count()
    reports = (
        query.order_by(Report.report_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": r.id,
                "report_date": str(r.report_date),
                "report_type": r.report_type,
                "style": r.style,
                "title": r.title,
                "summary": r.summary,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in reports
        ],
    }


@router.get("/research")
def get_research_reports(
    symbol: str = Query(None, description="股票代码（不填则获取全市场最新报告）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    refresh: bool = Query(False, description="是否从东方财富实时拉取"),
    db: Session = Depends(get_db),
):
    """获取券商研究报告（优先从数据库读取，refresh=True时从东方财富实时拉取）"""
    if refresh:
        from app.services.stock_sync import sync_research_reports
        sync_research_reports(db, symbol=symbol, max_pages=1)

    query = db.query(ResearchReport)
    if symbol:
        # 支持按代码或名称模糊搜索
        query = query.filter(
            (ResearchReport.stock_code.like(f"%{symbol}%")) |
            (ResearchReport.stock_name.like(f"%{symbol}%"))
        )

    total = query.count()
    reports = (
        query.order_by(desc(ResearchReport.publish_date))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "reports": [
            {
                "title": r.title,
                "stock_name": r.stock_name,
                "stock_code": r.stock_code,
                "org_name": r.org_name,
                "publish_date": str(r.publish_date) if r.publish_date else "",
                "rating": r.rating,
                "industry": r.industry,
                "researcher": r.researcher,
                "info_code": r.info_code,
                "predict_this_year_eps": r.predict_this_year_eps,
                "predict_this_year_pe": r.predict_this_year_pe,
                "predict_next_year_eps": r.predict_next_year_eps,
                "predict_next_year_pe": r.predict_next_year_pe,
                "predict_next_two_year_eps": r.predict_next_two_year_eps,
                "predict_next_two_year_pe": r.predict_next_two_year_pe,
                "url": r.url,
            }
            for r in reports
        ],
    }


@router.get("/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db)):
    """获取单个报告详情"""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "id": report.id,
        "report_date": str(report.report_date),
        "report_type": report.report_type,
        "style": report.style,
        "title": report.title,
        "summary": report.summary,
        "content_markdown": report.content_markdown,
        "content_json": report.content_json,
        "created_at": str(report.created_at) if report.created_at else None,
    }


@router.post("/generate")
def generate_report(
    report_type: str = Query("DAILY", description="报告类型: DAILY/STOCK"),
    stock_symbol: str = Query(None, description="股票代码（STOCK类型必填）"),
    style: str = Query(None, description="投资风格: steady/aggressive/conservative"),
    db: Session = Depends(get_db),
    user=Depends(get_member_user),
):
    """生成报告"""
    from app.api.admin import check_user_quota, log_api_call
    import time

    # 检查配额
    allowed, msg = check_user_quota(db, user.id, "report")
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)

    # 检查风格报告权限
    if style:
        allowed, msg = check_user_quota(db, user.id, "style_report")
        if not allowed:
            raise HTTPException(status_code=429, detail=msg)

    today = date.today()
    start_time = time.time()

    if report_type == "DAILY":
        report = generate_daily_report(db, today, style=style)
    elif report_type == "STOCK":
        if not stock_symbol:
            raise HTTPException(status_code=400, detail="stock_symbol required for STOCK report")
        from app.models.stock import Stock
        stock = db.query(Stock).filter(Stock.symbol == stock_symbol).first()
        if not stock:
            raise HTTPException(status_code=404, detail="Stock not found")
        report = generate_stock_report(db, stock.id, today)
    else:
        raise HTTPException(status_code=400, detail="Invalid report type")

    elapsed = int((time.time() - start_time) * 1000)
    log_api_call(db, user.id, user.username, "system", f"/api/reports/generate", "POST", 200, elapsed)

    return {"id": report.id, "title": report.title, "type": report.report_type, "style": report.style}


@router.post("/generate-style")
def generate_style_report_api(
    style: str = Query(..., description="投资风格: steady/aggressive/conservative"),
    db: Session = Depends(get_db),
    user=Depends(get_member_user),
):
    """生成风格化投资策略报告"""
    from app.api.admin import check_user_quota, log_api_call
    import time

    if style not in ("steady", "aggressive", "conservative"):
        raise HTTPException(status_code=400, detail="Invalid style. Must be one of: steady, aggressive, conservative")

    # 检查配额
    allowed, msg = check_user_quota(db, user.id, "report")
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)

    allowed, msg = check_user_quota(db, user.id, "style_report")
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)

    today = date.today()
    start_time = time.time()
    report = generate_style_report(db, today, style)
    elapsed = int((time.time() - start_time) * 1000)
    log_api_call(db, user.id, user.username, "system", f"/api/reports/generate-style", "POST", 200, elapsed)

    return {"id": report.id, "title": report.title, "type": report.report_type, "style": report.style}


@router.get("/{report_id}/pdf")
def download_report_pdf(report_id: int, db: Session = Depends(get_db), user=Depends(get_member_user)):
    """下载报告PDF"""
    from app.api.admin import check_user_quota, log_api_call
    import time

    # 检查配额
    allowed, msg = check_user_quota(db, user.id, "pdf")
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)

    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    from app.services.pdf_service import generate_pdf_bytes
    from fastapi.responses import Response
    import urllib.parse

    start_time = time.time()

    pdf_bytes = generate_pdf_bytes(report.content_markdown or "", report.title or "Report")
    # 使用ASCII安全的文件名，中文名用URL编码
    safe_filename = f"report_{report_id}_{report.report_date}.pdf"
    encoded_filename = urllib.parse.quote(f"{report.title or 'report'}_{report.report_date}.pdf")

    elapsed = int((time.time() - start_time) * 1000)
    log_api_call(db, user.id, user.username, "system", f"/api/reports/{report_id}/pdf", "GET", 200, elapsed)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"; filename*=UTF-8\'\'{encoded_filename}'},
    )
