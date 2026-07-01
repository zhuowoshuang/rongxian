"""Unified research-display summary for dashboard, signals, stocks, and pools."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.services.score_diagnostics import diagnose_real_scores
from app.services.system_status import build_system_status


def build_research_display_summary(
    db: Session,
    *,
    include_demo: bool = False,
    score_date: date | None = None,
) -> dict[str, Any]:
    system_status = build_system_status(db)
    diagnostics = diagnose_real_scores(db, score_date=score_date)
    diagnostics_summary = diagnostics.get("summary", {})
    low_score_reasons = diagnostics.get("low_score_reasons", [])[:5]
    diagnostics_items = diagnostics.get("items", [])
    real_items = [item for item in diagnostics_items if item.get("score_source") == "real_calculated"]
    signal_distribution = diagnostics.get("signal_distribution", {})
    risk_rising_count = signal_distribution.get("RISK_RISING", 0)
    avoid_observation_count = signal_distribution.get("AVOID_OBSERVATION", 0)
    risk_observation_count = risk_rising_count + avoid_observation_count
    real_highest_score = max((item.get("total_score") or 0) for item in real_items) if real_items else 0

    if diagnostics_summary.get("formal_real_count", 0) > 0:
        headline = "当前已有正式研究样本，可继续查看重点信号、股票池和个股追溯。"
    elif diagnostics_summary.get("real_count", 0) > 0:
        headline = "当前真实样本仍处于研究观察阶段，暂不形成正式高关注结论。"
    else:
        headline = "当前尚未形成可展示的真实研究样本，页面仅展示数据状态与待补齐项。"

    return {
        "include_demo": include_demo,
        "headline": headline,
        "system": {
            "data_mode": system_status.get("data_mode"),
            "data_mode_label": system_status.get("data_mode_label"),
            "warning": system_status.get("warning"),
            "provider_mode": system_status.get("provider_mode"),
            "real_score_count": system_status.get("real_score_count", 0),
            "demo_score_count": system_status.get("demo_score_count", 0),
            "real_signal_count": system_status.get("real_signal_count", 0),
            "demo_signal_count": system_status.get("demo_signal_count", 0),
            "latest_updates": system_status.get("latest_updates", {}),
            "counts": system_status.get("counts", {}),
            "financial_metrics_count": system_status.get("financial_metrics_count", 0),
            "technical_indicators_count": system_status.get("technical_indicators_count", 0),
        },
        "diagnostics": {
            "score_date": diagnostics_summary.get("score_date"),
            "real_count": diagnostics_summary.get("real_count", 0),
            "demo_count": diagnostics_summary.get("demo_count", 0),
            "formal_real_count": diagnostics_summary.get("formal_real_count", 0),
            "real_observation_count": diagnostics_summary.get("real_observation_count", 0),
            "data_quality_limited_count": diagnostics_summary.get("data_quality_limited_count", 0),
            "data_insufficient_count": diagnostics_summary.get("data_insufficient_count", 0),
            "risk_observation_count": risk_observation_count,
            "risk_rising_count": risk_rising_count,
            "avoid_observation_count": avoid_observation_count,
            "core_total": diagnostics_summary.get("core_total", 0),
            "core_ready_full_count": diagnostics_summary.get("core_ready_full_count", 0),
            "launch_data_status": diagnostics_summary.get("launch_data_status"),
            "message": diagnostics_summary.get("message"),
            "signal_distribution": diagnostics.get("signal_distribution", {}),
            "display_tier_distribution": diagnostics.get("display_tier_distribution", {}),
            "top_reasons": low_score_reasons,
            "avg_total_score": diagnostics_summary.get("avg_total_score"),
            "avg_quality_score": diagnostics_summary.get("avg_quality_score"),
            "avg_valuation_score": diagnostics_summary.get("avg_valuation_score"),
            "avg_growth_score": diagnostics_summary.get("avg_growth_score"),
            "avg_trend_score": diagnostics_summary.get("avg_trend_score"),
            "avg_risk_score": diagnostics_summary.get("avg_risk_score"),
            "real_highest_score": round(real_highest_score, 1) if real_highest_score else 0,
            "items": real_items[:20],
        },
    }
