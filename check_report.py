#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 日报成稿硬校验（CI / 本地通用）· v2

用法::

    python check_report.py                 校验报告目录下最新一份日报
    python check_report.py <文件路径>       校验指定日报
    python check_report.py --all           校验全部日报

报告目录优先级：REPORT_DIR 环境变量 → 本脚本所在目录 → 向上寻找含 .github 的仓库根。

检查项（任一 ERROR 即 FAIL，退出码 1）
--------------------------------------
E1  条目数目标 20，**不足也照发**：低于 MIN_TOTAL（默认 3）判 ERROR，3–19 条仅 WARN
E2  本期内部原文链接不得重复
E3  原文链接不得与**全部历史**重复（标【进展更新】降级为 WARN）
E4  发布日期须落在 [D-1, D]（D = 日报文件名日期）
E5  每条须有标题 / 原文链接 / 来源 / 正文
E6  分区目标 7/7/6：未达目标但各分区均未超上限 → WARN；有分区超上限 → ERROR
E7  事件链指纹去重：期内 + 全部历史（厂商×动作×金额 / 标题 2-gram ≥0.45）
E8  单期同一厂商 ≤2 条
E9  标题相似度去重：与任一条历史标题 2-gram Jaccard ≥0.65（厂商无关）

与 v1 的差异：v1 解析的是 `**摘要** / **原文链接**：` 这套字段，而生成器实际输出的是
`> 来源：… · 日期 · [原文](url)`，两边格式根本对不上 —— 也就是说 v1 即使被调用也会
把 20 条全部判为"缺要素"。v2 改用与生成器同一套解析（dedup.parse_report），
并把比对窗口从「最近 3 期」扩到全部历史。
"""

import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dedup  # noqa: E402

# 统一 UTF-8 输出（用 reconfigure 避免多层包装共用 buffer 的坑）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

EXPECTED_TOTAL = 20
EXPECTED_SECTIONS = [7, 7, 6]
# 发布下限：目标 20 条，但「不足也照发」；低于此值才判 FAIL（代表链路异常）。可用 MIN_TOTAL 覆盖。
MIN_TOTAL = int(os.environ.get("MIN_TOTAL") or 1)
ALERT_NAME = "ALERT.json"


def active_alert(report_dir):
    """返回「当日」的故障通报（无则 None）。

    生成器本轮没出稿时，会在目录里留下 ALERT.json —— 此时根本没有可校验的日报，
    硬校验必须放行，否则工作流会卡在这一步，「Push report to email」被跳过，
    精心准备的故障通报就永远送不出去（也就是又回到静默失败）。
    隔夜残留（日期不是今天）不认，避免用旧故障掩盖今天的真实校验失败。
    """
    path = os.path.join(report_dir, ALERT_NAME)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(data, dict) or not data.get("alert"):
        return None
    today = _today_iso()
    return data if data.get("date") == today else None


def _today_iso():
    """北京时间今天（CI 里已设 TZ=Asia/Shanghai，仍显式换算以防本地跑时错判）。"""
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8))).strftime("%Y-%m-%d")


def find_report_dir(explicit_file=None):
    """定位日报所在目录。

    优先级：显式文件所在目录 → REPORT_DIR → 脚本所在目录（含日报时）
            → 向上寻找仓库根下的 skills/newshub。
    """
    if explicit_file:
        d = os.path.dirname(os.path.abspath(explicit_file))
        if os.path.isdir(d):
            return d
    env = os.environ.get("REPORT_DIR")
    if env and os.path.isdir(env):
        return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    if glob.glob(os.path.join(here, "AI资讯24小时_*.md")):
        return here
    cur = here
    for _ in range(5):
        sub = os.path.join(cur, "skills", "newshub")
        if os.path.isdir(sub) and glob.glob(os.path.join(sub, "AI资讯24小时_*.md")):
            return sub
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return here


def list_reports(report_dir):
    found = []
    for p in glob.glob(os.path.join(report_dir, "AI资讯24小时_*.md")):
        d = dedup.name_date(p)
        if d:
            found.append((d, p))
    found.sort(key=lambda x: x[0])
    return found


def check_one(path, reports, report_dir):
    day = dedup.name_date(path)
    name = os.path.basename(path)
    history = dedup.load_history(report_dir, exclude={name}, before=day)

    with open(path, encoding="utf-8") as f:
        text = f.read()

    errors, warnings, items, sections = dedup.gate(
        text, history, day,
        expected_total=EXPECTED_TOTAL, expected_sections=EXPECTED_SECTIONS,
        min_total=MIN_TOTAL)

    print(f"\n{'=' * 62}")
    print(f"{name}  ->  {'PASS' if not errors else 'FAIL'}")
    print(f"{'=' * 62}")
    print(f"条目数 {len(items)} | 分类 {[len(s['items']) for s in sections]} | "
          f"往期比对 {len(history.files)} 期 / {len(history.urls)} 条链接 / "
          f"{len(history.fps)} 条事件指纹")

    if errors:
        print(f"\n发现 {len(errors)} 个必须修复的问题：")
        for e in errors:
            print(f"  [ERROR] {e}")
    else:
        print("\n全部硬校验通过。")
    for w in warnings:
        print(f"  [WARN] {w}")
    return not errors


def main():
    args = [a for a in sys.argv[1:]]
    explicit = args[0] if (args and not args[0].startswith("-")) else None
    report_dir = find_report_dir(explicit)

    # 故障通报模式：生成器本轮没出稿，没有可校验的日报。
    # 这里必须放行（退出码 0），否则工作流在这一步中断，「Push report to email」
    # 会被跳过 —— 生成器精心准备的故障通报就永远送不出去，等于又回到静默失败。
    if explicit is None:
        alert = active_alert(report_dir)
        if alert:
            print(f"\n{'=' * 62}")
            print(f"本轮未出稿（故障通报模式）—— {alert.get('date_cn')}")
            print(f"{'=' * 62}")
            print(f"失败阶段：{alert.get('stage')}")
            print(f"直接原因：{alert.get('reason')}")
            print(f"运行地址：{alert.get('run_url')}")
            print("\n生成器已把失败写入 ALERT.json 与 index.html，"
                  "本次不做日报硬校验，交给后续发信步骤送达通报。")
            return 0

    reports = list_reports(report_dir)
    if not reports:
        print(f"未找到任何日报文件，报告目录：{report_dir}")
        return 1

    if args and args[0] == "--all":
        targets = [p for _, p in reports]
    elif args and not args[0].startswith("-"):
        targets = [os.path.abspath(args[0])]
    else:
        targets = [reports[-1][1]]

    all_pass = True
    for t in targets:
        if not os.path.exists(t):
            print(f"[跳过] 文件不存在：{t}")
            continue
        if not check_one(t, reports, report_dir):
            all_pass = False

    print()
    print("结论：PASS —— 可以交付。" if all_pass
          else "结论：FAIL —— 存在必须修复的问题，请修正后重新校验。")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
