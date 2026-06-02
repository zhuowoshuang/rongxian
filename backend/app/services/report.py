"""
报告生成服务
生成详细的每日策略报告和个股深度分析报告
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


# ==================== 投资风格配置 ====================

STYLE_CONFIG = {
    "steady": {
        "name": "稳健型",
        "icon": "🛡️",
        "desc": "追求稳定收益，注重风险控制，偏好低波动、高股息的大盘蓝筹",
        "color": "blue",
        "max_position": 60,
        "single_stock_max": 8,
        "score_weights": {"quality": 1.5, "valuation": 1.3, "growth": 0.8, "trend": 0.7, "risk": 1.5},
        "min_score": 70,
        "risk_tolerance": "低",
        "suitable": "风险厌恶型投资者、退休人群、资金保值需求者",
        "strategy_desc": "以基本面扎实、盈利能力稳定的蓝筹股为核心，辅以高股息标的，通过分散持仓降低波动，追求长期稳健增值。",
    },
    "aggressive": {
        "name": "进取型",
        "icon": "🚀",
        "desc": "追求超额收益，承受较高波动，偏好高成长、强趋势标的",
        "color": "purple",
        "max_position": 90,
        "single_stock_max": 15,
        "score_weights": {"quality": 0.8, "valuation": 0.7, "growth": 1.5, "trend": 1.5, "risk": 0.6},
        "min_score": 60,
        "risk_tolerance": "高",
        "suitable": "风险承受能力较强的年轻人、专业投资者、追求高收益者",
        "strategy_desc": "聚焦高成长赛道和强势趋势标的，适度集中持仓，通过精选个股和波段操作追求显著超额收益。",
    },
    "conservative": {
        "name": "保守型",
        "icon": "🏦",
        "desc": "以本金安全为第一目标，偏好低估值、高安全边际的价值股",
        "color": "green",
        "max_position": 40,
        "single_stock_max": 6,
        "score_weights": {"quality": 1.3, "valuation": 1.5, "growth": 0.6, "trend": 0.5, "risk": 1.8},
        "min_score": 75,
        "risk_tolerance": "极低",
        "suitable": "风险极度厌恶者、大资金保守配置、资产保值需求者",
        "strategy_desc": "严格筛选低估值、高安全边际的标的，仓位严格控制，宁可错过不可做错，以绝对收益为目标。",
    },
}


# ==================== 评分维度文字解读 ====================

def _rating_text(rating: str) -> str:
    return {"BUY": "强烈买入", "ADD": "建议加仓", "WATCH": "观望等待", "REDUCE": "建议减仓", "SELL": "建议卖出"}.get(rating, rating)


def _signal_icon(sig_type: str) -> str:
    return {"BUY": "🟢", "ADD": "🔵", "WATCH": "⚪", "REDUCE": "🟡", "SELL": "🔴"}.get(sig_type, "⚪")


def _score_bar(score: float,满分: float) -> str:
    pct = score / 满分 * 100 if 满分 > 0 else 0
    filled = int(pct / 10)
    return "█" * filled + "░" * (10 - filled) + f" {score:.0f}/{满分:.0f}"


def _quality_comment(q: float) -> str:
    if q >= 25: return "公司质地优秀，盈利能力突出，现金流健康"
    if q >= 18: return "公司质地良好，具备一定竞争优势"
    if q >= 12: return "公司质地一般，部分指标有待改善"
    return "公司质地偏弱，需关注经营风险"


def _valuation_comment(v: float) -> str:
    if v >= 16: return "估值处于较低水平，具备安全边际"
    if v >= 10: return "估值合理，处于历史中位水平"
    if v >= 5: return "估值偏高，需警惕回调风险"
    return "估值较高，当前价位缺乏吸引力"


def _growth_comment(g: float) -> str:
    if g >= 16: return "成长性突出，营收和利润保持高增长"
    if g >= 10: return "成长性良好，业绩稳步增长"
    if g >= 5: return "成长性一般，增速有所放缓"
    return "成长性较弱，业绩面临下滑压力"


def _trend_comment(t: float) -> str:
    if t >= 16: return "技术面强势，均线多头排列，量价配合良好"
    if t >= 10: return "技术面偏强，整体趋势向好"
    if t >= 5: return "技术面中性，短期方向不明朗"
    return "技术面偏弱，均线空头排列，需等待企稳信号"


def _risk_comment(r: float) -> str:
    if r >= 8: return "风险可控，财务稳健，业绩稳定"
    if r >= 5: return "风险适中，需关注部分指标变化"
    return "风险偏高，需密切关注财务和经营变化"


# ==================== 每日策略报告 ====================

def generate_daily_report(db: Session, report_date: date, market_filter: list[str] = None, style: str = None) -> Report:
    """生成详细的每日策略报告，支持风格化定制"""
    signals = db.query(TradeSignal).filter(TradeSignal.signal_date == report_date).all()

    # 按类型分类信号
    dist = {"BUY": [], "ADD": [], "WATCH": [], "REDUCE": [], "SELL": []}
    for s in signals:
        stock = db.query(Stock).filter(Stock.id == s.stock_id).first()
        if not stock:
            continue
        score = db.query(StockScore).filter(
            StockScore.stock_id == s.stock_id, StockScore.score_date == report_date
        ).first()
        price = db.query(DailyPrice).filter(
            DailyPrice.stock_id == s.stock_id
        ).order_by(DailyPrice.trade_date.desc()).first()

        item = {
            "symbol": stock.symbol,
            "name": stock.name,
            "market": stock.market,
            "industry": stock.industry,
            "strength": s.signal_strength,
            "position": s.suggested_position,
            "entry_price": s.entry_price,
            "target_price": s.target_price,
            "stop_loss": s.stop_loss_price,
            "holding_period": s.holding_period,
            "logic": s.logic_json,
            "total_score": score.total_score if score else 0,
            "quality_score": score.quality_score if score else 0,
            "valuation_score": score.valuation_score if score else 0,
            "growth_score": score.growth_score if score else 0,
            "trend_score": score.trend_score if score else 0,
            "risk_score": score.risk_score if score else 0,
            "rating": score.rating if score else "N/A",
            "close": price.close if price else None,
            "pe": price.pe if price else None,
            "pb": price.pb if price else None,
        }
        dist.get(s.signal_type, []).append(item)

    # 市场情绪判断
    buy_add = len(dist["BUY"]) + len(dist["ADD"])
    reduce_sell = len(dist["REDUCE"]) + len(dist["SELL"])
    total = len(signals)

    if buy_add > reduce_sell * 2:
        market_status = "明显偏多"
        mood_desc = "市场情绪积极，多数标的呈现买入或加仓信号，适合适度提升仓位。"
    elif buy_add > reduce_sell:
        market_status = "中性偏多"
        mood_desc = "市场整体偏暖，但分化明显，建议精选个股、分批建仓。"
    elif reduce_sell > buy_add * 2:
        market_status = "明显偏空"
        mood_desc = "市场情绪低迷，多数标的发出减仓或卖出信号，建议降低仓位、控制风险。"
    elif reduce_sell > buy_add:
        market_status = "中性偏空"
        mood_desc = "市场承压，建议谨慎操作，减少新开仓，等待企稳信号。"
    else:
        market_status = "中性震荡"
        mood_desc = "多空力量均衡，市场处于震荡格局，建议维持现有仓位、观望为主。"

    # 风格化处理
    cfg = STYLE_CONFIG.get(style) if style else None
    style_label = f"（{cfg['name']}版）" if cfg else ""
    style_header = f"\n> **投资风格:** {cfg['icon']} {cfg['name']} — {cfg['desc']}\n" if cfg else ""

    # 按风格过滤和排序推荐标的
    if cfg:
        weights = cfg["score_weights"]
        for sig_list in dist.values():
            for item in sig_list:
                item["_style_score"] = (
                    item["quality_score"] * weights["quality"]
                    + item["valuation_score"] * weights["valuation"]
                    + item["growth_score"] * weights["growth"]
                    + item["trend_score"] * weights["trend"]
                    + item["risk_score"] * weights["risk"]
                )
        # 对买入/加仓信号按风格加权分排序
        dist["BUY"].sort(key=lambda x: x.get("_style_score", 0), reverse=True)
        dist["ADD"].sort(key=lambda x: x.get("_style_score", 0), reverse=True)

    # 生成详细 Markdown
    md = f"""# 每日策略报告{style_label}

> **报告日期:** {report_date}
> **市场状态:** {market_status}
> **信号总数:** {total} 只 | 买入 {len(dist["BUY"])} | 加仓 {len(dist["ADD"])} | 观望 {len(dist["WATCH"])} | 减仓 {len(dist["REDUCE"])} | 卖出 {len(dist["SELL"])}{style_header}

---

## 一、市场综述

{mood_desc}

当前共覆盖 **{total}** 只标的（A股 + 港股），信号分布如下：

| 信号类型 | 数量 | 占比 | 含义 |
|---------|------|------|------|
| 🟢 买入 | {len(dist["BUY"])} | {len(dist["BUY"])/max(total,1)*100:.0f}% | 强烈看好，建议建仓 |
| 🔵 加仓 | {len(dist["ADD"])} | {len(dist["ADD"])/max(total,1)*100:.0f}% | 趋势确认，可加仓 |
| ⚪ 观望 | {len(dist["WATCH"])} | {len(dist["WATCH"])/max(total,1)*100:.0f}% | 方向不明，等待信号 |
| 🟡 减仓 | {len(dist["REDUCE"])} | {len(dist["REDUCE"])/max(total,1)*100:.0f}% | 趋势转弱，逐步减仓 |
| 🔴 卖出 | {len(dist["SELL"])} | {len(dist["SELL"])/max(total,1)*100:.0f}% | 明确看空，建议离场 |

**建议总仓位:** {_suggested_position(buy_add, reduce_sell, total, cfg)}

---

## 二、重点推荐（买入/加仓信号）

"""
    if dist["BUY"] or dist["ADD"]:
        for item in sorted(dist["BUY"] + dist["ADD"], key=lambda x: x["total_score"], reverse=True):
            icon = _signal_icon("BUY" if item in dist["BUY"] else "ADD")
            close_str = f"{item['close']:.2f}" if item['close'] is not None else "N/A"
            entry = item['entry_price'] or 0
            target = item['target_price'] or 0
            stop = item['stop_loss'] or 0
            up_pct = f"{(target/entry-1)*100:.1f}%" if entry > 0 and target > 0 else "N/A"
            dn_pct = f"{(1-stop/entry)*100:.1f}%" if entry > 0 and stop > 0 else "N/A"
            entry_str = f"{entry:.2f}" if entry > 0 else "N/A"
            target_str = f"{target:.2f}" if target > 0 else "N/A"
            stop_str = f"{stop:.2f}" if stop > 0 else "N/A"
            md += f"""### {icon} {item['symbol']} {item['name']} — {_rating_text(item['rating'])}

| 指标 | 数值 |
|------|------|
| 综合评分 | {item['total_score']:.0f}/100 |
| 最新收盘 | {close_str} 元 |
| PE / PB | {item['pe'] or 'N/A'} / {item['pb'] or 'N/A'} |
| 建议仓位 | {item['position']}% |
| 入场价 | {entry_str} 元 |
| 目标价 | {target_str} 元（上涨空间 {up_pct}） |
| 止损价 | {stop_str} 元（下行风险 {dn_pct}） |
| 持有周期 | {item['holding_period']} |

**评分明细:**
- 质量分: {_score_bar(item['quality_score'], 30)} — {_quality_comment(item['quality_score'])}
- 估值分: {_score_bar(item['valuation_score'], 20)} — {_valuation_comment(item['valuation_score'])}
- 成长分: {_score_bar(item['growth_score'], 20)} — {_growth_comment(item['growth_score'])}
- 趋势分: {_score_bar(item['trend_score'], 20)} — {_trend_comment(item['trend_score'])}
- 风险分: {_score_bar(item['risk_score'], 10)} — {_risk_comment(item['risk_score'])}

"""
    else:
        md += "*当前无买入或加仓信号，建议观望等待机会。*\n\n"

    # 风险预警
    md += """---

## 三、风险预警（减仓/卖出信号）

"""
    if dist["REDUCE"] or dist["SELL"]:
        md += "> 以下标的发出风险信号，建议关注并考虑减仓操作。\n\n"
        for item in sorted(dist["REDUCE"] + dist["SELL"], key=lambda x: x["total_score"]):
            icon = _signal_icon("SELL" if item in dist["SELL"] else "REDUCE")
            reason = item["logic"].get("reason", "") if item.get("logic") else ""
            md += f"""### {icon} {item['symbol']} {item['name']} — {_rating_text(item['rating'])}

- **评分:** {item['total_score']:.0f}/100 | **收盘:** {item['close']:.2f} 元
- **信号理由:** {reason}
- **风险提示:** 评分偏低，基本面或技术面出现恶化迹象，建议逐步减仓或离场观望。

"""
    else:
        md += "*当前无减仓或卖出信号，整体持仓风险可控。*\n\n"

    # 观望标的
    md += """---

## 四、观望标的

"""
    if dist["WATCH"]:
        md += "| 代码 | 名称 | 评分 | 收盘价 | PE | 板块 |\n"
        md += "|------|------|------|--------|------|------|\n"
        for item in dist["WATCH"]:
            md += f"| {item['symbol']} | {item['name']} | {item['total_score']:.0f} | {item['close']:.2f} | {item['pe'] or 'N/A'} | {item['industry']} |\n"
        md += "\n以上标的处于观望区间，可纳入自选持续跟踪，等待信号转强后择机介入。\n"
    else:
        md += "*当前无观望标的。*\n"

    # 操作建议
    md += f"""

---

## 五、今日操作建议

1. **仓位管理:** {_suggested_position(buy_add, reduce_sell, total, cfg)}
2. **买入策略:** 对于评分 ≥75 的标的，可在回调至入场价附近分批建仓，严格设置止损。
3. **卖出策略:** 对于评分 <50 的标的，建议在反弹时逐步减仓，避免恋战。
4. **风险控制:** 单只标的仓位不超过总资产的 10%，总仓位控制在建议范围内。
5. **跟踪观察:** 持续关注观望标的的评分变化，等待买入信号触发。

---

## 六、评分模型说明

本报告采用 **100 分制多维评分模型**，从五个维度综合评估标的的投资价值：

| 维度 | 权重 | 评估内容 |
|------|------|----------|
| 质量分 | 30分 | ROE、现金流、毛利率、资产负债率 |
| 估值分 | 20分 | PE、PB、历史估值比较、股息率 |
| 成长分 | 20分 | 营收增长、利润增长、复合增长 |
| 趋势分 | 20分 | 均线系统、MACD、成交量 |
| 风险分 | 10分 | 业绩稳定性、负债/现金流、估值风险 |

**评级标准:** 买入 ≥85 | 加仓 ≥75 | 观望 ≥65 | 减仓 ≥50 | 卖出 <50

"""
    # 风格化专属内容
    if cfg:
        md += f"""---

## 七、{cfg['icon']} {cfg['name']}投资策略指南

**投资理念:** {cfg['strategy_desc']}

**适合人群:** {cfg['suitable']}

**风格特征:**
- 风险承受能力: **{cfg['risk_tolerance']}**
- 最大仓位上限: **{cfg['max_position']}%**
- 单只标的上限: **{cfg['single_stock_max']}%**
- 最低入选评分: **{cfg['min_score']}分**

**风格化评分权重调整:**
| 维度 | 标准权重 | {cfg['name']}权重 | 说明 |
|------|----------|-------------------|------|
| 质量分 | 1.0x | {cfg['score_weights']['quality']}x | {'重点考察' if cfg['score_weights']['quality'] > 1 else '适度关注'} |
| 估值分 | 1.0x | {cfg['score_weights']['valuation']}x | {'重点考察' if cfg['score_weights']['valuation'] > 1 else '适度关注'} |
| 成长分 | 1.0x | {cfg['score_weights']['growth']}x | {'重点考察' if cfg['score_weights']['growth'] > 1 else '适度关注'} |
| 趋势分 | 1.0x | {cfg['score_weights']['trend']}x | {'重点考察' if cfg['score_weights']['trend'] > 1 else '适度关注'} |
| 风险分 | 1.0x | {cfg['score_weights']['risk']}x | {'重点考察' if cfg['score_weights']['risk'] > 1 else '适度关注'} |

**{cfg['name']}操作纪律:**
"""
        if style == "steady":
            md += """1. 严格执行分散持仓原则，单一行业配置不超过 20%
2. 设定 5% 的个股止损线和 10% 的组合回撤止损线
3. 优先配置高股息标的，确保组合有稳定的现金流入
4. 市场波动加大时主动降低仓位至 40% 以下
5. 每季度审视持仓质量，淘汰评分下滑的标的
"""
        elif style == "aggressive":
            md += """1. 集中配置高确定性标的，前五大持仓可占组合 50% 以上
2. 设定 8% 的个股止损线，但允许更大波动空间
3. 积极把握趋势性机会，评分转强时果断加仓
4. 关注行业轮动和主题投资机会
5. 每月审视组合表现，及时调整不符合预期的标的
"""
        elif style == "conservative":
            md += """1. 绝对收益导向，任何单笔投资都要有明确的安全边际
2. 设定 3% 的严格止损线，宁可错杀不可深套
3. 仓位严格控制在 40% 以内，剩余资金配置货币基金
4. 只买入 PE < 25 且 PB < 2.5 的低估值标的
5. 重视股息收入，优先选择连续 3 年分红的标的
"""

    md += """
---

*本报告由 融衔 量化分析系统自动生成，基于公开市场数据和多维评分模型，仅供研究参考，不构成任何投资建议。投资有风险，入市需谨慎。*
"""

    content_json = {
        "market_status": market_status,
        "mood_desc": mood_desc,
        "signal_distribution": {k: len(v) for k, v in dist.items()},
        "buy_signals": dist["BUY"],
        "add_signals": dist["ADD"],
        "watch_signals": dist["WATCH"],
        "reduce_signals": dist["REDUCE"],
        "sell_signals": dist["SELL"],
        "suggested_position": _suggested_position(buy_add, reduce_sell, total),
    }

    report = Report(
        report_date=report_date,
        report_type=ReportType.DAILY,
        style=style,
        title=f"每日策略报告{style_label} — {report_date}（{market_status}）",
        summary=f"{market_status} | 买入:{len(dist['BUY'])} 加仓:{len(dist['ADD'])} 观望:{len(dist['WATCH'])} 减仓:{len(dist['REDUCE'])} 卖出:{len(dist['SELL'])}",
        content_markdown=md,
        content_json=content_json,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def _suggested_position(buy_add: int, reduce_sell: int, total: int, cfg: dict = None) -> str:
    if total == 0:
        return "暂无建议"
    ratio = buy_add / total
    max_pos = cfg["max_position"] if cfg else 80
    if ratio > 0.6:
        return f"{min(70, max_pos)}-{min(80, max_pos)}%（积极做多）" if max_pos >= 70 else f"{max_pos * 0.7:.0f}-{max_pos}%（{cfg['name']}上限配置）" if cfg else "70-80%（积极做多）"
    if ratio > 0.4:
        return f"{min(50, max_pos)}-{min(70, max_pos)}%（偏多配置）"
    if ratio > 0.2:
        return f"{min(30, max_pos)}-{min(50, max_pos)}%（均衡配置）"
    return f"20-{min(30, max_pos)}%（防御为主）"


# ==================== 个股深度分析报告 ====================

def generate_stock_report(db: Session, stock_id: int, report_date: date) -> Report:
    """生成个股深度分析报告"""
    stock = db.query(Stock).filter(Stock.id == stock_id).first()
    if not stock:
        raise ValueError("Stock not found")

    # 获取所有需要的数据
    score = db.query(StockScore).filter(
        StockScore.stock_id == stock_id, StockScore.score_date == report_date
    ).first()
    # 如果当天没有评分，取最近的
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

    # 近 20 日行情
    prices_20 = db.query(DailyPrice).filter(
        DailyPrice.stock_id == stock_id
    ).order_by(DailyPrice.trade_date.desc()).limit(20).all()

    # 近 60 日行情
    prices_60 = db.query(DailyPrice).filter(
        DailyPrice.stock_id == stock_id
    ).order_by(DailyPrice.trade_date.desc()).limit(60).all()

    # 财务数据（最近 4 期）
    financials = db.query(FinancialMetric).filter(
        FinancialMetric.stock_id == stock_id
    ).order_by(FinancialMetric.report_period.desc()).limit(4).all()

    # 技术指标
    tech = db.query(TechnicalIndicator).filter(
        TechnicalIndicator.stock_id == stock_id
    ).order_by(TechnicalIndicator.trade_date.desc()).first()

    # 同行业标的
    peers = db.query(Stock).filter(
        Stock.industry == stock.industry, Stock.id != stock_id, Stock.status == "ACTIVE"
    ).all()
    peer_scores = []
    for p in peers:
        ps = db.query(StockScore).filter(StockScore.stock_id == p.id).order_by(StockScore.score_date.desc()).first()
        pp = db.query(DailyPrice).filter(DailyPrice.stock_id == p.id).order_by(DailyPrice.trade_date.desc()).first()
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

    # === 生成报告 ===
    md = f"""# {stock.symbol} {stock.name} 深度分析报告

> **报告日期:** {report_date}
> **市场:** {stock.market} | **行业:** {stock.industry} | **板块:** {stock.sector}
> **综合评级:** {_rating_text(score.rating) if score else '暂无评分'}

---

## 一、公司概况

**{stock.name}**（{stock.symbol}.{stock.exchange}）是一家在{stock.exchange}上市的{stock.industry}行业公司，属于{stock.sector}板块。

"""
    # 行业地位
    if peer_scores:
        better_peers = [p for p in peer_scores if score and p["score"] < score.total_score]
        md += f"在同行业 {len(peer_scores) + 1} 家可比公司中，{stock.name}综合评分排名第 **{len(better_peers) + 1}** 位。"

    if latest_price:
        md += f"""

---

## 二、最新行情

| 指标 | 数值 |
|------|------|
| 最新收盘价 | {latest_price.close:.2f} 元 |
| 今日开盘 | {latest_price.open:.2f} 元 |
| 最高 / 最低 | {latest_price.high:.2f} / {latest_price.low:.2f} 元 |
| 成交量 | {latest_price.volume/10000:.0f} 万手 |
| 市盈率 (PE) | {latest_price.pe if latest_price.pe else 'N/A'} |
| 市净率 (PB) | {latest_price.pb if latest_price.pb else 'N/A'} |
| 总市值 | {f'{latest_price.market_cap:.0f} 亿' if latest_price.market_cap else 'N/A'} |
| 股息率 | {f'{latest_price.dividend_yield:.2f}%' if latest_price.dividend_yield else 'N/A'} |

"""
        if prices_20 and len(prices_20) >= 2:
            high_20 = max(p.high for p in prices_20)
            low_20 = min(p.low for p in prices_20)
            amp_20 = (high_20 - low_20) / low_20 * 100 if low_20 > 0 else 0
            amp_60 = (high_60 - low_60) / low_60 * 100 if low_60 > 0 else 0
            md += f"""### 近期价格走势

| 周期 | 涨跌幅 | 最高价 | 最低价 | 振幅 |
|------|--------|--------|--------|------|
| 近 20 日 | {price_change_20:+.2f}% | {high_20:.2f} | {low_20:.2f} | {amp_20:.1f}% |
| 近 60 日 | {price_change_60:+.2f}% | {high_60:.2f} | {low_60:.2f} | {amp_60:.1f}% |

"""
        if latest_price and high_60 > 0:
            md += f"**当前价位分析:** 收盘价 {latest_price.close:.2f} 元，距 60 日高点 {high_60:.2f} 元有 {(1-latest_price.close/high_60)*100:.1f}% 的空间，距 60 日低点 {low_60:.2f} 元上涨了 {(latest_price.close/low_60-1)*100:.1f}%。\n\n"
    else:
        md += "\n---\n\n## 二、最新行情\n\n> 暂无行情数据\n\n"

    # 技术面分析
    md += """---

## 三、技术面分析

"""
    if tech:
        # 均线分析
        ma_status = "多头排列" if tech.ma20 and tech.ma60 and tech.ma20 > tech.ma60 else "空头排列" if tech.ma20 and tech.ma60 and tech.ma20 < tech.ma60 else "交叉缠绕"
        ref_price = latest_price.close if latest_price else 0
        price_vs_ma20 = "站上" if ref_price > (tech.ma20 or 0) else "跌破"
        price_vs_ma60 = "站上" if ref_price > (tech.ma60 or 0) else "跌破"
        ma60_str = f"{tech.ma60:.2f}" if tech.ma60 else "N/A"
        ma120_str = f"{tech.ma120:.2f}" if tech.ma120 else "N/A"
        ma120_rel = "数据不足" if not tech.ma120 else ("站上MA120" if ref_price > tech.ma120 else "跌破MA120")
        ma_trend_desc = "短期趋势向好，可关注回调买入机会。" if ma_status == "多头排列" else "短期趋势偏弱，建议等待均线修复后再考虑介入。" if ma_status == "空头排列" else "趋势不明朗，建议观望。"
        macd_signal = "多头" if tech.macd > (tech.macd_signal or 0) else "空头"

        md += f"""### 均线系统

| 均线 | 数值 | 与现价关系 |
|------|------|-----------|
| MA20 | {tech.ma20:.2f} | {price_vs_ma20}MA20 |
| MA60 | {ma60_str} | {price_vs_ma60 + 'MA60' if tech.ma60 else '数据不足'} |
| MA120 | {ma120_str} | {ma120_rel} |

**均线状态:** {ma_status}。{ma_trend_desc}

### MACD 指标

| 指标 | 数值 | 信号 |
|------|------|------|
| MACD | {tech.macd:.4f} | {macd_signal} |
| 信号线 | {tech.macd_signal:.4f} | — |
| 柱状图 | {tech.macd_hist:.4f} | {'红柱' if (tech.macd_hist or 0) > 0 else '绿柱'} |

**MACD 解读:** {'MACD 在信号线上方，柱状图为红，短期动能偏强。' if (tech.macd or 0) > (tech.macd_signal or 0) else 'MACD 在信号线下方，柱状图为绿，短期动能偏弱，需等待金叉信号。'}

### RSI 指标

RSI(14) = **{tech.rsi14:.1f}** — {'超买区间，注意回调风险。' if tech.rsi14 > 70 else '超卖区间，可能存在反弹机会。' if tech.rsi14 < 30 else '中性区间。'}

### 成交量分析

| 指标 | 数值 |
|------|------|
| 5日均量 | {tech.volume_ma5/10000:.0f} 万手 |
| 20日均量 | {tech.volume_ma20/10000:.0f} 万手 |
| 量比 (5/20) | {tech.volume_ma5/tech.volume_ma20:.2f} |

**量能解读:** {'近期成交量温和放大，资金关注度提升。' if tech.volume_ma5 > tech.volume_ma20 * 1.1 else '近期成交量萎缩，市场参与度下降。' if tech.volume_ma5 < tech.volume_ma20 * 0.9 else '成交量保持平稳。'}

"""
    else:
        md += "*技术指标数据不足，无法进行技术面分析。*\n\n"

    # 财务分析
    md += """---

## 四、财务分析

"""
    if financials:
        md += "### 核心财务指标（近四期）\n\n"
        md += "| 报告期 | 营收(亿) | 营收增速 | 净利润(亿) | 利润增速 | 毛利率 | ROE | 负债率 |\n"
        md += "|--------|----------|----------|------------|----------|--------|-----|--------|\n"
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
            md += "\n### 财务趋势分析\n\n"

            if latest_f.revenue and prev_f.revenue:
                rev_trend = "增长" if latest_f.revenue > prev_f.revenue else "下滑"
                md += f"- **营收趋势:** 最新报告期营收 {latest_f.revenue:.1f} 亿，较上期{rev_trend} {abs((latest_f.revenue/prev_f.revenue-1)*100):.1f}%。\n"

            if latest_f.net_profit and prev_f.net_profit:
                np_trend = "增长" if latest_f.net_profit > prev_f.net_profit else "下滑"
                md += f"- **利润趋势:** 最新报告期净利润 {latest_f.net_profit:.1f} 亿，较上期{np_trend} {abs((latest_f.net_profit/prev_f.net_profit-1)*100):.1f}%。\n"

            if latest_f.roe is not None:
                if latest_f.roe > 15:
                    md += f"- **盈利能力:** ROE 为 {latest_f.roe:.1f}%，盈利能力优秀。\n"
                elif latest_f.roe > 10:
                    md += f"- **盈利能力:** ROE 为 {latest_f.roe:.1f}%，盈利能力良好。\n"
                else:
                    md += f"- **盈利能力:** ROE 为 {latest_f.roe:.1f}%，盈利能力一般。\n"

            if latest_f.debt_ratio is not None:
                if latest_f.debt_ratio > 70:
                    md += f"- **财务风险:** 资产负债率 {latest_f.debt_ratio:.1f}%，负债水平偏高，需关注偿债能力。\n"
                elif latest_f.debt_ratio > 50:
                    md += f"- **财务健康:** 资产负债率 {latest_f.debt_ratio:.1f}%，负债水平适中。\n"
                else:
                    md += f"- **财务健康:** 资产负债率 {latest_f.debt_ratio:.1f}%，财务结构稳健。\n"

        # EPS
        if financials[0].eps is not None:
            md += f"\n**最新每股收益 (EPS):** {financials[0].eps:.2f} 元"
            if latest_price and latest_price.close and financials[0].eps > 0:
                implied_pe = latest_price.close / financials[0].eps
                md += f"（隐含 PE 约 {implied_pe:.1f} 倍）"
            md += "\n"
    else:
        md += "*该标的暂无财务数据（港股财务数据暂不支持）。*\n"

    # 估值分析
    md += f"""

---

## 五、估值分析

"""
    if latest_price and (latest_price.pe is not None or latest_price.pb is not None):
        md += "| 估值指标 | 当前值 | 行业参考 | 判断 |\n"
        md += "|----------|--------|----------|------|\n"
        if latest_price.pe is not None:
            pe_judge = "低估" if latest_price.pe < 15 else "合理" if latest_price.pe < 30 else "偏高" if latest_price.pe < 50 else "高估"
            md += f"| 市盈率 (PE) | {latest_price.pe:.1f} | 15-30 | {pe_judge} |\n"
        if latest_price.pb is not None:
            pb_judge = "低估" if latest_price.pb < 1.5 else "合理" if latest_price.pb < 3 else "偏高" if latest_price.pb < 5 else "高估"
            md += f"| 市净率 (PB) | {latest_price.pb:.1f} | 1-3 | {pb_judge} |\n"
        if latest_price.dividend_yield is not None:
            dy_judge = "高股息" if latest_price.dividend_yield > 3 else "中等" if latest_price.dividend_yield > 1 else "低股息"
            md += f"| 股息率 | {latest_price.dividend_yield:.2f}% | 1-3% | {dy_judge} |\n"

        md += "\n**估值综合判断:** "
        if latest_price.pe and latest_price.pe < 20 and latest_price.pb and latest_price.pb < 2:
            md += "当前估值处于较低水平，具备一定安全边际，适合价值投资者关注。"
        elif latest_price.pe and latest_price.pe < 30:
            md += "估值处于合理区间，需结合成长性判断是否具备投资价值。"
        else:
            md += "估值偏高，需警惕回调风险，建议等待更好的买入时机。"
        md += "\n"
    else:
        md += "*该标暂无估值数据。*\n"

    # 评分详解
    md += f"""

---

## 六、综合评分详解

"""
    if score:
        md += f"""**综合评分: {score.total_score:.0f}/100 — {_rating_text(score.rating)}**

| 维度 | 得分 | 满分 | 占比 | 评价 |
|------|------|------|------|------|
| 质量分 | {score.quality_score:.0f} | 30 | {score.quality_score/30*100:.0f}% | {_quality_comment(score.quality_score)} |
| 估值分 | {score.valuation_score:.0f} | 20 | {score.valuation_score/20*100:.0f}% | {_valuation_comment(score.valuation_score)} |
| 成长分 | {score.growth_score:.0f} | 20 | {score.growth_score/20*100:.0f}% | {_growth_comment(score.growth_score)} |
| 趋势分 | {score.trend_score:.0f} | 20 | {score.trend_score/20*100:.0f}% | {_trend_comment(score.trend_score)} |
| 风险分 | {score.risk_score:.0f} | 10 | {score.risk_score/10*100:.0f}% | {_risk_comment(score.risk_score)} |

### 评分雷达图（文字版）

```
质量  {_score_bar(score.quality_score, 30)}
估值  {_score_bar(score.valuation_score, 20)}
成长  {_score_bar(score.growth_score, 20)}
趋势  {_score_bar(score.trend_score, 20)}
风险  {_score_bar(score.risk_score, 10)}
```
"""
    else:
        md += "*该标的暂无评分数据。*\n"

    # 同业比较
    md += f"""

---

## 七、同业比较

"""
    if peer_scores:
        all_peers = [{"symbol": stock.symbol, "name": stock.name, "score": score.total_score if score else 0, "rating": score.rating if score else "N/A", "close": latest_price.close if latest_price else 0, "pe": latest_price.pe if latest_price else None}] + peer_scores
        all_peers.sort(key=lambda x: x["score"], reverse=True)

        md += f"**{stock.industry}** 行业可比公司排名：\n\n"
        md += "| 排名 | 代码 | 名称 | 评分 | 评级 | 收盘价 | PE |\n"
        md += "|------|------|------|------|------|--------|------|\n"
        for i, p in enumerate(all_peers, 1):
            marker = " ← **当前标的**" if p["symbol"] == stock.symbol else ""
            md += f"| {i} | {p['symbol']} | {p['name']} | {p['score']:.0f} | {p['rating']} | {p['close']:.2f} | {p['pe'] or 'N/A'} |\n"

        rank = next(i for i, p in enumerate(all_peers, 1) if p["symbol"] == stock.symbol)
        md += f"\n在 {len(all_peers)} 家同行业公司中，{stock.name}综合评分排名第 **{rank}** 位。"
        if rank == 1:
            md += "为行业内最优标的。"
        elif rank <= len(all_peers) * 0.3:
            md += "处于行业前列，具备较强竞争力。"
        elif rank <= len(all_peers) * 0.6:
            md += "处于行业中游水平。"
        else:
            md += "处于行业后列，竞争力相对较弱。"
        md += "\n"
    else:
        md += f"*{stock.industry} 行业暂无其他可比公司数据。*\n"

    # 操作建议
    md += f"""

---

## 八、操作建议

"""
    if signal:
        entry = f"{signal.entry_price:.2f}" if signal.entry_price else "N/A"
        target = f"{signal.target_price:.2f}" if signal.target_price else "N/A"
        stop_loss = f"{signal.stop_loss_price:.2f}" if signal.stop_loss_price else "N/A"
        target_up = f"+{(signal.target_price/signal.entry_price-1)*100:.1f}%" if signal.target_price and signal.entry_price else ""
        stop_down = f"-{(1-signal.stop_loss_price/signal.entry_price)*100:.1f}%" if signal.stop_loss_price and signal.entry_price else ""
        strength_stars = "★" * (signal.signal_strength or 0) + "☆" * (5 - (signal.signal_strength or 0))

        md += f"""| 项目 | 建议 |
|------|------|
| 信号类型 | {_signal_icon(signal.signal_type)} **{signal.signal_type}** — {_rating_text(signal.signal_type)} |
| 信号强度 | {strength_stars} |
| 建议仓位 | {signal.suggested_position}% |
| 入场价位 | {entry} 元 |
| 目标价位 | {target} 元 {target_up} |
| 止损价位 | {stop_loss} 元 {stop_down} |
| 持有周期 | {signal.holding_period or '—'} |

"""
        if signal.signal_type in ("BUY", "ADD"):
            md += f"""**买入策略:**
1. 建议在 {entry} 元附近分批建仓，首次仓位不超过建议仓位的 50%。
2. 若价格回调至止损价 {stop_loss} 元以下，需严格执行止损。
3. 若价格上涨至目标价 {target} 元附近，可考虑减仓锁定利润。
4. 持有周期预计 {signal.holding_period or '视情况而定'}，期间持续跟踪评分变化。

"""
        elif signal.signal_type in ("REDUCE", "SELL"):
            md += f"""**卖出策略:**
1. 建议在反弹时逐步减仓，避免一次性卖出造成冲击。
2. 若价格跌破止损价 {stop_loss} 元，应果断离场。
3. 关注成交量变化，放量下跌时加速减仓。

"""
        else:
            md += "**观望策略:** 当前信号为观望，建议持续跟踪评分变化，等待明确的买入或卖出信号后再行动。\n\n"
    else:
        md += "*暂无交易信号。*\n\n"

    # 风险提示
    md += """---

## 九、风险提示

"""
    risks = []
    if latest_price and latest_price.pe and latest_price.pe > 50:
        risks.append(f"估值风险：当前 PE 为 {latest_price.pe:.1f}，估值偏高，存在回调压力。")
    if score and score.risk_score < 5:
        risks.append("财务风险：风险评分偏低，需关注财务健康状况。")
    if tech and tech.ma20 and tech.ma60 and tech.ma20 < tech.ma60:
        risks.append("趋势风险：均线空头排列，短期趋势偏弱。")
    if score and score.trend_score < 5:
        risks.append("技术风险：技术面评分较低，需等待企稳信号。")
    if not latest_price or (latest_price.pe is None and latest_price.pb is None):
        risks.append("数据风险：估值数据缺失，无法进行完整的估值分析。")

    if risks:
        for i, r in enumerate(risks, 1):
            md += f"{i}. ⚠️ {r}\n"
    else:
        md += "当前未发现明显风险因素。\n"

    md += f"""

---

*本报告由 融衔 量化分析系统自动生成，基于 {report_date} 公开市场数据和多维评分模型，仅供研究参考，不构成任何投资建议。投资有风险，入市需谨慎。*
"""

    report = Report(
        report_date=report_date,
        report_type=ReportType.STOCK,
        title=f"{stock.symbol} {stock.name} 深度分析报告",
        summary=f"{stock.name} | 评分 {score.total_score:.0f}/100 | 评级 {_rating_text(score.rating)} | 收盘 {latest_price.close:.2f}元" if score and latest_price else f"{stock.name} 深度分析报告",
        content_markdown=md,
        content_json={
            "stock_id": stock_id,
            "symbol": stock.symbol,
            "name": stock.name,
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


# ==================== 风格化投资策略报告 ====================

def generate_style_report(db: Session, report_date: date, style: str) -> Report:
    """生成专属风格化投资策略报告"""
    if style not in STYLE_CONFIG:
        raise ValueError(f"Invalid style: {style}. Must be one of: {list(STYLE_CONFIG.keys())}")

    cfg = STYLE_CONFIG[style]
    weights = cfg["score_weights"]

    # 获取当日所有信号
    signals = db.query(TradeSignal).filter(TradeSignal.signal_date == report_date).all()

    # 获取所有评分
    all_scores = db.query(StockScore).filter(StockScore.score_date == report_date).all()
    if not all_scores:
        all_scores = db.query(StockScore).order_by(StockScore.score_date.desc()).limit(200).all()

    # 计算风格加权分并筛选推荐标的
    style_ranked = []
    for sc in all_scores:
        style_score = (
            sc.quality_score * weights["quality"]
            + sc.valuation_score * weights["valuation"]
            + sc.growth_score * weights["growth"]
            + sc.trend_score * weights["trend"]
            + sc.risk_score * weights["risk"]
        )
        stock = db.query(Stock).filter(Stock.id == sc.stock_id).first()
        if stock:
            price = db.query(DailyPrice).filter(DailyPrice.stock_id == sc.stock_id).order_by(DailyPrice.trade_date.desc()).first()
            style_ranked.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "industry": stock.industry,
                "market": stock.market,
                "style_score": round(style_score, 1),
                "total_score": sc.total_score,
                "quality_score": sc.quality_score,
                "valuation_score": sc.valuation_score,
                "growth_score": sc.growth_score,
                "trend_score": sc.trend_score,
                "risk_score": sc.risk_score,
                "rating": sc.rating,
                "close": price.close if price else None,
                "pe": price.pe if price else None,
                "pb": price.pb if price else None,
                "dividend_yield": price.dividend_yield if price else None,
            })

    style_ranked.sort(key=lambda x: x["style_score"], reverse=True)
    top_picks = [s for s in style_ranked if s["total_score"] >= cfg["min_score"]][:15]

    # 获取信号中的风格匹配标的
    signal_map = {}
    for s in signals:
        stock = db.query(Stock).filter(Stock.id == s.stock_id).first()
        if stock:
            signal_map[stock.symbol] = s

    # 行业分布统计
    industry_dist = {}
    for item in top_picks:
        ind = item["industry"]
        industry_dist[ind] = industry_dist.get(ind, 0) + 1

    # 生成报告
    md = f"""# {cfg['icon']} {cfg['name']}投资策略报告

> **报告日期:** {report_date}
> **投资风格:** {cfg['icon']} {cfg['name']} — {cfg['desc']}
> **适合人群:** {cfg['suitable']}
> **风险承受:** {cfg['risk_tolerance']} | **最大仓位:** {cfg['max_position']}% | **单股上限:** {cfg['single_stock_max']}%

---

## 一、{cfg['name']}投资理念

{cfg['strategy_desc']}

**核心原则:**
- 仓位上限: {cfg['max_position']}%，严格控制整体风险暴露
- 单股上限: {cfg['single_stock_max']}%，避免个股集中风险
- 最低入选评分: {cfg['min_score']}分，确保标的基本面质量
- 风险容忍度: {cfg['risk_tolerance']}

---

## 二、风格化评分权重

| 维度 | 标准权重 | {cfg['name']}权重 | 权重说明 |
|------|----------|-------------------|----------|
| 质量分 | 1.0x | {weights['quality']}x | {'重点筛选，确保基本面扎实' if weights['quality'] > 1 else '适度考量' if weights['quality'] < 1 else '标准权重'} |
| 估值分 | 1.0x | {weights['valuation']}x | {'严格把关，要求安全边际' if weights['valuation'] > 1 else '适度放宽' if weights['valuation'] < 1 else '标准权重'} |
| 成长分 | 1.0x | {weights['growth']}x | {'重点关注高成长' if weights['growth'] > 1 else '稳定性优先' if weights['growth'] < 1 else '标准权重'} |
| 趋势分 | 1.0x | {weights['trend']}x | {'积极跟随趋势' if weights['trend'] > 1 else '更重基本面' if weights['trend'] < 1 else '标准权重'} |
| 风险分 | 1.0x | {weights['risk']}x | {'风控第一' if weights['risk'] > 1 else '适度容忍换取收益' if weights['risk'] < 1 else '标准权重'} |

---

## 三、{cfg['name']}精选标的（TOP 15）

"""
    if top_picks:
        md += "| 排名 | 代码 | 名称 | 风格分 | 综合分 | 质量 | 估值 | 成长 | 趋势 | 风险 | 评级 | 收盘价 | PE |\n"
        md += "|------|------|------|--------|--------|------|------|------|------|------|------|--------|------|\n"
        for i, item in enumerate(top_picks[:15], 1):
            md += f"| {i} | {item['symbol']} | {item['name']} | {item['style_score']:.0f} | {item['total_score']:.0f} | {item['quality_score']:.0f} | {item['valuation_score']:.0f} | {item['growth_score']:.0f} | {item['trend_score']:.0f} | {item['risk_score']:.0f} | {item['rating']} | {item['close']:.2f} | {item['pe'] or 'N/A'} |\n"

        md += f"\n**风格适配说明:** 以上标的按照{cfg['name']}加权评分排序，综合考虑了{cfg['name']}投资者的核心关注点。\n"
    else:
        md += f"*当前暂无符合{cfg['name']}标准的精选标的。*\n"

    # 风格化仓位配置建议
    md += f"""

---

## 四、{cfg['name']}仓位配置方案

"""
    if top_picks:
        md += "### 行业分布\n\n"
        md += "| 行业 | 标的数 | 建议配置 |\n"
        md += "|------|--------|----------|\n"
        for ind, count in sorted(industry_dist.items(), key=lambda x: x[1], reverse=True):
            alloc = min(count * cfg["single_stock_max"], 30)
            md += f"| {ind} | {count} | {alloc}% |\n"

        md += f"\n### 推荐组合配置\n\n"
        md += "| 标的 | 建议仓位 | 入场区间 | 止损位 | 目标位 |\n"
        md += "|------|----------|----------|--------|--------|\n"
        for item in top_picks[:5]:
            pos = cfg["single_stock_max"]
            close = item["close"] or 0
            entry_lo = f"{close * 0.97:.2f}" if close > 0 else "N/A"
            entry_hi = f"{close * 1.02:.2f}" if close > 0 else "N/A"
            stop = f"{close * 0.95:.2f}" if close > 0 else "N/A"
            target = f"{close * 1.10:.2f}" if close > 0 else "N/A"
            md += f"| {item['symbol']} {item['name']} | {pos}% | {entry_lo}-{entry_hi} | {stop} | {target} |\n"

        total_alloc = min(len(top_picks[:5]) * cfg["single_stock_max"], cfg["max_position"])
        md += f"\n**现金仓位:** 建议保留 **{100 - total_alloc}%** 作为现金储备\n"
    else:
        md += "*暂无推荐配置方案。*\n"

    # 风格化操作纪律
    md += f"""

---

## 五、{cfg['name']}操作纪律

"""
    if style == "steady":
        md += """### 买入纪律
1. 标的综合评分 ≥ 70 分，质量分和风险分必须达标
2. PE < 30，PB < 3，确保估值合理
3. 均线多头排列或至少 MA20 > MA60
4. 分批建仓，首次仓位不超过目标仓位的 50%

### 持有纪律
1. 单一行业配置不超过组合的 20%
2. 每周审视持仓，评分跌破 65 触发减仓预警
3. 组合回撤达到 8% 时主动降低仓位
4. 高股息标的优先持有，确保现金流入

### 卖出纪律
1. 个股亏损达到 5% 执行止损
2. 评分降至 REDUCE 级别时逐步减仓
3. 基本面出现重大恶化时果断清仓
4. 达到目标价后分批止盈
"""
    elif style == "aggressive":
        md += """### 买入纪律
1. 标的综合评分 ≥ 60 分，成长分和趋势分优先
2. 成长分 ≥ 15，趋势分 ≥ 15，确保有向上动能
3. MACD 金叉或即将金叉时介入
4. 可以在突破关键阻力位时追涨买入

### 持有纪律
1. 前五大持仓可占组合 50% 以上
2. 趋势未破前坚定持有，不轻易被洗出
3. 评分持续走强时可加仓至上限
4. 关注行业轮动，及时切换赛道

### 卖出纪律
1. 个股亏损达到 8% 执行止损
2. 趋势反转信号明确时（MACD 死叉 + 均线空头）清仓
3. 连续放量下跌时加速减仓
4. 达到目标价后可保留底仓继续跟踪
"""
    elif style == "conservative":
        md += """### 买入纪律
1. 标的综合评分 ≥ 75 分，质量分和风险分必须优秀
2. PE < 25，PB < 2.5，股息率 > 2%
3. 连续 3 年盈利且 ROE > 10%
4. 只在市场恐慌性下跌后逢低吸纳

### 持有纪律
1. 总仓位严格控制在 40% 以内
2. 单一行业配置不超过 15%
3. 优先持有高股息标的，股息再投资
4. 每月审视，任何评分下滑立即减仓

### 卖出纪律
1. 个股亏损达到 3% 执行止损（严格）
2. PE 超过 30 或 PB 超过 3.5 时考虑减仓
3. 公司分红政策变化时重新评估
4. 市场系统性风险加大时全部转为现金
"""

    # 当日信号匹配分析
    md += f"""

---

## 六、{cfg['name']}信号匹配分析

"""
    matched_signals = []
    for item in top_picks[:10]:
        sig = signal_map.get(item["symbol"])
        if sig:
            matched_signals.append((item, sig))

    if matched_signals:
        md += f"以下精选标的同时发出了交易信号，{cfg['name']}投资者可重点关注：\n\n"
        for item, sig in matched_signals:
            md += f"### {_signal_icon(sig.signal_type)} {item['symbol']} {item['name']}\n\n"
            md += f"- 风格加权分: **{item['style_score']:.0f}** | 综合评分: {item['total_score']:.0f}\n"
            md += f"- 信号类型: **{sig.signal_type}** | 信号强度: {'★' * (sig.signal_strength or 0)}{'☆' * (5 - (sig.signal_strength or 0))}\n"
            if sig.entry_price:
                md += f"- 入场价: {sig.entry_price:.2f} | 目标价: {sig.target_price or 0:.2f} | 止损: {sig.stop_loss_price or 0:.2f}\n"
            md += "\n"
    else:
        md += f"当前精选标的中暂无匹配的交易信号，建议持续跟踪等待信号触发。\n"

    # 风格化风险提示
    md += f"""

---

## 七、{cfg['name']}风险提示

"""
    if style == "steady":
        md += """1. 📊 **市场风险:** 即使选择稳健标的，市场系统性下跌仍可能造成损失
2. 📉 **利率风险:** 加息周期中高股息标的可能面临估值压力
3. 🏢 **经营风险:** 蓝筹股也可能出现基本面恶化，需持续跟踪
4. 💰 **机会成本:** 稳健策略可能错过部分高成长机会
"""
    elif style == "aggressive":
        md += """1. ⚡ **高波动风险:** 进取型标的波动较大，可能面临较大短期亏损
2. 📉 **追高风险:** 强势标的可能在高位买入后遭遇回调
3. 🔄 **风格漂移:** 市场风格切换时，成长股可能阶段性跑输
4. 💸 **集中度风险:** 集中持仓放大了个股风险
"""
    elif style == "conservative":
        md += """1. 📉 **价值陷阱:** 低估值可能是基本面恶化的反映
2. 💰 **收益有限:** 保守策略可能导致长期收益偏低
3. 📊 **市场适应性:** 在牛市中保守策略可能大幅跑输市场
4. 🏦 **现金贬值:** 大量现金配置可能被通胀侵蚀
"""

    md += f"""

---

*本报告由 融衔 量化分析系统自动生成，基于 {report_date} 公开市场数据和{cfg['name']}评分模型，仅供研究参考，不构成任何投资建议。投资有风险，入市需谨慎。*
"""

    report = Report(
        report_date=report_date,
        report_type="STYLE",
        style=style,
        title=f"{cfg['icon']} {cfg['name']}投资策略报告 — {report_date}",
        summary=f"{cfg['name']} | 精选{len(top_picks)}只标的 | 最高风格分{top_picks[0]['style_score']:.0f} | 最大仓位{cfg['max_position']}%" if top_picks else f"{cfg['name']}投资策略报告",
        content_markdown=md,
        content_json={
            "style": style,
            "style_name": cfg["name"],
            "top_picks": top_picks[:10],
            "industry_distribution": industry_dist,
            "max_position": cfg["max_position"],
            "single_stock_max": cfg["single_stock_max"],
            "risk_tolerance": cfg["risk_tolerance"],
        },
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
