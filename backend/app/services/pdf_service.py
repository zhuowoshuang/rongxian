"""
PDF 生成服务
使用 xhtml2pdf 将 Markdown 报告转换为专业排版的 PDF
"""
import re
import html
from xhtml2pdf import pisa


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
            html_parts.append(f'<div class="list-item"><span class="list-bullet">-</span> {_inline_html(line[2:])}</div>')
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
    # 转义 HTML
    text = html.escape(text)
    # 粗体
    text = re.sub(r"\*\*(.+?)\*\*", r'<strong>\1</strong>', text)
    # 行内代码
    text = re.sub(r"`([^`]+)`", r'<code class="inline-code">\1</code>', text)
    return text


def _build_pdf_html(md_content: str, title: str) -> str:
    """构建完整的 PDF HTML"""
    body_html = _md_to_html(md_content)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<style>
@page {{
    size: A4;
    margin: 2cm 1.5cm;
}}
body {{
    font-family: "SimSun", "Microsoft YaHei", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
    font-size: 11px;
    line-height: 1.7;
    color: #333;
    background: #fff;
}}
.cover {{
    text-align: center;
    padding-top: 120px;
    page-break-after: always;
}}
.cover h1 {{
    font-size: 28px;
    color: #1a1a2e;
    margin-bottom: 20px;
}}
.cover .subtitle {{
    font-size: 14px;
    color: #666;
    margin-bottom: 40px;
}}
.cover .brand {{
    font-size: 36px;
    font-weight: bold;
    color: #4f46e5;
    margin-bottom: 10px;
}}
.cover .date {{
    font-size: 12px;
    color: #999;
    margin-top: 60px;
}}
.cover .disclaimer {{
    font-size: 9px;
    color: #999;
    margin-top: 80px;
    padding: 0 40px;
    line-height: 1.5;
}}
.report-h1 {{
    font-size: 20px;
    color: #1a1a2e;
    border-bottom: 2px solid #4f46e5;
    padding-bottom: 8px;
    margin: 24px 0 12px 0;
}}
.report-h2 {{
    font-size: 16px;
    color: #1a1a2e;
    border-bottom: 1px solid #e5e7eb;
    padding-bottom: 6px;
    margin: 20px 0 10px 0;
}}
.report-h3 {{
    font-size: 13px;
    color: #374151;
    margin: 14px 0 8px 0;
}}
.report-hr {{
    border: none;
    border-top: 1px solid #e5e7eb;
    margin: 16px 0;
}}
.report-p {{
    margin: 6px 0;
    text-align: justify;
}}
.report-quote {{
    border-left: 3px solid #4f46e5;
    padding: 8px 12px;
    margin: 12px 0;
    background: #f8fafc;
    color: #555;
    font-style: italic;
}}
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
    padding: 6px 8px;
    text-align: left;
    border: 1px solid #e2e8f0;
    font-weight: 600;
}}
.report-table td {{
    padding: 5px 8px;
    border: 1px solid #e2e8f0;
    color: #334155;
}}
.report-table tr:nth-child(even) {{
    background: #f8fafc;
}}
.list-item {{
    margin: 4px 0;
    padding-left: 8px;
}}
.list-num {{
    color: #4f46e5;
    font-weight: bold;
    margin-right: 4px;
}}
.list-bullet {{
    color: #4f46e5;
    margin-right: 6px;
}}
.code-block {{
    background: #1e293b;
    color: #10b981;
    padding: 12px;
    border-radius: 6px;
    font-size: 10px;
    font-family: "Consolas", "Courier New", monospace;
    overflow-x: auto;
    margin: 12px 0;
}}
.inline-code {{
    background: #f1f5f9;
    color: #e11d48;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 10px;
    font-family: "Consolas", "Courier New", monospace;
}}
strong {{
    color: #1a1a2e;
}}
</style>
</head>
<body>
<div class="cover">
    <div class="brand">清数智算</div>
    <h1>{html.escape(title)}</h1>
    <div class="subtitle">量化分析报告系统</div>
    <div class="disclaimer">
        本报告由清数智算量化分析系统自动生成，基于公开市场数据和多维评分模型，仅供研究参考，不构成任何投资建议。投资有风险，入市需谨慎。
    </div>
</div>
{body_html}
</body>
</html>"""


def generate_pdf_bytes(md_content: str, title: str) -> bytes:
    """将 Markdown 内容转换为 PDF 字节流"""
    # 移除 emoji 字符（PDF字体不支持）
    import re
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "♀-♂"
        "☀-⭕"
        "‍"
        "⏏"
        "⏩"
        "⌚"
        "️"
        "〰"
        "⤴"
        "⤵"
        "]+",
        flags=re.UNICODE,
    )
    md_clean = emoji_pattern.sub("", md_content)
    title_clean = emoji_pattern.sub("", title)

    html_content = _build_pdf_html(md_clean, title_clean)

    from io import BytesIO
    result = BytesIO()
    status = pisa.CreatePDF(html_content, dest=result, encoding="utf-8")

    if status.err:
        raise Exception(f"PDF generation failed with {status.err} errors")

    return result.getvalue()
