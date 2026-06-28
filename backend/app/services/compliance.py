"""Helpers for compliant Chinese research-oriented display text."""

from __future__ import annotations

import re
from typing import Any


SIGNAL_DISPLAY_MAP = {
    "BUY": "高关注",
    "ADD": "增强关注",
    "WATCH": "观察",
    "REDUCE": "风险升高",
    "SELL": "回避观察",
}

GARBLE_MARKERS = ("姘", "蹇", "鑾", "鑼", "鐚", "閿", "闁", "鑴")

COMPLIANCE_REPLACEMENTS = [
    ("建议买入", "研究关注"),
    ("建议加仓", "增强关注"),
    ("建议减仓", "降低关注"),
    ("建议卖出", "回避观察"),
    ("建议观望", "继续观察"),
    ("建议研究关注", "研究关注"),
    ("可适当增强关注", "增强关注"),
    ("强烈推荐", "高优先级研究样本"),
    ("强烈买入", "高关注"),
    ("买入", "高关注"),
    ("加仓", "增强关注"),
    ("减仓", "风险升高"),
    ("卖出", "回避观察"),
    ("目标价", "模型观察价"),
    ("止损价", "风险警戒价"),
    ("止损位", "风险警戒位"),
    ("目标位", "模型观察位"),
    ("建议仓位", "研究仓位"),
    ("组合表现", "研究组合表现"),
    ("投资建议", "研究结论"),
    ("收益承诺", "历史研究测算结果"),
    ("收益保证", "历史研究测算结果"),
    ("确定性机会", "高优先级研究样本"),
    ("自动荐股", "研究筛选"),
    ("智能投顾", "智能投研工作台"),
    ("跑赢市场", "相对基准表现更强"),
    ("跑赢指数", "相对基准表现更强"),
    ("观望等待", "继续观察"),
]

EXPLICIT_COMPLIANCE_REPLACEMENTS = [
    ("建议买入", "建议重点研究"),
    ("建议加仓", "建议增强关注"),
    ("建议减仓", "建议降低关注"),
    ("建议卖出", "建议回避观察"),
    ("建议观望", "建议继续观察"),
    ("强烈买入", "高关注"),
    ("强烈推荐", "高优先级研究样本"),
    ("买入机会", "研究观察窗口"),
    ("建仓机会", "研究观察窗口"),
    ("操作建议", "研究提示"),
    ("投资建议", "研究结论"),
    ("买入策略", "研究观察策略"),
    ("卖出策略", "风险应对策略"),
    ("买入纪律", "研究观察纪律"),
    ("卖出纪律", "风险应对纪律"),
    ("建仓", "分步观察"),
    ("加仓", "增强关注"),
    ("减仓", "降低关注"),
    ("卖出", "回避观察"),
    ("止损价", "风险警戒价"),
    ("止损位", "风险警戒位"),
    ("目标价", "模型观察价"),
    ("目标位", "模型观察位"),
    ("建议仓位", "研究仓位"),
    ("止盈", "阶段观察"),
    ("清仓", "退出观察"),
    ("追高", "高位跟踪"),
    ("抄底", "逆势观察"),
]


def signal_display_label(signal_type: str | None) -> str:
    if not signal_type:
        return "待观察"
    return SIGNAL_DISPLAY_MAP.get(signal_type, signal_type)


def _looks_garbled(text: str) -> bool:
    if not text:
        return False
    marker_hits = sum(text.count(marker) for marker in GARBLE_MARKERS)
    question_hits = text.count("?")
    return marker_hits >= 2 or question_hits >= max(4, len(text) // 6)


def _try_fix_utf8_mojibake(text: str) -> str:
    try:
        repaired = text.encode("latin1").decode("utf-8")
    except Exception:
        return text
    return repaired if repaired and not _looks_garbled(repaired) else text


def normalize_research_text(text: str | None) -> str:
    if not text:
        return ""
    result = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if _looks_garbled(result):
        result = _try_fix_utf8_mojibake(result)
    for source, target in COMPLIANCE_REPLACEMENTS:
        result = result.replace(source, target)
    for source, target in EXPLICIT_COMPLIANCE_REPLACEMENTS:
        result = result.replace(source, target)
    result = re.sub(r"(?m)^(\*\*)?操作建议(:|\*\*:)", "研究提示:", result)
    result = re.sub(r"(?m)^(\*\*)?投资建议(:|\*\*:)", "研究结论:", result)
    result = re.sub(r"(?m)^(\*\*)?买入策略(:|\*\*:)", "研究观察策略:", result)
    result = re.sub(r"(?m)^(\*\*)?卖出策略(:|\*\*:)", "风险应对策略:", result)
    result = re.sub(r"(?m)^(\*\*)?买入纪律(:|\*\*:)", "研究观察纪律:", result)
    result = re.sub(r"(?m)^(\*\*)?卖出纪律(:|\*\*:)", "风险应对纪律:", result)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip()


def sanitize_research_text(text: str | None) -> str:
    normalized = normalize_research_text(text)
    if not normalized:
        return ""
    if _looks_garbled(normalized):
        return "原始文本存在编码异常，已隐藏原文，请以结构化评分和数据为准。"
    return normalized


def sanitize_nested_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {key: sanitize_nested_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [sanitize_nested_payload(item) for item in payload]
    if isinstance(payload, str):
        return sanitize_research_text(payload)
    return payload


def build_report_header(
    *,
    report_type: str,
    generated_at: str,
    data_as_of: str,
    data_sources: str,
    mode: str = "研究口径",
    has_live_trading: bool = False,
) -> str:
    live_text = "不含实盘交易数据" if not has_live_trading else "含部分实盘数据"
    return "\n".join(
        [
            "## 报告说明",
            f"- 报告类型: {report_type}",
            f"- 生成时间: {generated_at}",
            f"- 数据截至: {data_as_of}",
            f"- 数据来源: {data_sources}",
            f"- 数据口径: {mode}",
            f"- 实盘状态: {live_text}",
            "- 免责声明: 本报告由系统根据公开数据和模型规则生成，仅用于研究辅助，不构成投资建议，不代表未来收益。",
            "",
            "---",
            "",
        ]
    )


def build_report_footer(generated_at: str) -> str:
    return "\n".join(
        [
            "",
            "---",
            "",
            "## 免责声明",
            "- 本报告由系统根据公开市场数据、历史行情和模型规则自动生成，仅用于研究辅助。",
            "- 报告中的评分、信号、回测和情景推演不构成投资建议，也不代表未来收益。",
            "- 如存在指标缺失、样本不足、模拟数据或第三方抓取滞后，请以页面标注和管理员状态页为准。",
            f"- 报告生成时间: {generated_at}",
        ]
    )
