"""
PDF 生成服务 — 清数智算量化分析系统
使用 xhtml2pdf 将 Markdown 报告转换为专业排版的 PDF
特性：中文字体、数据清洗、研究评级映射、页眉页脚、免责声明
"""
import re
import html
from io import BytesIO
from xhtml2pdf import pisa


# ==================== 数据清洗 ====================

# 研究评级映射（内部枚举 → 中文展示）
RATING_MAP = {
    "BUY": "高关注",
    "ADD": "增强关注",
    "WATCH": "观察",
    "REDUCE": "风险升高",
    "SELL": "回避观察",
}

# 需要清洗的无效值
_NONE_VALUES = {"None", "none", "null", "undefined", "N/A", "n/a", "NaN", "nan", ""}

# 代码表达式检测（Python/JS 代码片段泄露到报告中）
_CODE_PATTERNS = [
    r"if\s+\w+\s+else",
    r"score\s+else",
    r"\.toFixed\(",
    r"lambda\s+",
    r"def\s+\w+\(",
    r"return\s+",
    r"import\s+",
    r"\.get\(",
    r"\.format\(",
    r"True\b",
    r"False\b",
    r"\bNone\b",
]


def clean_text(text: str) -> str:
    """清洗文本：替换英文枚举、清除 None、修复代码表达式泄露"""
    if not text:
        return ""

    # 替换英文研究评级为中文
    for eng, chn in RATING_MAP.items():
        text = text.replace(eng, chn)

    # 清除代码表达式泄露
    for pattern in _CODE_PATTERNS:
        text = re.sub(pattern, "暂无数据", text)

    return text


def clean_value(value) -> str:
    """清洗单个值：None/空 → '暂无数据'"""
    if value is None:
        return "暂无数据"
    s = str(value).strip()
    if s in _NONE_VALUES:
        return "暂无数据"
    # 检查是否是代码表达式
    for pattern in _CODE_PATTERNS:
        if re.search(pattern, s):
            return "暂无数据"
    return clean_text(s)


def clean_md_content(md: str) -> str:
    """清洗整个 Markdown 内容"""
    if not md:
        return ""

    # 替换英文枚举
    for eng, chn in RATING_MAP.items():
        md = md.replace(eng, chn)

    # 替换 None/null 展示
    md = re.sub(r'\bNone\b(?!\s*[-\d])', '暂无数据', md)
    md = re.sub(r'\bnull\b', '暂无数据', md)
    md = re.sub(r'\bundefined\b', '暂无数据', md)

    # 清理代码表达式泄露
    md = re.sub(r'\d+/\d+\s+if\s+\w+\s+else\s+["\']N/A["\']', '暂无数据', md)
    md = re.sub(r'if\s+\w+\s+else\s+["\']N/A["\']', '暂无数据', md)

    # 清理连续多个"暂无数据"
    md = re.sub(r'(暂无数据[，,、]\s*){2,}', '暂无数据，', md)

    # 清理连续空行
    md = re.sub(r'\n{3,}', '\n\n', md)

    return md


# ==================== Markdown → HTML ====================

def _md_to_html(md_content: str) -> str:
    """将 Markdown 转换为 HTML（支持表格、标题、列表、引用、代码块等）"""
    lines = md_content.split("\n")
    html_parts = []
    i = 0
    in_table = False
    table_header_done = False
    in_code = False
    code_lines = []
    in_blockquote = False
    quote_lines = []

    while i < len(lines):
        line = lines[i]

        # 代码块
        if line.strip().startswith("```"):
            if in_code:
                html_parts.append(f'<pre class="code-block"><code>{html.escape(chr(10).join(code_lines))}</code></pre>')
                code_lines = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        # 引用块
        if line.startswith("> "):
            if not in_blockquote:
                in_blockquote = True
                quote_lines = []
            quote_lines.append(line[2:])
            i += 1
            continue
        elif in_blockquote:
            html_parts.append(f'<blockquote class="report-quote">{_inline_html(chr(10).join(quote_lines))}</blockquote>')
            in_blockquote = False
            quote_lines = []

        # 空行
        if line.strip() == "":
            if in_table:
                html_parts.append("</tbody></table></div>")
                in_table = False
                table_header_done = False
            html_parts.append("<br/>")
            i += 1
            continue

        # 标题
        if line.startswith("# ") and not line.startswith("## "):
            html_parts.append(f'<h1 class="report-h1">{_inline_html(line[2:])}</h1>')
            i += 1
            continue
        if line.startswith("## "):
            html_parts.append(f'<h2 class="report-h2">{_inline_html(line[3:])}</h2>')
            i += 1
            continue
        if line.startswith("### "):
            html_parts.append(f'<h3 class="report-h3">{_inline_html(line[4:])}</h3>')
            i += 1
            continue

        # 水平线
        if line.strip() in ("---", "***", "___"):
            html_parts.append('<hr class="report-hr"/>')
            i += 1
            continue

        # 表格
        if line.startswith("|") and i + 1 < len(lines) and lines[i + 1].startswith("|"):
            if not in_table:
                html_parts.append('<div class="table-wrapper"><table class="report-table">')
                in_table = True
                table_header_done = False

            cells = [c.strip() for c in line.split("|")[1:-1]]

            if not table_header_done:
                html_parts.append("<thead><tr>")
                for c in cells:
                    html_parts.append(f'<th>{_inline_html(c)}</th>')
                html_parts.append("</tr></thead><tbody>")
                table_header_done = True
                # 跳过分隔行
                i += 2
                continue
            else:
                html_parts.append("<tr>")
                for c in cells:
                    html_parts.append(f'<td>{_inline_html(c)}</td>')
                html_parts.append("</tr>")
                i += 1
                continue

        if in_table:
            html_parts.append("</tbody></table></div>")
            in_table = False
            table_header_done = False

        # 有序列表
        if re.match(r"^\d+\.\s", line):
            text = re.sub(r"^\d+\.\s", "", line)
            html_parts.append(f'<div class="list-item"><span class="list-num">{re.match(r"^\d+", line).group()}.</span> {_inline_html(text)}</div>')
            i += 1
            continue

        # 无序列表
        if line.startswith("- "):
            html_parts.append(f'<div class="list-item"><span class="list-bullet">•</span> {_inline_html(line[2:])}</div>')
            i += 1
            continue

        # 普通段落
        html_parts.append(f'<p class="report-p">{_inline_html(line)}</p>')
        i += 1

    # 关闭未关闭的标签
    if in_table:
        html_parts.append("</tbody></table></div>")
    if in_blockquote:
        html_parts.append(f'<blockquote class="report-quote">{_inline_html(chr(10).join(quote_lines))}</blockquote>')
    if in_code:
        html_parts.append(f'<pre class="code-block"><code>{html.escape(chr(10).join(code_lines))}</code></pre>')

    return "\n".join(html_parts)


def _inline_html(text: str) -> str:
    """处理行内 Markdown 语法"""
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r'<strong>\1</strong>', text)
    text = re.sub(r"`([^`]+)`", r'<code class="inline-code">\1</code>', text)
    return text


# ==================== PDF HTML 模板 ====================

def _build_pdf_html(md_content: str, title: str, report_date: str = "", stock_symbol: str = "", stock_name: str = "") -> str:
    """构建完整的 PDF HTML（含封面、页眉页脚、免责声明）"""
    body_html = _md_to_html(md_content)

    # 封面信息
    cover_info = ""
    if stock_symbol:
        cover_info += f'<div class="cover-info">股票代码：{html.escape(stock_symbol)}</div>'
    if stock_name:
        cover_info += f'<div class="cover-info">公司名称：{html.escape(stock_name)}</div>'
    if report_date:
        cover_info += f'<div class="cover-info">报告日期：{html.escape(str(report_date))}</div>'

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
@page {{
    size: A4;
    margin: 2cm 1.8cm 2.5cm 1.8cm;
    @bottom-center {{
        content: "第 " counter(page) " 页";
        font-size: 9px;
        color: #94a3b8;
    }}
    @bottom-right {{
        content: "清数智算 · 研究辅助系统";
        font-size: 9px;
        color: #94a3b8;
    }}
}}

/* ── 基础排版 ── */
body {{
    font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans SC", "SimSun", "Helvetica Neue", Arial, sans-serif;
    font-size: 11px;
    line-height: 1.7;
    color: #1e293b;
    background: #fff;
}}

/* ── 封面 ── */
.cover {{
    text-align: center;
    padding-top: 100px;
    page-break-after: always;
}}
.cover .brand {{
    font-size: 36px;
    font-weight: bold;
    color: #7c3aed;
    margin-bottom: 8px;
}}
.cover .brand-sub {{
    font-size: 14px;
    color: #64748b;
    margin-bottom: 40px;
}}
.cover h1 {{
    font-size: 24px;
    color: #0f172a;
    margin-bottom: 16px;
    font-weight: 700;
}}
.cover-info {{
    font-size: 13px;
    color: #475569;
    margin: 4px 0;
}}
.cover .disclaimer {{
    font-size: 10px;
    color: #94a3b8;
    margin-top: 60px;
    padding: 0 30px;
    line-height: 1.6;
    border-top: 1px solid #e2e8f0;
    padding-top: 16px;
}}

/* ── 标题 ── */
.report-h1 {{
    font-size: 20px;
    color: #0f172a;
    border-bottom: 2px solid #7c3aed;
    padding-bottom: 8px;
    margin: 28px 0 14px 0;
    font-weight: 700;
}}
.report-h2 {{
    font-size: 16px;
    color: #0f172a;
    border-bottom: 1px solid #e2e8f0;
    padding-bottom: 6px;
    margin: 22px 0 10px 0;
    font-weight: 600;
}}
.report-h3 {{
    font-size: 13px;
    color: #334155;
    margin: 16px 0 8px 0;
    font-weight: 600;
}}
.report-hr {{
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 16px 0;
}}

/* ── 段落 ── */
.report-p {{
    margin: 6px 0;
    text-align: justify;
    color: #334155;
    font-size: 11px;
    line-height: 1.7;
}}

/* ── 引用 ── */
.report-quote {{
    border-left: 3px solid #7c3aed;
    padding: 8px 12px;
    margin: 12px 0;
    background: #f5f3ff;
    color: #475569;
    font-style: italic;
    border-radius: 0 6px 6px 0;
}}

/* ── 表格 ── */
.table-wrapper {{
    overflow-x: auto;
    margin: 12px 0;
}}
.report-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 10px;
}}
.report-table th {{
    background: #f1f5f9;
    color: #1e293b;
    padding: 7px 8px;
    text-align: left;
    border: 1px solid #d1d5db;
    font-weight: 600;
    font-size: 10px;
}}
.report-table td {{
    padding: 6px 8px;
    border: 1px solid #e5e7eb;
    color: #334155;
    font-size: 10px;
    line-height: 1.5;
}}
.report-table tr:nth-child(even) {{
    background: #f9fafb;
}}

/* ── 列表 ── */
.list-item {{
    margin: 4px 0;
    padding-left: 12px;
    color: #334155;
    font-size: 11px;
    line-height: 1.6;
}}
.list-num {{
    color: #7c3aed;
    font-weight: bold;
    margin-right: 4px;
}}
.list-bullet {{
    color: #7c3aed;
    margin-right: 6px;
}}

/* ── 代码 ── */
.code-block {{
    background: #f1f5f9;
    color: #334155;
    padding: 12px;
    border-radius: 6px;
    font-size: 10px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    overflow-x: auto;
    margin: 12px 0;
    border: 1px solid #e2e8f0;
}}
.inline-code {{
    background: #f1f5f9;
    color: #7c3aed;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 10px;
    font-family: "JetBrains Mono", "Consolas", monospace;
}}

/* ── 强调 ── */
strong {{
    color: #0f172a;
    font-weight: 600;
}}

/* ── 页脚免责声明 ── */
.page-footer {{
    font-size: 9px;
    color: #94a3b8;
    text-align: center;
    margin-top: 30px;
    padding-top: 10px;
    border-top: 1px solid #e2e8f0;
}}
</style>
</head>
<body>

<!-- 封面 -->
<div class="cover">
    <div class="brand">清数智算</div>
    <div class="brand-sub">智能投研工作台 · 研究辅助系统</div>
    <h1>{html.escape(title)}</h1>
    {cover_info}
    <div class="disclaimer">
        本报告由清数智算量化分析系统自动生成，基于公开市场数据和多维评分模型，仅供研究参考，不构成任何投资建议。
        投资有风险，入市需谨慎。报告中的研究评级、模型观察价、风险警戒价均为历史研究测算，不代表未来收益，不包含实盘交易建议。
    </div>
</div>

<!-- 正文 -->
{body_html}

<!-- 页脚免责声明 -->
<div class="page-footer">
    本报告由系统基于公开数据、数据库评分和规则模型生成，仅用于研究辅助，不构成投资建议。
</div>

</body>
</html>"""


def generate_pdf_bytes(md_content: str, title: str, report_date: str = "", stock_symbol: str = "", stock_name: str = "") -> bytes:
    """
    将 Markdown 内容转换为 PDF 字节流
    Args:
        md_content: Markdown 报告内容
        title: 报告标题
        report_date: 报告日期
        stock_symbol: 股票代码（个股报告时）
        stock_name: 股票名称（个股报告时）
    Returns:
        PDF 字节流
    """
    # 内容过大时截断
    MAX_CONTENT_LEN = 200000
    if len(md_content) > MAX_CONTENT_LEN:
        md_content = md_content[:MAX_CONTENT_LEN] + "\n\n---\n\n> **注意：报告内容过长，已截断显示。完整报告请在线查看。**\n"

    # 清洗数据
    md_clean = clean_md_content(md_content)
    title_clean = clean_text(title)

    # 移除 emoji 字符（PDF 字体不支持）
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "‍"
        "]+",
        flags=re.UNICODE,
    )
    md_clean = emoji_pattern.sub("", md_clean)
    title_clean = emoji_pattern.sub("", title_clean)

    html_content = _build_pdf_html(md_clean, title_clean, report_date, stock_symbol, stock_name)
    html_content = re.sub(
        r'content:\s*"[^"]*"\s*counter\(page\)\s*"[^"]*";',
        'content: "研究报告页脚";',
        html_content,
    )
    html_content = re.sub(
        r"@page\s*\{\s*size:\s*A4;\s*margin:\s*2cm 1\.8cm 2\.5cm 1\.8cm;\s*@bottom-center\s*\{.*?\}\s*@bottom-right\s*\{.*?\}\s*\}",
        "@page { size: A4; margin: 2cm 1.8cm 2.5cm 1.8cm; }",
        html_content,
        flags=re.S,
    )

    result = BytesIO()
    status = pisa.CreatePDF(html_content, dest=result, encoding="utf-8")

    if status.err:
        raise Exception(f"PDF 生成失败：{status.err} 个错误")

    return result.getvalue()


def generate_pdf_filename(stock_symbol: str = "", stock_name: str = "", report_type: str = "report", report_date: str = "") -> str:
    """生成友好的 PDF 文件名"""
    parts = []
    if stock_symbol:
        parts.append(stock_symbol)
    if stock_name:
        # 清理文件名中不允许的字符
        clean_name = re.sub(r'[<>:"/\\|?*]', '', stock_name)
        parts.append(clean_name)
    if report_type:
        type_label = {"DAILY": "每日策略报告", "STOCK": "深度研究报告", "STYLE": "风格策略报告"}.get(report_type, report_type)
        parts.append(type_label)
    if report_date:
        parts.append(str(report_date))
    return "_".join(parts) + ".pdf" if parts else "report.pdf"
