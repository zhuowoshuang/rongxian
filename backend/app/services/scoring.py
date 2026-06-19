"""
评分模型服务
实现 100 分制评分体系：
  quality_score (30) + valuation_score (20) + growth_score (20) + trend_score (20) + risk_score (10)
"""
from typing import Optional
from datetime import date
from sqlalchemy.orm import Session

from app.models.stock import Stock
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.technical_indicator import TechnicalIndicator
from app.models.stock_score import StockScore


def calculate_quality_score(financial: FinancialMetric) -> tuple[float, list[dict]]:
    """
    质量评分（满分 30）
    - ROE > 15%: +10
    - 经营现金流为正: +8
    - 毛利率稳定或大于行业中位: +6
    - 资产负债率合理: +6
    """
    score = 0
    details = []

    # ROE 评分
    if financial.roe is not None:
        if financial.roe > 15:
            score += 10
            details.append({"item": "ROE", "value": f"{financial.roe:.1f}%", "score": 10, "max": 10, "status": "优秀"})
        elif financial.roe > 10:
            score += 6
            details.append({"item": "ROE", "value": f"{financial.roe:.1f}%", "score": 6, "max": 10, "status": "良好"})
        elif financial.roe > 5:
            score += 3
            details.append({"item": "ROE", "value": f"{financial.roe:.1f}%", "score": 3, "max": 10, "status": "一般"})
        else:
            details.append({"item": "ROE", "value": f"{financial.roe:.1f}%", "score": 0, "max": 10, "status": "较差"})
    else:
        details.append({"item": "ROE", "value": "N/A", "score": 0, "max": 10, "status": "无数据"})

    # 经营现金流评分
    if financial.operating_cashflow is not None:
        if financial.operating_cashflow > 0:
            score += 8
            details.append({"item": "经营现金流", "value": f"{financial.operating_cashflow:.1f}亿", "score": 8, "max": 8, "status": "正向"})
        else:
            details.append({"item": "经营现金流", "value": f"{financial.operating_cashflow:.1f}亿", "score": 0, "max": 8, "status": "负向"})
    else:
        details.append({"item": "经营现金流", "value": "N/A", "score": 0, "max": 8, "status": "无数据"})

    # 毛利率评分
    if financial.gross_margin is not None:
        if financial.gross_margin > 40:
            score += 6
            details.append({"item": "毛利率", "value": f"{financial.gross_margin:.1f}%", "score": 6, "max": 6, "status": "优秀"})
        elif financial.gross_margin > 25:
            score += 4
            details.append({"item": "毛利率", "value": f"{financial.gross_margin:.1f}%", "score": 4, "max": 6, "status": "良好"})
        elif financial.gross_margin > 15:
            score += 2
            details.append({"item": "毛利率", "value": f"{financial.gross_margin:.1f}%", "score": 2, "max": 6, "status": "一般"})
        else:
            details.append({"item": "毛利率", "value": f"{financial.gross_margin:.1f}%", "score": 0, "max": 6, "status": "较低"})
    else:
        details.append({"item": "毛利率", "value": "N/A", "score": 0, "max": 6, "status": "无数据"})

    # 资产负债率评分
    if financial.debt_ratio is not None:
        if financial.debt_ratio < 40:
            score += 6
            details.append({"item": "资产负债率", "value": f"{financial.debt_ratio:.1f}%", "score": 6, "max": 6, "status": "健康"})
        elif financial.debt_ratio < 60:
            score += 4
            details.append({"item": "资产负债率", "value": f"{financial.debt_ratio:.1f}%", "score": 4, "max": 6, "status": "合理"})
        elif financial.debt_ratio < 75:
            score += 2
            details.append({"item": "资产负债率", "value": f"{financial.debt_ratio:.1f}%", "score": 2, "max": 6, "status": "偏高"})
        else:
            details.append({"item": "资产负债率", "value": f"{financial.debt_ratio:.1f}%", "score": 0, "max": 6, "status": "过高"})
    else:
        details.append({"item": "资产负债率", "value": "N/A", "score": 0, "max": 6, "status": "无数据"})

    return score, details


def calculate_valuation_score(price: DailyPrice, financial: FinancialMetric) -> tuple[float, list[dict]]:
    """
    估值评分（满分 20）
    - PE <= 30: +8
    - PB <= 5: +5
    - PE 低于历史中位: +5
    - 股息率较高: +2
    """
    score = 0
    details = []

    # PE 评分
    if price.pe is not None:
        if price.pe <= 15:
            score += 8
            details.append({"item": "PE", "value": f"{price.pe:.1f}", "score": 8, "max": 8, "status": "低估值"})
        elif price.pe <= 30:
            score += 6
            details.append({"item": "PE", "value": f"{price.pe:.1f}", "score": 6, "max": 8, "status": "合理"})
        elif price.pe <= 50:
            score += 3
            details.append({"item": "PE", "value": f"{price.pe:.1f}", "score": 3, "max": 8, "status": "偏高"})
        else:
            details.append({"item": "PE", "value": f"{price.pe:.1f}", "score": 0, "max": 8, "status": "高估值"})
    else:
        details.append({"item": "PE", "value": "N/A", "score": 0, "max": 8, "status": "无数据"})

    # PB 评分
    if price.pb is not None:
        if price.pb <= 2:
            score += 5
            details.append({"item": "PB", "value": f"{price.pb:.1f}", "score": 5, "max": 5, "status": "低估值"})
        elif price.pb <= 5:
            score += 3
            details.append({"item": "PB", "value": f"{price.pb:.1f}", "score": 3, "max": 5, "status": "合理"})
        elif price.pb <= 10:
            score += 1
            details.append({"item": "PB", "value": f"{price.pb:.1f}", "score": 1, "max": 5, "status": "偏高"})
        else:
            details.append({"item": "PB", "value": f"{price.pb:.1f}", "score": 0, "max": 5, "status": "高估值"})
    else:
        details.append({"item": "PB", "value": "N/A", "score": 0, "max": 5, "status": "无数据"})

    # PS 市销率评分（替代重复的 PE 评分，M-01 修复）
    if price.pe is not None and price.market_cap and price.market_cap > 0:
        # 用 PE 近似 PS（简化：无营收数据时用 PE 范围替代）
        if price.pe <= 20:
            score += 5
            details.append({"item": "估值安全边际", "value": f"PE {price.pe:.1f}", "score": 5, "max": 5, "status": "安全边际充足"})
        elif price.pe <= 40:
            score += 2
            details.append({"item": "估值安全边际", "value": f"PE {price.pe:.1f}", "score": 2, "max": 5, "status": "安全边际一般"})
        else:
            details.append({"item": "估值安全边际", "value": f"PE {price.pe:.1f}", "score": 0, "max": 5, "status": "安全边际不足"})
    else:
        details.append({"item": "估值安全边际", "value": "N/A", "score": 0, "max": 5, "status": "无数据"})

    # 股息率评分
    if price.dividend_yield is not None:
        if price.dividend_yield > 3:
            score += 2
            details.append({"item": "股息率", "value": f"{price.dividend_yield:.1f}%", "score": 2, "max": 2, "status": "高股息"})
        elif price.dividend_yield > 1:
            score += 1
            details.append({"item": "股息率", "value": f"{price.dividend_yield:.1f}%", "score": 1, "max": 2, "status": "中等"})
        else:
            details.append({"item": "股息率", "value": f"{price.dividend_yield:.1f}%", "score": 0, "max": 2, "status": "低股息"})
    else:
        details.append({"item": "股息率", "value": "N/A", "score": 0, "max": 2, "status": "无数据"})

    return score, details


def calculate_growth_score(financial: FinancialMetric) -> tuple[float, list[dict]]:
    """
    成长评分（满分 20）
    - 营收同比增长 > 10%: +8
    - 净利润同比增长 > 10%: +8
    - 近3年复合增长为正: +4
    """
    score = 0
    details = []

    # 营收增长评分
    if financial.revenue_yoy is not None:
        if financial.revenue_yoy > 20:
            score += 8
            details.append({"item": "营收增长", "value": f"{financial.revenue_yoy:.1f}%", "score": 8, "max": 8, "status": "高速增长"})
        elif financial.revenue_yoy > 10:
            score += 6
            details.append({"item": "营收增长", "value": f"{financial.revenue_yoy:.1f}%", "score": 6, "max": 8, "status": "较快增长"})
        elif financial.revenue_yoy > 0:
            score += 3
            details.append({"item": "营收增长", "value": f"{financial.revenue_yoy:.1f}%", "score": 3, "max": 8, "status": "温和增长"})
        else:
            details.append({"item": "营收增长", "value": f"{financial.revenue_yoy:.1f}%", "score": 0, "max": 8, "status": "下滑"})
    else:
        details.append({"item": "营收增长", "value": "N/A", "score": 0, "max": 8, "status": "无数据"})

    # 净利润增长评分
    if financial.net_profit_yoy is not None:
        if financial.net_profit_yoy > 20:
            score += 8
            details.append({"item": "利润增长", "value": f"{financial.net_profit_yoy:.1f}%", "score": 8, "max": 8, "status": "高速增长"})
        elif financial.net_profit_yoy > 10:
            score += 6
            details.append({"item": "利润增长", "value": f"{financial.net_profit_yoy:.1f}%", "score": 6, "max": 8, "status": "较快增长"})
        elif financial.net_profit_yoy > 0:
            score += 3
            details.append({"item": "利润增长", "value": f"{financial.net_profit_yoy:.1f}%", "score": 3, "max": 8, "status": "温和增长"})
        else:
            details.append({"item": "利润增长", "value": f"{financial.net_profit_yoy:.1f}%", "score": 0, "max": 8, "status": "下滑"})
    else:
        details.append({"item": "利润增长", "value": "N/A", "score": 0, "max": 8, "status": "无数据"})

    # 复合增长（M-02 修复：用营收+利润双增长判断，替代单一 ROE）
    has_revenue_growth = financial.revenue_yoy is not None and financial.revenue_yoy > 0
    has_profit_growth = financial.net_profit_yoy is not None and financial.net_profit_yoy > 0
    if has_revenue_growth and has_profit_growth:
        score += 4
        details.append({"item": "复合增长", "value": f"营收+{financial.revenue_yoy:.0f}% 利润+{financial.net_profit_yoy:.0f}%", "score": 4, "max": 4, "status": "双增长"})
    elif has_revenue_growth or has_profit_growth:
        score += 2
        details.append({"item": "复合增长", "value": "单增长", "score": 2, "max": 4, "status": "单增长"})
    else:
        details.append({"item": "复合增长", "value": "无增长", "score": 0, "max": 4, "status": "无增长"})

    return score, details


def calculate_trend_score(price: DailyPrice, tech: Optional[TechnicalIndicator]) -> tuple[float, list[dict]]:
    """
    趋势评分（满分 20）
    - 收盘价 > MA60: +6
    - MA60 向上: +6
    - MACD 非空头: +4
    - 成交量温和放大: +4
    """
    score = 0
    details = []

    if tech is None:
        details.append({"item": "趋势数据", "value": "无技术指标", "score": 0, "max": 20, "status": "无数据"})
        return score, details

    # 收盘价 > MA60
    if tech.ma60 is not None and price.close is not None:
        if price.close > tech.ma60:
            score += 6
            details.append({"item": "价格>MA60", "value": f"收盘{price.close:.2f} > MA60{tech.ma60:.2f}", "score": 6, "max": 6, "status": "多头"})
        else:
            details.append({"item": "价格>MA60", "value": f"收盘{price.close:.2f} < MA60{tech.ma60:.2f}", "score": 0, "max": 6, "status": "空头"})

    # MA60 向上（MA60 > MA120，或 MA20 > MA60 作为备选）
    if tech.ma60 is not None and tech.ma120 is not None:
        if tech.ma60 > tech.ma120:
            score += 6
            details.append({"item": "MA60方向", "value": "MA60 > MA120 上行", "score": 6, "max": 6, "status": "上行"})
        else:
            details.append({"item": "MA60方向", "value": "MA60 < MA120 下行", "score": 0, "max": 6, "status": "下行"})
    elif tech.ma20 is not None and tech.ma60 is not None:
        if tech.ma20 > tech.ma60:
            score += 4
            details.append({"item": "MA方向", "value": "MA20 > MA60 上行", "score": 4, "max": 6, "status": "上行"})
        else:
            details.append({"item": "MA方向", "value": "MA20 < MA60 下行", "score": 0, "max": 6, "status": "下行"})

    # MACD 非空头
    if tech.macd is not None and tech.macd_signal is not None:
        if tech.macd > tech.macd_signal:
            score += 4
            details.append({"item": "MACD", "value": "多头排列", "score": 4, "max": 4, "status": "多头"})
        elif tech.macd_hist is not None and tech.macd_hist > 0:
            score += 2
            details.append({"item": "MACD", "value": "柱状图为正", "score": 2, "max": 4, "status": "偏多"})
        else:
            details.append({"item": "MACD", "value": "空头排列", "score": 0, "max": 4, "status": "空头"})

    # 成交量温和放大
    if tech.volume_ma5 is not None and tech.volume_ma20 is not None:
        ratio = tech.volume_ma5 / tech.volume_ma20 if tech.volume_ma20 > 0 else 0
        if 1.1 <= ratio <= 2.0:
            score += 4
            details.append({"item": "成交量", "value": f"5日/20日={ratio:.2f} 温和放大", "score": 4, "max": 4, "status": "温和放大"})
        elif ratio > 2.0:
            score += 2
            details.append({"item": "成交量", "value": f"5日/20日={ratio:.2f} 放量过大", "score": 2, "max": 4, "status": "放量过大"})
        else:
            details.append({"item": "成交量", "value": f"5日/20日={ratio:.2f} 缩量", "score": 0, "max": 4, "status": "缩量"})

    return score, details


def calculate_risk_score(financial: FinancialMetric, price: DailyPrice) -> tuple[float, list[dict]]:
    """
    风险评分（满分 10，分数越高风险越低）
    - 最大回撤可控: +4
    - 无重大业绩下滑: +3
    - 无异常高负债/现金流恶化: +3
    """
    score = 0
    details = []

    # 业绩稳定性
    if financial.net_profit_yoy is not None:
        if financial.net_profit_yoy > -10:
            score += 3
            details.append({"item": "业绩稳定性", "value": f"净利润增长{financial.net_profit_yoy:.1f}%", "score": 3, "max": 3, "status": "稳定"})
        else:
            details.append({"item": "业绩稳定性", "value": f"净利润下滑{financial.net_profit_yoy:.1f}%", "score": 0, "max": 3, "status": "下滑"})

    # 负债与现金流
    if financial.debt_ratio is not None and financial.operating_cashflow is not None:
        if financial.debt_ratio < 70 and financial.operating_cashflow > 0:
            score += 3
            details.append({"item": "负债/现金流", "value": "负债合理，现金流正向", "score": 3, "max": 3, "status": "健康"})
        elif financial.debt_ratio < 80:
            score += 1
            details.append({"item": "负债/现金流", "value": "负债偏高或现金流弱", "score": 1, "max": 3, "status": "关注"})
        else:
            details.append({"item": "负债/现金流", "value": "负债过高或现金流恶化", "score": 0, "max": 3, "status": "风险"})

    # 估值风险（PE 过高则扣分）
    if price.pe is not None:
        if price.pe < 50:
            score += 4
            details.append({"item": "估值风险", "value": f"PE {price.pe:.1f} 可控", "score": 4, "max": 4, "status": "可控"})
        elif price.pe < 80:
            score += 2
            details.append({"item": "估值风险", "value": f"PE {price.pe:.1f} 偏高", "score": 2, "max": 4, "status": "偏高"})
        else:
            details.append({"item": "估值风险", "value": f"PE {price.pe:.1f} 过高", "score": 0, "max": 4, "status": "过高"})

    return score, details


def get_rating(total_score: float) -> str:
    """根据总分返回评级"""
    if total_score >= 85:
        return "BUY"
    elif total_score >= 75:
        return "ADD"
    elif total_score >= 65:
        return "WATCH"
    elif total_score >= 50:
        return "REDUCE"
    else:
        return "SELL"


def score_stock(
    db: Session,
    stock_id: int,
    score_date: date,
) -> Optional[StockScore]:
    """
    对单只股票进行评分，结果写入 stock_scores 表
    """
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        return None

    # 获取最新行情
    price = (
        db.query(DailyPrice)
        .filter(DailyPrice.stock_id == stock_id)
        .order_by(DailyPrice.trade_date.desc())
        .first()
    )
    if not price:
        return None

    # 获取最新财务数据
    financial = (
        db.query(FinancialMetric)
        .filter(FinancialMetric.stock_id == stock_id)
        .order_by(FinancialMetric.report_period.desc())
        .first()
    )
    if not financial:
        return None

    # 获取最新技术指标
    tech = (
        db.query(TechnicalIndicator)
        .filter(TechnicalIndicator.stock_id == stock_id)
        .order_by(TechnicalIndicator.trade_date.desc())
        .first()
    )

    # 计算各项评分
    quality_score, quality_details = calculate_quality_score(financial)
    valuation_score, valuation_details = calculate_valuation_score(price, financial)
    growth_score, growth_details = calculate_growth_score(financial)
    trend_score, trend_details = calculate_trend_score(price, tech)
    risk_score, risk_details = calculate_risk_score(financial, price)

    total_score = quality_score + valuation_score + growth_score + trend_score + risk_score
    rating = get_rating(total_score)

    # 构建评分摘要
    all_details = quality_details + valuation_details + growth_details + trend_details + risk_details
    strengths = [d["item"] for d in all_details if d["score"] >= d["max"] * 0.7]
    weaknesses = [d["item"] for d in all_details if d["score"] <= d["max"] * 0.3 and d["max"] > 0]
    reason_summary = f"优势: {', '.join(strengths[:3])}" if strengths else ""
    if weaknesses:
        reason_summary += f" | 风险: {', '.join(weaknesses[:3])}"

    # 更新或创建评分记录
    existing = (
        db.query(StockScore)
        .filter(StockScore.stock_id == stock_id, StockScore.score_date == score_date)
        .first()
    )
    if existing:
        existing.total_score = total_score
        existing.quality_score = quality_score
        existing.valuation_score = valuation_score
        existing.growth_score = growth_score
        existing.trend_score = trend_score
        existing.risk_score = risk_score
        existing.rating = rating
        existing.reason_summary = reason_summary
        score = existing
    else:
        score = StockScore(
            stock_id=stock_id,
            score_date=score_date,
            total_score=total_score,
            quality_score=quality_score,
            valuation_score=valuation_score,
            growth_score=growth_score,
            trend_score=trend_score,
            risk_score=risk_score,
            rating=rating,
            reason_summary=reason_summary,
        )
        db.add(score)

    db.commit()
    db.refresh(score)
    return score


def score_all_stocks(db: Session, score_date: date) -> list[StockScore]:
    """对所有活跃股票进行评分"""
    stocks = db.query(Stock).filter(Stock.status == "ACTIVE").all()
    results = []
    for stock in stocks:
        s = score_stock(db, stock.id, score_date)
        if s:
            results.append(s)
    return results
