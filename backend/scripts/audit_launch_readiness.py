"""
Launch readiness audit - read-only, no DB writes.
Usage: cd backend && PYTHONPATH=. python scripts/audit_launch_readiness.py
"""
from __future__ import annotations
import json, os, sys, sqlite3
from pathlib import Path

def main():
    db_path = Path(__file__).parent.parent / "stock_agent.db"
    if not db_path.exists():
        print("DB not found"); return
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()
    report = {}

    # === 1. Data coverage ===
    def count(sql):
        try: return c.execute(sql).fetchone()[0]
        except: return -1

    coverage = {
        "stocks": count("SELECT COUNT(*) FROM stocks"),
        "daily_prices": count("SELECT COUNT(*) FROM daily_prices"),
        "daily_prices_stocks": count("SELECT COUNT(DISTINCT stock_id) FROM daily_prices"),
        "prices_ge30": count("SELECT COUNT(*) FROM (SELECT stock_id FROM daily_prices GROUP BY stock_id HAVING COUNT(*) >= 30)"),
        "prices_ge60": count("SELECT COUNT(*) FROM (SELECT stock_id FROM daily_prices GROUP BY stock_id HAVING COUNT(*) >= 60)"),
        "prices_ge100": count("SELECT COUNT(*) FROM (SELECT stock_id FROM daily_prices GROUP BY stock_id HAVING COUNT(*) >= 100)"),
        "financial_metrics": count("SELECT COUNT(*) FROM financial_metrics"),
        "financial_stocks": count("SELECT COUNT(DISTINCT stock_id) FROM financial_metrics"),
        "technical_indicators": count("SELECT COUNT(*) FROM technical_indicators"),
        "technical_stocks": count("SELECT COUNT(DISTINCT stock_id) FROM technical_indicators"),
        "real_score": count("SELECT COUNT(*) FROM stock_scores WHERE score_source='real_calculated'"),
        "demo_score": count("SELECT COUNT(*) FROM stock_scores WHERE score_source='quick_seed_demo'"),
        "real_signal": count("SELECT COUNT(*) FROM trade_signals WHERE signal_source='real_calculated'"),
        "demo_signal": count("SELECT COUNT(*) FROM trade_signals WHERE signal_source='quick_seed_demo'"),
        "pe_non_null": count("SELECT COUNT(*) FROM daily_prices WHERE pe IS NOT NULL AND pe > 0"),
        "pb_non_null": count("SELECT COUNT(*) FROM daily_prices WHERE pb IS NOT NULL AND pb > 0"),
        "market_cap_non_null": count("SELECT COUNT(*) FROM daily_prices WHERE market_cap IS NOT NULL AND market_cap > 0"),
        "gross_margin_non_null": count("SELECT COUNT(*) FROM financial_metrics WHERE gross_margin IS NOT NULL AND gross_margin > 0"),
        "reports": count("SELECT COUNT(*) FROM reports"),
        "research_reports": count("SELECT COUNT(*) FROM research_reports"),
    }
    report["data_coverage"] = coverage

    # === 2. Core samples ===
    samples = {}
    for sym in ["002415", "600519", "300866"]:
        row = c.execute("SELECT id, name, market, exchange FROM stocks WHERE symbol=?", (sym,)).fetchone()
        if not row:
            samples[sym] = {"found": False}
            continue
        sid = row[0]
        prices = count(f"SELECT COUNT(*) FROM daily_prices WHERE stock_id={sid}")
        fin = count(f"SELECT COUNT(*) FROM financial_metrics WHERE stock_id={sid}")
        tech = count(f"SELECT COUNT(*) FROM technical_indicators WHERE stock_id={sid}")
        sc = c.execute(f"SELECT score_source, total_score, rating FROM stock_scores WHERE stock_id={sid} ORDER BY score_date DESC LIMIT 1").fetchone()
        sig = c.execute(f"SELECT signal_source, signal_type FROM trade_signals WHERE stock_id={sid} ORDER BY signal_date DESC LIMIT 1").fetchone()
        pe = c.execute(f"SELECT pe FROM daily_prices WHERE stock_id={sid} AND pe IS NOT NULL ORDER BY trade_date DESC LIMIT 1").fetchone()
        readiness = "ready_full" if prices >= 60 and fin >= 4 and tech >= 1 else ("ready_partial" if prices > 0 else "not_ready")
        samples[sym] = {
            "found": True, "name": row[1], "market": row[2], "exchange": row[3],
            "prices": prices, "financial": fin, "technical": tech,
            "readiness": readiness,
            "score_source": sc[0] if sc else None, "total_score": sc[1] if sc else None, "rating": sc[2] if sc else None,
            "signal_source": sig[0] if sig else None, "signal_type": sig[1] if sig else None,
            "pe": pe[0] if pe else None,
        }
    report["core_samples"] = samples

    # === 3. Bottlenecks ===
    report["bottlenecks"] = {
        "why_real_score_only_45": f"technical_indicators only covers {coverage['technical_stocks']} stocks; scoring requires price+financial+technical",
        "why_technical_only_66": "Only 66 stocks have had technical indicators computed from daily_prices",
        "why_pe_pb_low": f"PE={coverage['pe_non_null']}, PB={coverage['pb_non_null']} - external API rate-limited, fallback from financials only covers stocks with EPS/BVPS",
        "why_market_cap_zero": "No total_share data in DB; market_cap = close * total_share cannot be computed",
        "why_pools_empty": "All 45 real scores are SELL/REDUCE; pool thresholds require quality>=10, undervalued>=5, trend>=8 etc.",
        "why_no_formal_signals": "All 45 real signals are SELL(42)+REDUCE(3); no BUY/ADD/WATCH because scores are all < 65",
        "why_stocks_filter_lt_real": "Filters (market/rating/keyword) reduce visible count; demo isolation also reduces",
    }

    # === 4. Signal distribution ===
    sig_dist = {}
    for row in c.execute("SELECT signal_type, COUNT(*) FROM trade_signals WHERE signal_source='real_calculated' GROUP BY signal_type").fetchall():
        sig_dist[row[0]] = row[1]
    score_dist = {}
    for row in c.execute("SELECT rating, COUNT(*) FROM stock_scores WHERE score_source='real_calculated' GROUP BY rating").fetchall():
        score_dist[row[0]] = row[1]
    report["real_distribution"] = {"signals": sig_dist, "scores": score_dist}

    conn.close()
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))

if __name__ == "__main__":
    main()
