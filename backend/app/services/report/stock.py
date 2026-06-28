"""
个股深度分析报告生成模块 — 清算量化分析系统
从20年华尔街投资专家视角生成专业级个股研究报告
"""
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.technical_indicator import TechnicalIndicator
from app.models.report import Report
from app.core.constants import ReportType

from app.services.report.utils import (
    rating_text, signal_icon, score_bar, spark_line,
    quality_comment, valuation_comment, growth_comment,
    trend_comment, risk_comment,
)


# ==================== 个股深度分析报告（8000+字专业版）====================

def generate_stock_report(db: Session, stock_id: int, report_date: date) -> Report:
    """生成个股深度分析报告 — 从20年华尔街投资专家视角"""
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise ValueError("Stock not found")

    # 获取所有需要的数据
    score = db.query(StockScore).filter(
        StockScore.stock_id == stock_id, StockScore.score_date == report_date
    ).first()
    if not score:
        score = db.query(StockScore).filter(
            StockScore.stock_id == stock_id
        ).order_by(StockScore.score_date.desc()).first()

    signal = db.query(TradeSignal).filter(
        TradeSignal.stock_id == stock_id, TradeSignal.signal_date == report_date
    ).first()
    if not signal:
        signal = db.query(TradeSignal).filter(
            TradeSignal.stock_id == stock_id
        ).order_by(TradeSignal.signal_date.desc()).first()

    latest_price = db.query(DailyPrice).filter(
        DailyPrice.stock_id == stock_id
    ).order_by(DailyPrice.trade_date.desc()).first()

    prices_20 = db.query(DailyPrice).filter(
        DailyPrice.stock_id == stock_id
    ).order_by(DailyPrice.trade_date.desc()).limit(20).all()

    prices_60 = db.query(DailyPrice).filter(
        DailyPrice.stock_id == stock_id
    ).order_by(DailyPrice.trade_date.desc()).limit(60).all()

    financials = db.query(FinancialMetric).filter(
        FinancialMetric.stock_id == stock_id
    ).order_by(FinancialMetric.report_period.desc()).limit(4).all()

    tech = db.query(TechnicalIndicator).filter(
        TechnicalIndicator.stock_id == stock_id
    ).order_by(TechnicalIndicator.trade_date.desc()).first()

    peers = db.query(Stock).filter(
        Stock.industry == stock.industry, Stock.id != stock_id, Stock.status == "ACTIVE"
    ).all()
    peer_scores = []
    if peers:
        peer_ids = [p.id for p in peers]
        peer_map = {p.id: p for p in peers}
        # 批量查询同行最新评分（消除 N+1）
        from sqlalchemy import func as sqlfunc
        latest_score_sq = db.query(
            StockScore.stock_id, sqlfunc.max(StockScore.score_date).label("max_date")
        ).filter(StockScore.stock_id.in_(peer_ids)).group_by(StockScore.stock_id).subquery()
        peer_score_records = db.query(StockScore).join(
            latest_score_sq,
            (StockScore.stock_id == latest_score_sq.c.stock_id) &
            (StockScore.score_date == latest_score_sq.c.max_date)
        ).all()
        score_map = {sc.stock_id: sc for sc in peer_score_records}
        # 批量查询同行最新价格（消除 N+1）
        latest_price_sq = db.query(
            DailyPrice.stock_id, sqlfunc.max(DailyPrice.trade_date).label("max_date")
        ).filter(DailyPrice.stock_id.in_(peer_ids)).group_by(DailyPrice.stock_id).subquery()
        peer_price_records = db.query(DailyPrice).join(
            latest_price_sq,
            (DailyPrice.stock_id == latest_price_sq.c.stock_id) &
            (DailyPrice.trade_date == latest_price_sq.c.max_date)
        ).all()
        price_map = {pp.stock_id: pp for pp in peer_price_records}
        for pid in peer_ids:
            ps = score_map.get(pid)
            pp = price_map.get(pid)
            p = peer_map[pid]
            if ps and pp:
                peer_scores.append({"symbol": p.symbol, "name": p.name, "score": ps.total_score, "rating": ps.rating, "close": pp.close, "pe": pp.pe})

    # 价格统计
    if prices_60 and latest_price:
        high_60 = max(p.high for p in prices_60)
        low_60 = min(p.low for p in prices_60)
        avg_vol = sum(p.volume for p in prices_20) / len(prices_20) if prices_20 else 0
        price_change_20 = ((latest_price.close - prices_20[-1].close) / prices_20[-1].close * 100) if len(prices_20) >= 2 else 0
        price_change_60 = ((latest_price.close - prices_60[-1].close) / prices_60[-1].close * 100) if len(prices_60) >= 2 else 0
    else:
        high_60 = low_60 = avg_vol = price_change_20 = price_change_60 = 0

    # 价格走势迷你图
    close_prices = [p.close for p in reversed(prices_20)] if prices_20 else []
    price_spark = spark_line(close_prices) if close_prices else "数据不足"

    # === 生成报告 ===
    market_label = "A股" if stock.market == "A_SHARE" else "港股"
    md = f"""# {stock.symbol} {stock.name} 深度分析报告

> **报告日期:** {report_date} | **报告编号:** RPT-{report_date.strftime('%Y%m%d')}-{stock.symbol}
> **市场:** {market_label} | **交易所:** {stock.exchange} | **行业:** {stock.industry} | **板块:** {stock.sector}
> **综合评级:** {rating_text(score.rating) if score else '暂无评分'} | **综合评分:** {score.total_score:.0f}/100 if score else 'N/A'

---

## 一、公司概况与行业地位

### 1.1 公司简介

**{stock.name}**（{stock.symbol}.{stock.exchange}）是一家在{stock.exchange}上市的{stock.industry}行业龙头企业，隶属于{stock.sector}板块。作为{market_label}市场的重要标的，{stock.name}在{stock.industry}领域具有显著的市场影响力和竞争优势。

### 1.2 行业地位分析

"""
    if peer_scores:
        better_peers = [p for p in peer_scores if score and p["score"] < score.total_score]
        rank = len(better_peers) + 1
        total_peers = len(peer_scores) + 1
        md += f"在同行业 {total_peers} 家可比公司中，{stock.name}综合评分排名第 **{rank}** 位"
        if rank == 1:
            md += "，为行业内最优标的，具备绝对的竞争优势。"
        elif rank <= total_peers * 0.3:
            md += "，处于行业前列，具备较强的竞争力和市场话语权。"
        elif rank <= total_peers * 0.6:
            md += "，处于行业中游水平，需关注竞争对手的动态。"
        else:
            md += "，处于行业后列，需审视公司的竞争策略和转型方向。"
        md += "\n"
    else:
        md += f"> {stock.industry} 行业暂无其他可比公司数据，无法进行横向对比分析。\n"

    # 最新行情
    if latest_price:
        cap_str = f"{latest_price.market_cap:.0f} 亿" if latest_price.market_cap else "N/A"
        dy_str = f"{latest_price.dividend_yield:.2f}%" if latest_price.dividend_yield else "N/A"

        md += f"""
---

## 二、最新行情数据

### 2.1 核心行情指标

| 指标 | 数值 | 指标 | 数值 |
|------|------|------|------|
| 最新收盘价 | **{latest_price.close:.2f}** 元 | 今日开盘 | {latest_price.open:.2f} 元 |
| 最高价 | {latest_price.high:.2f} 元 | 最低价 | {latest_price.low:.2f} 元 |
| 成交量 | {latest_price.volume/10000:.0f} 万手 | 市盈率 (PE) | {latest_price.pe if latest_price.pe else 'N/A'} |
| 市净率 (PB) | {latest_price.pb if latest_price.pb else 'N/A'} | 总市值 | {cap_str} |
| 股息率 | {dy_str} | 换手率 | {(f"{latest_price.turnover_rate:.2f}" if latest_price.turnover_rate is not None else "N/A")}% |

### 2.2 近20日价格走势

```
{price_spark}
```

"""
        if prices_20 and len(prices_20) >= 2:
            high_20 = max(p.high for p in prices_20)
            low_20 = min(p.low for p in prices_20)
            amp_20 = (high_20 - low_20) / low_20 * 100 if low_20 > 0 else 0
            amp_60 = (high_60 - low_60) / low_60 * 100 if low_60 > 0 else 0
            md += f"""### 2.3 价格区间分析

| 周期 | 涨跌幅 | 最高价 | 最低价 | 振幅 |
|------|--------|--------|--------|------|
| 近 20 日 | {price_change_20:+.2f}% | {high_20:.2f} | {low_20:.2f} | {amp_20:.1f}% |
| 近 60 日 | {price_change_60:+.2f}% | {high_60:.2f} | {low_60:.2f} | {amp_60:.1f}% |

"""
        if latest_price and high_60 > 0:
            dist_high = (1 - latest_price.close / high_60) * 100
            dist_low = (latest_price.close / low_60 - 1) * 100
            md += f"""**价位定位分析:** 当前收盘价 {latest_price.close:.2f} 元，距60日高点 {high_60:.2f} 元有 **{dist_high:.1f}%** 的下行空间，距60日低点 {low_60:.2f} 元已上涨 **{dist_low:.1f}%**。"""
            if dist_high < 10:
                md += "当前价位接近阶段高点，追高风险较大，建议等待回调。"
            elif dist_low < 10:
                md += "当前价位接近阶段低点，可能是较好的建仓机会。"
            else:
                md += "当前价位处于区间中部，可关注方向突破。"
            md += "\n"
    else:
        md += "\n---\n\n## 二、最新行情\n\n> 暂无行情数据\n\n"

    # 技术面分析
    md += """---

## 三、技术面深度分析

"""
    if tech:
        ma_status = "多头排列" if tech.ma20 and tech.ma60 and tech.ma20 > tech.ma60 else "空头排列" if tech.ma20 and tech.ma60 and tech.ma20 < tech.ma60 else "交叉缠绕"
        ref_price = latest_price.close if latest_price else 0
        price_vs_ma20 = "站上" if ref_price > (tech.ma20 or 0) else "跌破"
        price_vs_ma60 = "站上" if ref_price > (tech.ma60 or 0) else "跌破"
        ma60_str = f"{tech.ma60:.2f}" if tech.ma60 else "N/A"
        ma120_str = f"{tech.ma120:.2f}" if tech.ma120 else "N/A"
        ma120_rel = "数据不足" if not tech.ma120 else ("站上MA120" if ref_price > tech.ma120 else "跌破MA120")

        if ma_status == "多头排列":
            ma_trend_desc = "均线呈多头排列，短期、中期趋势均向好，是典型的上升趋势形态。在技术分析中，多头排列意味着买方力量占据主导，回调至均线附近往往是较好的买入机会。"
            ma_advice = "建议在回调至MA20附近时分批建仓，止损设在MA60下方。"
        elif ma_status == "空头排列":
            ma_trend_desc = "均线呈空头排列，短期、中期趋势均偏弱，是典型的下降趋势形态。在空头排列修复之前，不宜盲目抄底。"
            ma_advice = "建议观望等待均线粘合或金叉信号，过早介入可能面临持续下跌风险。"
        else:
            ma_trend_desc = "均线交叉缠绕，市场处于方向选择阶段。这种形态下，突破方向将决定中期走势。"
            ma_advice = "建议等待方向明确后再行操作，可在突破时顺势介入。"

        macd_signal = "多头" if tech.macd > (tech.macd_signal or 0) else "空头"
        if (tech.macd or 0) > (tech.macd_signal or 0):
            macd_desc = "MACD在信号线上方运行，柱状图为红，显示短期动能偏强。MACD金叉是重要的买入信号，结合成交量放大可增强信号可靠性。"
        else:
            macd_desc = "MACD在信号线下方运行，柱状图为绿，显示短期动能偏弱。需等待MACD金叉信号确认后再考虑介入。"

        rsi_val = tech.rsi14 or 50
        if rsi_val > 70:
            rsi_desc = f"RSI({rsi_val:.0f})处于超买区间，短期存在回调压力。从历史经验看，RSI超过70后，标的往往会出现5-10%的技术性回调。"
        elif rsi_val < 30:
            rsi_desc = f"RSI({rsi_val:.0f})处于超卖区间，可能存在反弹机会。超卖信号在优质标的上往往预示着较好的短线买入时机。"
        else:
            rsi_desc = f"RSI({rsi_val:.0f})处于中性区间，暂无明显的超买超卖信号。"

        md += f"""### 3.1 均线系统分析

| 均线 | 数值 | 与现价关系 | 技术含义 |
|------|------|-----------|----------|
| MA20（短期） | {tech.ma20:.2f} | {price_vs_ma20}MA20 | 短期趋势{'向好' if price_vs_ma20 == '站上' else '偏弱'} |
| MA60（中期） | {ma60_str} | {price_vs_ma60 + 'MA60' if tech.ma60 else '数据不足'} | 中期趋势{'向好' if price_vs_ma60 == '站上' else '偏弱'} |
| MA120（长期） | {ma120_str} | {ma120_rel} | 长期趋势{'向好' if ma120_rel == '站上MA120' else '偏弱或数据不足'} |

**均线形态:** {ma_status}

**专家解读:** {ma_trend_desc}

**操作建议:** {ma_advice}

### 3.2 MACD 动能分析

| 指标 | 数值 | 信号 |
|------|------|------|
| MACD | {tech.macd:.4f} | {macd_signal} |
| 信号线 | {tech.macd_signal:.4f} | — |
| 柱状图 | {tech.macd_hist:.4f} | {'红柱（多头动能）' if (tech.macd_hist or 0) > 0 else '绿柱（空头动能）'} |

**专家解读:** {macd_desc}

### 3.3 RSI 相对强弱分析

**RSI(14) = {rsi_val:.1f}**

**专家解读:** {rsi_desc}

### 3.4 成交量分析

| 指标 | 数值 |
|------|------|
| 5日均量 | {tech.volume_ma5/10000:.0f} 万手 |
| 20日均量 | {tech.volume_ma20/10000:.0f} 万手 |
| 量比 (5/20) | {tech.volume_ma5/tech.volume_ma20:.2f} |

"""
        if tech.volume_ma5 > tech.volume_ma20 * 1.2:
            vol_desc = "成交量显著放大，资金关注度提升，可能是主力资金介入的信号。放量上涨是健康的量价关系，放量下跌则需警惕。"
        elif tech.volume_ma5 > tech.volume_ma20 * 1.1:
            vol_desc = "成交量温和放大，市场参与度有所提升，整体量价关系健康。"
        elif tech.volume_ma5 < tech.volume_ma20 * 0.8:
            vol_desc = "成交量明显萎缩，市场参与度下降。缩量下跌可能是抛压减弱的信号，缩量上涨则需警惕上攻乏力。"
        else:
            vol_desc = "成交量保持平稳，市场情绪稳定。"

        md += f"**专家解读:** {vol_desc}\n"
    else:
        md += "> 技术指标数据不足，无法进行技术面分析。建议等待更多交易数据积累后再做判断。\n\n"

    # 财务分析
    md += """
---

## 四、财务深度分析

"""
    if financials:
        md += """### 4.1 核心财务指标（近四期）

| 报告期 | 营收(亿) | 营收增速 | 净利润(亿) | 利润增速 | 毛利率 | ROE | 负债率 |
|--------|----------|----------|------------|----------|--------|-----|--------|
"""
        for f in financials:
            rev = f"{f.revenue:.1f}" if f.revenue else "N/A"
            rev_yoy = f"{f.revenue_yoy:+.1f}%" if f.revenue_yoy is not None else "N/A"
            np_ = f"{f.net_profit:.1f}" if f.net_profit else "N/A"
            np_yoy = f"{f.net_profit_yoy:+.1f}%" if f.net_profit_yoy is not None else "N/A"
            gm = f"{f.gross_margin:.1f}%" if f.gross_margin is not None else "N/A"
            roe = f"{f.roe:.1f}%" if f.roe is not None else "N/A"
            dr = f"{f.debt_ratio:.1f}%" if f.debt_ratio is not None else "N/A"
            md += f"| {f.report_period} | {rev} | {rev_yoy} | {np_} | {np_yoy} | {gm} | {roe} | {dr} |\n"

        # 趋势分析
        if len(financials) >= 2:
            latest_f = financials[0]
            prev_f = financials[1]
            md += "\n### 4.2 财务趋势深度解读\n\n"

            if latest_f.revenue and prev_f.revenue:
                rev_change = (latest_f.revenue / prev_f.revenue - 1) * 100
                rev_trend = "增长" if latest_f.revenue > prev_f.revenue else "下滑"
                md += f"**营收趋势:** 最新报告期营收 {latest_f.revenue:.1f} 亿，较上期{rev_trend} **{abs(rev_change):.1f}%**。"
                if rev_change > 20:
                    md += "营收高速增长，显示公司业务扩张势头强劲，市场份额持续提升。\n\n"
                elif rev_change > 5:
                    md += "营收稳健增长，公司经营状况良好。\n\n"
                elif rev_change > 0:
                    md += "营收小幅增长，增速放缓需关注未来增长动力。\n\n"
                else:
                    md += "营收出现下滑，需深入分析原因——是行业周期性因素还是公司竞争力下降。\n\n"

            if latest_f.net_profit and prev_f.net_profit:
                np_change = (latest_f.net_profit / prev_f.net_profit - 1) * 100
                np_trend = "增长" if latest_f.net_profit > prev_f.net_profit else "下滑"
                md += f"**利润趋势:** 最新报告期净利润 {latest_f.net_profit:.1f} 亿，较上期{np_trend} **{abs(np_change):.1f}%**。"
                if np_change > 20:
                    md += "利润高速增长，盈利能力显著提升，可能受益于产品提价或成本控制。\n\n"
                elif np_change > 0:
                    md += "利润稳步增长，盈利质量良好。\n\n"
                else:
                    md += "利润出现下滑，需关注成本压力和竞争格局变化。\n\n"

            if latest_f.roe is not None:
                md += f"**盈利能力:** ROE为 {latest_f.roe:.1f}%。"
                if latest_f.roe > 20:
                    md += "ROE超过20%，盈利能力卓越，属于行业顶尖水平。巴菲特最看重的财务指标之一就是ROE，持续高ROE是企业护城河的直接体现。\n\n"
                elif latest_f.roe > 15:
                    md += "ROE超过15%，盈利能力优秀，具备良好的股东回报能力。\n\n"
                elif latest_f.roe > 10:
                    md += "ROE处于中等水平，盈利能力尚可，但仍有提升空间。\n\n"
                else:
                    md += "ROE偏低，盈利能力较弱，需审视公司的资本配置效率。\n\n"

            if latest_f.debt_ratio is not None:
                md += f"**财务健康:** 资产负债率 {latest_f.debt_ratio:.1f}%。"
                if latest_f.debt_ratio > 70:
                    md += "负债水平偏高，需密切关注偿债能力和现金流状况。高杠杆经营在景气周期能放大收益，但在下行周期也会放大风险。\n\n"
                elif latest_f.debt_ratio > 50:
                    md += "负债水平适中，财务结构基本健康。\n\n"
                else:
                    md += "负债水平较低，财务结构稳健，抗风险能力较强。\n\n"

        if financials[0].eps is not None:
            md += f"**每股收益 (EPS):** {financials[0].eps:.2f} 元"
            if latest_price and latest_price.close and financials[0].eps > 0:
                implied_pe = latest_price.close / financials[0].eps
                md += f"（隐含PE约 {implied_pe:.1f} 倍）"
            md += "\n"
    else:
        md += "> 该标的暂无财务数据（部分港股财务数据可能暂不支持）。\n"

    # 估值分析
    md += f"""

---

## 五、估值分析与投资价值判断

"""
    if latest_price and (latest_price.pe is not None or latest_price.pb is not None):
        md += """### 5.1 估值指标一览

| 估值指标 | 当前值 | 合理区间 | 判断 |
|----------|--------|----------|------|
"""
        if latest_price.pe is not None:
            pe_judge = "低估" if latest_price.pe < 15 else "合理" if latest_price.pe < 30 else "偏高" if latest_price.pe < 50 else "高估"
            md += f"| 市盈率 (PE) | {latest_price.pe:.1f} | 15-30 | {pe_judge} |\n"
        if latest_price.pb is not None:
            pb_judge = "低估" if latest_price.pb < 1.5 else "合理" if latest_price.pb < 3 else "偏高" if latest_price.pb < 5 else "高估"
            md += f"| 市净率 (PB) | {latest_price.pb:.1f} | 1-3 | {pb_judge} |\n"
        if latest_price.dividend_yield is not None:
            dy_judge = "高股息" if latest_price.dividend_yield > 3 else "中等" if latest_price.dividend_yield > 1 else "低股息"
            md += f"| 股息率 | {latest_price.dividend_yield:.2f}% | 1-3% | {dy_judge} |\n"

        md += "\n### 5.2 估值综合判断\n\n"
        if latest_price.pe and latest_price.pe < 20 and latest_price.pb and latest_price.pb < 2:
            md += """当前估值处于较低水平，PE和PB均低于合理区间下限，具备充足的安全边际。从价值投资的角度来看，这是一个具有吸引力的估值区间。格雷厄姆曾说："投资的本质是在充分的安全边际下买入。"当前标的符合这一原则。

**投资建议:** 适合价值型投资者重点关注，可在回调时分批建仓。"""
        elif latest_price.pe and latest_price.pe < 30:
            md += """估值处于合理区间，既没有明显的低估机会，也不存在高估风险。这个估值水平下，投资决策更多取决于公司的成长性和行业前景。

**投资建议:** 需结合成长性判断是否具备投资价值，高成长可支撑当前估值，低成长则缺乏吸引力。"""
        else:
            md += """估值偏高，当前价格已经反映了较多的乐观预期。在高估值状态下，一旦业绩不及预期，股价可能面临较大的回调压力。

**投资建议:** 建议等待更好的买入时机，或者设定较高的安全边际后再考虑介入。"""
        md += "\n"
    else:
        md += "> 该标的暂无估值数据，无法进行估值分析。\n"

    # 评分详解
    md += f"""

---

## 六、综合评分详解

"""
    if score:
        md += f"""### 6.1 五维评分总览

**综合评分: {score.total_score:.0f}/100 — {rating_text(score.rating)}**

| 维度 | 得分 | 满分 | 占比 | 评价 |
|------|------|------|------|------|
| 质量分 | {score.quality_score:.0f} | 30 | {score.quality_score/30*100:.0f}% | {quality_comment(score.quality_score)} |
| 估值分 | {score.valuation_score:.0f} | 20 | {score.valuation_score/20*100:.0f}% | {valuation_comment(score.valuation_score)} |
| 成长分 | {score.growth_score:.0f} | 20 | {score.growth_score/20*100:.0f}% | {growth_comment(score.growth_score)} |
| 趋势分 | {score.trend_score:.0f} | 20 | {score.trend_score/20*100:.0f}% | {trend_comment(score.trend_score)} |
| 风险分 | {score.risk_score:.0f} | 10 | {score.risk_score/10*100:.0f}% | {risk_comment(score.risk_score)} |

### 6.2 评分雷达图

```
质量  {score_bar(score.quality_score, 30)}
估值  {score_bar(score.valuation_score, 20)}
成长  {score_bar(score.growth_score, 20)}
趋势  {score_bar(score.trend_score, 20)}
风险  {score_bar(score.risk_score, 10)}
```

### 6.3 评分解读

"""
        # 根据评分给出综合解读
        strengths = []
        weaknesses = []
        if score.quality_score >= 22:
            strengths.append("质量")
        else:
            weaknesses.append("质量")
        if score.valuation_score >= 14:
            strengths.append("估值")
        else:
            weaknesses.append("估值")
        if score.growth_score >= 14:
            strengths.append("成长")
        else:
            weaknesses.append("成长")
        if score.trend_score >= 14:
            strengths.append("趋势")
        else:
            weaknesses.append("趋势")
        if score.risk_score >= 7:
            strengths.append("风控")
        else:
            weaknesses.append("风控")

        if strengths:
            md += f"**优势维度:** {', '.join(strengths)}——"
            md += "这些维度表现突出，是支撑当前评分的核心因素。\n\n"
        if weaknesses:
            md += f"**待改善维度:** {', '.join(weaknesses)}——"
            md += "这些维度表现一般，是制约评分进一步提升的瓶颈。\n\n"
    else:
        md += "> 该标的暂无评分数据。\n"

    # 同业比较
    md += f"""

---

## 七、同业竞争格局分析

"""
    if peer_scores:
        all_peers = [{"symbol": stock.symbol, "name": stock.name, "score": score.total_score if score else 0, "rating": score.rating if score else "N/A", "close": latest_price.close if latest_price else 0, "pe": latest_price.pe if latest_price else None}] + peer_scores
        all_peers.sort(key=lambda x: x["score"], reverse=True)

        # 只展示 Top 20 + 当前标的
        rank = next(i for i, p in enumerate(all_peers, 1) if p["symbol"] == stock.symbol)
        show_peers = all_peers[:20]
        # 如果当前标的不在 Top 20，追加到末尾
        if rank > 20:
            current_peer = all_peers[rank - 1]
            show_peers.append(current_peer)

        md += f"### 7.1 {stock.industry}行业排名（Top 20）\n\n"
        md += "| 排名 | 代码 | 名称 | 评分 | 评级 | 收盘价 | PE |\n"
        md += "|------|------|------|------|------|--------|------|\n"
        for i, p in enumerate(show_peers, 1):
            actual_rank = next(j for j, x in enumerate(all_peers, 1) if x["symbol"] == p["symbol"])
            marker = " ← **当前标的**" if p["symbol"] == stock.symbol else ""
            md += f"| {actual_rank} | {p['symbol']} | {p['name']} | {p['score']:.0f} | {p['rating']} | {p['close']:.2f} | {p['pe'] or 'N/A'}{marker} |\n"

        md += f"\n### 7.2 竞争力评估\n\n"
        md += f"在 {len(all_peers)} 家同行业公司中，{stock.name}综合评分排名第 **{rank}** 位。"
        if rank == 1:
            md += "作为行业龙头，具备绝对的竞争优势和定价权。"
        elif rank <= len(all_peers) * 0.3:
            md += "处于行业前列，具备较强的竞争力和成长潜力。"
        elif rank <= len(all_peers) * 0.6:
            md += "处于行业中游水平，需关注行业竞争格局变化。"
        else:
            md += "处于行业后列，竞争力相对较弱，需审视公司战略方向。"
        md += "\n"
    else:
        md += f"> {stock.industry} 行业暂无其他可比公司数据。\n"

    # 操作建议
    md += f"""

---

## 八、操作策略建议

"""
    if signal:
        entry = f"{signal.entry_price:.2f}" if signal.entry_price else "N/A"
        target = f"{signal.target_price:.2f}" if signal.target_price else "N/A"
        stop_loss = f"{signal.stop_loss_price:.2f}" if signal.stop_loss_price else "N/A"
        target_up = f"+{(signal.target_price/signal.entry_price-1)*100:.1f}%" if signal.target_price and signal.entry_price else ""
        stop_down = f"-{(1-signal.stop_loss_price/signal.entry_price)*100:.1f}%" if signal.stop_loss_price and signal.entry_price else ""
        strength_stars = "★" * (signal.signal_strength or 0) + "☆" * (5 - (signal.signal_strength or 0))

        md += f"""### 8.1 交易信号

| 项目 | 建议 |
|------|------|
| 信号类型 | {signal_icon(signal.signal_type)} **{signal.signal_type}** — {rating_text(signal.signal_type)} |
| 信号强度 | {strength_stars} |
| 建议仓位 | {signal.suggested_position}% |
| 入场价位 | {entry} 元 |
| 目标价位 | {target} 元 {target_up} |
| 止损价位 | {stop_loss} 元 {stop_down} |
| 持有周期 | {signal.holding_period or '—'} |

"""
        if signal.signal_type in ("BUY", "ADD"):
            md += f"""### 8.2 买入策略

1. **建仓节奏:** 建议在 {entry} 元附近分批建仓，首次仓位不超过建议仓位的 30%
2. **加仓条件:** 价格回调至 {float(entry) * 0.97:.2f} 元附近可加仓至50%，突破 {float(entry) * 1.03:.2f} 元可追加至上限
3. **止损纪律:** 若价格跌破止损价 {stop_loss} 元，需严格执行止损，不找借口
4. **止盈策略:** 价格上涨至目标价 {target} 元附近，可分批减仓锁定利润
5. **持有周期:** 预计 {signal.holding_period or '视情况而定'}，期间持续跟踪评分变化
"""
        elif signal.signal_type in ("REDUCE", "SELL"):
            md += f"""### 8.2 卖出策略

1. **减仓节奏:** 建议在反弹时逐步减仓，每次减仓不超过持仓的30%
2. **止损纪律:** 若价格跌破 {stop_loss} 元，应果断清仓
3. **观察要点:** 关注成交量变化，放量下跌时加速减仓
4. **重新评估:** 卖出后持续跟踪，若评分回升至75以上可重新考虑介入
"""
        else:
            md += """### 8.2 观望策略

当前信号为观望，建议持续跟踪评分变化，等待明确的买入或卖出信号后再行动。观望期间可做好以下准备：
1. 设定买入触发条件（如评分突破75、MACD金叉等）
2. 设定卖出触发条件（如评分跌破60、跌破关键支撑等）
3. 做好资金准备，确保信号触发时能及时执行
"""
    else:
        md += "> 暂无交易信号。建议持续跟踪标的评分变化，等待信号生成。\n\n"

    # 风险提示
    md += """
---

## 九、风险提示

"""
    risks = []
    if latest_price and latest_price.pe and latest_price.pe > 50:
        risks.append(("估值风险", f"当前PE为 {latest_price.pe:.1f}，估值偏高，存在回调压力。高估值标的对业绩增速要求极高，一旦增速放缓可能面临戴维斯双杀。"))
    if score and score.risk_score < 5:
        risks.append(("财务风险", "风险评分偏低，需关注财务健康状况。低风险评分往往意味着公司在负债、现金流或业绩稳定性方面存在问题。"))
    if tech and tech.ma20 and tech.ma60 and tech.ma20 < tech.ma60:
        risks.append(("趋势风险", "均线空头排列，短期趋势偏弱。在趋势修复之前，标的可能继续承压。"))
    if score and score.trend_score < 5:
        risks.append(("技术风险", "技术面评分较低，需等待企稳信号。低技术评分意味着当前不是理想的介入时机。"))
    if not latest_price or (latest_price.pe is None and latest_price.pb is None):
        risks.append(("数据风险", "估值数据缺失，无法进行完整的估值分析。数据缺失会增加投资决策的不确定性。"))
    if latest_price and latest_price.dividend_yield is not None and latest_price.dividend_yield < 0.5:
        risks.append(("回报风险", "股息率极低，投资者主要依赖资本利得获得回报，在市场低迷时缺乏股息保护。"))

    if risks:
        for i, (risk_type, risk_desc) in enumerate(risks, 1):
            md += f"{i}. ⚠️ **{risk_type}:** {risk_desc}\n"
    else:
        md += "当前未发现明显风险因素。但投资者仍需保持警惕，密切关注市场和公司动态。\n"

    md += f"""

---

## 十、总结与投资建议

"""
    if score:
        if score.total_score >= 85:
            md += f"""**{stock.name}** 当前综合评分为 **{score.total_score:.0f}分**，达到"强烈买入"级别。该标的在质量、估值、成长、趋势等多个维度均表现出色，是当前市场中难得的优质投资标的。

**核心投资逻辑:**
- 基本面扎实，盈利能力突出
- 估值具备安全边际，下行风险有限
- 技术面确认上行趋势，上涨动能充足

**操作建议:** 建议积极参与，采用分批建仓策略，严格控制止损。"""
        elif score.total_score >= 75:
            md += f"""**{stock.name}** 当前综合评分为 **{score.total_score:.0f}分**，达到"建议加仓"级别。该标的整体表现良好，部分维度有亮点，适合已有底仓的投资者适度加仓。

**核心投资逻辑:**
- 基本面稳健，具备一定竞争优势
- 估值合理，风险收益比适中
- 趋势向好，但仍需确认

**操作建议:** 建议在回调时适度加仓，控制好仓位节奏。"""
        elif score.total_score >= 65:
            md += f"""**{stock.name}** 当前综合评分为 **{score.total_score:.0f}分**，处于"观望等待"区间。该标的部分维度表现尚可，但整体缺乏明确的方向性信号。

**核心关注点:**
- 等待基本面或技术面出现积极变化
- 关注评分趋势，若持续走强可考虑介入
- 做好资金准备，信号触发时及时行动

**操作建议:** 建议观望等待，不急于入场。"""
        else:
            md += f"""**{stock.name}** 当前综合评分为 **{score.total_score:.0f}分**，评分偏低。该标的在多个维度存在不足，投资风险较高。

**核心风险点:**
- 基本面或估值存在明显问题
- 技术面偏弱，下跌趋势未止
- 投资回报的不确定性较高

**操作建议:** 建议回避或减仓，等待基本面改善信号。"""
        md += "\n"

    md += f"""

---

> **免责声明:** 本报告由清算量化分析系统自动生成，基于 {report_date} 公开市场数据和多维量化评分模型，仅供研究参考，不构成任何投资建议。投资有风险，入市需谨慎。

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 清算量化分析系统 v2.0*
"""

    # AI 个股深度分析（DeepSeek）
    try:
        import logging
        logging.getLogger(__name__).info("开始生成 AI 个股分析...")
        from app.services.ai_service import generate_ai_stock_analysis
        ai_stock_data = {
            "name": stock.name,
            "symbol": stock.symbol,
            "market": stock.market,
            "industry": stock.industry,
            "total_score": score.total_score if score else 0,
            "rating": score.rating if score else "N/A",
            "quality_score": score.quality_score if score else 0,
            "valuation_score": score.valuation_score if score else 0,
            "growth_score": score.growth_score if score else 0,
            "trend_score": score.trend_score if score else 0,
            "risk_score": score.risk_score if score else 0,
            "close": latest_price.close if latest_price else None,
            "pe": latest_price.pe if latest_price else None,
            "pb": latest_price.pb if latest_price else None,
            "market_cap": latest_price.market_cap if latest_price else None,
            "dividend_yield": latest_price.dividend_yield if latest_price else None,
            "rsi14": tech.rsi14 if tech else None,
            "macd": tech.macd if tech else None,
            "ma20": tech.ma20 if tech else None,
            "ma60": tech.ma60 if tech else None,
            "signal_type": signal.signal_type if signal else None,
            "signal_strength": signal.signal_strength if signal else None,
            "entry_price": signal.entry_price if signal else None,
            "stop_loss": signal.stop_loss_price if signal else None,
            "financials": [{"period": f.report_period, "revenue_yoy": f.revenue_yoy, "net_profit_yoy": f.net_profit_yoy, "roe": f.roe} for f in financials[:4]],
        }
        ai_analysis = generate_ai_stock_analysis(db, ai_stock_data)
        logging.getLogger(__name__).info(f"AI 分析结果长度: {len(ai_analysis) if ai_analysis else 0}")
        if ai_analysis:
            md += f"""

---

## AI 深度洞察

> 以下分析由 DeepSeek 大模型生成，基于量化模型数据，仅供参考。

{ai_analysis}

"""
    except Exception as e:
        import logging
        import traceback
        logging.getLogger(__name__).warning(f"AI 个股分析生成失败: {e}")
        logging.getLogger(__name__).warning(traceback.format_exc())

    report = Report(
        report_date=report_date,
        report_type=ReportType.STOCK,
        title=f"{stock.symbol} {stock.name} 深度分析报告 — {report_date}",
        summary=f"{stock.name} | 评分 {score.total_score:.0f}/100 | 评级 {rating_text(score.rating)} | 收盘 {latest_price.close:.2f}元" if score and latest_price else f"{stock.name} 深度分析报告",
        content_markdown=md,
        content_json={
            "stock_id": stock_id,
            "symbol": stock.symbol,
            "name": stock.name,
            "market": stock.market,
            "industry": stock.industry,
            "score": score.total_score if score else None,
            "rating": score.rating if score else None,
            "signal_type": signal.signal_type if signal else None,
            "close": latest_price.close if latest_price else None,
            "pe": latest_price.pe if latest_price else None,
            "pb": latest_price.pb if latest_price else None,
        },
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
