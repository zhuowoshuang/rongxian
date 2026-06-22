"""
回测服务
基于数据库中的真实历史行情数据模拟策略表现
"""
import numpy as np
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, func

from app.models.stock import Stock

# 交易成本参数
COMMISSION_RATE = 0.00025  # 佣金费率 0.025%
STAMP_DUTY_RATE = 0.0005   # 印花税费率 0.05%（仅卖出）
MIN_COMMISSION = 5.0        # 最低佣金 5 元
TRANSFER_FEE_RATE = 0.00001  # 过户费率 0.001%（沪市）
SLIPPAGE_RATE = 0.001       # 滑点 0.1%（买入加价、卖出减价）


def _is_limit_locked(current_close: float, prev_close: float, symbol: str = "") -> bool:
    """
    判断是否涨跌停（A 股主板 ±10%，创业板/科创板 ±20%）
    涨跌停时无法成交
    """
    if not prev_close or prev_close <= 0:
        return False
    change_pct = (current_close - prev_close) / prev_close
    # 创业板 (300xxx) 和科创板 (688xxx) 涨跌幅限制 ±20%
    if symbol.startswith(("300", "301", "688")):
        return abs(change_pct) >= 0.198  # 留 0.2% 容差
    # 主板 ±10%
    return abs(change_pct) >= 0.098  # 留 0.2% 容差
from app.models.daily_price import DailyPrice
from app.models.stock_score import StockScore
from app.models.financial_metric import FinancialMetric


def run_backtest(
    db: Session,
    strategy: str,
    market: str,
    start_date: str,
    end_date: str,
    rebalance: str = "monthly",
    initial_capital: float = 1000000.0,
) -> dict:
    """
    基于真实历史数据运行回测
    策略：按评分选股，定期调仓，用真实价格计算收益
    """
    # 使用历史状态表消除生存偏差：包含回测期间有数据的所有股票
    from app.models.stock_status_history import StockStatusHistory
    # 获取回测期间有行情数据的股票（含已退市）
    stock_ids_with_prices = db.query(DailyPrice.stock_id).filter(
        DailyPrice.trade_date >= date.fromisoformat(start_date),
        DailyPrice.trade_date <= date.fromisoformat(end_date),
    ).distinct().subquery()
    stocks = db.query(Stock).filter(
        Stock.market == market,
        Stock.id.in_(stock_ids_with_prices),
    ).all()
    if not stocks:
        return {"error": "未找到该市场的股票"}

    stock_ids = [s.id for s in stocks]
    stock_map = {s.id: s for s in stocks}

    # 获取所有交易日
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)

    prices = (
        db.query(DailyPrice)
        .filter(
            DailyPrice.stock_id.in_(stock_ids),
            DailyPrice.trade_date >= start,
            DailyPrice.trade_date <= end,
        )
        .order_by(DailyPrice.trade_date)
        .all()
    )

    if not prices:
        return {"error": "该时间段内无历史数据，请先运行 seed 脚本导入数据"}

    # 按日期分组
    date_map: dict[date, dict[int, DailyPrice]] = {}
    for p in prices:
        if p.trade_date not in date_map:
            date_map[p.trade_date] = {}
        date_map[p.trade_date][p.stock_id] = p

    trade_dates = sorted(date_map.keys())
    if len(trade_dates) < 5:
        return {"error": f"历史数据不足（仅 {len(trade_dates)} 个交易日），无法回测"}

    # 预加载所有评分数据，按 stock_id 和 score_date 索引（消除前瞻偏差）
    all_score_records = (
        db.query(StockScore)
        .filter(StockScore.stock_id.in_(stock_ids))
        .order_by(StockScore.score_date)
        .all()
    )
    scores_by_stock: dict[int, list] = {}
    for sc in all_score_records:
        scores_by_stock.setdefault(sc.stock_id, []).append((sc.score_date, sc.total_score))

    def _get_score_at_date(sid: int, ref_date: date) -> float:
        """获取某只股票在 ref_date 当天或之前最近的评分（消除前瞻偏差）"""
        records = scores_by_stock.get(sid, [])
        best = None
        for score_date, total_score in records:
            if score_date <= ref_date:
                best = total_score
            else:
                break
        return best if best is not None else 50.0

    # 确定调仓频率
    if rebalance == "quarterly":
        rebalance_days = 63  # ~3 months
    else:
        rebalance_days = 21  # ~1 month

    # 初始化回测
    equity = initial_capital
    cash = initial_capital
    positions: dict[int, dict] = {}  # stock_id -> {shares, cost_price}
    equity_curve = []
    monthly_returns = []
    trade_log = []

    # 基准：等权持有所有股票
    benchmark_start_prices = {}
    first_date = trade_dates[0]
    for sid in stock_ids:
        if sid in date_map.get(first_date, {}):
            benchmark_start_prices[sid] = date_map[first_date][sid].close

    last_rebalance_idx = 0
    prev_equity = initial_capital
    prev_benchmark = initial_capital

    for i, td in enumerate(trade_dates):
        day_prices = date_map.get(td, {})

        # 计算当前持仓市值
        portfolio_value = cash
        for sid, pos in positions.items():
            if sid in day_prices:
                portfolio_value += pos["shares"] * day_prices[sid].close
            else:
                portfolio_value += pos["shares"] * pos["cost_price"]

        # 计算基准市值（等权）
        benchmark_value = 0
        benchmark_count = 0
        for sid, start_price in benchmark_start_prices.items():
            if sid in day_prices:
                ratio = day_prices[sid].close / start_price
                benchmark_value += (initial_capital / len(benchmark_start_prices)) * ratio
                benchmark_count += 1
        if benchmark_count == 0:
            benchmark_value = initial_capital

        equity_curve.append({
            "date": td.isoformat(),
            "equity": round(portfolio_value, 2),
            "benchmark": round(benchmark_value, 2),
        })

        # 判断是否需要调仓
        if i - last_rebalance_idx >= rebalance_days or i == 0:
            last_rebalance_idx = i

            # 按评分排序，选前 N 只（使用回测时点的评分，消除前瞻偏差）
            scored = [(sid, _get_score_at_date(sid, td)) for sid in stock_ids if sid in day_prices]
            scored.sort(key=lambda x: x[1], reverse=True)

            # 选评分 >= 65 的股票（买入/加仓级别）
            target_stocks = [(sid, sc) for sid, sc in scored if sc >= 65]
            if not target_stocks:
                target_stocks = scored[:5]  # 至少保留 5 只

            # 卖出不在目标列表中的持仓
            to_sell = [sid for sid in positions if sid not in {s[0] for s in target_stocks}]
            for sid in to_sell:
                if sid in day_prices:
                    sell_price = day_prices[sid].close * (1 - SLIPPAGE_RATE)  # 卖出滑点减价
                    # 涨跌停检查：跌停时无法卖出
                    prev_p = day_prices[sid].pre_close
                    symbol = stock_map[sid].symbol if sid in stock_map else ""
                    if prev_p and _is_limit_locked(sell_price, prev_p, symbol) and sell_price < prev_p:
                        continue  # 跌停，跳过卖出
                    shares = positions[sid]["shares"]
                    proceeds = shares * sell_price
                    # 计算交易成本（佣金 + 印花税 + 过户费）
                    commission = max(proceeds * COMMISSION_RATE, MIN_COMMISSION)
                    stamp_duty = proceeds * STAMP_DUTY_RATE
                    transfer_fee = proceeds * TRANSFER_FEE_RATE
                    total_cost = commission + stamp_duty + transfer_fee
                    net_proceeds = proceeds - total_cost
                    buy_cost = shares * positions[sid]["cost_price"]
                    pnl = net_proceeds - buy_cost
                    cash += net_proceeds
                    trade_log.append({
                        "date": td.isoformat(),
                        "symbol": stock_map[sid].symbol,
                        "name": stock_map[sid].name,
                        "action": "SELL",
                        "price": round(sell_price, 2),
                        "shares": shares,
                        "pnl": round(pnl, 2),
                        "commission": round(commission, 2),
                        "stamp_duty": round(stamp_duty, 2),
                    })
                    del positions[sid]

            # 计算可用资金分配
            total_value = cash + sum(
                pos["shares"] * day_prices[sid].close
                for sid, pos in positions.items() if sid in day_prices
            )
            target_value_per = total_value / max(len(target_stocks), 1)

            # 买入/调仓
            for sid, sc in target_stocks:
                if sid not in day_prices:
                    continue
                price = day_prices[sid].close * (1 + SLIPPAGE_RATE)  # 买入滑点加价
                # 涨跌停检查：涨停时无法买入
                prev_p = day_prices[sid].pre_close
                symbol = stock_map[sid].symbol if sid in stock_map else ""
                if prev_p and _is_limit_locked(price, prev_p, symbol) and price > prev_p:
                    continue  # 涨停，跳过买入
                current_value = positions[sid]["shares"] * price if sid in positions else 0
                diff = target_value_per - current_value

                if diff > price * 100:  # 至少 1 手（100 股）
                    shares_to_buy = int(diff / price / 100) * 100  # 整手
                    if shares_to_buy > 0:
                        buy_amount = shares_to_buy * price
                        # 计算交易成本（佣金 + 过户费）
                        commission = max(buy_amount * COMMISSION_RATE, MIN_COMMISSION)
                        transfer_fee = buy_amount * TRANSFER_FEE_RATE
                        total_needed = buy_amount + commission + transfer_fee
                        if cash >= total_needed:
                            cash -= total_needed
                            if sid in positions:
                                old = positions[sid]
                                total_shares = old["shares"] + shares_to_buy
                                avg_cost = (old["shares"] * old["cost_price"] + buy_amount) / total_shares
                                positions[sid] = {"shares": total_shares, "cost_price": avg_cost}
                            else:
                                positions[sid] = {"shares": shares_to_buy, "cost_price": price}
                            trade_log.append({
                                "date": td.isoformat(),
                                "symbol": stock_map[sid].symbol,
                                "name": stock_map[sid].name,
                                "action": "BUY",
                                "price": round(price, 2),
                                "shares": shares_to_buy,
                                "pnl": 0,
                                "commission": round(commission, 2),
                            })

        # 记录月度收益（策略 + 基准 + 超额）
        if i > 0:
            daily_ret = (portfolio_value - prev_equity) / prev_equity if prev_equity > 0 else 0
            daily_bench_ret = (benchmark_value - prev_benchmark) / prev_benchmark if prev_benchmark > 0 else 0

            month_label = td.strftime("%Y-%m")
            if not monthly_returns or monthly_returns[-1]["month"] != month_label:
                # 新月份开始
                if monthly_returns:
                    # 计算上月的超额收益
                    sr = monthly_returns[-1]["strategy_return"]
                    br = monthly_returns[-1]["benchmark_return"]
                    monthly_returns[-1]["excess_return"] = round(sr - br, 2)
                monthly_returns.append({
                    "month": month_label,
                    "strategy_return": round(daily_ret * 100, 2),
                    "benchmark_return": round(daily_bench_ret * 100, 2),
                    "excess_return": 0,
                })
            else:
                # 同一月份，累乘收益
                prev_sr = monthly_returns[-1]["strategy_return"] / 100
                prev_br = monthly_returns[-1]["benchmark_return"] / 100
                monthly_returns[-1]["strategy_return"] = round(
                    (1 + prev_sr) * (1 + daily_ret) * 100 - 100, 2
                )
                monthly_returns[-1]["benchmark_return"] = round(
                    (1 + prev_br) * (1 + daily_bench_ret) * 100 - 100, 2
                )

        prev_equity = portfolio_value
        prev_benchmark = benchmark_value

    # 计算最后一个月的超额收益
    if monthly_returns:
        sr = monthly_returns[-1]["strategy_return"]
        br = monthly_returns[-1]["benchmark_return"]
        monthly_returns[-1]["excess_return"] = round(sr - br, 2)

    # 最终清算
    final_date = trade_dates[-1]
    final_prices = date_map.get(final_date, {})
    final_equity = cash
    for sid, pos in positions.items():
        if sid in final_prices:
            final_equity += pos["shares"] * final_prices[sid].close
        else:
            final_equity += pos["shares"] * pos["cost_price"]

    # 计算指标
    total_return = (final_equity - initial_capital) / initial_capital
    n_days = (trade_dates[-1] - trade_dates[0]).days
    n_years = max(n_days / 365, 0.1)
    annual_return = (1 + total_return) ** (1 / n_years) - 1

    # 基准收益
    benchmark_final = equity_curve[-1]["benchmark"] if equity_curve else initial_capital
    benchmark_total = (benchmark_final - initial_capital) / initial_capital

    # 最大回撤
    peak = initial_capital
    max_dd = 0
    for point in equity_curve:
        if point["equity"] > peak:
            peak = point["equity"]
        dd = (peak - point["equity"]) / peak
        if dd > max_dd:
            max_dd = dd

    # 夏普比率（日收益率）
    daily_returns = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1]["equity"]
        curr = equity_curve[i]["equity"]
        if prev > 0:
            daily_returns.append((curr - prev) / prev)
    if daily_returns and np.std(daily_returns) > 0:
        sharpe = (np.mean(daily_returns) * 252) / (np.std(daily_returns) * np.sqrt(252))
    else:
        sharpe = 0

    # 胜率
    win_trades = len([t for t in trade_log if t.get("pnl", 0) > 0])
    sell_trades = [t for t in trade_log if t["action"] == "SELL"]
    win_rate = win_trades / len(sell_trades) if sell_trades else 0

    return {
        "total_return": round(total_return * 100, 2),
        "annual_return": round(annual_return * 100, 2),
        "benchmark_return": round(benchmark_total * 100, 2),
        "excess_return": round((total_return - benchmark_total) * 100, 2),
        "max_drawdown": round(max_dd * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "win_rate": round(win_rate * 100, 2),
        "total_trades": len(trade_log),
        "equity_curve": equity_curve,
        "monthly_returns": monthly_returns,
        "trade_log": trade_log,
    }


def simulate_portfolio(
    db: Session,
    holdings: list[dict],
) -> dict:
    """
    模拟买入回测
    holdings: [{"symbol": "600519", "buy_date": "2024-01-15", "shares": 100}, ...]
    """
    from app.models.stock import Stock
    from sqlalchemy import func as sqlfunc

    if not holdings:
        return {"error": "持仓列表为空"}

    # 解析持仓，获取买入价格
    positions = []
    total_invested = 0
    earliest_date = None

    for h in holdings:
        stock = db.query(Stock).filter(Stock.symbol == h["symbol"]).first()
        if not stock:
            return {"error": f"未找到股票: {h['symbol']}"}

        buy_date = date.fromisoformat(h["buy_date"])
        if earliest_date is None or buy_date < earliest_date:
            earliest_date = buy_date

        # 获取买入日的价格
        buy_price_row = (
            db.query(DailyPrice)
            .filter(DailyPrice.stock_id == stock.id, DailyPrice.trade_date >= buy_date)
            .order_by(DailyPrice.trade_date)
            .first()
        )
        if not buy_price_row:
            return {"error": f"{h['symbol']} 在 {h['buy_date']} 附近无价格数据"}

        buy_price = buy_price_row.close
        actual_buy_date = buy_price_row.trade_date
        cost = buy_price * h["shares"]
        total_invested += cost

        positions.append({
            "symbol": stock.symbol,
            "name": stock.name,
            "stock_id": stock.id,
            "buy_date": str(actual_buy_date),
            "buy_price": round(buy_price, 2),
            "shares": h["shares"],
            "cost": round(cost, 2),
        })

    # 获取从最早买入日到最新日的所有价格数据
    latest_date = db.query(sqlfunc.max(DailyPrice.trade_date)).scalar()
    all_stock_ids = [p["stock_id"] for p in positions]

    prices = (
        db.query(DailyPrice)
        .filter(
            DailyPrice.stock_id.in_(all_stock_ids),
            DailyPrice.trade_date >= earliest_date,
        )
        .order_by(DailyPrice.trade_date)
        .all()
    )

    # 按日期分组
    date_map: dict[date, dict[int, DailyPrice]] = {}
    for p in prices:
        if p.trade_date not in date_map:
            date_map[p.trade_date] = {}
        date_map[p.trade_date][p.stock_id] = p

    trade_dates = sorted(date_map.keys())

    # 计算基准（等权买入并持有全部A股）
    all_stocks = db.query(Stock).filter(Stock.market == "A_SHARE", Stock.status == "ACTIVE").all()
    benchmark_stock_ids = [s.id for s in all_stocks]
    benchmark_prices = (
        db.query(DailyPrice)
        .filter(
            DailyPrice.stock_id.in_(benchmark_stock_ids),
            DailyPrice.trade_date >= earliest_date,
        )
        .order_by(DailyPrice.trade_date)
        .all()
    )
    bench_date_map: dict[date, dict[int, DailyPrice]] = {}
    for p in benchmark_prices:
        if p.trade_date not in bench_date_map:
            bench_date_map[p.trade_date] = {}
        bench_date_map[p.trade_date][p.stock_id] = p

    # 计算基准起始价
    bench_start_prices = {}
    if trade_dates:
        first_td = trade_dates[0]
        for sid in benchmark_stock_ids:
            if sid in bench_date_map.get(first_td, {}):
                bench_start_prices[sid] = bench_date_map[first_td][sid].close

    # 构建权益曲线
    equity_curve = []
    monthly_returns = []
    prev_equity = total_invested
    prev_benchmark = total_invested

    for td in trade_dates:
        day_prices = date_map.get(td, {})

        # 计算当日组合市值
        portfolio_value = 0
        for pos in positions:
            sid = pos["stock_id"]
            if sid in day_prices:
                # 用买入日之后的价格
                if td >= date.fromisoformat(pos["buy_date"]):
                    portfolio_value += pos["shares"] * day_prices[sid].close
                else:
                    portfolio_value += pos["cost"]
            else:
                portfolio_value += pos["cost"]

        # 计算基准市值
        benchmark_value = 0
        bench_count = 0
        for sid, start_price in bench_start_prices.items():
            if sid in bench_date_map.get(td, {}):
                ratio = bench_date_map[td][sid].close / start_price
                benchmark_value += (total_invested / len(bench_start_prices)) * ratio
                bench_count += 1
        if bench_count == 0:
            benchmark_value = total_invested

        equity_curve.append({
            "date": td.isoformat(),
            "equity": round(portfolio_value, 2),
            "benchmark": round(benchmark_value, 2),
        })

        # 记录月度收益
        if equity_curve and len(equity_curve) > 1:
            daily_ret = (portfolio_value - prev_equity) / prev_equity if prev_equity > 0 else 0
            daily_bench_ret = (benchmark_value - prev_benchmark) / prev_benchmark if prev_benchmark > 0 else 0

            month_label = td.strftime("%Y-%m")
            if not monthly_returns or monthly_returns[-1]["month"] != month_label:
                if monthly_returns:
                    sr = monthly_returns[-1]["strategy_return"]
                    br = monthly_returns[-1]["benchmark_return"]
                    monthly_returns[-1]["excess_return"] = round(sr - br, 2)
                monthly_returns.append({
                    "month": month_label,
                    "strategy_return": round(daily_ret * 100, 2),
                    "benchmark_return": round(daily_bench_ret * 100, 2),
                    "excess_return": 0,
                })
            else:
                prev_sr = monthly_returns[-1]["strategy_return"] / 100
                prev_br = monthly_returns[-1]["benchmark_return"] / 100
                monthly_returns[-1]["strategy_return"] = round((1 + prev_sr) * (1 + daily_ret) * 100 - 100, 2)
                monthly_returns[-1]["benchmark_return"] = round((1 + prev_br) * (1 + daily_bench_ret) * 100 - 100, 2)

        prev_equity = portfolio_value
        prev_benchmark = benchmark_value

    # 计算最后一个月的超额收益
    if monthly_returns:
        sr = monthly_returns[-1]["strategy_return"]
        br = monthly_returns[-1]["benchmark_return"]
        monthly_returns[-1]["excess_return"] = round(sr - br, 2)

    # 计算最终收益
    final_value = equity_curve[-1]["equity"] if equity_curve else total_invested
    final_benchmark = equity_curve[-1]["benchmark"] if equity_curve else total_invested

    total_return = (final_value - total_invested) / total_invested * 100 if total_invested > 0 else 0
    benchmark_return = (final_benchmark - total_invested) / total_invested * 100 if total_invested > 0 else 0

    # 计算每只持仓的盈亏
    holding_details = []
    for pos in positions:
        sid = pos["stock_id"]
        latest_price_row = (
            db.query(DailyPrice)
            .filter(DailyPrice.stock_id == sid)
            .order_by(DailyPrice.trade_date.desc())
            .first()
        )
        current_price = latest_price_row.close if latest_price_row else pos["buy_price"]
        current_val = current_price * pos["shares"]
        pnl = current_val - pos["cost"]
        pnl_pct = pnl / pos["cost"] * 100 if pos["cost"] > 0 else 0

        holding_details.append({
            "symbol": pos["symbol"],
            "name": pos["name"],
            "buy_date": pos["buy_date"],
            "buy_price": pos["buy_price"],
            "shares": pos["shares"],
            "cost": pos["cost"],
            "current_price": round(current_price, 2),
            "current_value": round(current_val, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })

    return {
        "total_invested": round(total_invested, 2),
        "current_value": round(final_value, 2),
        "total_return": round(total_return, 2),
        "total_pnl": round(final_value - total_invested, 2),
        "benchmark_return": round(benchmark_return, 2),
        "excess_return": round(total_return - benchmark_return, 2),
        "holdings": holding_details,
        "equity_curve": equity_curve,
        "monthly_returns": monthly_returns,
    }
