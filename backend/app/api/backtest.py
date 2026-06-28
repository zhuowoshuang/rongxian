"""Backtest APIs."""

from __future__ import annotations

import time
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import get_current_analyst
from app.db.session import get_db
from app.schemas.backtest import BacktestRequest, SimulateRequest
from app.services.backtest import get_backtest_metadata, run_backtest, simulate_portfolio

router = APIRouter(prefix="/api/backtest", tags=["回测"])


@router.get("/meta")
def get_backtest_meta(
    market: str = "A_SHARE",
    db: Session = Depends(get_db),
    user=Depends(get_current_analyst),
):
    return get_backtest_metadata(db, market)


@router.post("/run")
def run_backtest_api(req: BacktestRequest, db: Session = Depends(get_db), user=Depends(get_current_analyst)):
    from app.api.admin import check_user_quota, log_api_call

    allowed, msg = check_user_quota(db, user.id, "backtest")
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)

    meta = get_backtest_metadata(db, req.market)
    if meta["earliest_date"] and req.start_date < meta["earliest_date"]:
        raise HTTPException(status_code=400, detail=f"开始日期超出可回测范围，最早日期为 {meta['earliest_date']}")
    if meta["latest_date"] and req.end_date > meta["latest_date"]:
        raise HTTPException(status_code=400, detail=f"结束日期超出可回测范围，最晚日期为 {meta['latest_date']}")
    if date.fromisoformat(req.start_date) >= date.fromisoformat(req.end_date):
        raise HTTPException(status_code=400, detail="开始日期必须早于结束日期")

    start_time = time.time()
    try:
        result = run_backtest(
            db=db,
            strategy=req.strategy,
            market=req.market,
            start_date=req.start_date,
            end_date=req.end_date,
            rebalance=req.rebalance,
            initial_capital=req.initial_capital,
        )
        elapsed = int((time.time() - start_time) * 1000)
        status_code = 400 if result.get("error") else 200
        log_api_call(db, user.id, user.username, "system", "/api/backtest/run", "POST", status_code, elapsed, result.get("error"))
        if result.get("error"):
            result["meta"] = result.get("meta") or meta
        return result
    except Exception as exc:
        elapsed = int((time.time() - start_time) * 1000)
        log_api_call(db, user.id, user.username, "system", "/api/backtest/run", "POST", 500, elapsed, str(exc)[:500])
        raise


@router.post("/simulate")
def simulate_portfolio_api(req: SimulateRequest, db: Session = Depends(get_db), user=Depends(get_current_analyst)):
    from app.api.admin import check_user_quota, log_api_call

    allowed, msg = check_user_quota(db, user.id, "simulation")
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)

    allowed, msg = check_user_quota(db, user.id, "backtest")
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)

    start_time = time.time()
    holdings = [holding.model_dump() for holding in req.holdings]
    try:
        result = simulate_portfolio(db=db, holdings=holdings)
        elapsed = int((time.time() - start_time) * 1000)
        status_code = 400 if result.get("error") else 200
        log_api_call(db, user.id, user.username, "system", "/api/backtest/simulate", "POST", status_code, elapsed, result.get("error"))
        return result
    except Exception as exc:
        elapsed = int((time.time() - start_time) * 1000)
        log_api_call(db, user.id, user.username, "system", "/api/backtest/simulate", "POST", 500, elapsed, str(exc)[:500])
        raise
