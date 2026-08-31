#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 日报成稿硬校验（GitHub Actions / 本地通用）。

用法:
    python check_report.py                  校验报告目录下最新一份日报
    python check_report.py <文件路径>       校验指定日报
    python check_report.py --all            校验全部日报

报告目录优先级:
    1. 环境变量 REPORT_DIR
    2. 本脚本所在目录（GitHub Actions 里即 skills/newshub/）
    3. 脚本所在向上 4 级（兼容本地工作区布局）

检查项（任一 ERROR 即判 FAIL，退出码 1）:
    E1 条目数必须恰为 20
    E2 本期内部同一原文链接不得重复出现（拆条凑数）
    E3 跨最近 3 期日报，原文链接不得重复
    E4 发布日期必须落在 [D-1, D]（D = 日报文件名日期）
    E5 每条必须五要素齐全：标题 / 摘要 / 发布日期 / 来源 / 原文链接
    E6 三个分类条目数应为 7 / 7 / 6

退出码: 0 = PASS, 1 = FAIL
"""

import glob
import io
import os
import re
import sys
import datetime
from collections import Counter, defaultdict

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def find_base_dir():
    env = os.environ.get("REPORT_DIR")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    if glob.glob(os.path.join(here, "AI资讯24小时_*.md")):
        return here
    cur = here
    for _ in range(5):
        if os.path.isdir(os.path.join(cur, ".git")) or os.path.isdir(os.path.join(cur, ".github")):
            sub = os.path.join(cur, "skills", "newshub")
            return sub if os.path.isdir(sub) else cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return here


BASE_DIR = find_base_dir()
REPORT_GLOB = os.path.join(BASE_DIR, "AI资讯24小时_*.md")

NAME_RE = re.compile(r"AI资讯24小时_(\d{4})年(\d{1,2})月(\d{1,2})日\.md")
URL_RE = re.compile(r"原文链接[**：：\s]*([^\s\)>\]|]+)")
DATE_RE = re.compile(r"发布日期[**：：\s]*(\d{4}-\d{2}-\d{2})")
SRC_RE = re.compile(r"来源[**：：\s]*(.+)")
ABS_RE = re.compile(r"摘要[**：：\s]*(.+)")

EXPECTED_TOTAL = 20
EXPECTED_SECTIONS = [7, 7, 6]
HISTORY_WINDOW = 3


def parse_name_date(path):
    m = NAME_RE.search(os.path.basename(path))
    if not m:
        return None
    return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def list_reports():
    found = []
    for p in glob.glob(REPORT_GLOB):
        d = parse_name_date(p)
        if d:
            found.append((d, p))
    found.sort(key=lambda x: x[0])
    return found


def split_sections(text):
    parts = re.split(r"\n(?=## )", text)
    out = []
    for part in parts:
        head = part.split("\n", 1)[0].strip()
        items = re.split(r"\n(?=### )", part)[1:]
        if items:
            out.append((head, items))
    return out


def parse_item(raw):
    lines = raw.split("\n")
    title = lines[0].lstrip("# ").strip()
    flat = raw

    url_m = URL_RE.search(flat)
    date_m = DATE_RE.search(flat)
    src_m = SRC_RE.search(flat)
    abs_m = ABS_RE.search(flat)

    if abs_m:
        abstract = abs_m.group(1).strip()
    else:
        body = []
        for ln in lines[1:]:
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            if URL_RE.match(s) or DATE_RE.match(s) or SRC_RE.match(s):
                continue
            if re.match(r"^[-*]\s*\*\*", s):
                continue
            body.append(s)
        abstract = " ".join(body).strip()

    return {
        "title": title,
        "abstract": abstract,
        "date": date_m.group(1) if date_m else None,
        "source": src_m.group(1).strip() if src_m else None,
        "url": url_m.group(1).strip() if url_m else None,
    }


def load(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def check(path, history_urls):
    errors, warnings = [], []
    text = load(path)
    day = parse_name_date(path)
    sections = split_sections(text)

    items = [it for _, group in sections for it in group]
    parsed = [parse_item(it) for it in items]

    if len(parsed) != EXPECTED_TOTAL:
        errors.append(f"E1 条目数为 {len(parsed)}，要求恰为 {EXPECTED_TOTAL}")

    counts = [len(g) for _, g in sections]
    if counts != EXPECTED_SECTIONS:
        errors.append(f"E6 分类分布为 {counts}，要求 {EXPECTED_SECTIONS}")

    for i, p in enumerate(parsed, 1):
        missing = [k for k in ("title", "abstract", "date", "source", "url") if not p.get(k)]
        if missing:
            errors.append(f"E5 第 {i} 条缺失要素：{'/'.join(missing)} -> {p['title'][:40]}")

    url_counter = Counter(p["url"] for p in parsed if p["url"])
    for u, c in url_counter.items():
        if c > 1:
            dup = [p["title"][:36] for p in parsed if p["url"] == u]
            errors.append(f"E2 本期重复链接 ×{c}：{u}\n     涉及：{' | '.join(dup)}")

    for p in parsed:
        if p["url"] and p["url"] in history_urls:
            errors.append(
                f"E3 与往期重复链接：{p['url']}\n"
                f"     往期出现于：{' , '.join(sorted(history_urls[p['url']]))}\n"
                f"     本期条目：{p['title'][:40]}"
            )

    if day:
        lo, hi = day - datetime.timedelta(days=1), day
        for i, p in enumerate(parsed, 1):
            if not p["date"]:
                continue
            try:
                d = datetime.date(*map(int, p["date"].split("-")))
            except ValueError:
                continue
            if d < lo:
                errors.append(f"E4 第 {i} 条超窗（发布 {p['date']}，窗口 {lo} ~ {hi}）：{p['title'][:40]}")
            elif d > hi:
                errors.append(f"E4 第 {i} 条日期晚于日报日（发布 {p['date']}，日报 {hi}）：{p['title'][:40]}")
    else:
        warnings.append("无法从文件名解析日期，跳过 E4 窗口校验")

    return errors, warnings, parsed, sections


def main():
    args = sys.argv[1:]
    reports = list_reports()
    if not reports:
        print(f"未找到任何日报文件，报告目录：{BASE_DIR}")
        return 1

    if args and args[0] == "--all":
        targets = [p for _, p in reports]
    elif args and not args[0].startswith("-"):
        targets = [os.path.abspath(args[0])]
    else:
        targets = [reports[-1][1]]

    all_fail = False
    for target in targets:
        if not os.path.exists(target):
            print(f"[跳过] 文件不存在：{target}")
            continue

        history_urls = defaultdict(set)
        cur_day = parse_name_date(target)
        for d, p in reports:
            if p == target or not cur_day or d >= cur_day:
                continue
            if len([1 for dd, _ in reports if dd < cur_day and dd > d]) >= HISTORY_WINDOW:
                continue
            for u in URL_RE.findall(load(p)):
                history_urls[u.strip()].add(os.path.basename(p))

        errors, warnings, parsed, sections = check(target, history_urls)
        print(f"\n{'=' * 62}")
        print(f"{os.path.basename(target)}  ->  {'PASS' if not errors else 'FAIL'}")
        print(f"{'=' * 62}")
        print(f"条目数 {len(parsed)} | 分类 {[len(g) for _, g in sections]} | 往期比对 {len(history_urls)} 条链接")

        if errors:
            print(f"\n发现 {len(errors)} 个必须修复的问题：")
            for e in errors:
                print(f"  [ERROR] {e}")
        else:
            print("\n全部硬校验通过。")

        for w in warnings:
            print(f"  [WARN] {w}")

        if errors:
            all_fail = True

    print()
    if all_fail:
        print("结论：FAIL —— 存在必须修复的问题。")
        return 1
    print("结论：PASS —— 可以交付。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
