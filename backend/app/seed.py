"""
真实数据种子脚本 - 使用东方财富 API
运行方式: python -m app.seed
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.models.stock import Stock
from app.models.daily_price import DailyPrice
from app.models.financial_metric import FinancialMetric
from app.models.technical_indicator import TechnicalIndicator
from app.models.stock_score import StockScore
from app.models.trade_signal import TradeSignal
from app.models.report import Report
from app.models.portfolio import Portfolio, PortfolioPosition
from app.data_providers import get_provider
from app.services.scoring import calculate_quality_score, calculate_valuation_score, calculate_growth_score, calculate_trend_score, calculate_risk_score, get_rating
from app.services.signal import determine_signal_type, calculate_position, calculate_prices
from app.core.constants import SignalStatus
from app.models.user import User
from app.models.setting import Setting
import bcrypt
import numpy as np
import statistics

provider = get_provider()


def _ema(data: list, period: int) -> list:
    """计算指数移动平均线（真实 EMA）"""
    if not data:
        return []
    multiplier = 2 / (period + 1)
    ema = [float(data[0])]
    for i in range(1, len(data)):
        ema.append(float(data[i]) * multiplier + ema[-1] * (1 - multiplier))
    return ema


def _rsi(closes: list, period: int = 14) -> float:
    """计算 RSI 相对强弱指数（真实算法）"""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
_use_mock = type(provider).__name__ == "MockProvider"

# 核心股票池 - 涵盖 A 股和港股优质标的（共40只）
CORE_STOCKS = [
    # ===== A股 - 消费板块 =====
    {"symbol": "600519", "name": "贵州茅台", "market": "A_SHARE", "exchange": "SH", "industry": "白酒", "sector": "消费"},
    {"symbol": "000858", "name": "五粮液", "market": "A_SHARE", "exchange": "SZ", "industry": "白酒", "sector": "消费"},
    {"symbol": "000568", "name": "泸州老窖", "market": "A_SHARE", "exchange": "SZ", "industry": "白酒", "sector": "消费"},
    {"symbol": "002304", "name": "洋河股份", "market": "A_SHARE", "exchange": "SZ", "industry": "白酒", "sector": "消费"},
    {"symbol": "600887", "name": "伊利股份", "market": "A_SHARE", "exchange": "SH", "industry": "乳制品", "sector": "消费"},
    {"symbol": "000651", "name": "格力电器", "market": "A_SHARE", "exchange": "SZ", "industry": "家电", "sector": "消费"},
    {"symbol": "000333", "name": "美的集团", "market": "A_SHARE", "exchange": "SZ", "industry": "家电", "sector": "消费"},
    # ===== A股 - 金融板块 =====
    {"symbol": "600036", "name": "招商银行", "market": "A_SHARE", "exchange": "SH", "industry": "银行", "sector": "金融"},
    {"symbol": "601318", "name": "中国平安", "market": "A_SHARE", "exchange": "SH", "industry": "保险", "sector": "金融"},
    {"symbol": "000001", "name": "平安银行", "market": "A_SHARE", "exchange": "SZ", "industry": "银行", "sector": "金融"},
    {"symbol": "601166", "name": "兴业银行", "market": "A_SHARE", "exchange": "SH", "industry": "银行", "sector": "金融"},
    {"symbol": "600030", "name": "中信证券", "market": "A_SHARE", "exchange": "SH", "industry": "证券", "sector": "金融"},
    # ===== A股 - 科技/新能源板块 =====
    {"symbol": "300750", "name": "宁德时代", "market": "A_SHARE", "exchange": "SZ", "industry": "电池", "sector": "新能源"},
    {"symbol": "601012", "name": "隆基绿能", "market": "A_SHARE", "exchange": "SH", "industry": "光伏", "sector": "新能源"},
    {"symbol": "002475", "name": "立讯精密", "market": "A_SHARE", "exchange": "SZ", "industry": "消费电子", "sector": "科技"},
    {"symbol": "300059", "name": "东方财富", "market": "A_SHARE", "exchange": "SZ", "industry": "金融科技", "sector": "科技"},
    {"symbol": "002415", "name": "海康威视", "market": "A_SHARE", "exchange": "SZ", "industry": "安防", "sector": "科技"},
    # ===== A股 - 医药板块 =====
    {"symbol": "600276", "name": "恒瑞医药", "market": "A_SHARE", "exchange": "SH", "industry": "医药", "sector": "医药"},
    {"symbol": "603259", "name": "药明康德", "market": "A_SHARE", "exchange": "SH", "industry": "CXO", "sector": "医药"},
    {"symbol": "300760", "name": "迈瑞医疗", "market": "A_SHARE", "exchange": "SZ", "industry": "医疗器械", "sector": "医药"},
    # ===== A股 - 公用事业/工业 =====
    {"symbol": "600900", "name": "长江电力", "market": "A_SHARE", "exchange": "SH", "industry": "电力", "sector": "公用事业"},
    {"symbol": "601888", "name": "中国中免", "market": "A_SHARE", "exchange": "SH", "industry": "免税", "sector": "消费"},
    {"symbol": "600585", "name": "海螺水泥", "market": "A_SHARE", "exchange": "SH", "industry": "水泥", "sector": "工业"},
    # ===== 港股 - 科技板块 =====
    {"symbol": "00700", "name": "腾讯控股", "market": "HK", "exchange": "HK", "industry": "互联网", "sector": "科技"},
    {"symbol": "09988", "name": "阿里巴巴-W", "market": "HK", "exchange": "HK", "industry": "电商", "sector": "科技"},
    {"symbol": "09618", "name": "京东集团-SW", "market": "HK", "exchange": "HK", "industry": "电商", "sector": "科技"},
    {"symbol": "01810", "name": "小米集团-W", "market": "HK", "exchange": "HK", "industry": "消费电子", "sector": "科技"},
    {"symbol": "03690", "name": "美团-W", "market": "HK", "exchange": "HK", "industry": "本地生活", "sector": "科技"},
    {"symbol": "09888", "name": "百度集团-SW", "market": "HK", "exchange": "HK", "industry": "搜索引擎", "sector": "科技"},
    {"symbol": "09999", "name": "网易-S", "market": "HK", "exchange": "HK", "industry": "游戏", "sector": "科技"},
    {"symbol": "01024", "name": "快手-W", "market": "HK", "exchange": "HK", "industry": "短视频", "sector": "科技"},
    # ===== 港股 - 金融板块 =====
    {"symbol": "02318", "name": "中国平安H", "market": "HK", "exchange": "HK", "industry": "保险", "sector": "金融"},
    {"symbol": "01299", "name": "友邦保险", "market": "HK", "exchange": "HK", "industry": "保险", "sector": "金融"},
    {"symbol": "00388", "name": "香港交易所", "market": "HK", "exchange": "HK", "industry": "交易所", "sector": "金融"},
    {"symbol": "03968", "name": "招商银行H", "market": "HK", "exchange": "HK", "industry": "银行", "sector": "金融"},
    # ===== 港股 - 消费/医药板块 =====
    {"symbol": "02020", "name": "安踏体育", "market": "HK", "exchange": "HK", "industry": "运动服饰", "sector": "消费"},
    {"symbol": "09633", "name": "农夫山泉", "market": "HK", "exchange": "HK", "industry": "饮料", "sector": "消费"},
    {"symbol": "02269", "name": "药明生物", "market": "HK", "exchange": "HK", "industry": "CXO", "sector": "医药"},
    {"symbol": "00027", "name": "银河娱乐", "market": "HK", "exchange": "HK", "industry": "博彩", "sector": "消费"},
    {"symbol": "01928", "name": "金沙中国有限公司", "market": "HK", "exchange": "HK", "industry": "博彩", "sector": "消费"},
]


def seed(force: bool = False):
    """执行数据种子 - 使用真实东方财富数据"""
    print("=" * 60)
    print("融衔 数据初始化 (东方财富真实数据)")
    print("=" * 60)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # 创建测试账号
    _seed_users(db)

    # 检查是否已有数据
    existing = db.query(Stock).count()
    if existing > 0 and not force:
        print(f"Database already has {existing} stocks. Skipping seed.")
        print("To re-seed: python -m app.seed --force")
        db.close()
        return

    if force:
        print("Force mode: clearing existing data...")
        _clear_data(db)

    # 0. 同步全量A股+港股列表（新浪+腾讯）
    print("\n[0/8] Syncing full stock list (A-share + HK)...")
    from app.services.stock_sync import sync_stock_list
    sync_result = sync_stock_list(db, market="ALL")
    print(f"  Synced: {sync_result['total']} stocks (A-share + HK)")

    # 1. 插入核心股票（带行业/板块信息），并构建全量 stock_map
    print("\n[1/8] Seeding core stocks with industry info...")
    # 先用 CORE_STOCKS 更新行业信息
    for s in CORE_STOCKS:
        existing_stock = db.query(Stock).filter(Stock.symbol == s["symbol"]).first()
        if existing_stock:
            existing_stock.industry = s.get("industry", "")
            existing_stock.sector = s.get("sector", "")
            existing_stock.market = s.get("market", existing_stock.market)
            existing_stock.exchange = s.get("exchange", existing_stock.exchange)
        else:
            stock = Stock(**s)
            db.add(stock)
    db.commit()

    # 构建全量 stock_map（所有 ACTIVE 股票）
    all_stocks = db.query(Stock).filter(Stock.status == "ACTIVE").all()
    stock_map = {s.symbol: s.id for s in all_stocks}
    print(f"  Core stocks: {len(CORE_STOCKS)} with industry data")
    print(f"  Total active stocks: {len(stock_map)}")

    # 2. 获取真实行情数据 (并发抓取)
    print(f"\n[2/8] Fetching daily prices for {len(stock_map)} stocks...")
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    today = date.today()
    start = today - timedelta(days=180)
    price_count = 0
    failed_count = 0

    def _fetch_one_price(symbol, stock_id):
        """抓取单只股票的价格数据"""
        try:
            df = provider.fetch_daily_prices(symbol, start, today)
            if df.empty:
                return symbol, stock_id, []
            rows = []
            for _, row in df.iterrows():
                trade_date = row["trade_date"]
                if hasattr(trade_date, "date"):
                    trade_date = trade_date.date()
                rows.append(DailyPrice(
                    stock_id=stock_id,
                    trade_date=trade_date,
                    open=round(row["open"], 2),
                    high=round(row["high"], 2),
                    low=round(row["low"], 2),
                    close=round(row["close"], 2),
                    pre_close=round(row["pre_close"], 2) if row.get("pre_close") and not _is_nan(row["pre_close"]) else None,
                    volume=round(row["volume"], 0),
                    turnover=round(row["turnover"], 0),
                    turnover_rate=round(row["turnover_rate"], 2) if not _is_nan(row.get("turnover_rate")) else 0,
                    market_cap=round(row["market_cap"], 0) if row.get("market_cap") and not _is_nan(row["market_cap"]) else None,
                    pe=round(row["pe"], 2) if row.get("pe") and not _is_nan(row["pe"]) else None,
                    pb=round(row["pb"], 2) if row.get("pb") and not _is_nan(row["pb"]) else None,
                    dividend_yield=round(row["dividend_yield"], 2) if row.get("dividend_yield") and not _is_nan(row["dividend_yield"]) else None,
                ))
            return symbol, stock_id, rows
        except Exception as e:
            return symbol, stock_id, None

    # 并发抓取，最多 10 个线程
    items = list(stock_map.items())
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_fetch_one_price, sym, sid): sym for sym, sid in items}
        done = 0
        for future in as_completed(futures):
            done += 1
            sym, sid, rows = future.result()
            if rows is None:
                failed_count += 1
            elif rows:
                db.add_all(rows)
                price_count += len(rows)
            # 每 100 只股票提交一次
            if done % 100 == 0:
                db.commit()
                print(f"  Progress: {done}/{len(items)} stocks, {price_count} prices")
    db.commit()
    print(f"  Total: {price_count} daily prices ({failed_count} failed)")

    # 3. 获取真实财务数据 (并发抓取)
    print(f"\n[3/8] Fetching financial metrics for {len(stock_map)} stocks...")
    fin_count = 0
    fin_failed = 0

    def _fetch_one_financial(symbol, stock_id):
        """抓取单只股票的财务数据"""
        try:
            df = provider.fetch_financial_metrics(symbol)
            if df.empty:
                return symbol, stock_id, []
            rows = []
            for _, row in df.iterrows():
                rows.append(FinancialMetric(
                    stock_id=stock_id,
                    report_period=row.get("report_period", ""),
                    revenue=_safe_round(row.get("revenue"), 2),
                    revenue_yoy=_safe_round(row.get("revenue_yoy"), 2),
                    net_profit=_safe_round(row.get("net_profit"), 2),
                    net_profit_yoy=_safe_round(row.get("net_profit_yoy"), 2),
                    gross_margin=_safe_round(row.get("gross_margin"), 2),
                    net_margin=_safe_round(row.get("net_margin"), 2),
                    roe=_safe_round(row.get("roe"), 2),
                    roa=_safe_round(row.get("roa"), 2),
                    debt_ratio=_safe_round(row.get("debt_ratio"), 2),
                    operating_cashflow=_safe_round(row.get("operating_cashflow"), 2),
                    free_cashflow=_safe_round(row.get("free_cashflow"), 2),
                    eps=_safe_round(row.get("eps"), 2),
                    book_value_per_share=_safe_round(row.get("book_value_per_share"), 2),
                ))
            return symbol, stock_id, rows
        except Exception as e:
            return symbol, stock_id, None

    # Yahoo Finance 限流较严，用 3 个线程
    items = list(stock_map.items())
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(_fetch_one_financial, sym, sid): sym for sym, sid in items}
        done = 0
        for future in as_completed(futures):
            done += 1
            sym, sid, rows = future.result()
            if rows is None:
                fin_failed += 1
            elif rows:
                db.add_all(rows)
                fin_count += len(rows)
            if done % 50 == 0:
                db.commit()
                print(f"  Progress: {done}/{len(items)} stocks, {fin_count} reports")
    db.commit()
    print(f"  Total: {fin_count} financial reports ({fin_failed} failed)")

    # 3.5 从已有数据计算估值 (PE/PB)
    print("\n[3.5/8] Computing valuation from price + financial data...")
    for symbol, stock_id in stock_map.items():
        latest_price = db.query(DailyPrice).filter(
            DailyPrice.stock_id == stock_id
        ).order_by(DailyPrice.trade_date.desc()).first()
        latest_fin = db.query(FinancialMetric).filter(
            FinancialMetric.stock_id == stock_id
        ).order_by(FinancialMetric.report_period.desc()).first()
        if latest_price and latest_fin:
            if latest_fin.eps and latest_fin.eps > 0:
                latest_price.pe = round(latest_price.close / latest_fin.eps, 2)
            if latest_fin.book_value_per_share and latest_fin.book_value_per_share > 0:
                latest_price.pb = round(latest_price.close / latest_fin.book_value_per_share, 2)
    db.commit()
    print("  Valuation computed from financial data")

    # 4. 计算技术指标
    print("\n[4/8] Computing technical indicators...")
    tech_count = _compute_technicals(db, stock_map)
    print(f"  Total: {tech_count} technical indicators")

    # 5. 评分
    print("\n[5/8] Scoring stocks...")
    score_count = _score_stocks(db, stock_map, today)
    print(f"  Total: {score_count} scores")

    # 6. 生成信号
    print("\n[6/8] Generating trading signals...")
    signal_count = _generate_signals(db, today)
    print(f"  Total: {signal_count} signals")

    # 7. 生成报告
    print("\n[7/8] Generating daily report...")
    report = generate_daily_report(db, today)
    print(f"  Report: {report.title}")

    # 8. 创建组合
    print("\n[8/8] Creating portfolio...")
    _create_portfolio(db, today)

    db.close()
    print("\n" + "=" * 60)
    print("Seed completed successfully!")
    print("=" * 60)
    print("Disclaimer: 本系统仅用于研究和辅助分析，不构成任何投资建议。")


def _seed_users(db):
    """创建测试账号"""
    test_accounts = [
        {"username": "admin", "password": "admin123", "display_name": "管理员", "role": "admin"},
        {"username": "demo", "password": "demo123", "display_name": "演示用户", "role": "user"},
        {"username": "analyst", "password": "analyst123", "display_name": "分析师", "role": "analyst"},
        {"username": "guest", "password": "guest123", "display_name": "访客", "role": "guest"},
    ]
    for acc in test_accounts:
        existing = db.query(User).filter(User.username == acc["username"]).first()
        if not existing:
            pw_hash = bcrypt.hashpw(acc["password"].encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            user = User(
                username=acc["username"],
                password_hash=pw_hash,
                display_name=acc["display_name"],
                role=acc["role"],
            )
            db.add(user)
            print(f"  Created user: {acc['username']} / {acc['password']}")
        else:
            # 确保已有用户的 role 始终正确
            if existing.role != acc["role"]:
                existing.role = acc["role"]
                print(f"  Updated {acc['username']} role -> {acc['role']}")
    db.commit()

    # 创建默认通知设置
    default_settings = [
        ("email_smtp_host", "smtp.qq.com", "SMTP 服务器"),
        ("email_smtp_port", "465", "SMTP 端口"),
        ("email_sender", "", "发件邮箱 (QQ邮箱)"),
        ("email_password", "", "邮箱授权码"),
        ("email_recipient", "", "收件邮箱"),
        ("feishu_webhook", "", "飞书 Webhook URL"),
        ("feishu_enabled", "false", "启用飞书推送"),
    ]
    for key, value, desc in default_settings:
        existing = db.query(Setting).filter(Setting.key == key).first()
        if not existing:
            db.add(Setting(key=key, value=value, description=desc))
    db.commit()


def _clear_data(db):
    """清除所有数据表（保留用户）"""
    for model in [PortfolioPosition, Portfolio, Report, TradeSignal, StockScore, TechnicalIndicator, FinancialMetric, DailyPrice, Stock]:
        db.query(model).delete()
    db.commit()


def _compute_technicals(db, stock_map):
    """计算技术指标（真实算法）"""
    count = 0
    for symbol, stock_id in stock_map.items():
        prices = db.query(DailyPrice).filter(DailyPrice.stock_id == stock_id).order_by(DailyPrice.trade_date).all()
        if len(prices) < 26:
            continue
        closes = [p.close for p in prices]
        volumes = [p.volume for p in prices]

        # 预计算全量 EMA 序列
        ema12_series = _ema(closes, 12)
        ema26_series = _ema(closes, 26)
        macd_series = [ema12_series[i] - ema26_series[i] for i in range(len(closes))]
        macd_signal_series = _ema(macd_series, 9)

        for i, p in enumerate(prices):
            if i < 19:
                continue
            ma20 = float(np.mean(closes[max(0, i-19):i+1]))
            ma60 = float(np.mean(closes[max(0, i-59):i+1])) if i >= 59 else None
            ma120 = float(np.mean(closes[max(0, i-119):i+1])) if i >= 119 else None
            vol_ma5 = float(np.mean(volumes[max(0, i-4):i+1]))
            vol_ma20 = float(np.mean(volumes[max(0, i-19):i+1]))

            # 真实 MACD（EMA12 - EMA26，信号线为 MACD 的 9 周期 EMA）
            macd = macd_series[i]
            macd_sig = macd_signal_series[i]

            # 真实 RSI（14 周期 Wilder 平滑）
            rsi = _rsi(closes[:i+1], 14)

            # 真实布林带（MA20 ± 2 倍标准差）
            window = closes[max(0, i-19):i+1]
            boll_std = statistics.stdev(window) if len(window) >= 2 else 0
            boll_upper = ma20 + 2 * boll_std
            boll_lower = ma20 - 2 * boll_std

            ti = TechnicalIndicator(
                stock_id=stock_id,
                trade_date=p.trade_date,
                ma20=round(ma20, 2),
                ma60=round(ma60, 2) if ma60 else None,
                ma120=round(ma120, 2) if ma120 else None,
                macd=round(macd, 4),
                macd_signal=round(macd_sig, 4),
                macd_hist=round(macd - macd_sig, 4),
                rsi14=round(rsi, 2),
                boll_upper=round(boll_upper, 2),
                boll_middle=round(ma20, 2),
                boll_lower=round(boll_lower, 2),
                volume_ma5=round(vol_ma5, 0),
                volume_ma20=round(vol_ma20, 0),
            )
            db.add(ti)
            count += 1
    db.commit()
    return count


def _score_stocks(db, stock_map, score_date):
    """对所有股票使用真实算法评分"""
    count = 0
    for symbol, stock_id in stock_map.items():
        price = db.query(DailyPrice).filter(DailyPrice.stock_id == stock_id).order_by(DailyPrice.trade_date.desc()).first()
        financial = db.query(FinancialMetric).filter(FinancialMetric.stock_id == stock_id).order_by(FinancialMetric.report_period.desc()).first()
        tech = db.query(TechnicalIndicator).filter(TechnicalIndicator.stock_id == stock_id).order_by(TechnicalIndicator.trade_date.desc()).first()

        if not price:
            continue

        q_score, q_detail = calculate_quality_score(financial) if financial else (0, ["无财务数据"])
        v_score, v_detail = calculate_valuation_score(price, financial) if financial else (0, ["无财务数据"])
        g_score, g_detail = calculate_growth_score(financial) if financial else (0, ["无财务数据"])
        t_score, t_detail = calculate_trend_score(price, tech) if tech else (0, ["无技术数据"])
        r_score, r_detail = calculate_risk_score(financial, price) if financial else (0, ["无财务数据"])

        total = q_score + v_score + g_score + t_score + r_score
        all_details = q_detail + v_detail + g_detail + t_detail + r_detail
        # detail 列表元素为 dict: {"item": ..., "value": ..., "score": ..., "status": ...}
        if all_details:
            reason = "; ".join(f"{d['item']}{d['value']}" if isinstance(d, dict) else str(d) for d in all_details[:5])
        else:
            reason = f"质量{q_score:.0f} 估值{v_score:.0f} 成长{g_score:.0f} 趋势{t_score:.0f} 风险{r_score:.0f}"

        rating = get_rating(total)

        score = StockScore(
            stock_id=stock_id,
            score_date=score_date,
            total_score=round(total, 1),
            quality_score=round(q_score, 1),
            valuation_score=round(v_score, 1),
            growth_score=round(g_score, 1),
            trend_score=round(t_score, 1),
            risk_score=round(r_score, 1),
            rating=rating,
            reason_summary=reason,
        )
        db.add(score)
        count += 1
    db.commit()
    return count


def _generate_signals(db, signal_date):
    """生成交易信号"""
    count = 0
    scores = db.query(StockScore).filter(StockScore.score_date == signal_date).all()
    for sc in scores:
        price = db.query(DailyPrice).filter(DailyPrice.stock_id == sc.stock_id).order_by(DailyPrice.trade_date.desc()).first()
        if not price:
            continue

        sig_type, strength, logic = determine_signal_type(sc)
        position = calculate_position(sig_type, strength)
        entry, target, stop_loss = calculate_prices(price, sig_type)

        holding_map = {"BUY": "3-6个月", "ADD": "2-4个月", "WATCH": "-", "REDUCE": "逐步减仓", "SELL": "立即"}

        signal = TradeSignal(
            stock_id=sc.stock_id,
            signal_date=signal_date,
            signal_type=sig_type,
            signal_strength=strength,
            suggested_position=position,
            entry_price=entry,
            target_price=target,
            stop_loss_price=stop_loss,
            holding_period=holding_map.get(sig_type, "-"),
            logic_json={
                "total_score": sc.total_score,
                "quality_score": sc.quality_score,
                "valuation_score": sc.valuation_score,
                "growth_score": sc.growth_score,
                "trend_score": sc.trend_score,
                "risk_score": sc.risk_score,
                "reason": logic,
            },
            risk_json={"items": ["关注宏观经济变化"] if sc.risk_score and sc.risk_score >= 5 else ["风险评分偏低", "注意仓位控制"]},
            status=SignalStatus.ACTIVE,
        )
        db.add(signal)
        count += 1
    db.commit()
    return count


def _create_portfolio(db, score_date):
    """创建模拟组合"""
    portfolio = Portfolio(
        name="基本面中长期组合",
        strategy_type="fundamental_medium_long",
        target_position=65.0,
        cash_ratio=35.0,
    )
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)

    buy_scores = db.query(StockScore).filter(
        StockScore.score_date == score_date,
        StockScore.rating.in_(["BUY", "ADD"])
    ).all()
    pos_ratio = 65.0 / max(len(buy_scores), 1)
    for sc in buy_scores:
        price = db.query(DailyPrice).filter(DailyPrice.stock_id == sc.stock_id).order_by(DailyPrice.trade_date.desc()).first()
        if price:
            # 模拟持仓收益：买入价比当前价低 5-15%
            import random
            cost_factor = random.uniform(0.85, 0.95)
            cost = round(price.close * cost_factor, 2)
            ret = round((price.close - cost) / cost * 100, 2)
            pp = PortfolioPosition(
                portfolio_id=portfolio.id,
                stock_id=sc.stock_id,
                position_ratio=round(pos_ratio, 1),
                cost_price=cost,
                current_price=price.close,
                unrealized_return=ret,
            )
            db.add(pp)
    db.commit()
    print(f"  Created portfolio with {len(buy_scores)} positions")


def _safe_round(val, decimals):
    """安全四舍五入，处理 None/NaN"""
    if val is None or _is_nan(val):
        return None
    try:
        return round(float(val), decimals)
    except (ValueError, TypeError):
        return None


def _is_nan(val):
    """判断是否为 NaN"""
    if val is None:
        return True
    try:
        import math
        return math.isnan(float(val))
    except (ValueError, TypeError):
        return True


def refresh_daily():
    """每日增量刷新 - 更新所有有行情数据的股票"""
    import time
    print(f"[{date.today()}] Daily refresh starting...")
    db = SessionLocal()

    today = date.today()
    yesterday = today - timedelta(days=1)

    # 获取所有有行情数据的股票（不仅限于CORE_STOCKS）
    stocks_with_prices = db.query(Stock).filter(
        Stock.status == "ACTIVE",
        Stock.id.in_(db.query(DailyPrice.stock_id).distinct())
    ).all()

    if not stocks_with_prices:
        print("No stocks with price data. Run seed first.")
        db.close()
        return

    stock_map = {s.symbol: s.id for s in stocks_with_prices}
    print(f"  Found {len(stock_map)} stocks with existing data")

    # 更新行情
    for idx, (symbol, stock_id) in enumerate(stock_map.items()):
        if idx > 0 and not _use_mock:
            time.sleep(1)  # 减少等待时间
        try:
            df = provider.fetch_daily_prices(symbol, yesterday, today)
            for _, row in df.iterrows():
                trade_date = row["trade_date"]
                if hasattr(trade_date, "date"):
                    trade_date = trade_date.date()
                existing = db.query(DailyPrice).filter(
                    DailyPrice.stock_id == stock_id,
                    DailyPrice.trade_date == trade_date
                ).first()
                if existing:
                    continue
                dp = DailyPrice(
                    stock_id=stock_id,
                    trade_date=trade_date,
                    open=round(row["open"], 2),
                    high=round(row["high"], 2),
                    low=round(row["low"], 2),
                    close=round(row["close"], 2),
                    pre_close=round(row["pre_close"], 2) if row.get("pre_close") and not _is_nan(row["pre_close"]) else None,
                    volume=round(row["volume"], 0),
                    turnover=round(row["turnover"], 0),
                    turnover_rate=round(row["turnover_rate"], 2) if not _is_nan(row.get("turnover_rate")) else 0,
                )
                db.add(dp)
            db.commit()
        except Exception as e:
            db.rollback()
            if idx < 5:  # 只打印前几个错误
                print(f"  Error refreshing {symbol}: {e}")

    print(f"  Price refresh completed for {len(stock_map)} stocks")

    # 重新评分和生成信号
    _score_stocks(db, stock_map, today)
    _generate_signals(db, today)
    generate_daily_report(db, today)

    db.close()
    print(f"[{today}] Daily refresh completed.")


# 导入报告生成（放在最后避免循环引用）
from app.services.report import generate_daily_report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Force re-seed (clear existing data)")
    parser.add_argument("--refresh", action="store_true", help="Daily refresh only")
    args = parser.parse_args()

    if args.refresh:
        refresh_daily()
    else:
        seed(force=args.force)
