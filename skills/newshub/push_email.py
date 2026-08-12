#!/usr/bin/env python3
"""读取新闻 HTML 报告，通过 163 SMTP 推送到邮箱。

用法:
  python push_email.py [报告路径]   # 默认 index.html (当前目录)

凭据(必须经由环境变量传入, 绝不硬编码):
  NEWS_SMTP_USER  发件人 (默认 newshub01@163.com)
  NEWS_SMTP_TO    收件人 (默认 newshub01@163.com)
  NEWS_SMTP_AUTH  163 邮箱客户端授权码 (必填, 缺失则报错退出)
"""
import smtplib, ssl, os, sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timezone, timedelta

SMTP_HOST = "smtp.163.com"
SMTP_PORT = 465
SENDER = os.environ.get("NEWS_SMTP_USER", "newshub01@163.com")
RECIPIENT = os.environ.get("NEWS_SMTP_TO", "newshub01@163.com")
AUTH = os.environ.get("NEWS_SMTP_AUTH")


def main():
    if not AUTH:
        print(
            "ERROR: 缺少授权码。请在运行环境设置 NEWS_SMTP_AUTH "
            "(GitHub Actions 中通过 secrets 注入, 例如 secrets.NEWS_SMTP_AUTH)。",
            file=sys.stderr,
        )
        sys.exit(1)

    path = sys.argv[1] if len(sys.argv) > 1 else "index.html"
    if not os.path.exists(path):
        print("ERROR: 未找到报告文件:", path, file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    bj = timezone(timedelta(hours=8))
    today = datetime.now(bj).strftime("%Y年%m月%d日")
    title = "全球新闻汇总 | " + today

    msg = MIMEMultipart("alternative")
    msg["Subject"] = title
    msg["From"] = SENDER
    msg["To"] = RECIPIENT
    msg.attach(MIMEText(html, "html", "utf-8"))

    with open(path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        'attachment; filename="%s"' % os.path.basename(path),
    )
    msg.attach(part)

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as s:
        s.login(SENDER, AUTH)
        s.sendmail(SENDER, [RECIPIENT], msg.as_string())
    print("OK: 已发送", os.path.basename(path), "->", RECIPIENT)


if __name__ == "__main__":
    main()
