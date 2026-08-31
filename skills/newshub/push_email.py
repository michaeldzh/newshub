#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 AI 资讯日报通过 163 SMTP 推送到邮箱。

用法:
  python push_email.py                      自动取当天日报（md + index.html）
  python push_email.py <md路径> [html路径]  显式指定

行为:
  - 正文 = index.html（渲染后的 HTML，收件人直接可见标题/摘要/来源/原文链接）
  - 附件 = 日报 Markdown 原文（供存档）
  - 主题 = "AI 资讯 24 小时 | YYYY年M月D日"，日期按北京时间且优先取文件名

凭据（必须经由环境变量注入，绝不硬编码）:
  NEWS_SMTP_USER  发件人（默认 newshub01@163.com）
  NEWS_SMTP_TO    收件人（默认 newshub01@163.com）
  NEWS_SMTP_AUTH  163 客户端授权码（必填，缺失则报错退出）
"""

import os
import re
import sys
import glob
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.header import Header
from datetime import datetime, timezone, timedelta

SMTP_HOST = "smtp.163.com"
SMTP_PORT = 465
SENDER = os.environ.get("NEWS_SMTP_USER", "newshub01@163.com")
RECIPIENT = os.environ.get("NEWS_SMTP_TO", "newshub01@163.com")
AUTH = os.environ.get("NEWS_SMTP_AUTH")

NAME_RE = re.compile(r"AI资讯24小时_(\d{4})年(\d{1,2})月(\d{1,2})日\.md")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def pick_latest_md():
    files = glob.glob(os.path.join(SCRIPT_DIR, "AI资讯24小时_*.md"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def subject_from(md_path):
    m = NAME_RE.search(os.path.basename(md_path or ""))
    if m:
        return "AI 资讯 24 小时 | %s年%s月%s日" % (m.group(1), int(m.group(2)), int(m.group(3)))
    bj = timezone(timedelta(hours=8))
    d = datetime.now(bj)
    return "AI 资讯 24 小时 | %d年%d月%d日" % (d.year, d.month, d.day)


def attach_file(msg, path, mime_subtype):
    with open(path, "rb") as f:
        part = MIMEBase("application", mime_subtype)
        part.set_payload(f.read())
    encoders.encode_base64(part)
    # 中文文件名需按 RFC2231 编码，否则部分客户端显示为乱码
    fname = os.path.basename(path)
    part.add_header("Content-Disposition", "attachment", filename=("utf-8", "", fname))
    msg.attach(part)


def main():
    if not AUTH:
        print("ERROR: 缺少授权码。请设置 NEWS_SMTP_AUTH（GitHub Actions 中用 secrets 注入）。",
              file=sys.stderr)
        sys.exit(1)

    args = [a for a in sys.argv[1:] if a]
    md_path = args[0] if len(args) > 0 else pick_latest_md()
    html_path = args[1] if len(args) > 1 else os.path.join(SCRIPT_DIR, "index.html")

    if not md_path or not os.path.exists(md_path):
        print("ERROR: 未找到日报 Markdown。当前目录：%s" % SCRIPT_DIR, file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(html_path):
        print("ERROR: 未找到 HTML 正文：%s" % html_path, file=sys.stderr)
        sys.exit(1)

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    subject = subject_from(md_path)

    msg = MIMEMultipart("mixed")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg.attach(MIMEText(html, "html", "utf-8"))
    attach_file(msg, md_path, "octet-stream")

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=60) as s:
        s.login(SENDER, AUTH)
        s.sendmail(SENDER, [RECIPIENT], msg.as_string())

    print("OK: 邮件已发送 | 主题=%s | 收件人=%s | 附件=%s"
          % (subject, RECIPIENT, os.path.basename(md_path)))


if __name__ == "__main__":
    main()
