"""
风格化投资策略报告生成模块

从20年华尔街投资专家视角，生成专属风格化投资策略报告（8000+字专业版）。
支持 steady（稳健型）、aggressive（进取型）、conservative（保守型）三种风格。
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

from app.services.report.style_config import STYLE_CONFIG
from app.services.report.utils import (
    rating_text, signal_icon, score_bar, distribution_bar,
    quality_comment, valuation_comment, growth_comment,
    trend_comment, risk_comment, suggested_position,
)


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
            md += f"""### {signal_icon(sig.signal_type)} {item['symbol']} {item['name']}（{market_label}）

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
