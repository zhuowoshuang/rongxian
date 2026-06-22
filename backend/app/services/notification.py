"""
通知推送服务
支持 QQ 邮箱、飞书 Webhook 推送每日信号和报告
"""
import smtplib
import json
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date
from typing import Optional
from html import escape as html_escape
import logging
import httpx

logger = logging.getLogger(__name__)


class NotificationService:
    """统一通知推送服务"""

    def __init__(self, config: dict = None):
        self.config = config or {}

    # ==================== QQ 邮箱 ====================

    def send_email(self, to_email: str, subject: str, html_content: str, max_retries: int = 2) -> bool:
        """通过 QQ 邮箱发送邮件（含重试）"""
        smtp_host = self.config.get("email_smtp_host", "smtp.qq.com")
        smtp_port = int(self.config.get("email_smtp_port", 465))
        sender = self.config.get("email_sender", "")
        password = self.config.get("email_password", "")

        if not sender or not password:
            logger.warning("Email not configured: missing sender or password")
            return False

        for attempt in range(max_retries + 1):
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"融衔 <{sender}>"
                msg["To"] = to_email

                html_part = MIMEText(html_content, "html", "utf-8")
                msg.attach(html_part)

                with smtplib.SMTP_SSL(smtp_host, smtp_port) as server:
                    server.login(sender, password)
                    server.sendmail(sender, [to_email], msg.as_string())

                logger.info(f"Email sent to {to_email}: {subject}")
                return True
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"Email send attempt {attempt + 1} failed, retrying: {e}")
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Email send failed after {max_retries + 1} attempts: {e}")
                    return False

    def build_daily_email(self, market_status: str, signals: list, indices: list) -> str:
        """构建每日信号邮件 HTML"""
        signal_rows = ""
        for s in signals[:10]:
            color = "#16a34a" if s["type"] == "BUY" else "#2563eb" if s["type"] == "ADD" else "#d97706" if s["type"] == "REDUCE" else "#dc2626"
            sym = html_escape(str(s['symbol']))
            name = html_escape(str(s['name']))
            sig_type = html_escape(str(s['type']))
            signal_rows += f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #f0f0f0">{sym}</td>
                <td style="padding:8px;border-bottom:1px solid #f0f0f0">{name}</td>
                <td style="padding:8px;border-bottom:1px solid #f0f0f0;color:{color};font-weight:bold">{sig_type}</td>
                <td style="padding:8px;border-bottom:1px solid #f0f0f0">{s['score']}</td>
                <td style="padding:8px;border-bottom:1px solid #f0f0f0">{s['position']}%</td>
            </tr>"""

        index_rows = ""
        for idx in indices:
            change_color = "#16a34a" if idx["change_pct"] >= 0 else "#dc2626"
            index_rows += f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #f0f0f0">{idx['name']}</td>
                <td style="padding:8px;border-bottom:1px solid #f0f0f0">{idx['current']:,.2f}</td>
                <td style="padding:8px;border-bottom:1px solid #f0f0f0;color:{change_color}">{idx['change_pct']:+.2f}%</td>
            </tr>"""

        return f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
            <div style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:20px;border-radius:12px;color:white;text-align:center">
                <h1 style="margin:0;font-size:24px">融衔 每日报告</h1>
                <p style="margin:8px 0 0;opacity:0.8">{date.today()} | 市场状态: {market_status}</p>
            </div>

            <div style="margin-top:20px;padding:16px;background:#f9fafb;border-radius:8px">
                <h2 style="font-size:16px;color:#374151;margin:0 0 12px">市场概览</h2>
                <table style="width:100%;border-collapse:collapse">
                    <tr style="background:#f3f4f6">
                        <th style="padding:8px;text-align:left;font-size:12px;color:#6b7280">指数</th>
                        <th style="padding:8px;text-align:left;font-size:12px;color:#6b7280">点位</th>
                        <th style="padding:8px;text-align:left;font-size:12px;color:#6b7280">涨跌</th>
                    </tr>
                    {index_rows}
                </table>
            </div>

            <div style="margin-top:16px;padding:16px;background:#f9fafb;border-radius:8px">
                <h2 style="font-size:16px;color:#374151;margin:0 0 12px">今日信号</h2>
                <table style="width:100%;border-collapse:collapse">
                    <tr style="background:#f3f4f6">
                        <th style="padding:8px;text-align:left;font-size:12px;color:#6b7280">代码</th>
                        <th style="padding:8px;text-align:left;font-size:12px;color:#6b7280">名称</th>
                        <th style="padding:8px;text-align:left;font-size:12px;color:#6b7280">信号</th>
                        <th style="padding:8px;text-align:left;font-size:12px;color:#6b7280">评分</th>
                        <th style="padding:8px;text-align:left;font-size:12px;color:#6b7280">仓位</th>
                    </tr>
                    {signal_rows}
                </table>
            </div>

            <p style="text-align:center;font-size:11px;color:#9ca3af;margin-top:20px">
                本系统仅用于研究和辅助分析，不构成任何投资建议。
            </p>
        </div>"""

    # ==================== 飞书 Webhook ====================

    def send_feishu(self, title: str, content: str) -> bool:
        """通过飞书 Webhook 发送消息"""
        webhook_url = self.config.get("feishu_webhook", "")
        if not webhook_url:
            logger.warning("Feishu not configured: missing webhook URL")
            return False

        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": "purple",
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content,
                    }
                ],
            },
        }

        for attempt in range(3):
            try:
                with httpx.Client(timeout=10, trust_env=False) as client:
                    resp = client.post(
                        webhook_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                    )
                    data = resp.json()
                    if data.get("code") == 0 or data.get("StatusCode") == 0:
                        logger.info(f"Feishu message sent: {title}")
                        return True
                    else:
                        logger.error(f"Feishu API error: {data}")
                        return False
            except Exception as e:
                if attempt < 2:
                    logger.warning(f"Feishu send attempt {attempt + 1} failed, retrying: {e}")
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Feishu send failed after 3 attempts: {e}")
                    return False

    def build_daily_feishu(self, market_status: str, signals: list, indices: list) -> str:
        """构建飞书每日消息 Markdown"""
        lines = [f"**📊 市场状态: {market_status}**\n"]

        lines.append("**市场指数**")
        for idx in indices:
            emoji = "🟢" if idx["change_pct"] >= 0 else "🔴"
            lines.append(f"{emoji} {idx['name']}: {idx['current']:,.2f} ({idx['change_pct']:+.2f}%)")

        lines.append("\n**今日信号**")
        for s in signals[:8]:
            emoji = "🟢" if s["type"] == "BUY" else "🔵" if s["type"] == "ADD" else "🟡" if s["type"] == "WATCH" else "🟠" if s["type"] == "REDUCE" else "🔴"
            lines.append(f"{emoji} **{s['symbol']} {s['name']}** → {s['type']} (评分:{s['score']} 仓位:{s['position']}%)")

        lines.append("\n---\n*本系统仅用于研究和辅助分析，不构成任何投资建议。*")
        return "\n".join(lines)

    # ==================== 统一推送 ====================

    def push_daily_report(self, market_status: str, signals: list, indices: list,
                          to_email: str = None, feishu: bool = False) -> dict:
        """推送每日报告"""
        results = {"email": False, "feishu": False}

        if to_email:
            subject = f"融衔 每日报告 - {date.today()} | {market_status}"
            html = self.build_daily_email(market_status, signals, indices)
            results["email"] = self.send_email(to_email, subject, html)

        if feishu:
            title = f"融衔 每日报告 - {date.today()}"
            content = self.build_daily_feishu(market_status, signals, indices)
            results["feishu"] = self.send_feishu(title, content)

        return results


def get_notification_service(db=None) -> NotificationService:
    """从数据库读取配置并创建通知服务实例"""
    config = {}
    if db:
        from app.models.setting import Setting
        settings = db.query(Setting).filter(
            Setting.key.in_([
                "email_smtp_host", "email_smtp_port", "email_sender", "email_password",
                "email_recipient", "feishu_webhook", "feishu_enabled",
            ])
        ).all()
        for s in settings:
            config[s.key] = s.value

    return NotificationService(config)
