"""Reports API."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.report import Report
from app.models.research_report import ResearchReport
from app.models.stock import Stock
from app.services.compliance import build_report_footer, build_report_header, sanitize_research_text
from app.services.report import generate_daily_report, generate_stock_report, generate_style_report

router = APIRouter(prefix="/api/reports", tags=["报告"])


def _present_report_markdown(report: Report) -> str:
    content = sanitize_research_text(report.content_markdown or "")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = build_report_header(
        report_type=report.report_type,
        generated_at=generated_at,
        data_as_of=str(report.report_date),
        data_sources="公开市场数据、数据库评分、第三方研报抓取结果",
        mode="研究口径 / 历史回溯 / 非实盘",
        has_live_trading=False,
    )
    footer = build_report_footer(generated_at)
    return f"{header}{content}{footer}"


def _persist_compliant_report(report: Report, db: Session) -> Report:
    report.title = sanitize_research_text(report.title)
    report.summary = sanitize_research_text(report.summary)
    report.content_markdown = _present_report_markdown(report)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.get("")
def list_reports(
    report_type: str = Query(None, description="report type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(Report)
    if report_type:
        query = query.filter(Report.report_type == report_type)

    total = query.count()
    reports = query.order_by(Report.report_date.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": report.id,
                "report_date": str(report.report_date),
                "report_type": report.report_type,
                "style": report.style,
                "title": sanitize_research_text(report.title),
                "summary": sanitize_research_text(report.summary),
                "created_at": str(report.created_at) if report.created_at else None,
            }
            for report in reports
        ],
    }


@router.get("/research")
def get_research_reports(
    symbol: str = Query(None, description="stock code or name"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    refresh: bool = Query(False, description="refresh from provider"),
    db: Session = Depends(get_db),
):
    if refresh:
        from app.services.stock_sync import sync_research_reports

        sync_research_reports(db, symbol=symbol, max_pages=1)

    query = db.query(ResearchReport)
    if symbol:
        query = query.filter(
            (ResearchReport.stock_code.like(f"%{symbol}%")) | (ResearchReport.stock_name.like(f"%{symbol}%"))
        )

    total = query.count()
    reports = query.order_by(desc(ResearchReport.publish_date)).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "reports": [
            {
                "title": report.title,
                "stock_name": report.stock_name,
                "stock_code": report.stock_code,
                "org_name": report.org_name,
                "publish_date": str(report.publish_date) if report.publish_date else "",
                "rating": sanitize_research_text(report.rating),
                "industry": report.industry,
                "researcher": report.researcher,
                "info_code": report.info_code,
                "predict_this_year_eps": report.predict_this_year_eps,
                "predict_this_year_pe": report.predict_this_year_pe,
                "predict_next_year_eps": report.predict_next_year_eps,
                "predict_next_year_pe": report.predict_next_year_pe,
                "predict_next_two_year_eps": report.predict_next_two_year_eps,
                "predict_next_two_year_pe": report.predict_next_two_year_pe,
                "url": report.url,
            }
            for report in reports
        ],
    }


@router.get("/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return {
        "id": report.id,
        "report_date": str(report.report_date),
        "report_type": report.report_type,
        "style": report.style,
        "title": sanitize_research_text(report.title),
        "summary": sanitize_research_text(report.summary),
        "content_markdown": _present_report_markdown(report),
        "content_json": report.content_json,
        "created_at": str(report.created_at) if report.created_at else None,
    }


@router.post("/generate")
def generate_report(
    report_type: str = Query("DAILY", description="report type"),
    stock_symbol: str = Query(None, description="stock code"),
    style: str = Query(None, description="style"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    from app.api.admin import check_user_quota, log_api_call
    import time

    allowed, msg = check_user_quota(db, user.id, "report")
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)
    if style:
        allowed, msg = check_user_quota(db, user.id, "style_report")
        if not allowed:
            raise HTTPException(status_code=429, detail=msg)

    start_time = time.time()
    report_date = date.today()
    if report_type == "DAILY":
        report = generate_daily_report(db, report_date, style=style)
    elif report_type == "STOCK":
        if not stock_symbol:
            raise HTTPException(status_code=400, detail="stock_symbol required for STOCK report")
        stock = db.query(Stock).filter(Stock.symbol == stock_symbol).first()
        if not stock:
            raise HTTPException(status_code=404, detail="Stock not found")
        report = generate_stock_report(db, stock.id, report_date)
        if style:
            report.style = style
    else:
        raise HTTPException(status_code=400, detail="Invalid report type")

    report = _persist_compliant_report(report, db)
    elapsed = int((time.time() - start_time) * 1000)
    log_api_call(db, user.id, user.username, "system", "/api/reports/generate", "POST", 200, elapsed)
    stock_name = None
    market = None
    if report.report_type == "STOCK" and stock_symbol:
        stock = db.query(Stock).filter(Stock.symbol == stock_symbol).first()
        stock_name = stock.name if stock else None
        market = stock.market if stock else None
    return {
        "id": report.id,
        "title": report.title,
        "type": report.report_type,
        "style": report.style,
        "stock_code": stock_symbol,
        "stock_name": stock_name,
        "market": market,
        "created_at": str(report.created_at) if report.created_at else None,
        "html_url": f"/reports/{report.id}",
        "pdf_url": f"/api/reports/{report.id}/pdf",
        "png_url": f"/reports/{report.id}",
        "png_supported": True,
    }


@router.post("/generate-style")
def generate_style_report_api(
    style: str = Query(..., description="style"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    from app.api.admin import check_user_quota, log_api_call
    import time

    if style not in ("steady", "aggressive", "conservative"):
        raise HTTPException(status_code=400, detail="Invalid style. Must be one of: steady, aggressive, conservative")
    allowed, msg = check_user_quota(db, user.id, "report")
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)
    allowed, msg = check_user_quota(db, user.id, "style_report")
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)

    start_time = time.time()
    report = generate_style_report(db, date.today(), style)
    report = _persist_compliant_report(report, db)
    elapsed = int((time.time() - start_time) * 1000)
    log_api_call(db, user.id, user.username, "system", "/api/reports/generate-style", "POST", 200, elapsed)
    return {"id": report.id, "title": report.title, "type": report.report_type, "style": report.style}


@router.get("/{report_id}/pdf")
def download_report_pdf(report_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.api.admin import check_user_quota, log_api_call
    from app.services.pdf_service import generate_pdf_bytes
    from fastapi.responses import Response
    import time
    import urllib.parse

    allowed, msg = check_user_quota(db, user.id, "pdf")
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)

    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    start_time = time.time()

    # 从报告标题解析股票信息（如 "300866 安克创新 深度分析报告"）
    stock_symbol = ""
    stock_name = ""
    title = report.title or ""
    import re as _re
    sym_match = _re.search(r'(\d{5,6})\s+(\S+)', title)
    if sym_match:
        stock_symbol = sym_match.group(1)
        stock_name = sym_match.group(2)

    from app.services.pdf_service import generate_pdf_filename

    pdf_bytes = generate_pdf_bytes(
        _present_report_markdown(report),
        report.title or "研究报告",
        report_date=str(report.report_date),
        stock_symbol=stock_symbol,
        stock_name=stock_name,
    )
    safe_filename = generate_pdf_filename(stock_symbol, stock_name, report.report_type, str(report.report_date))
    ascii_filename = _re.sub(r"[^A-Za-z0-9._-]+", "_", safe_filename).strip("_") or "report.pdf"
    encoded_filename = urllib.parse.quote(safe_filename)
    elapsed = int((time.time() - start_time) * 1000)
    log_api_call(db, user.id, user.username, "system", f"/api/reports/{report_id}/pdf", "GET", 200, elapsed)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'},
    )
