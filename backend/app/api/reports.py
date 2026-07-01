"""Reports API."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.db.session import get_db
from app.models.report import Report, ReportEvent
from app.models.research_report import ResearchReport
from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.technical_indicator import TechnicalIndicator
from app.models.trade_signal import TradeSignal
from app.services.audit import log_operation
from app.services.compliance import build_report_footer, build_report_header, sanitize_research_text
from app.services.data_credibility import (
    REAL_SCORE_SOURCE,
    REPORT_STATUS_DEMO,
    REPORT_STATUS_INSUFFICIENT,
    REPORT_STATUS_PARTIAL_NO_VALUATION,
    REPORT_STATUS_REAL,
    report_data_status,
)
from app.services.quota import check_quota
from app.services.report import generate_daily_report, generate_stock_report, generate_style_report
from app.services.score_diagnostics import diagnose_single_stock_score

router = APIRouter(prefix="/api/reports", tags=["报告"])


def _report_status_from_display_tier(display_tier: str | None) -> str:
    mapping = {
        "formal_real": "real_backed",
        "real_observation": "real_observation",
        "data_quality_limited": "data_quality_limited",
        "data_insufficient": "data_insufficient",
        "demo_only": "demo_backed",
    }
    return mapping.get(display_tier or "", "data_insufficient")


def _latest_score_for_stock(db: Session, stock_id: int) -> StockScore | None:
    return db.query(StockScore).filter(StockScore.stock_id == stock_id).order_by(StockScore.score_date.desc()).first()


def _latest_price_for_stock(db: Session, stock_id: int) -> DailyPrice | None:
    return db.query(DailyPrice).filter(DailyPrice.stock_id == stock_id).order_by(DailyPrice.trade_date.desc()).first()


def _report_status_meta(report: Report) -> tuple[str, str | None]:
    content_json = report.content_json if isinstance(report.content_json, dict) else {}
    status = content_json.get("report_data_status")
    source = content_json.get("score_source_used")
    if status:
        return status, source
    return REPORT_STATUS_REAL, source


def _report_warning_block(status: str, source: str | None) -> str:
    if status == REPORT_STATUS_REAL:
        return ""
    if status == REPORT_STATUS_DEMO:
        return (
            "> 研究提示：本报告基于演示评分或历史演示链路生成，仅用于系统联调与展示，"
            "不代表真实评分结论，不构成投资建议。\n\n"
        )
    return (
        "> 研究提示：当前真实行情已接入，但财务、技术指标或真实评分尚未完成，"
        "本报告仅展示数据状态与待补齐项，不构成正式研究结论。\n\n"
    )


def _present_report_markdown(report: Report) -> str:
    content = sanitize_research_text(report.content_markdown or "")
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status, source = _report_status_meta(report)
    header = build_report_header(
        report_type=report.report_type,
        generated_at=generated_at,
        data_as_of=str(report.report_date),
        data_sources="公开市场数据、数据库评分、第三方研报抓取结果",
        mode="研究口径 / 历史回放 / 非实盘",
        has_live_trading=False,
    )
    footer = build_report_footer(generated_at)
    return f"{header}{_report_warning_block(status, source)}{content}{footer}"


def _persist_compliant_report(report: Report, db: Session) -> Report:
    report.title = sanitize_research_text(report.title)
    report.summary = sanitize_research_text(report.summary)
    report.content_markdown = _present_report_markdown(report)
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def _get_accessible_report(db: Session, report_id: int, user) -> Report:
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在或已删除")
    if user.role != "admin" and report.user_id != user.id:
        log_operation(
            db,
            user=user,
            action="permission_denied",
            target_type="report",
            target_id=report_id,
            status="failed",
            message="attempt to access another user's report",
        )
        raise HTTPException(status_code=403, detail="无权访问该报告")
    return report


def _serialize_report_list_item(db: Session, report: Report) -> dict:
    status, source = _report_status_meta(report)
    return {
        "id": report.id,
        "report_date": str(report.report_date),
        "report_type": report.report_type,
        "style": report.style,
        "stock_code": report.stock_code,
        "stock_name": report.stock_name,
        "market": report.market,
        "title": sanitize_research_text(report.title),
        "summary": sanitize_research_text(report.summary),
        "download_count": db.query(ReportEvent).filter(ReportEvent.report_id == report.id, ReportEvent.action == "download").count(),
        "html_views": db.query(ReportEvent).filter(ReportEvent.report_id == report.id, ReportEvent.format == "html", ReportEvent.action == "view").count(),
        "png_downloads": db.query(ReportEvent).filter(ReportEvent.report_id == report.id, ReportEvent.format == "png", ReportEvent.action == "download").count(),
        "pdf_downloads": db.query(ReportEvent).filter(ReportEvent.report_id == report.id, ReportEvent.format == "pdf", ReportEvent.action == "download").count(),
        "created_at": str(report.created_at) if report.created_at else None,
        "report_data_status": status,
        "score_source_used": source,
    }


def _build_data_insufficient_report(stock: Stock, report_date: date, score_source: str | None) -> Report:
    status = report_data_status(score_source)
    title = f"{stock.symbol} {stock.name} 数据状态说明"
    summary = "真实行情已接入，但底层真实评分链路尚未完成。本报告仅说明当前数据状态与待补齐项。"
    content = "\n".join(
        [
            f"# {stock.symbol} {stock.name} 数据状态说明",
            "",
            "## 当前已接入",
            "- 已接入股票基础信息与历史行情数据。",
            "- 可继续同步第三方研报、财务数据和技术指标。",
            "",
            "## 当前未完成",
            "- 真实五维评分尚未生成或无法验证来源。",
            "- 正式研究信号尚未生成或仍处于演示隔离状态。",
            "- 当前不能形成完整个股研究结论。",
            "",
            "## 使用边界",
            "- 本页仅用于研究辅助和系统联调。",
            "- 不构成投资建议，不代表未来收益。",
        ]
    )
    return Report(
        report_date=report_date,
        report_type="STOCK",
        style="data_status",
        stock_code=stock.symbol,
        stock_name=stock.name,
        market=stock.market,
        title=title,
        summary=summary,
        content_markdown=content,
        content_json={
            "report_data_status": status,
            "score_source_used": score_source,
            "report_mode": "data_status",
        },
    )


def _build_data_status_report_v2(db: Session, stock: Stock, report_date: date, score_source: str | None) -> Report:
    status = report_data_status(score_source)
    price_count = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id).count()
    financial_count = db.query(FinancialMetric).filter(FinancialMetric.stock_id == stock.id).count()
    technical_count = db.query(TechnicalIndicator).filter(TechnicalIndicator.stock_id == stock.id).count()
    score_count = db.query(StockScore).filter(StockScore.stock_id == stock.id, StockScore.score_source == REAL_SCORE_SOURCE).count()
    signal_count = db.query(TradeSignal).filter(TradeSignal.stock_id == stock.id).count()

    missing_items: list[str] = []
    if price_count == 0:
        missing_items.append("行情")
    if financial_count == 0:
        missing_items.append("财务")
    if technical_count == 0:
        missing_items.append("技术指标")
    if score_count == 0:
        missing_items.append("真实评分")
    if price_count == 0 or financial_count == 0:
        missing_items.append("估值字段")
    if price_count == 0:
        missing_items.append("市值字段")

    content = "\n".join(
        [
            f"# {stock.symbol} {stock.name} 数据状态说明",
            "",
            "## 核心摘要",
            "该股票已进入基础股票库，但当前尚未形成完整真实评分链路。",
            "",
            "## 当前覆盖状态",
            "- 股票基础信息：已接入",
            f"- 行情数据：{'暂无' if price_count == 0 else f'{price_count} 条'}",
            f"- 财务数据：{'暂无' if financial_count == 0 else f'{financial_count} 期'}",
            f"- 技术指标：{'暂无' if technical_count == 0 else '已接入'}",
            f"- 真实评分：{'暂无' if score_count == 0 else f'{score_count} 条'}",
            f"- 研究信号：{'暂无' if signal_count == 0 else f'{signal_count} 条'}",
            "",
            "## 缺失数据",
            *(f"- {item}" for item in missing_items),
            "",
            "## 为什么不能形成评分",
            f"因为当前缺少{'、'.join(missing_items) if missing_items else '关键因子'}，系统不会用演示评分伪装成真实研究结论。",
            "",
            "## 后续补数路径",
            "1. 补行情",
            "2. 补财务",
            "3. 计算技术指标",
            "4. 生成真实评分",
            "5. 形成研究信号",
            "",
            "## 推荐替代演示样本",
            "- 002415 海康威视",
            "- 600519 贵州茅台",
            "",
            "## 免责声明",
            "仅用于研究辅助，不构成投资建议。",
        ]
    )
    return Report(
        report_date=report_date,
        report_type="STOCK",
        style="data_status",
        stock_code=stock.symbol,
        stock_name=stock.name,
        market=stock.market,
        title=f"{stock.symbol} {stock.name} 数据状态说明",
        summary="该股票已进入基础股票库，但当前尚未形成完整真实评分链路。本报告用于说明当前覆盖状态、缺失项与后续补数路径。",
        content_markdown=content,
        content_json={
            "report_data_status": status,
            "score_source_used": score_source,
            "report_mode": "data_status",
            "missing_items": missing_items,
            "price_count": price_count,
            "financial_count": financial_count,
            "technical_count": technical_count,
            "score_count": score_count,
            "signal_count": signal_count,
        },
    )


@router.get("")
def list_reports(
    report_type: str = Query(None, description="report type"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    query = db.query(Report)
    if user.role != "admin":
        query = query.filter(Report.user_id == user.id)
    if report_type:
        query = query.filter(Report.report_type == report_type)

    total = query.count()
    reports = query.order_by(Report.report_date.desc(), Report.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_serialize_report_list_item(db, report) for report in reports],
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
def get_report(report_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    report = _get_accessible_report(db, report_id, user)
    db.add(
        ReportEvent(
            user_id=user.id,
            report_id=report.id,
            stock_code=report.stock_code,
            report_type=report.report_type,
            format="html",
            action="view",
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    db.commit()
    log_operation(db, user=user, action="report_html_view", target_type="report", target_id=report.id, message=f"report_id={report.id}", request=request)
    status, source = _report_status_meta(report)
    return {
        "id": report.id,
        "report_date": str(report.report_date),
        "report_type": report.report_type,
        "style": report.style,
        "stock_code": report.stock_code,
        "stock_name": report.stock_name,
        "market": report.market,
        "title": sanitize_research_text(report.title),
        "summary": sanitize_research_text(report.summary),
        "content_markdown": _present_report_markdown(report),
        "content_json": report.content_json,
        "created_at": str(report.created_at) if report.created_at else None,
        "report_data_status": status,
        "score_source_used": source,
    }


@router.post("/generate")
def generate_report(
    report_type: str = Query("DAILY", description="report type"),
    stock_symbol: str = Query(None, description="stock code"),
    style: str = Query(None, description="style"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    from app.api.admin import log_api_call
    import time

    allowed, msg = check_quota(db, user, "report")
    if not allowed:
        log_operation(db, user=user, action="report_generate", target_type="report", status="failed", message=msg)
        raise HTTPException(status_code=429, detail=msg)

    start_time = time.time()
    report_date = date.today()
    stock_name = None
    market = None

    if report_type == "DAILY":
        report = generate_daily_report(db, report_date, style=style)
        if not isinstance(report.content_json, dict):
            report.content_json = {}
        report.content_json.setdefault("report_data_status", REPORT_STATUS_REAL)
    elif report_type == "STOCK":
        if not stock_symbol:
            raise HTTPException(status_code=400, detail="请先选择要生成报告的股票")
        stock = db.query(Stock).filter(Stock.symbol == stock_symbol).first()
        if not stock:
            raise HTTPException(status_code=404, detail="未找到该股票，请重新选择")
        stock_name = stock.name
        market = stock.market
        diagnostics = diagnose_single_stock_score(db, stock.symbol) or {}
        latest_score = _latest_score_for_stock(db, stock.id)
        latest_price = _latest_price_for_stock(db, stock.id)
        score_source = getattr(latest_score, "score_source", None)
        status = _report_status_from_display_tier(diagnostics.get("display_tier"))
        if score_source != REAL_SCORE_SOURCE or status in {REPORT_STATUS_DEMO, REPORT_STATUS_INSUFFICIENT, "data_quality_limited"}:
            report = _build_data_status_report_v2(db, stock, report_date, score_source)
            if not isinstance(report.content_json, dict):
                report.content_json = {}
            report.content_json["report_data_status"] = status
            report.content_json["score_source_used"] = score_source
            report.content_json["display_tier"] = diagnostics.get("display_tier")
        else:
            report = generate_stock_report(db, stock.id, report_date)
            if style:
                report.style = style
            report.stock_code = stock.symbol
            report.stock_name = stock.name
            report.market = stock.market
            if not isinstance(report.content_json, dict):
                report.content_json = {}
            report.content_json["report_data_status"] = status
            report.content_json["score_source_used"] = score_source
            report.content_json["display_tier"] = diagnostics.get("display_tier")
    else:
        raise HTTPException(status_code=400, detail="报告类型无效，请重新选择")

    report.user_id = user.id
    report = _persist_compliant_report(report, db)
    db.add(
        ReportEvent(
            user_id=user.id,
            report_id=report.id,
            stock_code=report.stock_code or stock_symbol,
            report_type=report.report_type,
            format="html",
            action="generate",
        )
    )
    db.commit()
    elapsed = int((time.time() - start_time) * 1000)
    log_api_call(db, user.id, user.username, "system", "/api/reports/generate", "POST", 200, elapsed)
    log_operation(db, user=user, action="report_generate", target_type="report", target_id=report.id, message=f"{report.report_type} {report.stock_code or ''}")
    status, source = _report_status_meta(report)
    return {
        "id": report.id,
        "report_id": report.id,
        "title": report.title,
        "type": report.report_type,
        "style": report.style,
        "stock_code": stock_symbol,
        "stock_name": stock_name,
        "market": market,
        "created_at": str(report.created_at) if report.created_at else None,
        "html_url": f"/reports/{report.id}",
        "pdf_url": f"/api/reports/{report.id}/pdf",
        "png_url": f"/api/reports/{report.id}/png",
        "png_supported": True,
        "report_data_status": status,
        "score_source_used": source,
    }


@router.post("/generate-style")
def generate_style_report_api(
    style: str = Query(..., description="style"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    from app.api.admin import log_api_call
    import time

    if style not in ("steady", "aggressive", "conservative"):
        raise HTTPException(status_code=400, detail="报告风格无效，请重新选择")
    allowed, msg = check_quota(db, user, "report")
    if not allowed:
        log_operation(db, user=user, action="report_generate", target_type="report", status="failed", message=msg)
        raise HTTPException(status_code=429, detail=msg)

    start_time = time.time()
    report = generate_style_report(db, date.today(), style)
    if not isinstance(report.content_json, dict):
        report.content_json = {}
    report.content_json.setdefault("report_data_status", REPORT_STATUS_REAL)
    report = _persist_compliant_report(report, db)
    elapsed = int((time.time() - start_time) * 1000)
    log_api_call(db, user.id, user.username, "system", "/api/reports/generate-style", "POST", 200, elapsed)
    log_operation(db, user=user, action="report_generate", target_type="report", target_id=report.id, message=f"STYLE {style}")
    return {"id": report.id, "title": report.title, "type": report.report_type, "style": report.style, "report_data_status": REPORT_STATUS_REAL}


@router.get("/{report_id}/pdf")
def download_report_pdf(report_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from app.api.admin import log_api_call
    from app.services.pdf_service import generate_pdf_bytes
    from fastapi.responses import Response
    import re as _re
    import time
    import urllib.parse

    allowed, msg = check_quota(db, user, "pdf")
    if not allowed:
        log_operation(db, user=user, action="report_pdf_download", target_type="report", target_id=report_id, status="failed", message=msg, request=request)
        raise HTTPException(status_code=429, detail=msg)

    report = _get_accessible_report(db, report_id, user)
    start_time = time.time()

    stock_symbol = ""
    stock_name = ""
    title = report.title or ""
    sym_match = _re.search(r"(\d{5,6})\s+(\S+)", title)
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
    db.add(
        ReportEvent(
            user_id=user.id,
            report_id=report.id,
            stock_code=report.stock_code,
            report_type=report.report_type,
            format="pdf",
            action="download",
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    db.commit()
    log_operation(db, user=user, action="report_pdf_download", target_type="report", target_id=report.id, message=f"report_id={report.id}", request=request)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_filename}'},
    )


@router.get("/{report_id}/png")
def download_report_png(report_id: int, request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    from fastapi.responses import Response
    from PIL import Image, ImageDraw, ImageFont
    import io
    import urllib.parse

    allowed, msg = check_quota(db, user, "png")
    if not allowed:
        log_operation(db, user=user, action="report_png_download", target_type="report", target_id=report_id, status="failed", message=msg, request=request)
        raise HTTPException(status_code=429, detail=msg)

    report = _get_accessible_report(db, report_id, user)
    status, _source = _report_status_meta(report)

    image = Image.new("RGB", (1200, 760), "#f6fafc")
    draw = ImageDraw.Draw(image)
    try:
        font_title = ImageFont.truetype("msyh.ttc", 42)
        font = ImageFont.truetype("msyh.ttc", 26)
        font_small = ImageFont.truetype("msyh.ttc", 22)
    except Exception:
        font_title = font = font_small = ImageFont.load_default()
    draw.rounded_rectangle((48, 48, 1152, 712), radius=26, fill="#ffffff", outline="#d7e5ee", width=2)
    draw.text((86, 86), (report.title or "研究报告")[:34], fill="#14324a", font=font_title)
    draw.text((86, 158), f"对象：{report.stock_code or '-'} {report.stock_name or ''} | {report.report_type} | {report.report_date}", fill="#486176", font=font)
    summary = (report.summary or "暂无摘要").replace("\n", " ")
    draw.text((86, 235), "核心摘要", fill="#0f766e", font=font)
    y = 286
    for i in range(0, min(len(summary), 180), 36):
        draw.text((106, y), summary[i:i + 36], fill="#1f2f3d", font=font_small)
        y += 40
    if status != "formal":
        draw.text((86, 560), "本摘要基于演示评分或数据不足状态生成，仅供研究辅助。", fill="#9f3a38", font=font_small)
    draw.text((86, 610), "主要风险：市场波动、数据滞后、模型假设偏差。", fill="#9f3a38", font=font_small)
    draw.text((86, 660), "仅用于研究与辅助分析，不构成投资建议。", fill="#66788a", font=font_small)
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    db.add(
        ReportEvent(
            user_id=user.id,
            report_id=report.id,
            stock_code=report.stock_code,
            report_type=report.report_type,
            format="png",
            action="download",
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    )
    db.commit()
    log_operation(db, user=user, action="report_png_download", target_type="report", target_id=report.id, message=f"report_id={report.id}", request=request)
    filename = f"{report.stock_code or report.report_type}_{report.stock_name or '报告'}_报告摘要_{report.report_date}.png"
    return Response(content=buf.getvalue(), media_type="image/png", headers={"Content-Disposition": f"attachment; filename*=UTF-8''{urllib.parse.quote(filename)}"})
