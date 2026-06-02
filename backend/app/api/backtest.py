"""回测中心 API"""
import time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.backtest import BacktestRequest, SimulateRequest
from app.services.backtest import run_backtest, simulate_portfolio
from app.api.auth import get_current_analyst

router = APIRouter(prefix="/api/backtest", tags=["回测"])


@router.post("/run")
def run_backtest_api(req: BacktestRequest, db: Session = Depends(get_db), user=Depends(get_current_analyst)):
    """
    运行回测
    请求体：strategy, market, start_date, end_date, rebalance, initial_capital
    """
    from app.api.admin import check_user_quota, log_api_call

    allowed, msg = check_user_quota(db, user.id, "backtest")
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)

    start_time = time.time()
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
    log_api_call(db, user.id, user.username, "system", "/api/backtest/run", "POST", 200, elapsed)

    return result


@router.post("/simulate")
def simulate_portfolio_api(req: SimulateRequest, db: Session = Depends(get_db), user=Depends(get_current_analyst)):
    """
    模拟买入回测
    请求体：holdings - [{symbol, buy_date, shares}]
    """
    from app.api.admin import check_user_quota, log_api_call

    allowed, msg = check_user_quota(db, user.id, "simulation")
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)

    allowed, msg = check_user_quota(db, user.id, "backtest")
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)

    holdings = [h.model_dump() for h in req.holdings]
    start_time = time.time()
    result = simulate_portfolio(db=db, holdings=holdings)
    elapsed = int((time.time() - start_time) * 1000)
    log_api_call(db, user.id, user.username, "system", "/api/backtest/simulate", "POST", 200, elapsed)

    return result
