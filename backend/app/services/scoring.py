"""
评分模型服务（重构版）
实现 100 分制评分体系：
  quality_score (30) + valuation_score (20) + growth_score (20) + trend_score (20) + risk_score (10)

重构要点：
- 消除 PE 重复计算（原估值 8 + 安全边际 5 + 风险 4 = 17 分来自同一指标）
- 引入行业内百分位排名，替代全市场统一阈值
- 引入基本面趋势（ROE 同比变化）
- 风险维度用波动率替代 PE
"""
from typing import Optional
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.stock import Stock
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.technical_indicator import TechnicalIndicator
from app.models.stock_score import StockScore


# ==================== 行业统计工具 ====================

def _compute_industry_stats(db: Session, stock_ids: list[int]) -> dict:
    """
    计算每个行业的估值/质量指标分位数，用于行业内相对排名
    返回: {industry: {pe_q20/q50/q80, pb_q20/q50/q80, roe_q20/q50/q80, gm_q20/q50/q80,
           dr_q20/q50/q80, div_q20/q50/q80, vol_q20/q50/q80, count}}
    """
    if not stock_ids:
        return {}

    from datetime import timedelta
    import math
    from collections import defaultdict

    # 批量加载所有 Stock 到 dict（消除 N+1）
    all_stocks = db.query(Stock).filter(Stock.id.in_(stock_ids)).all()
    stock_map = {s.id: s for s in all_stocks}

    # 获取每只股票的最新价格（子查询 + join，一次查询）
    latest_price_subq = db.query(
        DailyPrice.stock_id,
        func.max(DailyPrice.trade_date).label("max_date")
    ).filter(DailyPrice.stock_id.in_(stock_ids)).group_by(DailyPrice.stock_id).subquery()

    latest_prices = db.query(DailyPrice).join(
        latest_price_subq,
        (DailyPrice.stock_id == latest_price_subq.c.stock_id) &
        (DailyPrice.trade_date == latest_price_subq.c.max_date)
    ).all()

    # 按行业分组价格数据
    industry_data: dict[str, dict] = {}
    for p in latest_prices:
        stock = stock_map.get(p.stock_id)
        if not stock or not stock.industry:
            continue
        ind = stock.industry
        if ind not in industry_data:
            industry_data[ind] = {"pe": [], "pb": [], "div": [], "vol": [], "roe": [], "gm": [], "dr": []}
        if p.pe is not None and 0 < p.pe < 500:
            industry_data[ind]["pe"].append(p.pe)
        if p.pb is not None and 0 < p.pb < 100:
            industry_data[ind]["pb"].append(p.pb)
        if p.dividend_yield is not None:
            industry_data[ind]["div"].append(p.dividend_yield)

    # 批量获取每只股票最新财务数据（消除 N+1）
    latest_fin_subq = db.query(
        FinancialMetric.stock_id,
        func.max(FinancialMetric.report_period).label("max_period")
    ).filter(FinancialMetric.stock_id.in_(stock_ids)).group_by(FinancialMetric.stock_id).subquery()

    latest_financials = db.query(FinancialMetric).join(
        latest_fin_subq,
        (FinancialMetric.stock_id == latest_fin_subq.c.stock_id) &
        (FinancialMetric.report_period == latest_fin_subq.c.max_period)
    ).all()

    for f in latest_financials:
        stock = stock_map.get(f.stock_id)
        if not stock or not stock.industry:
            continue
        ind = stock.industry
        if ind not in industry_data:
            industry_data[ind] = {"pe": [], "pb": [], "div": [], "vol": [], "roe": [], "gm": [], "dr": []}
        if f.roe is not None:
            industry_data[ind]["roe"].append(f.roe)
        if f.gross_margin is not None:
            industry_data[ind]["gm"].append(f.gross_margin)
        if f.debt_ratio is not None:
            industry_data[ind]["dr"].append(f.debt_ratio)

    # 计算每只股票的 60 日波动率并按行业分组
    latest_date = db.query(func.max(DailyPrice.trade_date)).scalar()
    if latest_date:
        vol_start = latest_date - timedelta(days=90)
        vol_prices = db.query(DailyPrice).filter(
            DailyPrice.stock_id.in_(stock_ids),
            DailyPrice.trade_date >= vol_start,
            DailyPrice.trade_date <= latest_date,
        ).order_by(DailyPrice.stock_id, DailyPrice.trade_date).all()

        prices_by_stock = defaultdict(list)
        for p in vol_prices:
            prices_by_stock[p.stock_id].append(p.close)

        for sid, closes in prices_by_stock.items():
            if len(closes) < 20:
                continue
            stock = stock_map.get(sid)
            if not stock or not stock.industry:
                continue
            daily_returns = [(closes[i] - closes[i-1]) / closes[i-1] for i in range(1, len(closes)) if closes[i-1] > 0]
            if len(daily_returns) >= 10:
                mean_ret = sum(daily_returns) / len(daily_returns)
                var = sum((r - mean_ret) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
                annual_vol = math.sqrt(var) * math.sqrt(252) * 100
                ind = stock.industry
                if ind not in industry_data:
                    industry_data[ind] = {"pe": [], "pb": [], "div": [], "vol": [], "roe": [], "gm": [], "dr": []}
                industry_data[ind]["vol"].append(annual_vol)

    # 计算分位数（标准公式：idx = (n-1) * pct/100）
    def percentile(data, pct):
        if not data or len(data) < 2:
            return None
        sorted_data = sorted(data)
        idx = (len(sorted_data) - 1) * pct / 100
        lower = int(idx)
        upper = min(lower + 1, len(sorted_data) - 1)
        frac = idx - lower
        return sorted_data[lower] * (1 - frac) + sorted_data[upper] * frac

    stats = {}
    for ind, data in industry_data.items():
        stats[ind] = {
            "pe_q20": percentile(data["pe"], 20), "pe_q50": percentile(data["pe"], 50), "pe_q80": percentile(data["pe"], 80),
            "pb_q20": percentile(data["pb"], 20), "pb_q50": percentile(data["pb"], 50), "pb_q80": percentile(data["pb"], 80),
            "roe_q20": percentile(data["roe"], 20), "roe_q50": percentile(data["roe"], 50), "roe_q80": percentile(data["roe"], 80),
            "gm_q20": percentile(data["gm"], 20), "gm_q50": percentile(data["gm"], 50), "gm_q80": percentile(data["gm"], 80),
            "dr_q20": percentile(data["dr"], 20), "dr_q50": percentile(data["dr"], 50), "dr_q80": percentile(data["dr"], 80),
            "div_q20": percentile(data["div"], 20), "div_q50": percentile(data["div"], 50), "div_q80": percentile(data["div"], 80),
            "vol_q20": percentile(data["vol"], 20), "vol_q50": percentile(data["vol"], 50), "vol_q80": percentile(data["vol"], 80),
            "count": len(data["pe"]),
        }
    return stats


def _industry_rank_score(value: float, q_low: float, q_mid: float, q_high: float, max_score: float, lower_is_better: bool = True) -> tuple[float, str]:
    """
    根据行业内分位数排名计算得分
    lower_is_better: True 表示值越低越好（如 PE），False 表示值越高越好（如股息率）
    """
    if value is None or q_low is None:
        return 0, "无数据"

    if lower_is_better:
        if value <= q_low:
            return max_score, "行业前 20%"
        elif value <= q_mid:
            return max_score * 0.75, "行业前 50%"
        elif value <= q_high:
            return max_score * 0.4, "行业中等"
        else:
            return 0, "行业后 20%"
    else:
        if value >= q_high:
            return max_score, "行业前 20%"
        elif value >= q_mid:
            return max_score * 0.75, "行业前 50%"
        elif value >= q_low:
            return max_score * 0.4, "行业中等"
        else:
            return 0, "行业后 20%"


# ==================== 质量评分 ====================

def calculate_quality_score(financial: FinancialMetric, prev_financial: Optional[FinancialMetric] = None, industry_stats: Optional[dict] = None) -> tuple[float, list[dict]]:
    """
    质量评分（满分 30）
    - ROE 水平（行业内排名）: +8
    - ROE 趋势（同比变化）: +2
    - 经营现金流为正: +8
    - 毛利率（行业内排名）: +6
    - 资产负债率（行业内排名）: +6
    """
    score = 0
    details = []
    ind = industry_stats or {}

    # ROE 水平（行业内排名）
    if financial.roe is not None:
        roe_q20 = ind.get("roe_q20", 15)
        roe_q50 = ind.get("roe_q50", 10)
        roe_q80 = ind.get("roe_q80", 5)
        # ROE 越高越好
        if roe_q20 and financial.roe >= roe_q20:
            s = 8
            status = "行业前 20%"
        elif roe_q50 and financial.roe >= roe_q50:
            s = 6
            status = "行业前 50%"
        elif roe_q80 and financial.roe >= roe_q80:
            s = 3
            status = "行业中等"
        else:
            s = 0
            status = "行业后 20%"
        # 无行业数据时用绝对阈值兜底
        if not ind:
            if financial.roe > 15:
                s, status = 8, "优秀"
            elif financial.roe > 10:
                s, status = 6, "良好"
            elif financial.roe > 5:
                s, status = 3, "一般"
            else:
                s, status = 0, "较差"
        score += s
        details.append({"item": "ROE", "value": f"{financial.roe:.1f}%", "score": s, "max": 8, "status": status})
    else:
        details.append({"item": "ROE", "value": "N/A", "score": 0, "max": 8, "status": "无数据"})

    # ROE 趋势（同比变化）
    if financial.roe is not None and prev_financial is not None and prev_financial.roe is not None:
        roe_change = financial.roe - prev_financial.roe
        if roe_change > 2:
            s = 2
            status = "提升"
        elif roe_change > -2:
            s = 1
            status = "稳定"
        else:
            s = 0
            status = "下降"
        score += s
        details.append({"item": "ROE趋势", "value": f"{'+' if roe_change >= 0 else ''}{roe_change:.1f}pp", "score": s, "max": 2, "status": status})
    else:
        details.append({"item": "ROE趋势", "value": "N/A", "score": 0, "max": 2, "status": "无历史数据"})

    # 经营现金流
    if financial.operating_cashflow is not None:
        if financial.operating_cashflow > 0:
            score += 8
            details.append({"item": "经营现金流", "value": f"{financial.operating_cashflow:.1f}亿", "score": 8, "max": 8, "status": "正向"})
        else:
            details.append({"item": "经营现金流", "value": f"{financial.operating_cashflow:.1f}亿", "score": 0, "max": 8, "status": "负向"})
    else:
        details.append({"item": "经营现金流", "value": "N/A", "score": 0, "max": 8, "status": "无数据"})

    # 毛利率（行业内排名）
    if financial.gross_margin is not None:
        if ind:
            gm_q20 = ind.get("gm_q20", 40)
            gm_q50 = ind.get("gm_q50", 25)
            gm_q80 = ind.get("gm_q80", 15)
            if gm_q20 and financial.gross_margin >= gm_q20:
                s = 6
                status = "行业前 20%"
            elif gm_q50 and financial.gross_margin >= gm_q50:
                s = 4
                status = "行业前 50%"
            elif gm_q80 and financial.gross_margin >= gm_q80:
                s = 2
                status = "行业中等"
            else:
                s = 0
                status = "行业后 20%"
        else:
            if financial.gross_margin > 40:
                s, status = 6, "优秀"
            elif financial.gross_margin > 25:
                s, status = 4, "良好"
            elif financial.gross_margin > 15:
                s, status = 2, "一般"
            else:
                s, status = 0, "较低"
        score += s
        details.append({"item": "毛利率", "value": f"{financial.gross_margin:.1f}%", "score": s, "max": 6, "status": status})
    else:
        details.append({"item": "毛利率", "value": "N/A", "score": 0, "max": 6, "status": "无数据"})

    # 资产负债率（行业内排名，越低越好）
    if financial.debt_ratio is not None:
        if ind:
            dr_q20 = ind.get("dr_q20", 40)
            dr_q50 = ind.get("dr_q50", 60)
            dr_q80 = ind.get("dr_q80", 75)
            # 负债率越低越好，所以 q20 是最好的
            if dr_q20 and financial.debt_ratio <= dr_q20:
                s = 6
                status = "行业前 20%（低负债）"
            elif dr_q50 and financial.debt_ratio <= dr_q50:
                s = 4
                status = "行业前 50%"
            elif dr_q80 and financial.debt_ratio <= dr_q80:
                s = 2
                status = "行业中等"
            else:
                s = 0
                status = "行业后 20%（高负债）"
        else:
            if financial.debt_ratio < 40:
                s, status = 6, "健康"
            elif financial.debt_ratio < 60:
                s, status = 4, "合理"
            elif financial.debt_ratio < 75:
                s, status = 2, "偏高"
            else:
                s, status = 0, "过高"
        score += s
        details.append({"item": "资产负债率", "value": f"{financial.debt_ratio:.1f}%", "score": s, "max": 6, "status": status})
    else:
        details.append({"item": "资产负债率", "value": "N/A", "score": 0, "max": 6, "status": "无数据"})

    return score, details


# ==================== 估值评分 ====================

def calculate_valuation_score(price: DailyPrice, financial: FinancialMetric, industry_stats: Optional[dict] = None) -> tuple[float, list[dict]]:
    """
    估值评分（满分 20）— 消除 PE 重复计算
    - PE（行业内排名）: +8
    - PB（行业内排名）: +5
    - 股息率（行业内排名）: +5
    - PS（如有营收数据）: +2
    注意：PE 只在此处计分一次，不在风险维度重复
    """
    score = 0
    details = []
    ind = industry_stats or {}

    # PE 评分（行业内排名）
    if price.pe is not None and price.pe > 0:
        if ind and ind.get("pe_q20") is not None:
            s, status = _industry_rank_score(price.pe, ind["pe_q20"], ind["pe_q50"], ind["pe_q80"], 8, lower_is_better=True)
        else:
            # 无行业数据时用绝对阈值兜底
            if price.pe <= 15:
                s, status = 8, "低估值"
            elif price.pe <= 30:
                s, status = 6, "合理"
            elif price.pe <= 50:
                s, status = 3, "偏高"
            else:
                s, status = 0, "高估值"
        score += s
        details.append({"item": "PE", "value": f"{price.pe:.1f}", "score": s, "max": 8, "status": status})
    else:
        details.append({"item": "PE", "value": "N/A", "score": 0, "max": 8, "status": "无数据"})

    # PB 评分（行业内排名）
    if price.pb is not None and price.pb > 0:
        if ind and ind.get("pb_q20") is not None:
            s, status = _industry_rank_score(price.pb, ind["pb_q20"], ind["pb_q50"], ind["pb_q80"], 5, lower_is_better=True)
        else:
            if price.pb <= 2:
                s, status = 5, "低估值"
            elif price.pb <= 5:
                s, status = 3, "合理"
            elif price.pb <= 10:
                s, status = 1, "偏高"
            else:
                s, status = 0, "高估值"
        score += s
        details.append({"item": "PB", "value": f"{price.pb:.1f}", "score": s, "max": 5, "status": status})
    else:
        details.append({"item": "PB", "value": "N/A", "score": 0, "max": 5, "status": "无数据"})

    # 股息率评分（行业内排名，越高越好）
    if price.dividend_yield is not None:
        if ind and ind.get("div_q50") is not None:
            div_q20 = ind.get("div_q20", 1)
            div_q50 = ind["div_q50"]
            div_q80 = ind.get("div_q80", 3)
            s, status = _industry_rank_score(price.dividend_yield, div_q20, div_q50, div_q80, 5, lower_is_better=False)
        else:
            if price.dividend_yield > 3:
                s, status = 5, "高股息"
            elif price.dividend_yield > 1:
                s, status = 3, "中等"
            else:
                s, status = 0, "低股息"
        score += s
        details.append({"item": "股息率", "value": f"{price.dividend_yield:.1f}%", "score": s, "max": 5, "status": status})
    else:
        details.append({"item": "股息率", "value": "N/A", "score": 0, "max": 5, "status": "无数据"})

    # PS 市销率（如有营收数据，用市值/营收计算）
    if price.market_cap and price.market_cap > 0 and financial.revenue and financial.revenue > 0:
        ps = price.market_cap / financial.revenue
        if ps <= 2:
            s = 2
            status = "低估值"
        elif ps <= 5:
            s = 1
            status = "合理"
        else:
            s = 0
            status = "偏高"
        score += s
        details.append({"item": "PS", "value": f"{ps:.1f}", "score": s, "max": 2, "status": status})
    else:
        details.append({"item": "PS", "value": "N/A", "score": 0, "max": 2, "status": "无数据"})

    return score, details


# ==================== 成长评分 ====================

def calculate_growth_score(financial: FinancialMetric) -> tuple[float, list[dict]]:
    """
    成长评分（满分 20）
    - 营收同比增长 > 20%: +8
    - 净利润同比增长 > 20%: +8
    - 双增长: +4
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

    # 复合增长
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


# ==================== 趋势评分 ====================

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


# ==================== 风险评分 ====================

def calculate_risk_score(financial: FinancialMetric, price: DailyPrice, tech: Optional[TechnicalIndicator] = None, industry_stats: Optional[dict] = None) -> tuple[float, list[dict]]:
    """
    风险评分（满分 10，分数越高风险越低）
    - 业绩稳定性: +3
    - 负债/现金流: +3
    - 波动率（行业内排名）: +4

    注意：PE 不在此处计分，避免与估值维度重复
    """
    score = 0
    details = []
    ind = industry_stats or {}

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

    # 波动率风险（行业内排名，低波动 = 高分）
    if tech and tech.ma20 is not None and price.close is not None and price.close > 0:
        # 用 Bollinger 带宽近似波动率
        if tech.boll_upper is not None and tech.boll_lower is not None and tech.ma20 > 0:
            bandwidth = (tech.boll_upper - tech.boll_lower) / tech.ma20 * 100
            if ind and ind.get("vol_q50") is not None:
                # 用行业内波动率中位数作为参考
                vol_q20 = ind.get("vol_q20", 15)
                vol_q50 = ind["vol_q50"]
                vol_q80 = ind.get("vol_q80", 40)
                s, status = _industry_rank_score(bandwidth, vol_q20, vol_q50, vol_q80, 4, lower_is_better=True)
            else:
                if bandwidth < 5:
                    s, status = 4, "低波动"
                elif bandwidth < 10:
                    s, status = 3, "中等波动"
                elif bandwidth < 15:
                    s, status = 1, "较高波动"
                else:
                    s, status = 0, "高波动"
            score += s
            details.append({"item": "波动率", "value": f"带宽{bandwidth:.1f}%", "score": s, "max": 4, "status": status})
        else:
            details.append({"item": "波动率", "value": "N/A", "score": 0, "max": 4, "status": "无布林带数据"})
    else:
        details.append({"item": "波动率", "value": "N/A", "score": 0, "max": 4, "status": "无数据"})

    return score, details


# ==================== 评级 ====================

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


# ==================== 单股评分 ====================

def score_stock(
    db: Session,
    stock_id: int,
    score_date: date,
    industry_stats: Optional[dict] = None,
) -> Optional[StockScore]:
    """
    对单只股票进行评分，结果写入 stock_scores 表
    """
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        return None

    # 获取 score_date 当日或之前的最新行情（防止前视偏差）
    price = (
        db.query(DailyPrice)
        .filter(DailyPrice.stock_id == stock_id, DailyPrice.trade_date <= score_date)
        .order_by(DailyPrice.trade_date.desc())
        .first()
    )
    if not price:
        return None

    # 获取 score_date 之前的最新财务数据（防止前视偏差）
    # 财务报告有滞后性：Q1 报告 4 月底出，Q2 报告 8 月底出，Q3 报告 10 月底出，年报 4 月底出
    financial = (
        db.query(FinancialMetric)
        .filter(FinancialMetric.stock_id == stock_id, FinancialMetric.report_period <= score_date)
        .order_by(FinancialMetric.report_period.desc())
        .first()
    )
    if not financial:
        return None

    # 获取前一期财务数据（用于趋势判断）
    prev_financial = (
        db.query(FinancialMetric)
        .filter(FinancialMetric.stock_id == stock_id, FinancialMetric.report_period < financial.report_period)
        .order_by(FinancialMetric.report_period.desc())
        .first()
    )

    # 获取 score_date 当日或之前的最新技术指标
    tech = (
        db.query(TechnicalIndicator)
        .filter(TechnicalIndicator.stock_id == stock_id, TechnicalIndicator.trade_date <= score_date)
        .order_by(TechnicalIndicator.trade_date.desc())
        .first()
    )

    # 获取行业统计
    ind_stats = None
    if industry_stats and stock.industry:
        ind_stats = industry_stats.get(stock.industry)

    # 计算各项评分
    quality_score, quality_details = calculate_quality_score(financial, prev_financial, ind_stats)
    valuation_score, valuation_details = calculate_valuation_score(price, financial, ind_stats)
    growth_score, growth_details = calculate_growth_score(financial)
    trend_score, trend_details = calculate_trend_score(price, tech)
    risk_score, risk_details = calculate_risk_score(financial, price, tech, ind_stats)

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

    db.flush()
    return score


# ==================== 批量评分 ====================

def score_all_stocks(db: Session, score_date: date) -> list[StockScore]:
    """对所有活跃股票进行评分（批量提交，每 100 只 flush 一次）"""
    stocks = db.query(Stock).filter(Stock.status == "ACTIVE").all()
    if not stocks:
        return []

    stock_ids = [s.id for s in stocks]

    # 批量计算行业统计（一次查询）
    industry_stats = _compute_industry_stats(db, stock_ids)

    results = []
    for i, stock in enumerate(stocks):
        s = score_stock(db, stock.id, score_date, industry_stats)
        if s:
            results.append(s)
        # 每 100 只 flush 一次，最后统一 commit
        if (i + 1) % 100 == 0:
            db.flush()
    db.commit()
    return results
