#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日 AI 资讯 → 163 邮箱推送（仓库内自包含版本）

读取当前目录下最新的 AI资讯24小时_*.md，转 HTML 正文并作为附件，经 163 SMTP(SSL) 发送。
所有敏感信息经环境变量注入，不硬编码。

环境变量：
  NEWS_SMTP_USER   发件人，默认 newshub01@163.com
  NEWS_SMTP_TO     收件人，默认 newshub01@163.com
  NEWS_SMTP_AUTH   163 授权码（必填，由调用方注入 Secrets）
可选参数：
  python push_email.py [指定md路径]
"""

import os
import re
import sys
import ssl
import smtplib
import base64
import datetime
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

SMTP_HOST = "smtp.163.com"
SMTP_PORT = 465
SENDER = os.environ.get("NEWS_SMTP_USER") or "newshub01@163.com"
RECIPIENT = os.environ.get("NEWS_SMTP_TO") or "newshub01@163.com"
AUTH = os.environ.get("NEWS_SMTP_AUTH")

if not AUTH:
    raise SystemExit("ERROR: 环境变量 NEWS_SMTP_AUTH 未设置（163 邮箱授权码）")


def find_latest_md():
    here = Path(".")
    files = sorted(here.glob("AI资讯24小时_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit("ERROR: 未找到 AI资讯24小时_*.md")
    return files[0]


def md_to_html(md):
    out, in_list = [], False

    def inline(t):
        t = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2" target="_blank">\1</a>', t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        return t

    for line in md.split("\n"):
        s = line.strip()
        if s.startswith("### "):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<h3>{inline(s[4:])}</h3>")
        elif s.startswith("## "):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<h2>{inline(s[3:])}</h2>")
        elif s.startswith("# "):
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<h1>{inline(s[2:])}</h1>")
        elif s.startswith("- "):
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{inline(s[2:])}</li>")
        elif s == "":
            if in_list:
                out.append("</ul>"); in_list = False
            out.append("<br>")
        else:
            if in_list:
                out.append("</ul>"); in_list = False
            out.append(f"<p>{inline(s)}</p>")
    if in_list:
        out.append("</ul>")
    body = "\n".join(out)
    today = datetime.date.today().strftime("%Y年%-m月%-d日") if hasattr(datetime.date.today(), "strftime") else ""
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{font-family:-apple-system,'Microsoft YaHei',sans-serif;max-width:860px;margin:0 auto;padding:24px;line-height:1.7;color:#1f2328}}
h1{{font-size:26px;border-bottom:3px solid #2d6cdf;padding-bottom:8px}}
h2{{font-size:21px;margin-top:28px;color:#2d6cdf}}
h3{{font-size:17px;margin-top:18px}}
ul{{background:#f7f9fc;border-left:4px solid #2d6cdf;padding:10px 22px}}
a{{color:#2d6cdf}}
</style></head><body>{body}</body></html>"""


def main():
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else find_latest_md()
    md = path.read_text(encoding="utf-8")
    html_body = md_to_html(md)
    title = path.stem

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"AI 资讯 24 小时 | {title.replace('AI资讯24小时_', '').replace('_', ' ')}"
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg.attach(MIMEText(md, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with open(path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", 'attachment', filename=path.name)
    msg.attach(part)

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as s:
        s.login(SENDER, AUTH)
        s.sendmail(SENDER, [RECIPIENT], msg.as_string())
    print(f"OK: 已推送 {path.name} 至 {RECIPIENT}")


if __name__ == "__main__":
    main()
