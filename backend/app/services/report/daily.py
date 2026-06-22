"""
每日策略报告 — 融衔量化分析系统
从20年华尔街投资专家视角生成专业级每日投资策略报告
"""
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from app.models.stock import Stock
from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal
from app.models.daily_price import DailyPrice
from app.models.report import Report
from app.core.constants import ReportType

from app.services.report.style_config import STYLE_CONFIG
from app.services.report.utils import (
    rating_text, signal_icon, score_bar,
    distribution_bar, market_breadth_chart,
    quality_comment, valuation_comment, growth_comment,
    trend_comment, risk_comment, suggested_position,
    market_index_summary,
)


# ==================== 每日策略报告（8000+字专业版）====================

def generate_daily_report(db: Session, report_date: date, market_filter: list[str] = None, style: str = None) -> Report:
    """生成详细的每日策略报告 — 从20年华尔街投资专家视角"""

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
        fallback_view = "作为深耕市场二十年的从业者，我观察到当前市场的多头信号密度处于较高水平。历史经验表明，当买入信号占比超过40%时，往往是中长期布局的较好时机。但投资者仍需保持理性，避免盲目追高，建议采用分批建仓策略。"
    elif buy_add > reduce_sell:
        market_status = "中性偏多"
        mood_desc = "市场整体偏暖，但分化明显，建议精选个股、分批建仓。结构性机会与风险并存，选股能力将成为决定收益的关键因素。"
        fallback_view = "从专业角度来看，当前市场呈现出典型的结构性行情特征。部分行业和个股表现强势，但整体市场并未形成一致性的做多共识。这种环境下，自下而上的个股精选策略往往优于自上而下的行业配置策略。建议投资者重点关注那些在基本面、估值和技术面三重共振的标的。"
    elif reduce_sell > buy_add * 2:
        market_status = "明显偏空"
        mood_desc = "市场情绪低迷，多数标的发出减仓或卖出信号，建议降低仓位、控制风险。系统性风险正在释放，防守应成为当前的首要策略。"
        fallback_view = "在二十年的投资生涯中，我深刻理解'保住本金'的重要性。当前市场空头信号密集，这是市场在发出警告。历史反复证明，在熊市中保住本金的投资者，往往能在下一轮牛市中获得超额回报。建议投资者严格执行止损纪律，将仓位降至防御水平，耐心等待市场企稳信号。"
    elif reduce_sell > buy_add:
        market_status = "中性偏空"
        mood_desc = "市场承压，建议谨慎操作，减少新开仓，等待企稳信号。市场正在消化利空因素，短期仍需时间筑底。"
        fallback_view = "当前市场处于调整期，空头力量略占上风但并未形成压倒性优势。从技术分析角度看，这往往是市场筑底过程中的正常表现。建议投资者控制好仓位，利用市场调整的机会，逐步布局那些基本面扎实、估值合理的优质标的。"
    else:
        market_status = "中性震荡"
        mood_desc = "多空力量均衡，市场处于震荡格局，建议维持现有仓位、观望为主。方向选择需要新的催化剂。"
        fallback_view = "震荡市是最考验投资者耐心的市场环境。在这种行情中，频繁交易往往会导致本金的损耗。我的建议是：保持现有仓位不动，利用震荡区间做好高抛低吸，同时密切关注可能打破平衡的宏观因素或政策信号。"

    # 尝试使用 AI 生成专家观点，失败时使用模板
    expert_view = fallback_view
    try:
        from app.services.ai_service import generate_ai_market_insight
        ai_view = generate_ai_market_insight(db, {
            "market_status": market_status,
            "buy_add": buy_add,
            "reduce_sell": reduce_sell,
            "top_buys": [
                {"symbol": it["symbol"], "name": it["name"], "score": it["total_score"]}
                for it in dist.get("BUY", [])[:5]
            ],
            "risk_items": [
                {"symbol": it["symbol"], "name": it["name"], "risk_score": it.get("risk_score", 0)}
                for it in dist.get("SELL", [])[:3]
            ],
        })
        if ai_view and len(ai_view) > 50:
            expert_view = ai_view
    except Exception:
        pass  # AI 不可用时静默降级到模板

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
    breadth_chart = market_breadth_chart(buy_add, reduce_sell, total)
    dist_chart = distribution_bar({"BUY": len(dist["BUY"]), "ADD": len(dist["ADD"]), "WATCH": len(dist["WATCH"]), "REDUCE": len(dist["REDUCE"]), "SELL": len(dist["SELL"])}, total)

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

**建议总仓位:** {suggested_position(buy_add, reduce_sell, total, cfg)}

---

## 二、重点推荐标的深度剖析（买入/加仓信号）

"""
    if dist["BUY"] or dist["ADD"]:
        all_recs = sorted(dist["BUY"] + dist["ADD"], key=lambda x: x["total_score"], reverse=True)
        for idx, item in enumerate(all_recs, 1):
            sig_type = "BUY" if item in dist["BUY"] else "ADD"
            icon = signal_icon(sig_type)
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

            md += f"""### {idx}. {icon} {item['symbol']} {item['name']}（{market_label}·{item['industry']}）— {rating_text(item['rating'])}

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
质量  {score_bar(item['quality_score'], 30)} {quality_comment(item['quality_score'])}
估值  {score_bar(item['valuation_score'], 20)} {valuation_comment(item['valuation_score'])}
成长  {score_bar(item['growth_score'], 20)} {growth_comment(item['growth_score'])}
趋势  {score_bar(item['trend_score'], 20)} {trend_comment(item['trend_score'])}
风险  {score_bar(item['risk_score'], 10)} {risk_comment(item['risk_score'])}
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
            icon = signal_icon(sig_type)
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

            md += f"""### {icon} {item['symbol']} {item['name']}（{market_label}）— {rating_text(item['rating'])}

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
{suggested_position(buy_add, reduce_sell, total, cfg)}
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
        "suggested_position": suggested_position(buy_add, reduce_sell, total),
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
