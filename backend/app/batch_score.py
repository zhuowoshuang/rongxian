"""
批量评分脚本 - 对所有有价格数据的股票进行评分和生成信号
运行方式: python -m app.batch_score
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from app.db.session import SessionLocal
from app.models.stock import Stock
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.technical_indicator import TechnicalIndicator
from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal
from app.services.scoring import (
    _latest_financial_for_stock,
    calculate_growth_score,
    calculate_quality_score,
    calculate_risk_score,
    calculate_trend_score,
    calculate_valuation_score,
    get_rating,
)
from app.services.signal import determine_signal_type, calculate_position, calculate_prices
from app.core.constants import SignalStatus
from sqlalchemy import func

def batch_score():
    """对所有有价格数据的股票进行评分"""
    db = SessionLocal()
    today = date.today()

    print("=" * 60)
    print("批量评分脚本")
    print("=" * 60)

    # 获取所有有最新价格数据的股票
    latest_price_subq = (
        db.query(
            DailyPrice.stock_id,
            func.max(DailyPrice.trade_date).label("max_date")
        )
        .group_by(DailyPrice.stock_id)
        .subquery()
    )

    stocks_with_prices = (
        db.query(Stock)
        .join(latest_price_subq, Stock.id == latest_price_subq.c.stock_id)
        .filter(Stock.status == "ACTIVE")
        .all()
    )

    print(f"找到 {len(stocks_with_prices)} 只有价格数据的股票")

    scored = 0
    signals = 0
    errors = 0

    for stock in stocks_with_prices:
        try:
            # 获取最新价格
            latest_price = (
                db.query(DailyPrice)
                .filter(DailyPrice.stock_id == stock.id)
                .order_by(DailyPrice.trade_date.desc())
                .first()
            )
            if not latest_price:
                continue

            # 获取最新财务数据
            financial = _latest_financial_for_stock(db, stock.id)

            # 获取最新技术指标
            tech = (
                db.query(TechnicalIndicator)
                .filter(TechnicalIndicator.stock_id == stock.id)
                .order_by(TechnicalIndicator.trade_date.desc())
                .first()
            )

            # 计算评分（传入可能为 None 的参数）
            quality_score, quality_details = calculate_quality_score(financial) if financial else (0, [])
            valuation_score, valuation_details = calculate_valuation_score(latest_price, financial) if financial else (0, [])
            growth_score, growth_details = calculate_growth_score(financial) if financial else (0, [])
            trend_score, trend_details = calculate_trend_score(latest_price, tech) if tech else (0, [])
            risk_score, risk_details = calculate_risk_score(financial, latest_price) if financial else (0, [])

            total_score = quality_score + valuation_score + growth_score + trend_score + risk_score
            rating = get_rating(total_score)

            # 生成评分理由
            reason_parts = []
            if quality_score > 0:
                reason_parts.append(f"质量{quality_score:.0f}")
            if valuation_score > 0:
                reason_parts.append(f"估值{valuation_score:.0f}")
            if growth_score > 0:
                reason_parts.append(f"成长{growth_score:.0f}")
            if trend_score > 0:
                reason_parts.append(f"趋势{trend_score:.0f}")
            if risk_score > 0:
                reason_parts.append(f"风险{risk_score:.0f}")
            reason = " ".join(reason_parts) if reason_parts else "数据不足"

            # 保存评分（更新或插入）
            existing_score = db.query(StockScore).filter(
                StockScore.stock_id == stock.id,
                StockScore.score_date == today
            ).first()

            if existing_score:
                existing_score.total_score = total_score
                existing_score.quality_score = quality_score
                existing_score.valuation_score = valuation_score
                existing_score.growth_score = growth_score
                existing_score.trend_score = trend_score
                existing_score.risk_score = risk_score
                existing_score.rating = rating
                existing_score.reason_summary = reason
            else:
                score = StockScore(
                    stock_id=stock.id,
                    score_date=today,
                    total_score=total_score,
                    quality_score=quality_score,
                    valuation_score=valuation_score,
                    growth_score=growth_score,
                    trend_score=trend_score,
                    risk_score=risk_score,
                    rating=rating,
                    reason_summary=reason,
                )
                db.add(score)
            scored += 1

            # 生成交易信号
            # 创建临时 StockScore 对象用于信号判断
            temp_score = StockScore(
                total_score=total_score,
                quality_score=quality_score,
                valuation_score=valuation_score,
                growth_score=growth_score,
                trend_score=trend_score,
                risk_score=risk_score,
                rating=rating,
            )
            signal_type, signal_strength, logic_text = determine_signal_type(temp_score)
            if signal_type:
                entry_price, target_price, stop_loss = calculate_prices(latest_price, signal_type)
                position = calculate_position(signal_type, signal_strength)

                logic = {
                    "total_score": total_score,
                    "reason": reason,
                }

                # 保存信号（更新或插入）
                existing_signal = db.query(TradeSignal).filter(
                    TradeSignal.stock_id == stock.id,
                    TradeSignal.signal_date == today
                ).first()

                if existing_signal:
                    existing_signal.signal_type = signal_type
                    existing_signal.signal_strength = min(5, max(1, int(total_score / 20)))
                    existing_signal.suggested_position = position
                    existing_signal.entry_price = entry_price
                    existing_signal.target_price = target_price
                    existing_signal.stop_loss_price = stop_loss
                    existing_signal.logic_json = logic
                else:
                    signal = TradeSignal(
                        stock_id=stock.id,
                        signal_date=today,
                        signal_type=signal_type,
                        signal_strength=min(5, max(1, int(total_score / 20))),
                        suggested_position=position,
                        entry_price=entry_price,
                        target_price=target_price,
                        stop_loss_price=stop_loss,
                        holding_period="中期" if signal_type in ("BUY", "ADD") else "短期",
                        logic_json=logic,
                        status=SignalStatus.ACTIVE,
                    )
                    db.add(signal)
                signals += 1

            # 每 100 只股票提交一次
            if scored % 100 == 0:
                db.commit()
                print(f"  已处理 {scored} 只股票...")

        except Exception as e:
            errors += 1
            print(f"  ERROR {stock.symbol}: {e}")
            db.rollback()
            continue

    db.commit()
    db.close()

    print(f"\n完成！")
    print(f"  评分: {scored} 只股票")
    print(f"  信号: {signals} 个交易信号")
    print(f"  错误: {errors} 个")

if __name__ == "__main__":
    batch_score()
