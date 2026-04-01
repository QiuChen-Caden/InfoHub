"""多渠道通知发送 — 带响应校验和重试"""

import time
import logging
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Tuple
from datetime import datetime

from models import NewsItem

log = logging.getLogger("infohub.notify")

MAX_RETRIES = 2
RETRY_DELAY = 3


def _post_with_retry(url: str, json_data: dict, timeout: int = 30,
                     label: str = "") -> bool:
    """POST 请求，带重试和响应校验，返回是否成功"""
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=json_data, timeout=timeout)
            resp.raise_for_status()
            return True
        except Exception as e:
            if attempt < MAX_RETRIES:
                log.warning(f"{label} 第 {attempt+1} 次失败: {e}, 重试...")
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                log.error(f"{label} 发送失败（已重试 {MAX_RETRIES} 次）: {e}")
    return False


class Notifier:
    def __init__(self, config: dict):
        self.config = config
        self.batch_interval = config.get("batch_interval", 2)

    def send(self, items: List[NewsItem], now: datetime) -> Tuple[int, int]:
        """发送到所有已配置渠道，返回 (成功数, 失败数)"""
        message = self._format_message(items, now)
        success, fail = 0, 0

        channels = [
            ("telegram_bot_token", self._send_telegram),
            ("feishu_webhook_url", self._send_feishu),
            ("dingtalk_webhook_url", self._send_dingtalk),
            ("email_from", self._send_email),
            ("slack_webhook_url", self._send_slack),
        ]

        for key, sender in channels:
            if not self.config.get(key):
                continue
            try:
                if key == "email_from":
                    ok = sender(message, now)
                else:
                    ok = sender(message)
                if ok:
                    success += 1
                else:
                    fail += 1
            except Exception as e:
                log.error(f"通知渠道异常 {key}: {e}")
                fail += 1

        return success, fail

    def _format_message(self, items: List[NewsItem], now: datetime) -> str:
        lines = [f"InfoHub {now.strftime('%m-%d %H:%M')} ({len(items)} 条)\n"]

        by_tag: dict = {}
        for item in items:
            tag = item.tags[0] if item.tags else "其他"
            by_tag.setdefault(tag, []).append(item)

        for tag, tag_items in by_tag.items():
            lines.append(f"\n【{tag}】")
            for it in tag_items[:10]:
                score = f" ({it.score:.1f})" if it.score else ""
                lines.append(f"- {it.title}{score}")
                if it.url:
                    lines.append(f"  {it.url}")

        if items and items[0].summary:
            lines.append(f"\n---\nAI 分析\n{items[0].summary}")

        return "\n".join(lines)

    def _send_telegram(self, message: str) -> bool:
        token = self.config["telegram_bot_token"]
        chat_id = self.config["telegram_chat_id"]
        all_ok = True
        for chunk in self._split(message, 4000):
            ok = _post_with_retry(
                f"https://api.telegram.org/bot{token}/sendMessage",
                {"chat_id": chat_id, "text": chunk,
                 "disable_web_page_preview": True},
                label="Telegram",
            )
            if not ok:
                all_ok = False
            time.sleep(self.batch_interval)
        return all_ok

    def _send_feishu(self, message: str) -> bool:
        url = self.config["feishu_webhook_url"]
        all_ok = True
        for chunk in self._split(message, 29000):
            ok = _post_with_retry(url, {
                "msg_type": "interactive",
                "card": {"schema": "2.0", "body": {"elements": [
                    {"tag": "markdown", "content": chunk}
                ]}},
            }, label="飞书")
            if not ok:
                all_ok = False
            time.sleep(self.batch_interval)
        return all_ok

    def _send_dingtalk(self, message: str) -> bool:
        url = self.config["dingtalk_webhook_url"]
        all_ok = True
        for chunk in self._split(message, 20000):
            ok = _post_with_retry(url, {
                "msgtype": "markdown",
                "markdown": {"title": "InfoHub", "text": chunk},
            }, label="钉钉")
            if not ok:
                all_ok = False
            time.sleep(self.batch_interval)
        return all_ok

    def _send_email(self, message: str, now: datetime) -> bool:
        msg = MIMEMultipart()
        msg["From"] = self.config["email_from"]
        msg["To"] = self.config["email_to"]
        msg["Subject"] = f"InfoHub {now.strftime('%Y-%m-%d %H:%M')}"
        msg.attach(MIMEText(message, "plain", "utf-8"))

        smtp_server = self._detect_smtp(self.config["email_from"])
        try:
            with smtplib.SMTP_SSL(smtp_server, 465) as server:
                server.login(self.config["email_from"],
                             self.config["email_password"])
                server.send_message(msg)
            return True
        except Exception as e:
            log.error(f"邮件发送失败: {e}")
            return False

    def _send_slack(self, message: str) -> bool:
        url = self.config["slack_webhook_url"]
        all_ok = True
        for chunk in self._split(message, 4000):
            ok = _post_with_retry(url, {"text": chunk}, label="Slack")
            if not ok:
                all_ok = False
            time.sleep(self.batch_interval)
        return all_ok

    @staticmethod
    def _split(text: str, max_bytes: int) -> List[str]:
        if max_bytes <= 0:
            return [text]
        chunks, current = [], ""
        for line in text.split("\n"):
            if len((current + "\n" + line).encode("utf-8")) > max_bytes:
                if current:
                    chunks.append(current)
                current = line
            else:
                current = current + "\n" + line if current else line
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _detect_smtp(email: str) -> str:
        domain = email.split("@")[1]
        return {
            "gmail.com": "smtp.gmail.com",
            "qq.com": "smtp.qq.com",
            "163.com": "smtp.163.com",
            "outlook.com": "smtp-mail.outlook.com",
        }.get(domain, f"smtp.{domain}")
