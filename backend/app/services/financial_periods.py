"""Utilities for normalizing financial report periods into sortable dates."""

from __future__ import annotations

from datetime import date
from typing import Any


CHINESE_REPORT_SUFFIXES = {
    "一季报": "-03-31",
    "中报": "-06-30",
    "半年报": "-06-30",
    "三季报": "-09-30",
    "年报": "-12-31",
}

QUARTER_REPORT_SUFFIXES = {
    "Q1": "-03-31",
    "Q2": "-06-30",
    "Q3": "-09-30",
    "Q4": "-12-31",
}


def normalize_report_period_to_date(report_period: str | None) -> date | None:
    if not report_period:
        return None

    value = str(report_period).strip()
    if not value:
        return None

    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        pass

    normalized = value.upper().replace(" ", "")
    for suffix, date_suffix in CHINESE_REPORT_SUFFIXES.items():
        if normalized.endswith(suffix) and len(normalized) >= 4:
            year = normalized[:4]
            if year.isdigit():
                try:
                    return date.fromisoformat(f"{year}{date_suffix}")
                except ValueError:
                    return None

    for suffix, date_suffix in QUARTER_REPORT_SUFFIXES.items():
        if normalized.endswith(suffix) and len(normalized) >= 6:
            year = normalized[:4]
            if year.isdigit():
                try:
                    return date.fromisoformat(f"{year}{date_suffix}")
                except ValueError:
                    return None

    return None


def normalize_report_date(value: Any, report_period: str | None = None) -> date | None:
    if value is None:
        return normalize_report_period_to_date(report_period)
    if isinstance(value, date):
        return value
    if hasattr(value, "date"):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return normalize_report_period_to_date(report_period)
