"""
报告生成服务 — 融衔量化分析系统
从20年华尔街投资专家视角生成专业级投资研究报告
覆盖A股+港股全市场标的，每份报告不低于8000字，图文结合
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


# ==================== 工具函数 ====================

def _rating_text(rating: str) -> str:
    return {"BUY": "强烈买入", "ADD": "建议加仓", "WATCH": "观望等待", "REDUCE": "建议减仓", "SELL": "建议卖出"}.get(rating, rating)


def _signal_icon(sig_type: str) -> str:
    return {"BUY": "🟢", "ADD": "🔵", "WATCH": "⚪", "REDUCE": "🟡", "SELL": "🔴"}.get(sig_type, "⚪")


def _score_bar(score: float, max_score: float) -> str:
    pct = score / max_score * 100 if max_score > 0 else 0
    filled = int(pct / 10)
    return "█" * filled + "░" * (10 - filled) + f" {score:.0f}/{max_score:.0f}"


def _spark_line(values: list, width: int = 20) -> str:
    """生成ASCII迷你走势图"""
    if not values or len(values) < 2:
        return "数据不足"
    mn, mx = min(values), max(values)
    rng = mx - mn if mx > mn else 1
    chars = "▁▂▃▄▅▆▇█"
    result = ""
    step = max(1, len(values) // width)
    sampled = values[::step][:width]
    for v in sampled:
        idx = int((v - mn) / rng * (len(chars) - 1))
        result += chars[idx]
    return result


def _distribution_bar(counts: dict, total: int) -> str:
    """生成信号分布柱状图"""
    if total == 0:
        return "无数据"
    lines = []
    max_len = 30
    for label, count in [("买入", counts.get("BUY", 0)), ("加仓", counts.get("ADD", 0)),
                          ("观望", counts.get("WATCH", 0)), ("减仓", counts.get("REDUCE", 0)),
                          ("卖出", counts.get("SELL", 0))]:
        bar_len = int(count / total * max_len)
        bar = "█" * bar_len + "░" * (max_len - bar_len)
        lines.append(f"  {label} |{bar}| {count}只 ({count/total*100:.0f}%)")
    return "\n".join(lines)


def _market_breadth_chart(buy_add: int, reduce_sell: int, total: int) -> str:
    """生成市场广度图"""
    if total == 0:
        return "数据不足"
    bull_pct = buy_add / total * 100
    bear_pct = reduce_sell / total * 100
    bull_bar = int(bull_pct / 2)
    bear_bar = int(bear_pct / 2)
    return f"""
```
市场多空力量对比
{'─' * 52}
多头 {'▓' * bull_bar}{'░' * (50 - bull_bar)} {bull_pct:.0f}%
空头 {'▒' * bear_bar}{'░' * (50 - bear_bar)} {bear_pct:.0f}%
{'─' * 52}
```"""


def _quality_comment(q: float) -> str:
    if q >= 25: return "质地优秀，盈利突出，现金流健康，护城河深厚"
    if q >= 18: return "质地良好，具备一定竞争优势和盈利韧性"
    if q >= 12: return "质地一般，部分财务指标有待改善"
    return "质地偏弱，需密切关注经营风险和现金流状况"


def _valuation_comment(v: float) -> str:
    if v >= 16: return "估值极具吸引力，安全边际充足，价值投资者首选"
    if v >= 10: return "估值合理，处于历史中位水平，具备投资价值"
    if v >= 5: return "估值偏高，需警惕回调风险，建议等待更好的买点"
    return "估值较高，当前价位缺乏安全边际，不建议追高"


def _growth_comment(g: float) -> str:
    if g >= 16: return "成长性卓越，营收和利润保持高速增长，成长动能强劲"
    if g >= 10: return "成长性良好，业绩稳步增长，增长趋势延续"
    if g >= 5: return "成长性一般，增速有所放缓，需关注增长可持续性"
    return "成长性较弱，业绩面临下滑压力，需谨慎对待"


def _trend_comment(t: float) -> str:
    if t >= 16: return "技术面强势，均线多头排列，量价配合良好，趋势明确"
    if t >= 10: return "技术面偏强，整体趋势向好，可关注回调买入机会"
    if t >= 5: return "技术面中性，短期方向不明朗，建议观望等待突破"
    return "技术面偏弱，均线空头排列，需等待企稳信号确认"


def _risk_comment(r: float) -> str:
    if r >= 8: return "风险可控，财务结构稳健，业绩确定性强"
    if r >= 5: return "风险适中，需关注部分指标变化，做好仓位管理"
    return "风险偏高，需密切关注财务和经营变化，严格止损"


def _suggested_position(buy_add: int, reduce_sell: int, total: int, cfg: dict = None) -> str:
    if total == 0:
        return "暂无建议"
    ratio = buy_add / total
    max_pos = cfg["max_position"] if cfg else 80
    if ratio > 0.6:
        if cfg:
            return f"{max_pos * 0.7:.0f}-{max_pos}%（{cfg['name']}上限配置）"
        return f"{min(70, max_pos)}-{min(80, max_pos)}%（积极做多）"
    if ratio > 0.4:
        return f"{min(50, max_pos)}-{min(70, max_pos)}%（偏多配置）"
    if ratio > 0.2:
        return f"{min(30, max_pos)}-{min(50, max_pos)}%（均衡配置）"
    return f"20-{min(30, max_pos)}%（防御为主）"


def _market_index_summary(db: Session, report_date: date) -> str:
    """生成市场指数概览"""
    # 获取有数据的标的中最新行情
    latest_prices = db.query(DailyPrice).order_by(DailyPrice.trade_date.desc()).limit(50).all()
    if not latest_prices:
        return "> 当前暂无市场行情数据。"

    # 统计涨跌
    up_count = sum(1 for p in latest_prices if p.close > (p.pre_close or p.close))
    down_count = sum(1 for p in latest_prices if p.close < (p.pre_close or p.close))
    flat_count = len(latest_prices) - up_count - down_count

    avg_change = 0
    changes = []
    for p in latest_prices:
        if p.pre_close and p.pre_close > 0:
            changes.append((p.close - p.pre_close) / p.pre_close * 100)
    if changes:
        avg_change = sum(changes) / len(changes)

    return f"""**市场温度计:**
```
涨跌家数统计（样本 {len(latest_prices)} 只）
{'─' * 40}
上涨: {'█' * min(up_count, 30)} {up_count}家
下跌: {'▒' * min(down_count, 30)} {down_count}家
平盘: {'░' * min(flat_count, 30)} {flat_count}家
{'─' * 40}
平均涨跌幅: {avg_change:+.2f}%
```"""


# ==================== 每日策略报告（8000+字专业版）====================

def generate_daily_report(db: Session, report_date: date, market_filter: list[str] = None, style: str = None) -> Report:
    """生成详细的每日策略报告 — 从20年华尔街投资专家视角"""
    from sqlalchemy import func as sqlfunc

    signals = db.query(TradeSignal).filter(TradeSignal.signal_date == report_date).all()

    # 获取所有有评分的股票（确保覆盖全部标的）
    all_scores = db.query(StockScore).filter(StockScore.score_date == report_date).all()
    if not all_scores:
        all_scores = db.query(StockScore).order_by(StockScore.score_date.desc()).limit(500).all()

    # 收集所有需要查询的 stock_id
    signal_stock_ids = set(s.stock_id for s in signals)
    score_stock_ids = set(sc.stock_id for sc in all_scores)
    all_stock_ids = signal_stock_ids | score_stock_ids

    # 批量查询 Stock（消除 N+1）
    stocks = db.query(Stock).filter(Stock.id.in_(all_stock_ids)).all() if all_stock_ids else []
    stock_map = {s.id: s for s in stocks}

    # 批量查询最新评分（消除 N+1）
    score_today = {sc.stock_id: sc for sc in all_scores}
    # 对于没有当天评分的，查最新评分
    missing_score_ids = signal_stock_ids - set(score_today.keys())
    if missing_score_ids:
        latest_score_sq = db.query(
            StockScore.stock_id,
            sqlfunc.max(StockScore.score_date).label("max_date")
        ).filter(StockScore.stock_id.in_(missing_score_ids)).group_by(StockScore.stock_id).subquery()
        extra_scores = db.query(StockScore).join(
            latest_score_sq,
            (StockScore.stock_id == latest_score_sq.c.stock_id) &
            (StockScore.score_date == latest_score_sq.c.max_date)
        ).all()
        for sc in extra_scores:
            score_today[sc.stock_id] = sc

    # 批量查询最新价格（消除 N+1）
    latest_price_sq = db.query(
        DailyPrice.stock_id,
        sqlfunc.max(DailyPrice.trade_date).label("max_date")
    ).filter(DailyPrice.stock_id.in_(all_stock_ids)).group_by(DailyPrice.stock_id).subquery()
    prices = db.query(DailyPrice).join(
        latest_price_sq,
        (DailyPrice.stock_id == latest_price_sq.c.stock_id) &
        (DailyPrice.trade_date == latest_price_sq.c.max_date)
    ).all() if all_stock_ids else []
    price_map = {p.stock_id: p for p in prices}

    def _build_item(stock, score, price, signal=None):
        return {
            "symbol": stock.symbol,
            "name": stock.name,
            "market": stock.market,
            "exchange": stock.exchange,
            "industry": stock.industry,
            "sector": stock.sector,
            "strength": signal.signal_strength if signal else 0,
            "position": signal.suggested_position if signal else 0,
            "entry_price": signal.entry_price if signal else None,
            "target_price": signal.target_price if signal else None,
            "stop_loss": signal.stop_loss_price if signal else None,
            "holding_period": signal.holding_period if signal else "-",
            "logic": signal.logic_json if signal else None,
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
            "dividend_yield": price.dividend_yield if price else None,
            "market_cap": price.market_cap if price else None,
            "volume": price.volume if price else None,
        }

    # 按类型分类信号
    dist = {"BUY": [], "ADD": [], "WATCH": [], "REDUCE": [], "SELL": []}
    for s in signals:
        stock = stock_map.get(s.stock_id)
        if not stock:
            continue
        score = score_today.get(s.stock_id)
        price = price_map.get(s.stock_id)
        item = _build_item(stock, score, price, s)
        dist.get(s.signal_type, []).append(item)

    # 补充没有信号但有评分的标的到观望列表
    for sc in all_scores:
        if sc.stock_id in signal_stock_ids:
            continue
        stock = stock_map.get(sc.stock_id)
        if not stock:
            continue
        price = price_map.get(sc.stock_id)
        item = _build_item(stock, sc, price)
        dist["WATCH"].append(item)

    # 统计
    total = sum(len(v) for v in dist.values())
    buy_add = len(dist["BUY"]) + len(dist["ADD"])
    reduce_sell = len(dist["REDUCE"]) + len(dist["SELL"])

    # 市场情绪判断
    if buy_add > reduce_sell * 2:
        market_status = "明显偏多"
        mood_desc = "市场情绪积极，多数标的呈现买入或加仓信号，适合适度提升仓位。从量化信号来看，多头力量占据绝对优势，这是一个值得积极参与的市场环境。"
        expert_view = "作为深耕市场二十年的从业者，我观察到当前市场的多头信号密度处于较高水平。历史经验表明，当买入信号占比超过40%时，往往是中长期布局的较好时机。但投资者仍需保持理性，避免盲目追高，建议采用分批建仓策略。"
    elif buy_add > reduce_sell:
        market_status = "中性偏多"
        mood_desc = "市场整体偏暖，但分化明显，建议精选个股、分批建仓。结构性机会与风险并存，选股能力将成为决定收益的关键因素。"
        expert_view = "从专业角度来看，当前市场呈现出典型的结构性行情特征。部分行业和个股表现强势，但整体市场并未形成一致性的做多共识。这种环境下，自下而上的个股精选策略往往优于自上而下的行业配置策略。建议投资者重点关注那些在基本面、估值和技术面三重共振的标的。"
    elif reduce_sell > buy_add * 2:
        market_status = "明显偏空"
        mood_desc = "市场情绪低迷，多数标的发出减仓或卖出信号，建议降低仓位、控制风险。系统性风险正在释放，防守应成为当前的首要策略。"
        expert_view = "在二十年的投资生涯中，我深刻理解'保住本金'的重要性。当前市场空头信号密集，这是市场在发出警告。历史反复证明，在熊市中保住本金的投资者，往往能在下一轮牛市中获得超额回报。建议投资者严格执行止损纪律，将仓位降至防御水平，耐心等待市场企稳信号。"
    elif reduce_sell > buy_add:
        market_status = "中性偏空"
        mood_desc = "市场承压，建议谨慎操作，减少新开仓，等待企稳信号。市场正在消化利空因素，短期仍需时间筑底。"
        expert_view = "当前市场处于调整期，空头力量略占上风但并未形成压倒性优势。从技术分析角度看，这往往是市场筑底过程中的正常表现。建议投资者控制好仓位，利用市场调整的机会，逐步布局那些基本面扎实、估值合理的优质标的。"
    else:
        market_status = "中性震荡"
        mood_desc = "多空力量均衡，市场处于震荡格局，建议维持现有仓位、观望为主。方向选择需要新的催化剂。"
        expert_view = "震荡市是最考验投资者耐心的市场环境。在这种行情中，频繁交易往往会导致本金的损耗。我的建议是：保持现有仓位不动，利用震荡区间做好高抛低吸，同时密切关注可能打破平衡的宏观因素或政策信号。"

    # 风格化处理
    cfg = STYLE_CONFIG.get(style) if style else None
    style_label = f"（{cfg['name']}版）" if cfg else ""
    style_header = f"\n> **投资风格:** {cfg['icon']} {cfg['name']} — {cfg['desc']}\n" if cfg else ""

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
        dist["BUY"].sort(key=lambda x: x.get("_style_score", 0), reverse=True)
        dist["ADD"].sort(key=lambda x: x.get("_style_score", 0), reverse=True)

    # 市场广度图
    breadth_chart = _market_breadth_chart(buy_add, reduce_sell, total)
    dist_chart = _distribution_bar({"BUY": len(dist["BUY"]), "ADD": len(dist["ADD"]), "WATCH": len(dist["WATCH"]), "REDUCE": len(dist["REDUCE"]), "SELL": len(dist["SELL"])}, total)

    # 按板块统计
    sector_stats = {}
    for sig_list in dist.values():
        for item in sig_list:
            sec = item.get("sector", "其他")
            if sec not in sector_stats:
                sector_stats[sec] = {"total": 0, "buy_add": 0, "reduce_sell": 0, "avg_score": []}
            sector_stats[sec]["total"] += 1
            sector_stats[sec]["avg_score"].append(item["total_score"])
            if item in dist["BUY"] or item in dist["ADD"]:
                sector_stats[sec]["buy_add"] += 1
            if item in dist["REDUCE"] or item in dist["SELL"]:
                sector_stats[sec]["reduce_sell"] += 1

    # A股/港股分类统计
    a_share_items = []
    hk_items = []
    for sig_list in dist.values():
        for item in sig_list:
            if item["market"] == "A_SHARE":
                a_share_items.append(item)
            else:
                hk_items.append(item)

    # 生成详细 Markdown 报告
    md = f"""# 每日策略报告{style_label}

> **报告日期:** {report_date} | **报告编号:** RPT-{report_date.strftime('%Y%m%d')}-DAILY
> **市场状态:** {market_status}
> **覆盖标的:** {total} 只（A股 {len(a_share_items)} 只 + 港股 {len(hk_items)} 只）
> **信号分布:** 🟢买入 {len(dist["BUY"])} | 🔵加仓 {len(dist["ADD"])} | ⚪观望 {len(dist["WATCH"])} | 🟡减仓 {len(dist["REDUCE"])} | 🔴卖出 {len(dist["SELL"])}{style_header}

---

## 一、宏观市场综述

### 1.1 市场情绪仪表盘

{breadth_chart}

{mood_desc}

### 1.2 专家视角

> {expert_view}

### 1.3 信号分布全景

```
{dist_chart}
```

### 1.4 板块热度矩阵

| 板块 | 标的数 | 多头信号 | 空头信号 | 平均评分 | 板块评级 |
|------|--------|----------|----------|----------|----------|
"""
    for sec, stats in sorted(sector_stats.items(), key=lambda x: sum(x[1]["avg_score"]) / max(len(x[1]["avg_score"]), 1), reverse=True):
        avg = sum(stats["avg_score"]) / max(len(stats["avg_score"]), 1)
        sec_rating = "⭐⭐⭐" if avg >= 80 else "⭐⭐" if avg >= 65 else "⭐"
        md += f"| {sec} | {stats['total']} | {stats['buy_add']} | {stats['reduce_sell']} | {avg:.0f} | {sec_rating} |\n"

    md += f"""
### 1.5 A股 vs 港股对比

| 市场 | 标的数 | 买入/加仓 | 减仓/卖出 | 平均评分 |
|------|--------|-----------|-----------|----------|
| A股 | {len(a_share_items)} | {sum(1 for i in a_share_items if i in dist["BUY"] or i in dist["ADD"])} | {sum(1 for i in a_share_items if i in dist["REDUCE"] or i in dist["SELL"])} | {sum(i["total_score"] for i in a_share_items) / max(len(a_share_items), 1):.0f} |
| 港股 | {len(hk_items)} | {sum(1 for i in hk_items if i in dist["BUY"] or i in dist["ADD"])} | {sum(1 for i in hk_items if i in dist["REDUCE"] or i in dist["SELL"])} | {sum(i["total_score"] for i in hk_items) / max(len(hk_items), 1):.0f} |

**建议总仓位:** {_suggested_position(buy_add, reduce_sell, total, cfg)}

---

## 二、重点推荐标的深度剖析（买入/加仓信号）

"""
    if dist["BUY"] or dist["ADD"]:
        all_recs = sorted(dist["BUY"] + dist["ADD"], key=lambda x: x["total_score"], reverse=True)
        for idx, item in enumerate(all_recs, 1):
            sig_type = "BUY" if item in dist["BUY"] else "ADD"
            icon = _signal_icon(sig_type)
            close_str = f"{item['close']:.2f}" if item['close'] is not None else "N/A"
            entry = item['entry_price'] or 0
            target = item['target_price'] or 0
            stop = item['stop_loss'] or 0
            up_pct = f"{(target/entry-1)*100:.1f}%" if entry > 0 and target > 0 else "N/A"
            dn_pct = f"{(1-stop/entry)*100:.1f}%" if entry > 0 and stop > 0 else "N/A"
            entry_str = f"{entry:.2f}" if entry > 0 else "N/A"
            target_str = f"{target:.2f}" if target > 0 else "N/A"
            stop_str = f"{stop:.2f}" if stop > 0 else "N/A"
            cap_str = f"{item['market_cap']:.0f}亿" if item.get('market_cap') else "N/A"
            dy_str = f"{item['dividend_yield']:.2f}%" if item.get('dividend_yield') else "N/A"
            vol_str = f"{item['volume']/10000:.0f}万" if item.get('volume') else "N/A"
            market_label = "A股" if item["market"] == "A_SHARE" else "港股"
            strength_stars = "★" * (item.get("strength") or 0) + "☆" * (5 - (item.get("strength") or 0))

            # 根据信号类型给出不同的专家解读
            if sig_type == "BUY":
                expert_analysis = f"""**🔍 专家深度解读:**

从多维度分析框架来看，{item['name']}当前呈现出难得的"三重共振"格局——基本面扎实（质量分{item['quality_score']:.0f}/30）、估值具备安全边际（估值分{item['valuation_score']:.0f}/20）、技术面确认上行趋势（趋势分{item['trend_score']:.0f}/20）。

在二十年的投资实践中，我发现这类标的往往具备较高的风险收益比。建议投资者在{entry_str}元附近的回调区间分批建仓，采用"金字塔式"加仓策略——首次建仓占总仓位的30%，确认突破后加仓至50%，趋势加速时加仓至上限。"""
            else:
                expert_analysis = f"""**🔍 专家深度解读:**

{item['name']}已被纳入加仓观察名单，表明该标的的中期趋势正在走强。当前综合评分{item['total_score']:.0f}分，距离强买入信号（85分）仍有提升空间，但成长性和趋势性的边际改善值得关注。

从实战角度看，加仓信号的核心逻辑是"趋势确认后的顺势而为"。建议已有底仓的投资者在回调至{entry_str}元附近时适度加仓，但需严格控制加仓节奏，避免过度集中。"""

            md += f"""### {idx}. {icon} {item['symbol']} {item['name']}（{market_label}·{item['industry']}）— {_rating_text(item['rating'])}

| 核心指标 | 数值 | 核心指标 | 数值 |
|----------|------|----------|------|
| 综合评分 | **{item['total_score']:.0f}**/100 | 最新收盘 | {close_str} 元 |
| PE / PB | {item['pe'] or 'N/A'} / {item['pb'] or 'N/A'} | 总市值 | {cap_str} |
| 股息率 | {dy_str} | 成交量 | {vol_str} |
| 入场价 | {entry_str} 元 | 建议仓位 | {item['position']}% |
| 目标价 | {target_str} 元（↑{up_pct}） | 止损价 | {stop_str} 元（↓{dn_pct}） |
| 持有周期 | {item['holding_period']} | 信号强度 | {strength_stars} |

**评分明细:**
```
质量  {_score_bar(item['quality_score'], 30)} {_quality_comment(item['quality_score'])}
估值  {_score_bar(item['valuation_score'], 20)} {_valuation_comment(item['valuation_score'])}
成长  {_score_bar(item['growth_score'], 20)} {_growth_comment(item['growth_score'])}
趋势  {_score_bar(item['trend_score'], 20)} {_trend_comment(item['trend_score'])}
风险  {_score_bar(item['risk_score'], 10)} {_risk_comment(item['risk_score'])}
```

{expert_analysis}

"""
    else:
        md += "> 当前无买入或加仓信号，市场整体偏谨慎，建议观望等待机会。\n\n"

    # 风险预警
    md += """---

## 三、风险预警信号深度分析（减仓/卖出信号）

"""
    if dist["REDUCE"] or dist["SELL"]:
        md += """> ⚠️ **风险警示:** 以下标的发出了明确的风险信号。在我的投资哲学中，"不亏钱"比"赚钱"更重要。当系统发出减仓或卖出信号时，投资者应当认真对待，而非心存侥幸。

"""
        for item in sorted(dist["REDUCE"] + dist["SELL"], key=lambda x: x["total_score"]):
            sig_type = "SELL" if item in dist["SELL"] else "REDUCE"
            icon = _signal_icon(sig_type)
            reason = item["logic"].get("reason", "") if item.get("logic") else ""
            market_label = "A股" if item["market"] == "A_SHARE" else "港股"

            close_val = item.get('close')
            close_str = f"{close_val:.2f}" if close_val else "N/A"
            close_stop = f"{close_val * 0.95:.2f}" if close_val else "N/A"

            if sig_type == "SELL":
                risk_advice = f"""**⚠️ 卖出策略:**
- 立即启动止损程序，在{close_str}元附近分批离场
- 若出现放量下跌，加速清仓，不要犹豫
- 卖出后至少观望2-3周，等待情绪修复后再考虑重新介入"""
            else:
                risk_advice = f"""**⚠️ 减仓策略:**
- 建议在反弹时逐步减仓，每次减仓不超过持仓的30%
- 设定{close_stop}元为最终止损线
- 关注成交量变化，缩量反弹是最佳减仓时机"""

            md += f"""### {icon} {item['symbol']} {item['name']}（{market_label}）— {_rating_text(item['rating'])}

| 指标 | 数值 |
|------|------|
| 综合评分 | {item['total_score']:.0f}/100 |
| 最新收盘 | {close_str} 元 |
| PE / PB | {item['pe'] or 'N/A'} / {item['pb'] or 'N/A'} |
| 信号理由 | {reason} |

{risk_advice}

"""
    else:
        md += "> 当前无减仓或卖出信号，整体持仓风险可控。但投资者仍需保持警惕，密切关注市场变化。\n\n"

    # 全部标的评分总览
    md += """---

## 四、全部覆盖标的评分总览

"""
    # 按评分排序所有标的
    all_items = []
    for sig_list in dist.values():
        all_items.extend(sig_list)
    all_items.sort(key=lambda x: x["total_score"], reverse=True)

    # A股标的
    md += "### 4.1 A股标的评分排名\n\n"
    md += "| 排名 | 代码 | 名称 | 行业 | 综合分 | 质量 | 估值 | 成长 | 趋势 | 风险 | 评级 | 收盘价 | PE |\n"
    md += "|------|------|------|------|--------|------|------|------|------|------|------|--------|------|\n"
    a_share_sorted = sorted([i for i in all_items if i["market"] == "A_SHARE"], key=lambda x: x["total_score"], reverse=True)
    for rank, item in enumerate(a_share_sorted, 1):
        signal_mark = ""
        if item in dist["BUY"]:
            signal_mark = " 🟢"
        elif item in dist["ADD"]:
            signal_mark = " 🔵"
        elif item in dist["REDUCE"]:
            signal_mark = " 🟡"
        elif item in dist["SELL"]:
            signal_mark = " 🔴"
        _c = f"{item['close']:.2f}" if item.get('close') is not None else "N/A"
        md += f"| {rank} | {item['symbol']} | {item['name']}{signal_mark} | {item['industry']} | {item['total_score']:.0f} | {item['quality_score']:.0f} | {item['valuation_score']:.0f} | {item['growth_score']:.0f} | {item['trend_score']:.0f} | {item['risk_score']:.0f} | {item['rating']} | {_c} | {item['pe'] or 'N/A'} |\n"

    # 港股标的
    md += "\n### 4.2 港股标的评分排名\n\n"
    md += "| 排名 | 代码 | 名称 | 行业 | 综合分 | 质量 | 估值 | 成长 | 趋势 | 风险 | 评级 | 收盘价 | PE |\n"
    md += "|------|------|------|------|--------|------|------|------|------|------|------|--------|------|\n"
    hk_sorted = sorted([i for i in all_items if i["market"] == "HK"], key=lambda x: x["total_score"], reverse=True)
    for rank, item in enumerate(hk_sorted, 1):
        signal_mark = ""
        if item in dist["BUY"]:
            signal_mark = " 🟢"
        elif item in dist["ADD"]:
            signal_mark = " 🔵"
        elif item in dist["REDUCE"]:
            signal_mark = " 🟡"
        elif item in dist["SELL"]:
            signal_mark = " 🔴"
        _c = f"{item['close']:.2f}" if item.get('close') is not None else "N/A"
        md += f"| {rank} | {item['symbol']} | {item['name']}{signal_mark} | {item['industry']} | {item['total_score']:.0f} | {item['quality_score']:.0f} | {item['valuation_score']:.0f} | {item['growth_score']:.0f} | {item['trend_score']:.0f} | {item['risk_score']:.0f} | {item['rating']} | {_c} | {item['pe'] or 'N/A'} |\n"

    # 操作建议
    md += f"""

---

## 五、今日操作策略与仓位管理

### 5.1 仓位配置建议

```
{_suggested_position(buy_add, reduce_sell, total, cfg)}
```

### 5.2 分场景操作指南

**场景一：当前仓位较低（<30%）**
- 对于评分≥80的买入信号标的，可在回调至入场价附近建仓，首次仓位不超过总仓位的15%
- 对于评分70-80的加仓信号标的，可小仓位试探性建仓，仓位控制在5-8%
- 预留至少30%现金应对市场波动

**场景二：当前仓位适中（30-60%）**
- 持有评分≥75的优质标的，不轻易减仓
- 对评分<60的持仓标的启动减仓程序
- 利用市场回调优化持仓结构，将资金向高评分标的集中

**场景三：当前仓位较重（>60%）**
- 对评分<50的标的坚决减仓，释放仓位空间
- 对评分50-65的标的设定严格止损线
- 总仓位逐步降至建议范围内

### 5.3 风险控制纪律

1. **止损纪律:** 任何单只标的亏损达到8%必须止损，不找借口
2. **仓位纪律:** 单只标的仓位不超过总资产的10%，行业集中度不超过30%
3. **情绪纪律:** 不因短期涨跌改变中期策略，严格执行交易计划
4. **跟踪纪律:** 每周审视持仓评分变化，评分连续下降的标的启动减仓程序

---

## 六、量化评分模型详解

本报告采用 **100分制五维量化评分模型**，从以下维度综合评估标的投资价值：

```
┌─────────────────────────────────────────────────────────┐
│                   五维评分模型架构                        │
├─────────────┬──────┬───────────────────────────────────────┤
│ 维度        │ 权重  │ 核心指标                              │
├─────────────┼──────┼───────────────────────────────────────┤
│ 质量分      │ 30分  │ ROE、经营现金流、毛利率、资产负债率      │
│ 估值分      │ 20分  │ PE、PB、历史估值比较、股息率            │
│ 成长分      │ 20分  │ 营收增速、利润增速、复合增长率           │
│ 趋势分      │ 20分  │ 均线系统、MACD、RSI、成交量             │
│ 风险分      │ 10分  │ 业绩稳定性、负债/现金流、估值风险        │
└─────────────┴──────┴───────────────────────────────────────┘
```

**评级标准:**
- 🟢 **强烈买入 (BUY):** 综合评分 ≥ 85，且各维度均有亮点
- 🔵 **建议加仓 (ADD):** 综合评分 75-84，趋势向好
- ⚪ **观望等待 (WATCH):** 综合评分 65-74，方向不明
- 🟡 **建议减仓 (REDUCE):** 综合评分 50-64，趋势转弱
- 🔴 **建议卖出 (SELL):** 综合评分 < 50，基本面或技术面恶化

"""
    # 风格化专属内容
    if cfg:
        md += f"""---

## 七、{cfg['icon']} {cfg['name']}投资策略指南

### 7.1 投资理念

{cfg['strategy_desc']}

**适合人群:** {cfg['suitable']}

### 7.2 风格特征

| 参数 | 设定值 |
|------|--------|
| 风险承受能力 | {cfg['risk_tolerance']} |
| 最大仓位上限 | {cfg['max_position']}% |
| 单只标的上限 | {cfg['single_stock_max']}% |
| 最低入选评分 | {cfg['min_score']}分 |

### 7.3 风格化评分权重

| 维度 | 标准权重 | {cfg['name']}权重 | 说明 |
|------|----------|-------------------|------|
| 质量分 | 1.0x | {cfg['score_weights']['quality']}x | {'重点考察' if cfg['score_weights']['quality'] > 1 else '适度关注'} |
| 估值分 | 1.0x | {cfg['score_weights']['valuation']}x | {'重点考察' if cfg['score_weights']['valuation'] > 1 else '适度关注'} |
| 成长分 | 1.0x | {cfg['score_weights']['growth']}x | {'重点考察' if cfg['score_weights']['growth'] > 1 else '适度关注'} |
| 趋势分 | 1.0x | {cfg['score_weights']['trend']}x | {'重点考察' if cfg['score_weights']['trend'] > 1 else '适度关注'} |
| 风险分 | 1.0x | {cfg['score_weights']['risk']}x | {'重点考察' if cfg['score_weights']['risk'] > 1 else '适度关注'} |

### 7.4 {cfg['name']}操作纪律

"""
        if style == "steady":
            md += """**买入纪律:**
1. 标的综合评分 ≥ 70 分，质量分和风险分必须达标
2. PE < 30，PB < 3，确保估值合理
3. 均线多头排列或至少 MA20 > MA60
4. 分批建仓，首次仓位不超过目标仓位的 50%

**持有纪律:**
1. 单一行业配置不超过组合的 20%
2. 每周审视持仓，评分跌破 65 触发减仓预警
3. 组合回撤达到 8% 时主动降低仓位
4. 高股息标的优先持有，确保现金流入

**卖出纪律:**
1. 个股亏损达到 5% 执行止损
2. 评分降至 REDUCE 级别时逐步减仓
3. 基本面出现重大恶化时果断清仓
4. 达到目标价后分批止盈
"""
        elif style == "aggressive":
            md += """**买入纪律:**
1. 标的综合评分 ≥ 60 分，成长分和趋势分优先
2. 成长分 ≥ 15，趋势分 ≥ 15，确保有向上动能
3. MACD 金叉或即将金叉时介入
4. 可以在突破关键阻力位时追涨买入

**持有纪律:**
1. 前五大持仓可占组合 50% 以上
2. 趋势未破前坚定持有，不轻易被洗出
3. 评分持续走强时可加仓至上限
4. 关注行业轮动，及时切换赛道

**卖出纪律:**
1. 个股亏损达到 8% 执行止损
2. 趋势反转信号明确时（MACD 死叉 + 均线空头）清仓
3. 连续放量下跌时加速减仓
4. 达到目标价后可保留底仓继续跟踪
"""
        elif style == "conservative":
            md += """**买入纪律:**
1. 标的综合评分 ≥ 75 分，质量分和风险分必须优秀
2. PE < 25，PB < 2.5，股息率 > 2%
3. 连续 3 年盈利且 ROE > 10%
4. 只在市场恐慌性下跌后逢低吸纳

**持有纪律:**
1. 总仓位严格控制在 40% 以内
2. 单一行业配置不超过 15%
3. 优先持有高股息标的，股息再投资
4. 每月审视，任何评分下滑立即减仓

**卖出纪律:**
1. 个股亏损达到 3% 执行止损（严格）
2. PE 超过 30 或 PB 超过 3.5 时考虑减仓
3. 公司分红政策变化时重新评估
4. 市场系统性风险加大时全部转为现金
"""

    md += f"""

---

## 八、风险提示与免责声明

### 8.1 系统性风险提示

1. **宏观经济风险:** 全球经济增长放缓、通胀预期变化、货币政策调整等宏观因素可能对市场整体估值产生压力
2. **地缘政治风险:** 国际关系变化、贸易摩擦升级等地缘政治因素可能引发市场波动
3. **流动性风险:** 市场流动性收紧可能导致资产价格非理性下跌
4. **政策监管风险:** 行业监管政策变化可能对特定板块产生重大影响

### 8.2 个股风险提示

1. **基本面风险:** 公司业绩不及预期、财务造假等可能导致股价大幅下跌
2. **估值风险:** 高估值标的面临估值回归的压力
3. **行业风险:** 行业景气度下行可能导致整个板块表现不佳
4. **流动性风险:** 小市值标的可能存在流动性不足的问题

### 8.3 免责声明

> 本报告由融衔量化分析系统自动生成，基于{report_date}公开市场数据和多维量化评分模型。报告中的分析、建议和评分仅供参考，不构成任何形式的投资建议或承诺。
>
> 投资有风险，入市需谨慎。过往业绩不代表未来表现。投资者应根据自身风险承受能力和投资目标，独立做出投资决策，并自行承担投资风险。
>
> 本系统及报告作者不对因使用本报告信息而产生的任何直接或间接损失承担责任。

---

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 融衔量化分析系统 v2.0*
*本报告共覆盖 {total} 只标的（A股 {len(a_share_items)} 只 + 港股 {len(hk_items)} 只），包含 {len(dist['BUY'])} 个买入信号、{len(dist['ADD'])} 个加仓信号、{len(dist['WATCH'])} 个观望信号、{len(dist['REDUCE'])} 个减仓信号、{len(dist['SELL'])} 个卖出信号*
"""

    # AI 深度洞察（DeepSeek）
    ai_analysis = ""
    try:
        from app.services.ai_service import generate_ai_market_insight
        ai_market_data = {
            "market_status": market_status,
            "buy_add": buy_add,
            "reduce_sell": reduce_sell,
            "top_buys": [{"symbol": s["symbol"], "name": s["name"], "score": s.get("total_score", 0), "type": s.get("signal_type", "")} for s in (dist["BUY"] + dist["ADD"])[:5]],
            "risk_items": [{"symbol": s["symbol"], "name": s["name"], "type": s.get("signal_type", "")} for s in (dist["REDUCE"] + dist["SELL"])[:5]],
        }
        ai_analysis = generate_ai_market_insight(db, ai_market_data)
        if ai_analysis:
            md += f"""

---

## AI 深度洞察

> 以下分析由 DeepSeek 大模型生成，基于当日量化数据，仅供参考。

{ai_analysis}

"""
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"AI 市场分析生成失败: {e}")

    content_json = {
        "market_status": market_status,
        "mood_desc": mood_desc,
        "expert_view": expert_view,
        "signal_distribution": {k: len(v) for k, v in dist.items()},
        "total_coverage": total,
        "a_share_count": len(a_share_items),
        "hk_count": len(hk_items),
        "buy_signals": dist["BUY"],
        "add_signals": dist["ADD"],
        "watch_signals": dist["WATCH"][:20],
        "reduce_signals": dist["REDUCE"],
        "sell_signals": dist["SELL"],
        "sector_stats": {k: {"total": v["total"], "avg_score": sum(v["avg_score"]) / max(len(v["avg_score"]), 1)} for k, v in sector_stats.items()},
        "suggested_position": _suggested_position(buy_add, reduce_sell, total),
    }

    report = Report(
        report_date=report_date,
        report_type=ReportType.DAILY,
        style=style,
        title=f"每日策略报告{style_label} — {report_date}（{market_status}·覆盖{total}只标的）",
        summary=f"{market_status} | A股{len(a_share_items)}只+港股{len(hk_items)}只 | 买入:{len(dist['BUY'])} 加仓:{len(dist['ADD'])} 观望:{len(dist['WATCH'])} 减仓:{len(dist['REDUCE'])} 卖出:{len(dist['SELL'])}",
        content_markdown=md,
        content_json=content_json,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


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

    # 价格走势迷你图
    close_prices = [p.close for p in reversed(prices_20)] if prices_20 else []
    price_spark = _spark_line(close_prices) if close_prices else "数据不足"

    # === 生成报告 ===
    market_label = "A股" if stock.market == "A_SHARE" else "港股"
    md = f"""# {stock.symbol} {stock.name} 深度分析报告

> **报告日期:** {report_date} | **报告编号:** RPT-{report_date.strftime('%Y%m%d')}-{stock.symbol}
> **市场:** {market_label} | **交易所:** {stock.exchange} | **行业:** {stock.industry} | **板块:** {stock.sector}
> **综合评级:** {_rating_text(score.rating) if score else '暂无评分'} | **综合评分:** {score.total_score:.0f}/100 if score else 'N/A'

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

**综合评分: {score.total_score:.0f}/100 — {_rating_text(score.rating)}**

| 维度 | 得分 | 满分 | 占比 | 评价 |
|------|------|------|------|------|
| 质量分 | {score.quality_score:.0f} | 30 | {score.quality_score/30*100:.0f}% | {_quality_comment(score.quality_score)} |
| 估值分 | {score.valuation_score:.0f} | 20 | {score.valuation_score/20*100:.0f}% | {_valuation_comment(score.valuation_score)} |
| 成长分 | {score.growth_score:.0f} | 20 | {score.growth_score/20*100:.0f}% | {_growth_comment(score.growth_score)} |
| 趋势分 | {score.trend_score:.0f} | 20 | {score.trend_score/20*100:.0f}% | {_trend_comment(score.trend_score)} |
| 风险分 | {score.risk_score:.0f} | 10 | {score.risk_score/10*100:.0f}% | {_risk_comment(score.risk_score)} |

### 6.2 评分雷达图

```
质量  {_score_bar(score.quality_score, 30)}
估值  {_score_bar(score.valuation_score, 20)}
成长  {_score_bar(score.growth_score, 20)}
趋势  {_score_bar(score.trend_score, 20)}
风险  {_score_bar(score.risk_score, 10)}
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

        md += f"### 7.1 {stock.industry}行业排名\n\n"
        md += "| 排名 | 代码 | 名称 | 评分 | 评级 | 收盘价 | PE |\n"
        md += "|------|------|------|------|------|--------|------|\n"
        for i, p in enumerate(all_peers, 1):
            marker = " ← **当前标的**" if p["symbol"] == stock.symbol else ""
            md += f"| {i} | {p['symbol']} | {p['name']} | {p['score']:.0f} | {p['rating']} | {p['close']:.2f} | {p['pe'] or 'N/A'} |\n"

        rank = next(i for i, p in enumerate(all_peers, 1) if p["symbol"] == stock.symbol)
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
| 信号类型 | {_signal_icon(signal.signal_type)} **{signal.signal_type}** — {_rating_text(signal.signal_type)} |
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

> **免责声明:** 本报告由融衔量化分析系统自动生成，基于 {report_date} 公开市场数据和多维量化评分模型，仅供研究参考，不构成任何投资建议。投资有风险，入市需谨慎。

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 融衔量化分析系统 v2.0*
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
        summary=f"{stock.name} | 评分 {score.total_score:.0f}/100 | 评级 {_rating_text(score.rating)} | 收盘 {latest_price.close:.2f}元" if score and latest_price else f"{stock.name} 深度分析报告",
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


# ==================== 风格化投资策略报告（8000+字专业版）====================

def generate_style_report(db: Session, report_date: date, style: str) -> Report:
    """生成专属风格化投资策略报告 — 从20年华尔街投资专家视角"""
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

    # 批量查询 Stock 和最新 DailyPrice（消除 N+1）
    score_stock_ids = [sc.stock_id for sc in all_scores]
    stocks_list = db.query(Stock).filter(Stock.id.in_(score_stock_ids)).all()
    stock_map = {s.id: s for s in stocks_list}

    # 批量查询每个 stock 的最新价格
    latest_price_subq = db.query(
        DailyPrice.stock_id,
        func.max(DailyPrice.trade_date).label("max_date")
    ).filter(DailyPrice.stock_id.in_(score_stock_ids)).group_by(DailyPrice.stock_id).subquery()

    latest_prices = db.query(DailyPrice).join(
        latest_price_subq,
        (DailyPrice.stock_id == latest_price_subq.c.stock_id) &
        (DailyPrice.trade_date == latest_price_subq.c.max_date)
    ).all()
    price_map = {p.stock_id: p for p in latest_prices}

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
        stock = stock_map.get(sc.stock_id)
        if stock:
            price = price_map.get(sc.stock_id)
            style_ranked.append({
                "symbol": stock.symbol,
                "name": stock.name,
                "industry": stock.industry,
                "market": stock.market,
                "sector": stock.sector,
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
                "market_cap": price.market_cap if price else None,
            })

    style_ranked.sort(key=lambda x: x["style_score"], reverse=True)
    top_picks = [s for s in style_ranked if s["total_score"] >= cfg["min_score"]][:15]

    # 获取信号中的风格匹配标的（批量查询消除 N+1）
    signal_stock_ids = [s.stock_id for s in signals]
    signal_stocks = db.query(Stock).filter(Stock.id.in_(signal_stock_ids)).all() if signal_stock_ids else []
    signal_stock_map = {s.id: s for s in signal_stocks}
    signal_map = {}
    for s in signals:
        stock = signal_stock_map.get(s.stock_id)
        if stock:
            signal_map[stock.symbol] = s

    # 行业分布统计
    industry_dist = {}
    for item in top_picks:
        ind = item["industry"]
        industry_dist[ind] = industry_dist.get(ind, 0) + 1

    # A股/港股分类
    a_share_picks = [p for p in top_picks if p["market"] == "A_SHARE"]
    hk_picks = [p for p in top_picks if p["market"] == "HK"]

    # 风格化专家解读
    style_expert_views = {
        "steady": "作为一名经历过多次市场周期的资深投资者，我深刻理解稳健型投资的价值。在2008年金融危机、2015年A股异常波动、2020年疫情冲击中，那些坚持稳健策略的投资者最终都获得了令人满意的回报。稳健不是保守，而是在风险可控的前提下追求确定性收益。当前市场环境下，高股息蓝筹股和行业龙头是最适合稳健型投资者的标的。",
        "aggressive": "进取型投资的核心在于'确定性下的集中'。这不是赌博，而是在深入研究后对高确信度标的的重仓配置。在我的职业生涯中，最成功的投资往往来自于对少数标的的深度理解和集中持有。但进取不等于盲目冒险——严格的风险管理和止损纪律是进取型投资者的生存底线。当前市场中，那些处于高景气赛道、具备强增长逻辑的标的是进取型投资者的首选。",
        "conservative": "保守型投资是最考验耐心的策略，但也是长期复利效应最显著的策略。巴菲特说过：'第一条规则是永远不要亏钱，第二条规则是永远不要忘记第一条。'保守型投资者应当像猎人一样耐心等待，只在安全边际充足时出手。当前市场中，低估值、高股息、业绩稳定的标的是保守型投资者的理想选择。"
    }

    # 生成报告
    md = f"""# {cfg['icon']} {cfg['name']}投资策略报告

> **报告日期:** {report_date} | **报告编号:** RPT-{report_date.strftime('%Y%m%d')}-STYLE-{style.upper()}
> **投资风格:** {cfg['icon']} {cfg['name']} — {cfg['desc']}
> **适合人群:** {cfg['suitable']}
> **风险承受:** {cfg['risk_tolerance']} | **最大仓位:** {cfg['max_position']}% | **单股上限:** {cfg['single_stock_max']}%
> **精选标的:** {len(top_picks)} 只（A股 {len(a_share_picks)} 只 + 港股 {len(hk_picks)} 只）

---

## 一、{cfg['name']}投资理念与哲学

### 1.1 核心投资理念

{cfg['strategy_desc']}

### 1.2 专家视角

> {style_expert_views.get(style, "")}

### 1.3 核心原则

| 原则 | 设定值 | 说明 |
|------|--------|------|
| 仓位上限 | {cfg['max_position']}% | 严格控制整体风险暴露 |
| 单股上限 | {cfg['single_stock_max']}% | 避免个股集中风险 |
| 最低入选评分 | {cfg['min_score']}分 | 确保标的基本面质量 |
| 风险容忍度 | {cfg['risk_tolerance']} | 明确风险承受边界 |

**投资纪律:** 严格执行以上原则，不因市场情绪而动摇。纪律是投资成功的基石，尤其对于{cfg['name']}投资者而言，遵守纪律比追求收益更加重要。

---

## 二、风格化评分权重体系

### 2.1 权重配置

| 维度 | 标准权重 | {cfg['name']}权重 | 权重说明 |
|------|----------|-------------------|----------|
| 质量分 | 1.0x | {weights['quality']}x | {'重点筛选，确保基本面扎实' if weights['quality'] > 1 else '适度考量' if weights['quality'] < 1 else '标准权重'} |
| 估值分 | 1.0x | {weights['valuation']}x | {'严格把关，要求安全边际' if weights['valuation'] > 1 else '适度放宽' if weights['valuation'] < 1 else '标准权重'} |
| 成长分 | 1.0x | {weights['growth']}x | {'重点关注高成长' if weights['growth'] > 1 else '稳定性优先' if weights['growth'] < 1 else '标准权重'} |
| 趋势分 | 1.0x | {weights['trend']}x | {'积极跟随趋势' if weights['trend'] > 1 else '更重基本面' if weights['trend'] < 1 else '标准权重'} |
| 风险分 | 1.0x | {weights['risk']}x | {'风控第一' if weights['risk'] > 1 else '适度容忍换取收益' if weights['risk'] < 1 else '标准权重'} |

### 2.2 权重设计理念

"""
    if style == "steady":
        md += """稳健型投资者的核心诉求是在控制风险的前提下获取稳定回报。因此，我们在评分权重上做了以下调整：
- **质量分 (1.5x):** 优先选择基本面扎实、盈利能力稳定的标的，这是稳健投资的基石
- **估值分 (1.3x):** 要求足够的安全边际，避免在高估值区间买入
- **风险分 (1.5x):** 高度重视风险控制，低风险标的优先入选
- **成长分 (0.8x):** 适度降低成长性要求，宁选稳定不选爆发
- **趋势分 (0.7x):** 不追涨杀跌，更看重基本面而非短期趋势
"""
    elif style == "aggressive":
        md += """进取型投资者追求超额收益，愿意承受更高的波动和风险。权重调整逻辑：
- **成长分 (1.5x):** 重点筛选高成长标的，成长是超额收益的核心来源
- **趋势分 (1.5x):** 积极跟随趋势，顺势而为是进攻型策略的关键
- **质量分 (0.8x):** 适度放宽质量要求，给成长股更多空间
- **估值分 (0.7x):** 允许适度高估，用成长消化估值
- **风险分 (0.6x):** 适度容忍风险，换取更高收益弹性
"""
    elif style == "conservative":
        md += """保守型投资者以本金安全为第一目标，追求绝对收益。权重调整逻辑：
- **风险分 (1.8x):** 最高优先级，任何风险因素都不能忽视。低风险是保守投资的基石
- **估值分 (1.5x):** 严格要求安全边际，只买低估值标的。格雷厄姆的安全边际理论是保守投资的核心
- **质量分 (1.3x):** 基本面必须扎实，拒绝任何质量瑕疵。ROE、现金流、负债率都必须达标
- **成长分 (0.6x):** 不追求高增长，稳定即可。宁要确定的10%，不要不确定的50%
- **趋势分 (0.5x):** 不在意短期趋势，更看重长期价值。价值回归需要时间，耐心是保守投资者的美德
"""

    md += f"""
---

## 三、{cfg['name']}精选标的（TOP 15）

"""
    if top_picks:
        md += "### 3.1 精选标的排名\n\n"
        md += "| 排名 | 代码 | 名称 | 市场 | 行业 | 风格分 | 综合分 | 质量 | 估值 | 成长 | 趋势 | 风险 | 评级 | 收盘价 | PE |\n"
        md += "|------|------|------|------|------|--------|--------|------|------|------|------|------|------|--------|------|\n"
        for i, item in enumerate(top_picks[:15], 1):
            market_label = "A股" if item["market"] == "A_SHARE" else "港股"
            _c = f"{item['close']:.2f}" if item.get('close') is not None else "N/A"
            md += f"| {i} | {item['symbol']} | {item['name']} | {market_label} | {item['industry']} | {item['style_score']:.0f} | {item['total_score']:.0f} | {item['quality_score']:.0f} | {item['valuation_score']:.0f} | {item['growth_score']:.0f} | {item['trend_score']:.0f} | {item['risk_score']:.0f} | {item['rating']} | {_c} | {item['pe'] or 'N/A'} |\n"

        md += f"\n### 3.2 风格适配说明\n\n"
        md += f"以上标的按照{cfg['name']}加权评分排序，综合考虑了{cfg['name']}投资者的核心关注点。排名靠前的标的在{cfg['name']}视角下具备更高的投资价值。\n"

        # TOP 5 详细分析
        md += f"\n### 3.3 TOP 5 标的深度解读\n\n"
        for i, item in enumerate(top_picks[:5], 1):
            market_label = "A股" if item["market"] == "A_SHARE" else "港股"
            cap_str = f"{item['market_cap']:.0f}亿" if item.get('market_cap') else "N/A"
            dy_str = f"{item['dividend_yield']:.2f}%" if item.get('dividend_yield') else "N/A"

            if style == "steady":
                pick_reason = f"质量分{item['quality_score']:.0f}和风险分{item['risk_score']:.0f}表现突出，符合稳健型投资者对基本面扎实和风险可控的核心要求"
            elif style == "aggressive":
                pick_reason = f"成长分{item['growth_score']:.0f}和趋势分{item['trend_score']:.0f}领先，具备高成长和强趋势的双重特征"
            else:
                pick_reason = f"估值分{item['valuation_score']:.0f}和风险分{item['risk_score']:.0f}优秀，安全边际充足，适合保守型投资者。低估值提供了下行保护，高风险分确保了财务稳健性"

            md += f"""**第{i}名: {item['symbol']} {item['name']}（{market_label}·{item['industry']}）**

| 指标 | 数值 | 指标 | 数值 |
|------|------|------|------|
| 风格加权分 | **{item['style_score']:.0f}** | 综合评分 | {item['total_score']:.0f} |
| 收盘价 | {(f"{item['close']:.2f}" if item.get('close') is not None else "N/A")}元 | PE/PB | {item['pe'] or 'N/A'}/{item['pb'] or 'N/A'} |
| 市值 | {cap_str} | 股息率 | {dy_str} |

**入选理由:** {pick_reason}。

"""

    else:
        md += f"> 当前暂无符合{cfg['name']}标准（最低{cfg['min_score']}分）的精选标的。建议降低筛选标准或等待市场机会。\n\n"

    # 仓位配置方案
    md += f"""---

## 四、{cfg['name']}仓位配置方案

"""
    if top_picks:
        md += "### 4.1 行业分布\n\n"
        md += "| 行业 | 标的数 | 建议配置 | 配置说明 |\n"
        md += "|------|--------|----------|----------|\n"
        for ind, count in sorted(industry_dist.items(), key=lambda x: x[1], reverse=True):
            alloc = min(count * cfg["single_stock_max"], 30)
            md += f"| {ind} | {count} | {alloc}% | {'适度集中' if count >= 3 else '分散配置'} |\n"

        md += f"\n### 4.2 推荐组合配置\n\n"
        md += "| 标的 | 建议仓位 | 入场区间 | 止损位 | 目标位 | 预期收益 |\n"
        md += "|------|----------|----------|--------|--------|----------|\n"
        for item in top_picks[:5]:
            pos = cfg["single_stock_max"]
            close = item["close"] or 0
            entry_lo = f"{close * 0.97:.2f}" if close > 0 else "N/A"
            entry_hi = f"{close * 1.02:.2f}" if close > 0 else "N/A"
            stop = f"{close * 0.95:.2f}" if close > 0 else "N/A"
            target = f"{close * 1.10:.2f}" if close > 0 else "N/A"
            md += f"| {item['symbol']} {item['name']} | {pos}% | {entry_lo}-{entry_hi} | {stop} | {target} | +10% |\n"

        total_alloc = min(len(top_picks[:5]) * cfg["single_stock_max"], cfg["max_position"])
        md += f"""
### 4.3 仓位总览

```
┌─────────────────────────────────────────────────┐
│              {cfg['name']}仓位配置                │
├─────────────────────────────────────────────────┤
│ 持仓仓位: {'█' * int(total_alloc / 2)}{'░' * (50 - int(total_alloc / 2))} {total_alloc}%
│ 现金仓位: {'█' * int((100 - total_alloc) / 2)}{'░' * (50 - int((100 - total_alloc) / 2))} {100 - total_alloc}%
├─────────────────────────────────────────────────┤
│ 最大仓位上限: {cfg['max_position']}%
│ 单股仓位上限: {cfg['single_stock_max']}%
└─────────────────────────────────────────────────┘
```

**现金仓位:** 建议保留 **{100 - total_alloc}%** 作为现金储备，用于应对市场波动和把握突发机会。
"""
    else:
        md += "> 暂无推荐配置方案。\n"

    # 操作纪律
    md += f"""

---

## 五、{cfg['name']}操作纪律

"""
    if style == "steady":
        md += """### 5.1 买入纪律

1. 标的综合评分 ≥ 70 分，质量分和风险分必须达标
2. PE < 30，PB < 3，确保估值合理
3. 均线多头排列或至少 MA20 > MA60
4. 分批建仓，首次仓位不超过目标仓位的 50%
5. 只在市场情绪稳定时建仓，避免在恐慌期抄底

### 5.2 持有纪律

1. 单一行业配置不超过组合的 20%
2. 每周审视持仓，评分跌破 65 触发减仓预警
3. 组合回撤达到 8% 时主动降低仓位
4. 高股息标的优先持有，确保现金流入
5. 定期再平衡，维持目标仓位配置

### 5.3 卖出纪律

1. 个股亏损达到 5% 执行止损
2. 评分降至 REDUCE 级别时逐步减仓
3. 基本面出现重大恶化时果断清仓
4. 达到目标价后分批止盈
5. 市场系统性风险加大时主动降仓
"""
    elif style == "aggressive":
        md += """### 5.1 买入纪律

1. 标的综合评分 ≥ 60 分，成长分和趋势分优先
2. 成长分 ≥ 15，趋势分 ≥ 15，确保有向上动能
3. MACD 金叉或即将金叉时介入
4. 可以在突破关键阻力位时追涨买入
5. 行业景气度向上时加大配置力度

### 5.2 持有纪律

1. 前五大持仓可占组合 50% 以上
2. 趋势未破前坚定持有，不轻易被洗出
3. 评分持续走强时可加仓至上限
4. 关注行业轮动，及时切换赛道
5. 设定动态止盈线，保护浮盈

### 5.3 卖出纪律

1. 个股亏损达到 8% 执行止损
2. 趋势反转信号明确时（MACD 死叉 + 均线空头）清仓
3. 连续放量下跌时加速减仓
4. 达到目标价后可保留底仓继续跟踪
5. 行业景气度拐头时果断切换
"""
    elif style == "conservative":
        md += """### 5.1 买入纪律

1. 标的综合评分 ≥ 75 分，质量分和风险分必须优秀
2. PE < 25，PB < 2.5，股息率 > 2%
3. 连续 3 年盈利且 ROE > 10%
4. 只在市场恐慌性下跌后逢低吸纳
5. 安全边际必须超过 30% 才考虑建仓

### 5.2 持有纪律

1. 总仓位严格控制在 40% 以内
2. 单一行业配置不超过 15%
3. 优先持有高股息标的，股息再投资
4. 每月审视，任何评分下滑立即减仓
5. 保持充足的现金储备应对极端行情

### 5.3 卖出纪律

1. 个股亏损达到 3% 执行止损（严格）
2. PE 超过 30 或 PB 超过 3.5 时考虑减仓
3. 公司分红政策变化时重新评估
4. 市场系统性风险加大时全部转为现金
5. 宁可错杀不可深套，本金安全第一
"""

    # 信号匹配分析
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
            market_label = "A股" if item["market"] == "A_SHARE" else "港股"
            md += f"""### {_signal_icon(sig.signal_type)} {item['symbol']} {item['name']}（{market_label}）

- 风格加权分: **{item['style_score']:.0f}** | 综合评分: {item['total_score']:.0f}
- 信号类型: **{sig.signal_type}** | 信号强度: {'★' * (sig.signal_strength or 0)}{'☆' * (5 - (sig.signal_strength or 0))}
"""
            if sig.entry_price:
                md += f"- 入场价: {sig.entry_price:.2f} | 目标价: {sig.target_price or 0:.2f} | 止损: {sig.stop_loss_price or 0:.2f}\n"
            md += "\n"
    else:
        md += f"> 当前精选标的中暂无匹配的交易信号，建议持续跟踪等待信号触发。\n"

    # 风格化风险提示
    md += f"""

---

## 七、{cfg['name']}风险提示

"""
    if style == "steady":
        md += """1. 📊 **市场风险:** 即使选择稳健标的，市场系统性下跌仍可能造成损失。2008年和2015年的经验表明，没有绝对安全的标的。
2. 📉 **利率风险:** 加息周期中高股息标的可能面临估值压力，债券收益率上升会降低股票的相对吸引力。
3. 🏢 **经营风险:** 蓝筹股也可能出现基本面恶化，如行业变革、管理层变动等不可预见因素。
4. 💰 **机会成本:** 稳健策略可能错过部分高成长机会，在牛市中可能跑输进取型策略。
5. 📊 **通胀风险:** 如果收益率低于通胀率，实际购买力将下降。
"""
    elif style == "aggressive":
        md += """1. ⚡ **高波动风险:** 进取型标的波动较大，可能面临30%以上的短期回撤，需要强大的心理承受能力。
2. 📉 **追高风险:** 强势标的可能在高位买入后遭遇回调，追涨策略在市场转向时损失惨重。
3. 🔄 **风格漂移:** 市场风格切换时，成长股可能阶段性跑输价值股，导致策略失效。
4. 💸 **集中度风险:** 集中持仓放大了个股风险，单只标的暴雷可能对组合造成重大打击。
5. 🎯 **估值风险:** 高成长标的往往估值较高，一旦增速不及预期可能面临戴维斯双杀。
"""
    elif style == "conservative":
        md += """1. 📉 **价值陷阱:** 低估值可能是基本面恶化的反映，而非真正的投资机会。便宜有便宜的道理，需要深入分析低估的原因。
2. 💰 **收益有限:** 保守策略可能导致长期收益偏低，在牛市中大幅跑输市场。需要做好心理准备接受相对较低的回报。
3. 📊 **市场适应性:** 在牛市中保守策略可能大幅跑输市场，投资者可能因FOMO而改变策略。坚持纪律是最大的挑战。
4. 🏦 **现金贬值:** 大量现金配置可能被通胀侵蚀，实际购买力下降。需要在安全和收益之间找到平衡。
5. ⏰ **时间成本:** 等待完美买点可能错过大量机会，过度保守也是一种风险。价值回归可能需要很长时间。
6. 🎯 **选股难度:** 符合保守型标准的标的数量有限，可选范围较窄。可能需要放宽标准或等待更长的时间。
"""

    # 统计信息
    total_all = len(style_ranked)
    a_share_total = sum(1 for s in style_ranked if s["market"] == "A_SHARE")
    hk_total = sum(1 for s in style_ranked if s["market"] == "HK")
    avg_score = sum(s["total_score"] for s in style_ranked) / max(len(style_ranked), 1)

    md += f"""

---

## 八、{cfg['name']}市场环境分析

### 8.1 当前市场格局

本次{cfg['name']}策略报告覆盖了 **{total_all}** 只标的，其中A股 **{a_share_total}** 只、港股 **{hk_total}** 只，标的池平均综合评分为 **{avg_score:.0f}** 分。

"""
    if top_picks:
        top_avg = sum(p["style_score"] for p in top_picks) / len(top_picks)
        md += f"""### 8.2 精选标的质量评估

本次精选的 {len(top_picks)} 只标的，平均风格加权分为 **{top_avg:.0f}** 分，平均综合评分为 **{sum(p['total_score'] for p in top_picks) / len(top_picks):.0f}** 分。

| 指标 | 精选标的 | 全部标的 |
|------|----------|----------|
| 平均风格分 | {top_avg:.0f} | {sum(s['style_score'] for s in style_ranked) / max(len(style_ranked), 1):.0f} |
| 平均综合分 | {sum(p['total_score'] for p in top_picks) / len(top_picks):.0f} | {avg_score:.0f} |
| A股占比 | {len(a_share_picks)}/{len(top_picks)} | {a_share_total}/{total_all} |
| 港股占比 | {len(hk_picks)}/{len(top_picks)} | {hk_total}/{total_all} |

### 8.3 行业配置建议

"""
        # 行业分析
        for ind, count in sorted(industry_dist.items(), key=lambda x: x[1], reverse=True)[:5]:
            ind_picks = [p for p in top_picks if p["industry"] == ind]
            ind_avg = sum(p["style_score"] for p in ind_picks) / max(len(ind_picks), 1)
            md += f"- **{ind}**: {count}只标的入选，平均风格分{ind_avg:.0f}分"
            if style == "steady":
                md += "，适合稳健型投资者作为核心配置，该行业标的通常具备稳定的现金流和分红能力"
            elif style == "aggressive":
                md += "，成长性和趋势性突出，适合进攻型配置，关注行业景气度和竞争格局变化"
            else:
                md += "，估值安全边际充足，适合保守型投资者，重点关注低估值带来的安全保护"
            md += "\n"

    md += f"""

### 8.4 {cfg['name']}投资时间框架

"""
    if style == "steady":
        md += """**短期（1-3个月）:** 关注市场情绪变化，在回调时逐步建仓高评分标的
**中期（3-12个月）:** 持有核心仓位，定期再平衡，享受分红收益
**长期（1年以上）:** 复利效应显现，稳健策略的超额收益逐步体现"""
    elif style == "aggressive":
        md += """**短期（1-3个月）:** 积极把握趋势性机会，快进快出
**中期（3-12个月）:** 集中持有高确信度标的，跟踪行业轮动
**长期（1年以上）:** 适时兑现收益，避免长期持有高估值标的"""
    else:
        md += """**短期（1-3个月）:** 保持低仓位（不超过20%），耐心等待市场恐慌性下跌带来的买入机会
**中期（3-12个月）:** 在安全边际充足时逐步建仓，重点关注那些被市场错杀的优质低估值标的
**长期（1年以上）:** 享受低估值修复和分红带来的复利回报，保守策略的长期复利效应往往超出预期"""

    md += f"""

---

## 九、总结与展望

### 9.1 策略总结

本报告为{cfg['name']}投资者提供了完整的投资框架，包括：
- **{len(top_picks)}只精选标的**，覆盖A股和港股市场
- **完整的仓位配置方案**，确保风险分散
- **严格的操作纪律**，指导买入、持有和卖出决策
- **全面的风险提示**，帮助投资者做好风险管理
- **详细的市场环境分析**，把握投资时机

### 9.2 核心结论

当前市场环境下，{cfg['name']}投资者应保持{cfg['risk_tolerance']}风险偏好，将仓位控制在{cfg['max_position']}%以内。重点关注那些在{cfg['name']}视角下评分靠前的标的，严格执行操作纪律，在控制风险的前提下追求合理回报。

### 9.3 专家寄语

> {style_expert_views.get(style, "")}

### 9.4 行动清单

- [ ] 审阅本报告精选标的列表
- [ ] 根据自身持仓情况制定调仓计划
- [ ] 设定止损止盈的具体价位
- [ ] 建立定期审视机制（每周/每月）
- [ ] 记录投资日志，跟踪策略执行情况

---

> **免责声明:** 本报告由融衔量化分析系统自动生成，基于 {report_date} 公开市场数据和{cfg['name']}评分模型，仅供研究参考，不构成任何投资建议。投资有风险，入市需谨慎。

*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 融衔量化分析系统 v2.0*
"""

    # AI 风格策略洞察（DeepSeek）
    try:
        from app.services.ai_service import generate_ai_style_insight
        ai_style_data = {
            "style_name": cfg["name"],
            "style_desc": cfg.get("desc", ""),
            "pick_count": len(top_picks),
            "industry_dist": industry_dist,
            "top_picks": [{"symbol": p["symbol"], "name": p["name"], "style_score": p.get("style_score", 0), "total_score": p.get("total_score", 0), "rating": p.get("rating", "")} for p in top_picks[:10]],
            "max_position": cfg["max_position"],
            "total_position": cfg.get("total_position", "N/A"),
        }
        ai_analysis = generate_ai_style_insight(db, ai_style_data)
        if ai_analysis:
            md += f"""

---

## AI 深度洞察

> 以下分析由 DeepSeek 大模型生成，基于{cfg['name']}策略量化数据，仅供参考。

{ai_analysis}

"""
    except Exception as e:
        import logging
        import traceback
        logging.getLogger(__name__).warning(f"AI 风格分析生成失败: {e}")
        logging.getLogger(__name__).warning(traceback.format_exc())

    report = Report(
        report_date=report_date,
        report_type="STYLE",
        style=style,
        title=f"{cfg['icon']} {cfg['name']}投资策略报告 — {report_date}",
        summary=f"{cfg['name']} | 精选{len(top_picks)}只标的 | A股{len(a_share_picks)}只+港股{len(hk_picks)}只 | 最高风格分{top_picks[0]['style_score']:.0f} | 最大仓位{cfg['max_position']}%" if top_picks else f"{cfg['name']}投资策略报告",
        content_markdown=md,
        content_json={
            "style": style,
            "style_name": cfg["name"],
            "top_picks": top_picks[:10],
            "a_share_count": len(a_share_picks),
            "hk_count": len(hk_picks),
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
