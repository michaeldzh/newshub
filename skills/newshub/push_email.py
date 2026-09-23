#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 AI 资讯日报通过 163 SMTP 推送到邮箱。

用法:
  python push_email.py                      自动取最新日报（md + index.html）
  python push_email.py <md路径> [html路径]  显式指定
  python push_email.py index.html           只给 HTML：正文取它，附件自动找最新 md

行为（正常出稿）:
  - 正文 = index.html（渲染后的 HTML，收件人直接可见标题/摘要/来源/原文链接）
  - 附件 = 日报 Markdown 原文（供存档）
  - 主题 = "AI 资讯 24 小时 | YYYY年M月D日"，日期按北京时间且优先取文件名

行为（本轮未出稿 —— 目录下存在**当日**的 ALERT.json）:
  - 主题 = "⚠️ [AI 日报异常] YYYY年M月D日 未出稿 —— <原因>"
  - 正文 = index.html（生成器写好的故障通报页）
  - 附件 = ALERT.json（机器可读的故障记录），并标记高优先级
  故障通报的三重送达（邮件 / Pages / 仓库 ALERT.json）见 generate.emit_alert()。
  本文件只负责「邮件」这一路：让收件人第一眼就知道今天没有日报、以及为什么。

凭据（必须经由环境变量注入，绝不硬编码）:
  NEWS_SMTP_USER  发件人（默认 newshub01@163.com）
  NEWS_SMTP_TO    收件人（默认 newshub01@163.com）
  NEWS_SMTP_AUTH  163 客户端授权码（必填，缺失则报错退出）
"""

import glob
import json
import os
import re
import smtplib
import ssl
import sys
from email import encoders
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta

SMTP_HOST = "smtp.163.com"
SMTP_PORT = 465
SENDER = os.environ.get("NEWS_SMTP_USER", "newshub01@163.com")
RECIPIENT = os.environ.get("NEWS_SMTP_TO", "newshub01@163.com")
AUTH = os.environ.get("NEWS_SMTP_AUTH")

NAME_RE = re.compile(r"AI资讯24小时_(\d{4})年(\d{1,2})月(\d{1,2})日\.md")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALERT_NAME = "ALERT.json"
BJ = timezone(timedelta(hours=8))


def today_bj():
    return datetime.now(BJ).strftime("%Y-%m-%d")


def today_md_path():
    d = datetime.now(BJ)
    return os.path.join(SCRIPT_DIR, "AI资讯24小时_%d年%d月%d日.md" % (d.year, d.month, d.day))


def pick_latest_md():
    """优先取「今天」那一期，取不到再退回 mtime 最新的。

    不能只靠 mtime：CI 里 checkout 是一次性解压，所有文件 mtime 几乎相同，
    max(mtime) 可能挑到昨天（甚至上个月）的日报 —— 附件与主题就一起错了。
    """
    today = today_md_path()
    if os.path.exists(today):
        return today
    files = glob.glob(os.path.join(SCRIPT_DIR, "AI资讯24小时_*.md"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def load_alert():
    """读取「当日」的故障通报。隔夜残留（日期不是今天）一律忽略，按正常模式处理。"""
    path = os.path.join(SCRIPT_DIR, ALERT_NAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:  # noqa: BLE001 —— 通报损坏不该拖垮发信
        print("WARN: %s 解析失败：%s" % (ALERT_NAME, e))
        return None
    if not isinstance(data, dict) or not data.get("alert"):
        return None
    if data.get("date") != today_bj():
        print("WARN: %s 的日期是 %s 而非今日，按正常模式处理"
              % (ALERT_NAME, data.get("date")))
        return None
    return data


def split_args(argv):
    """位置参数按扩展名分流为 (md, html)。

    为什么要分流：工作流调用的是 `python push_email.py index.html`，而 v1 把第一个
    位置参数一律当成 md 路径 —— 结果「日报 Markdown 附件」实际附的是 index.html，
    md 原文从未随信发出。这里按扩展名分流，工作流无需改动即可修好。
    """
    md = html = None
    for a in argv:
        low = a.lower()
        if low.endswith(".html") or low.endswith(".htm"):
            html = a
        else:
            md = a
    return md, html


def subject_from(md_path):
    m = NAME_RE.search(os.path.basename(md_path or ""))
    if m:
        return "AI 资讯 24 小时 | %s年%s月%s日" % (m.group(1), int(m.group(2)), int(m.group(3)))
    d = datetime.now(BJ)
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


def resolve_path(p):
    """相对路径 → 绝对路径：先按当前目录解释，找不到再退回脚本所在目录。

    CI 里工作流是 `cd skills/newshub; python push_email.py index.html`，cwd 恰好就是
    脚本目录；但本地跑或换目录跑时 cwd 不是，`index.html` 会被判成「不存在」而
    直接报错退出 —— 于是明明有日报却发不出去。这里兜一层，两边都能用。
    """
    if os.path.isabs(p):
        return p
    cand = os.path.abspath(p)
    if os.path.exists(cand):
        return cand
    return os.path.join(SCRIPT_DIR, p)


def main():
    if not AUTH:
        print("ERROR: 缺少授权码。请设置 NEWS_SMTP_AUTH（GitHub Actions 中用 secrets 注入）。",
              file=sys.stderr)
        sys.exit(1)

    md_path, html_path = split_args([a for a in sys.argv[1:] if a])
    if html_path is None:
        html_path = os.path.join(SCRIPT_DIR, "index.html")
    else:
        html_path = resolve_path(html_path)
    if md_path is not None:
        md_path = resolve_path(md_path)

    alert = load_alert()
    if alert:
        # 故障通报模式：今天没有日报，正文就是通报页
        if not os.path.exists(html_path):
            print("ERROR: 故障通报页不存在：%s" % html_path, file=sys.stderr)
            sys.exit(1)
        subject = "⚠️ [AI 日报异常] %s 未出稿 —— %s" % (
            alert.get("date_cn") or today_bj(),
            (alert.get("reason") or "未知原因")[:40])
        attachment = os.path.join(SCRIPT_DIR, ALERT_NAME)
    else:
        if md_path is None:
            md_path = pick_latest_md()
        if not md_path or not os.path.exists(md_path):
            print("ERROR: 未找到日报 Markdown。当前目录：%s" % SCRIPT_DIR, file=sys.stderr)
            sys.exit(1)
        if not os.path.exists(html_path):
            print("ERROR: 未找到 HTML 正文：%s" % html_path, file=sys.stderr)
            sys.exit(1)
        subject = subject_from(md_path)
        attachment = md_path

    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()

    msg = MIMEMultipart("mixed")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    if alert:
        msg["X-Priority"] = "1"
        msg["Importance"] = "high"
    msg.attach(MIMEText(html, "html", "utf-8"))
    attach_file(msg, attachment, "octet-stream")

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=60) as s:
        s.login(SENDER, AUTH)
        s.sendmail(SENDER, [RECIPIENT], msg.as_string())

    print("OK: 邮件已发送 | 模式=%s | 主题=%s | 收件人=%s | 附件=%s"
          % ("故障通报" if alert else "正常日报", subject, RECIPIENT,
             os.path.basename(attachment)))


if __name__ == "__main__":
    main()
