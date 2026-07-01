import json
from datetime import date
from pathlib import Path

import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.stock import Stock
from app.models.technical_indicator import TechnicalIndicator
from app.services.scoring import (
    _latest_financial_for_stock,
    _previous_financial_for_stock,
    calculate_growth_score,
    calculate_quality_score,
    calculate_risk_score,
    calculate_trend_score,
    calculate_valuation_score,
)

COMMISSION_RATE = 0.00025
STAMP_DUTY_RATE = 0.0005
MIN_COMMISSION = 5.0
TRANSFER_FEE_RATE = 0.00001
SLIPPAGE_RATE = 0.001

_STRATEGY_DIR = Path(__file__).resolve().parents[1] / "strategies"
_STRATEGY_MAP = {
    "qingshu_1_short": "qingshu_1_short.json",
    "qingshu_2_mid": "qingshu_2_mid.json",
    "qingshu_3_mid_long": "qingshu_3_mid_long.json",
    "qingshu_4_long": "qingshu_4_long.json",
}


def load_strategy_config(strategy_id: str) -> dict:
    strategy_file = _STRATEGY_MAP.get(strategy_id)
    if not strategy_file:
        raise ValueError("未找到对应策略配置")
    with open(_STRATEGY_DIR / strategy_file, "r", encoding="utf-8") as handle:
        return json.load(handle)


def build_backtest_cache_key(user_id: int, stock_code: str, strategy_id: str, start_date: str, end_date: str, rebalance_frequency: str) -> str:
    return f"backtest:{user_id}:{stock_code}:{strategy_id}:{start_date}:{end_date}:{rebalance_frequency}"


def get_backtest_metadata(db: Session, market: str, stock_code: str | None = None) -> dict:
    stock_query = db.query(Stock.id).filter(Stock.market == market)
    if stock_code:
        stock_query = stock_query.filter(Stock.symbol == stock_code)
    stock_ids = [row[0] for row in stock_query.all()]
    if not stock_ids:
        return {
            "market": market,
            "earliest_date": None,
            "latest_date": None,
            "trade_day_count": 0,
            "sample_count": 0,
            "price_count": 0,
            "fees": {
                "commission_rate": COMMISSION_RATE,
                "stamp_duty_rate": STAMP_DUTY_RATE,
                "transfer_fee_rate": TRANSFER_FEE_RATE,
                "min_commission": MIN_COMMISSION,
                "slippage_rate": SLIPPAGE_RATE,
            },
            "assumptions": {
                "has_slippage": True,
                "has_commission": True,
                "handles_limit_lock": True,
                "handles_suspension": False,
                "benchmark": "selected_stock_buy_and_hold",
            },
        }

    earliest = db.query(func.min(DailyPrice.trade_date)).filter(DailyPrice.stock_id.in_(stock_ids)).scalar()
    latest = db.query(func.max(DailyPrice.trade_date)).filter(DailyPrice.stock_id.in_(stock_ids)).scalar()
    trade_day_count = db.query(func.count(func.distinct(DailyPrice.trade_date))).filter(DailyPrice.stock_id.in_(stock_ids)).scalar() or 0
    price_count = db.query(DailyPrice).filter(DailyPrice.stock_id.in_(stock_ids)).count()
    return {
        "market": market,
        "earliest_date": str(earliest) if earliest else None,
        "latest_date": str(latest) if latest else None,
        "trade_day_count": trade_day_count,
        "sample_count": len(stock_ids),
        "price_count": price_count,
        "fees": {
            "commission_rate": COMMISSION_RATE,
            "stamp_duty_rate": STAMP_DUTY_RATE,
            "transfer_fee_rate": TRANSFER_FEE_RATE,
            "min_commission": MIN_COMMISSION,
            "slippage_rate": SLIPPAGE_RATE,
        },
        "assumptions": {
            "has_slippage": True,
            "has_commission": True,
            "handles_limit_lock": True,
            "handles_suspension": False,
            "benchmark": "selected_stock_buy_and_hold" if stock_code else "market_proxy",
        },
    }


def _get_stock_context(db: Session, stock_code: str, market: str):
    stock = db.query(Stock).filter(Stock.symbol == stock_code, Stock.market == market).first()
    if not stock:
        raise ValueError("未找到该股票")
    return stock


def _normalize_strategy_config(raw: dict, strategy_id: str) -> dict:
    defaults = raw.get("default_params", {})
    horizon = raw.get("horizon", "")
    if strategy_id == "qingshu_1_short":
        weights = {"quality": 0.1, "valuation": 0.1, "growth": 0.1, "trend": 0.45, "risk": 0.25}
        thresholds = {"enter": 56, "reduce": 46}
    elif strategy_id == "qingshu_2_mid":
        weights = {"quality": 0.2, "valuation": 0.25, "growth": 0.15, "trend": 0.25, "risk": 0.15}
        thresholds = {"enter": 58, "reduce": 48}
    elif strategy_id == "qingshu_3_mid_long":
        weights = {"quality": 0.28, "valuation": 0.14, "growth": 0.24, "trend": 0.18, "risk": 0.16}
        thresholds = {"enter": 60, "reduce": 50}
    else:
        weights = {"quality": 0.3, "valuation": 0.2, "growth": 0.15, "trend": 0.1, "risk": 0.25}
        thresholds = {"enter": 62, "reduce": 54}
    return {
        "strategy_id": strategy_id,
        "name": raw.get("name", strategy_id),
        "horizon": horizon,
        "description": raw.get("description", ""),
        "lookback_days": int(defaults.get("lookback_days", 60)),
        "rebalance": defaults.get("rebalance", "monthly"),
        "weights": weights,
        "thresholds": thresholds,
        "weekly_volatility_enabled": True,
        "weekly_volatility_threshold": 0.15,
        "weekly_volatility_direction": "positive_pending_confirmation",
        "weekly_volatility_method": "pending_trader_definition",
        "risk_volatility_method": "bollinger_bandwidth_with_candidate_fields",
        "volatility_score_version": "v1_pending_trader_confirmation",
    }


def _score_selected_stock(db: Session, stock_id: int, ref_date: date, strategy_cfg: dict) -> dict | None:
    price = db.query(DailyPrice).filter(DailyPrice.stock_id == stock_id, DailyPrice.trade_date <= ref_date).order_by(DailyPrice.trade_date.desc()).first()
    financial = _latest_financial_for_stock(db, stock_id, ref_date)
    prev_financial = _previous_financial_for_stock(db, stock_id, financial)
    tech = db.query(TechnicalIndicator).filter(TechnicalIndicator.stock_id == stock_id, TechnicalIndicator.trade_date <= ref_date).order_by(TechnicalIndicator.trade_date.desc()).first()
    if not price or not financial:
        return None

    quality, _ = calculate_quality_score(financial, prev_financial)
    valuation, _ = calculate_valuation_score(price, financial)
    growth, _ = calculate_growth_score(financial)
    trend, trend_details = calculate_trend_score(price, tech)
    risk, _ = calculate_risk_score(financial, price, tech)

    weighted = (
        quality * strategy_cfg["weights"]["quality"]
        + valuation * strategy_cfg["weights"]["valuation"]
        + growth * strategy_cfg["weights"]["growth"]
        + trend * strategy_cfg["weights"]["trend"]
        + risk * strategy_cfg["weights"]["risk"]
    )
    return {
        "quality": quality,
        "valuation": valuation,
        "growth": growth,
        "trend": trend,
        "risk": risk,
        "weighted_score": round(weighted * 4, 2),
        "trend_details": trend_details,
    }


def _assess_backtest_support(db: Session, stock_id: int, start: date, end: date, price_count: int) -> dict:
    financial_before_start = (
        db.query(FinancialMetric.id)
        .filter(FinancialMetric.stock_id == stock_id, FinancialMetric.report_date <= start)
        .first()
        is not None
    )
    technical_before_start = (
        db.query(TechnicalIndicator.id)
        .filter(TechnicalIndicator.stock_id == stock_id, TechnicalIndicator.trade_date <= start)
        .first()
        is not None
    )
    basic_available = price_count >= 5
    factor_available = basic_available and financial_before_start and technical_before_start
    return {
        "basic_available": basic_available,
        "factor_available": factor_available,
        "financial_before_start": financial_before_start,
        "technical_before_start": technical_before_start,
        "price_count": price_count,
        "recommended_mode": "factor" if factor_available else "basic" if basic_available else "unavailable",
        "factor_reason": None
        if factor_available
        else "选定日期前缺少可用财务或技术数据，暂不支持完整因子回测，但仍可运行基础行情回测。",
        "basic_reason": None if basic_available else "选定日期范围内行情样本不足，建议扩大日期范围。",
    }


def _build_basic_backtest_result(stock: Stock, prices: list[DailyPrice], initial_capital: float, support: dict, strategy_cfg: dict, rebalance: str) -> dict:
    first_close = prices[0].close
    last_close = prices[-1].close
    shares = initial_capital / first_close if first_close else 0
    equity_curve = []
    monthly_returns = []
    prev_equity = initial_capital

    for index, price in enumerate(prices):
        equity = round(shares * price.close, 2) if shares else initial_capital
        equity_curve.append({"date": price.trade_date.isoformat(), "equity": equity, "benchmark": equity})
        if index > 0:
            month = price.trade_date.strftime("%Y-%m")
            daily_return = (equity - prev_equity) / prev_equity if prev_equity else 0
            if not monthly_returns or monthly_returns[-1]["month"] != month:
                monthly_returns.append({"month": month, "strategy_return": round(daily_return * 100, 2), "benchmark_return": round(daily_return * 100, 2), "excess_return": 0})
            else:
                current_strategy = monthly_returns[-1]["strategy_return"] / 100
                monthly_returns[-1]["strategy_return"] = round((1 + current_strategy) * (1 + daily_return) * 100 - 100, 2)
                monthly_returns[-1]["benchmark_return"] = monthly_returns[-1]["strategy_return"]
            monthly_returns[-1]["excess_return"] = 0
        prev_equity = equity

    total_return = (equity_curve[-1]["equity"] - initial_capital) / initial_capital if initial_capital else 0
    period_days = max((prices[-1].trade_date - prices[0].trade_date).days, 1)
    annual_return = (1 + total_return) ** (365 / period_days) - 1 if total_return > -1 else -1
    return {
        "user_visible_message": "研究测算 / 非实盘 / 不代表未来收益",
        "stock_code": stock.symbol,
        "stock_name": stock.name,
        "market": stock.market,
        "strategy_id": strategy_cfg["strategy_id"],
        "strategy_name": f"{strategy_cfg['name']}（基础行情回测）",
        "rebalance_frequency": rebalance,
        "total_return": round(total_return * 100, 2),
        "annual_return": round(annual_return * 100, 2),
        "benchmark_return": round(total_return * 100, 2),
        "excess_return": 0.0,
        "max_drawdown": round(_max_drawdown([point["equity"] for point in equity_curve]) * 100, 2),
        "sharpe_ratio": 0.0,
        "win_rate": 0.0,
        "total_trades": 1,
        "equity_curve": equity_curve,
        "monthly_returns": monthly_returns,
        "trade_log": [
            {
                "date": prices[0].trade_date.isoformat(),
                "action": "BUY_AND_HOLD",
                "symbol": stock.symbol,
                "name": stock.name,
                "price": round(first_close, 2),
                "shares": round(shares, 2),
                "strategy_id": strategy_cfg["strategy_id"],
                "strategy_name": f"{strategy_cfg['name']}（基础行情回测）",
            }
        ],
        "support": support,
        "mode": "basic",
    }


def _max_drawdown(values: list[float]) -> float:
    peak = values[0]
    worst = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, (peak - value) / peak)
    return worst


def run_backtest(db: Session, strategy: str, market: str, start_date: str, end_date: str, rebalance: str = "monthly", initial_capital: float = 1000000.0, stock_code: str | None = None) -> dict:
    if not stock_code:
        return {"error": "请先选择具体股票后再运行回测"}

    stock = _get_stock_context(db, stock_code, market)
    raw_strategy = load_strategy_config(strategy)
    strategy_cfg = _normalize_strategy_config(raw_strategy, strategy)

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    prices = (
        db.query(DailyPrice)
        .filter(DailyPrice.stock_id == stock.id, DailyPrice.trade_date >= start, DailyPrice.trade_date <= end)
        .order_by(DailyPrice.trade_date.asc())
        .all()
    )
    if not prices:
        return {"error": "该股票在所选日期范围内暂无可用行情数据。"}
    support = _assess_backtest_support(db, stock.id, start, end, len(prices))
    if not support["factor_available"] and support["basic_available"]:
        return _build_basic_backtest_result(stock, prices, initial_capital, support, strategy_cfg, rebalance)
    if len(prices) < 10:
        return {"error": "该股票在选定日期范围内缺少财务或评分数据。建议扩大日期范围或选择完整链路样本（如 002415 海康威视 / 600519 贵州茅台 / 000776 广发证券）。"}

    trade_dates = [item.trade_date for item in prices]
    price_map = {item.trade_date: item for item in prices}
    rebalance_days = 21 if rebalance == "monthly" else 63

    cash = initial_capital
    shares = 0
    entry_cost = 0.0
    trade_log = []
    equity_curve = []
    monthly_returns = []
    last_rebalance_index = -rebalance_days
    benchmark_start_close = prices[0].close
    prev_equity = initial_capital
    prev_benchmark = initial_capital
    strategy_snapshots = []

    for index, trade_date in enumerate(trade_dates):
        price = price_map[trade_date]
        current_equity = cash + shares * price.close
        benchmark_equity = initial_capital * (price.close / benchmark_start_close) if benchmark_start_close else initial_capital

        should_rebalance = index == 0 or index - last_rebalance_index >= rebalance_days
        if should_rebalance:
            last_rebalance_index = index
            score_bundle = _score_selected_stock(db, stock.id, trade_date, strategy_cfg)
            if score_bundle is None and support["basic_available"]:
                return _build_basic_backtest_result(stock, prices, initial_capital, support, strategy_cfg, rebalance)
            if score_bundle is None:
                return {"error": "该股票在选定日期范围内缺少财务或评分数据。建议扩大日期范围或选择完整链路样本（如 002415 海康威视 / 600519 贵州茅台 / 000776 广发证券）。"}
            weighted_score = score_bundle["weighted_score"]
            signal = "hold"
            if weighted_score >= strategy_cfg["thresholds"]["enter"] and shares == 0:
                signal = "buy"
            elif weighted_score <= strategy_cfg["thresholds"]["reduce"] and shares > 0:
                signal = "sell"

            strategy_snapshots.append(
                {
                    "date": trade_date.isoformat(),
                    "weighted_score": weighted_score,
                    "quality": score_bundle["quality"],
                    "valuation": score_bundle["valuation"],
                    "growth": score_bundle["growth"],
                    "trend": score_bundle["trend"],
                    "risk": score_bundle["risk"],
                    "signal": signal,
                }
            )

            execution_price = price.close * (1 + SLIPPAGE_RATE) if signal == "buy" else price.close * (1 - SLIPPAGE_RATE)
            if signal == "buy":
                buyable = int(cash / max(execution_price, 0.01) / 100) * 100
                if buyable > 0:
                    buy_amount = buyable * execution_price
                    commission = max(buy_amount * COMMISSION_RATE, MIN_COMMISSION)
                    transfer_fee = buy_amount * TRANSFER_FEE_RATE
                    total_needed = buy_amount + commission + transfer_fee
                    if cash >= total_needed:
                        cash -= total_needed
                        shares += buyable
                        entry_cost = execution_price
                        trade_log.append(
                            {
                                "date": trade_date.isoformat(),
                                "action": "BUY",
                                "symbol": stock.symbol,
                                "name": stock.name,
                                "price": round(execution_price, 2),
                                "shares": buyable,
                                "strategy_id": strategy_cfg["strategy_id"],
                                "strategy_name": strategy_cfg["name"],
                                "weighted_score": weighted_score,
                            }
                        )
            elif signal == "sell" and shares > 0:
                sell_amount = shares * execution_price
                commission = max(sell_amount * COMMISSION_RATE, MIN_COMMISSION)
                stamp_duty = sell_amount * STAMP_DUTY_RATE
                transfer_fee = sell_amount * TRANSFER_FEE_RATE
                cash += sell_amount - commission - stamp_duty - transfer_fee
                pnl = (execution_price - entry_cost) * shares
                trade_log.append(
                    {
                        "date": trade_date.isoformat(),
                        "action": "SELL",
                        "symbol": stock.symbol,
                        "name": stock.name,
                        "price": round(execution_price, 2),
                        "shares": shares,
                        "strategy_id": strategy_cfg["strategy_id"],
                        "strategy_name": strategy_cfg["name"],
                        "weighted_score": weighted_score,
                        "pnl": round(pnl, 2),
                    }
                )
                shares = 0
                entry_cost = 0.0

            current_equity = cash + shares * price.close

        equity_curve.append(
            {
                "date": trade_date.isoformat(),
                "equity": round(current_equity, 2),
                "benchmark": round(benchmark_equity, 2),
            }
        )

        if index > 0:
            month = trade_date.strftime("%Y-%m")
            daily_return = (current_equity - prev_equity) / prev_equity if prev_equity else 0
            daily_benchmark = (benchmark_equity - prev_benchmark) / prev_benchmark if prev_benchmark else 0
            if not monthly_returns or monthly_returns[-1]["month"] != month:
                if monthly_returns:
                    monthly_returns[-1]["excess_return"] = round(monthly_returns[-1]["strategy_return"] - monthly_returns[-1]["benchmark_return"], 2)
                monthly_returns.append({"month": month, "strategy_return": round(daily_return * 100, 2), "benchmark_return": round(daily_benchmark * 100, 2), "excess_return": 0})
            else:
                current_strategy = monthly_returns[-1]["strategy_return"] / 100
                current_benchmark = monthly_returns[-1]["benchmark_return"] / 100
                monthly_returns[-1]["strategy_return"] = round((1 + current_strategy) * (1 + daily_return) * 100 - 100, 2)
                monthly_returns[-1]["benchmark_return"] = round((1 + current_benchmark) * (1 + daily_benchmark) * 100 - 100, 2)
        prev_equity = current_equity
        prev_benchmark = benchmark_equity

    if monthly_returns:
        monthly_returns[-1]["excess_return"] = round(monthly_returns[-1]["strategy_return"] - monthly_returns[-1]["benchmark_return"], 2)

    final_equity = equity_curve[-1]["equity"]
    final_benchmark = equity_curve[-1]["benchmark"]
    total_return = (final_equity - initial_capital) / initial_capital
    benchmark_return = (final_benchmark - initial_capital) / initial_capital
    period_days = max((trade_dates[-1] - trade_dates[0]).days, 1)
    annual_return = (1 + total_return) ** (365 / period_days) - 1
    equity_values = [point["equity"] for point in equity_curve]
    daily_returns = [(equity_values[i] - equity_values[i - 1]) / equity_values[i - 1] for i in range(1, len(equity_values)) if equity_values[i - 1] > 0]
    sharpe = (np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252)) if daily_returns and np.std(daily_returns) > 0 else 0.0
    sell_trades = [item for item in trade_log if item["action"] == "SELL"]
    win_rate = len([item for item in sell_trades if item.get("pnl", 0) > 0]) / len(sell_trades) if sell_trades else 0.0

    return {
        "user_visible_message": "研究测算 / 非实盘 / 不代表未来收益",
        "stock_code": stock.symbol,
        "stock_name": stock.name,
        "market": stock.market,
        "strategy_id": strategy_cfg["strategy_id"],
        "strategy_name": strategy_cfg["name"],
        "rebalance_frequency": rebalance,
        "total_return": round(total_return * 100, 2),
        "annual_return": round(annual_return * 100, 2),
        "benchmark_return": round(benchmark_return * 100, 2),
        "excess_return": round((total_return - benchmark_return) * 100, 2),
        "max_drawdown": round(_max_drawdown(equity_values) * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "win_rate": round(win_rate * 100, 2),
        "total_trades": len(trade_log),
        "metrics": {
            "total_return": round(total_return * 100, 2),
            "annual_return": round(annual_return * 100, 2),
            "benchmark_return": round(benchmark_return * 100, 2),
            "max_drawdown": round(_max_drawdown(equity_values) * 100, 2),
            "sharpe_ratio": round(sharpe, 2),
            "win_rate": round(win_rate * 100, 2),
        },
        "equity_curve": equity_curve,
        "benchmark_curve": [{"date": point["date"], "value": point["benchmark"]} for point in equity_curve],
        "monthly_returns": monthly_returns,
        "trade_log": trade_log,
        "strategy_snapshot": strategy_snapshots,
        "strategy_config": strategy_cfg,
        "cache_key": None,
    }


def simulate_portfolio(db: Session, holdings: list[dict]) -> dict:
    if not holdings:
        return {"error": "持仓列表为空"}

    positions = []
    total_invested = 0.0
    earliest_date = None

    for holding in holdings:
        stock = db.query(Stock).filter(Stock.symbol == holding["symbol"]).first()
        if not stock:
            return {"error": f"未找到股票 {holding['symbol']}"}
        buy_date = date.fromisoformat(holding["buy_date"])
        earliest_date = buy_date if earliest_date is None else min(earliest_date, buy_date)
        buy_price_row = db.query(DailyPrice).filter(DailyPrice.stock_id == stock.id, DailyPrice.trade_date >= buy_date).order_by(DailyPrice.trade_date.asc()).first()
        if not buy_price_row:
            return {"error": f"{holding['symbol']} 在 {holding['buy_date']} 附近无价格数据"}
        cost = buy_price_row.close * holding["shares"]
        total_invested += cost
        positions.append(
            {
                "symbol": stock.symbol,
                "name": stock.name,
                "stock_id": stock.id,
                "buy_date": str(buy_price_row.trade_date),
                "buy_price": round(buy_price_row.close, 2),
                "shares": holding["shares"],
                "cost": round(cost, 2),
            }
        )

    prices = (
        db.query(DailyPrice)
        .filter(DailyPrice.stock_id.in_([item["stock_id"] for item in positions]), DailyPrice.trade_date >= earliest_date)
        .order_by(DailyPrice.trade_date.asc())
        .all()
    )
    date_map = {}
    for price in prices:
        date_map.setdefault(price.trade_date, {})[price.stock_id] = price
    trade_dates = sorted(date_map.keys())
    equity_curve = []
    monthly_returns = []
    prev_equity = total_invested

    for trade_date in trade_dates:
        current_value = 0.0
        for position in positions:
            current_price = date_map.get(trade_date, {}).get(position["stock_id"])
            if current_price and trade_date >= date.fromisoformat(position["buy_date"]):
                current_value += current_price.close * position["shares"]
            else:
                current_value += position["cost"]
        equity_curve.append({"date": trade_date.isoformat(), "equity": round(current_value, 2), "benchmark": round(total_invested, 2)})
        if len(equity_curve) > 1:
            month = trade_date.strftime("%Y-%m")
            daily_return = (current_value - prev_equity) / prev_equity if prev_equity else 0
            if not monthly_returns or monthly_returns[-1]["month"] != month:
                monthly_returns.append({"month": month, "strategy_return": round(daily_return * 100, 2), "benchmark_return": 0, "excess_return": round(daily_return * 100, 2)})
            else:
                current_strategy = monthly_returns[-1]["strategy_return"] / 100
                monthly_returns[-1]["strategy_return"] = round((1 + current_strategy) * (1 + daily_return) * 100 - 100, 2)
                monthly_returns[-1]["excess_return"] = monthly_returns[-1]["strategy_return"]
        prev_equity = current_value

    current_value = equity_curve[-1]["equity"] if equity_curve else total_invested
    total_return = (current_value - total_invested) / total_invested * 100 if total_invested > 0 else 0
    return {
        "total_invested": round(total_invested, 2),
        "current_value": round(current_value, 2),
        "total_return": round(total_return, 2),
        "total_pnl": round(current_value - total_invested, 2),
        "benchmark_return": 0,
        "excess_return": round(total_return, 2),
        "holdings": positions,
        "equity_curve": equity_curve,
        "monthly_returns": monthly_returns,
    }
