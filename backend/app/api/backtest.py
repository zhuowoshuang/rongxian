"""Backtest APIs."""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import time

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_member_user
from app.db.session import get_db
from app.models.report import BacktestTask
from app.models.stock import Stock
from app.schemas.backtest import BacktestRequest, SimulateRequest
from app.services.audit import log_operation
from app.services.backtest import get_backtest_metadata, run_backtest, simulate_portfolio
from app.services.quota import check_quota

router = APIRouter(prefix="/api/backtest", tags=["回测"])


@router.get("/strategies")
def list_strategies(user=Depends(get_member_user)):
    base = Path(__file__).resolve().parents[1] / "strategies"
    items = []
    for name in ["qingshu_1_short.json", "qingshu_2_mid.json", "qingshu_3_mid_long.json", "qingshu_4_long.json"]:
        with open(base / name, "r", encoding="utf-8") as f:
            item = json.load(f)
        item["key"] = name.replace(".json", "")
        items.append(item)
    return {"items": items}


@router.get("/meta")
def get_backtest_meta(market: str = "A_SHARE", db: Session = Depends(get_db), user=Depends(get_member_user)):
    return get_backtest_metadata(db, market)


@router.post("/run")
def run_backtest_api(req: BacktestRequest, db: Session = Depends(get_db), user=Depends(get_member_user)):
    from app.api.admin import log_api_call

    allowed, msg = check_quota(db, user, "backtest")
    if not allowed:
        log_operation(db, user=user, action="backtest_run", target_type="backtest", status="failed", message=msg)
        raise HTTPException(status_code=429, detail=msg)

    meta = get_backtest_metadata(db, req.market)
    if meta["earliest_date"] and req.start_date < meta["earliest_date"]:
        msg = f"开始日期超出可回测范围，最早日期为 {meta['earliest_date']}"
        log_operation(db, user=user, action="backtest_run", target_type="backtest", status="failed", message=msg)
        raise HTTPException(status_code=400, detail=msg)
    if meta["latest_date"] and req.end_date > meta["latest_date"]:
        msg = f"结束日期超出可回测范围，最晚日期为 {meta['latest_date']}"
        log_operation(db, user=user, action="backtest_run", target_type="backtest", status="failed", message=msg)
        raise HTTPException(status_code=400, detail=msg)
    if date.fromisoformat(req.start_date) >= date.fromisoformat(req.end_date):
        msg = "开始日期必须早于结束日期"
        log_operation(db, user=user, action="backtest_run", target_type="backtest", status="failed", message=msg)
        raise HTTPException(status_code=400, detail=msg)

    start_time = time.time()
    try:
        result = run_backtest(
            db=db,
            strategy=req.resolved_strategy_id,
            market=req.market,
            start_date=req.start_date,
            end_date=req.end_date,
            rebalance=req.resolved_rebalance_frequency,
            initial_capital=req.initial_capital,
            stock_code=req.resolved_stock_code,
        )
        elapsed = int((time.time() - start_time) * 1000)
        status_code = 400 if result.get("error") else 200
        log_api_call(db, user.id, user.username, "system", "/api/backtest/run", "POST", status_code, elapsed, result.get("error"))

        symbol = req.resolved_stock_code
        stock = db.query(Stock).filter(Stock.symbol == symbol).first() if symbol else None
        task = BacktestTask(
            user_id=user.id,
            stock_code=symbol,
            stock_name=req.stock_name or (stock.name if stock else None),
            market=req.market,
            strategy=req.resolved_strategy_id,
            strategy_name=result.get("strategy_name"),
            rebalance_frequency=req.resolved_rebalance_frequency,
            start_date=req.start_date,
            end_date=req.end_date,
            status="failed" if result.get("error") else "success",
            error_message=result.get("error"),
            result_json=json.dumps(result, ensure_ascii=False),
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        log_operation(db, user=user, action="backtest_run", target_type="backtest", target_id=task.id, status="failed" if result.get("error") else "success", message=result.get("error") or f"{req.strategy} {symbol or req.market}")
        if result.get("error"):
            result["meta"] = result.get("meta") or meta
        return result
    except Exception as exc:
        elapsed = int((time.time() - start_time) * 1000)
        log_api_call(db, user.id, user.username, "system", "/api/backtest/run", "POST", 500, elapsed, str(exc)[:500])
        log_operation(db, user=user, action="backtest_run", target_type="backtest", status="failed", message="回测执行异常")
        raise


@router.post("/simulate")
def simulate_portfolio_api(req: SimulateRequest, db: Session = Depends(get_db), user=Depends(get_member_user)):
    from app.api.admin import log_api_call

    allowed, msg = check_quota(db, user, "backtest")
    if not allowed:
        log_operation(db, user=user, action="backtest_run", target_type="simulation", status="failed", message=msg)
        raise HTTPException(status_code=429, detail=msg)

    start_time = time.time()
    holdings = [holding.model_dump() for holding in req.holdings]
    try:
        result = simulate_portfolio(db=db, holdings=holdings)
        elapsed = int((time.time() - start_time) * 1000)
        status_code = 400 if result.get("error") else 200
        log_api_call(db, user.id, user.username, "system", "/api/backtest/simulate", "POST", status_code, elapsed, result.get("error"))
        log_operation(db, user=user, action="backtest_run", target_type="simulation", status="failed" if result.get("error") else "success", message=result.get("error") or "portfolio simulation")
        return result
    except Exception as exc:
        elapsed = int((time.time() - start_time) * 1000)
        log_api_call(db, user.id, user.username, "system", "/api/backtest/simulate", "POST", 500, elapsed, str(exc)[:500])
        log_operation(db, user=user, action="backtest_run", target_type="simulation", status="failed", message="组合测算执行异常")
        raise
