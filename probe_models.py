#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探活：问网关要一份可用模型清单，并逐个做一次最小对话调用。

为什么需要它
------------
2026-10-11、10-12 连续两天不出稿，原因是网关返回
  503 model_not_found「分组 default 下模型 agnes-2.0-flash 无可用渠道（distributor）」
—— 供应商侧把模型下线/改名了。CI 日志里只能看到「LLM 调用失败」，
看不到「到底还有哪些模型能用」，所以修不出手。
本脚本就是补这个盲区：一条命令列出**当前真正可用**的模型。

用法
----
  # PowerShell
  $env:ANTHROPIC_API_KEY='sk-xxx'
  python probe_models.py

  # Git Bash
  ANTHROPIC_API_KEY=sk-xxx python probe_models.py

可选：
  ANTHROPIC_BASE_URL   默认 https://api.agnes-ai.cn/v1
  PROBE_ALL=1          对清单里**每个**模型都试一次真实对话（默认只试前 8 个）
"""
import os
import sys

import requests

BASE_URL = (os.environ.get("ANTHROPIC_BASE_URL") or "https://api.agnes-ai.cn/v1").rstrip("/")
API_KEY = os.environ.get("ANTHROPIC_API_KEY")
PROBE_ALL = os.environ.get("PROBE_ALL", "").lower() in ("1", "true", "yes")

NON_CHAT_HINTS = (
    "image", "img", "video", "tts", "asr", "whisper", "speech", "audio", "voice",
    "embed", "rerank", "moderation", "ocr", "-sd", "flux", "kling", "veo", "sora",
    "seedance", "seedream", "dall", "midjourney", "upscale", "matting", "avatar",
)


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def main():
    if not API_KEY:
        die("ERROR: 未设置 ANTHROPIC_API_KEY。\n"
            "  PowerShell : $env:ANTHROPIC_API_KEY='sk-xxx'\n"
            "  Git Bash   : export ANTHROPIC_API_KEY=sk-xxx")
    headers = {"Authorization": f"Bearer {API_KEY}"}

    print(f"网关：{BASE_URL}")
    try:
        r = requests.get(BASE_URL + "/models", headers=headers, timeout=30)
    except Exception as e:  # noqa: BLE001
        die(f"ERROR: 连接网关失败：{type(e).__name__}: {e}")

    print(f"GET /models → HTTP {r.status_code}")
    if r.status_code != 200:
        die(f"ERROR: 列举模型失败：{r.text[:400]}\n"
            "（401/403 = key 无效或无权限；404 = 该网关不支持 /models）")

    try:
        items = r.json().get("data") or []
    except Exception as e:  # noqa: BLE001
        die(f"ERROR: 清单不是合法 JSON：{type(e).__name__}: {e}｜{r.text[:200]}")

    ids = [m.get("id") for m in items if isinstance(m, dict) and m.get("id")]
    if not ids:
        die("ERROR: 清单为空 —— 该 key 名下一个模型都没开通。")

    chat = [i for i in ids if not any(h in i.lower() for h in NON_CHAT_HINTS)]
    other = [i for i in ids if i not in chat]
    print(f"\n共 {len(ids)} 个模型（对话类 {len(chat)} 个）：")
    for i in chat:
        print(f"  · {i}")
    if other:
        print(f"  （另有图像/视频/语音/向量类 {len(other)} 个：{', '.join(other[:8])}"
              f"{' …' if len(other) > 8 else ''}）")

    targets = chat if PROBE_ALL else chat[:8]
    print(f"\n逐个试一次真实对话（{'全部' if PROBE_ALL else '前 %d 个' % len(targets)}）……")
    ok_list, bad_list = [], []
    for m in targets:
        try:
            resp = requests.post(
                BASE_URL + "/chat/completions", headers={**headers,
                                                         "Content-Type": "application/json"},
                json={"model": m, "max_tokens": 16,
                      "messages": [{"role": "user", "content": "回复两个字：可用"}]},
                timeout=60)
        except Exception as e:  # noqa: BLE001
            bad_list.append(m)
            print(f"  ✗ {m:<28} 连接异常 {type(e).__name__}: {e}")
            continue
        if resp.status_code == 200:
            try:
                text = resp.json()["choices"][0]["message"]["content"]
            except Exception:  # noqa: BLE001
                text = "(结构异常)"
            ok_list.append(m)
            print(f"  ✓ {m:<28} {str(text).strip()[:40]!r}")
        else:
            bad_list.append(m)
            print(f"  ✗ {m:<28} {resp.status_code} {resp.text[:120]}")

    print("\n" + "=" * 68)
    print(f"可用 {len(ok_list)} / 不可用 {len(bad_list)}")
    if ok_list:
        print(f"\n把下面这行填进仓库 Secret ANTHROPIC_MODEL 即可：\n  {ok_list[0]}")
        print("（generate.py 也会自动按 /models 挑备选，填错不会直接空窗）")
    else:
        print("\n没有任何对话模型可用 —— 去 Agnes AI 控制台确认套餐/额度与模型开通情况。")
    return 0 if ok_list else 1


if __name__ == "__main__":
    sys.exit(main())
