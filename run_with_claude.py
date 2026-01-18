#!/usr/bin/env python3
"""
使用第三方 Claude API 运行新闻聚合器
直接使用 requests 调用，避免 SDK 兼容性问题
"""

import os
import sys
import json
import subprocess
import requests

def run_news_aggregator_with_claude():
    """使用 Claude 来执行新闻聚合任务"""

    # 获取环境变量
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    base_url = os.environ.get('ANTHROPIC_BASE_URL', 'https://api.anthropic.com')

    if not api_key:
        print("错误：未找到 ANTHROPIC_API_KEY 环境变量")
        sys.exit(1)

    print("=" * 50)
    print("使用 Claude API 运行新闻聚合器")
    print(f"API 端点: {base_url}")
    print("=" * 50)

    # 构建 API 端点
    api_endpoint = f"{base_url}/v1/messages"

    # 构建请求头
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    # 构建初始消息
    messages = [{
        "role": "user",
        "content": """请帮我执行新闻聚合任务：

1. 运行命令：python enhanced_news_aggregator.py api-config.json
2. 确认 HTML 报告生成成功
3. 报告生成的文件名和位置

请使用 bash 工具来执行命令。"""
    }]

    # 定义可用的工具
    tools = [{
        "name": "bash",
        "description": "Execute bash commands to run scripts and check files",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute"
                }
            },
            "required": ["command"]
        }
    }]

    # 开始对话循环
    max_iterations = 5
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        print(f"\n--- 迭代 {iteration} ---")

        # 构建请求数据
        request_data = {
            "model": "claude-sonnet-4-5-20250929",
            "max_tokens": 4096,
            "messages": messages,
            "tools": tools
        }

        # 调用 Claude API
        print("正在调用 Claude API...")
        try:
            response = requests.post(
                api_endpoint,
                headers=headers,
                json=request_data,
                timeout=60
            )

            if response.status_code != 200:
                print(f"API 调用失败: {response.status_code}")
                print(f"响应: {response.text}")
                return False

            result = response.json()
            print(f"Claude 响应类型: {result.get('stop_reason')}")

        except Exception as e:
            print(f"API 调用异常: {str(e)}")
            return False

        # 处理响应
        content_blocks = result.get('content', [])
        tool_uses = []
        assistant_content = []

        for block in content_blocks:
            if block.get('type') == 'text':
                print(f"\nClaude: {block.get('text')}")
                assistant_content.append(block)
            elif block.get('type') == 'tool_use':
                tool_uses.append(block)
                assistant_content.append(block)

        # 添加助手消息到历史
        messages.append({
            "role": "assistant",
            "content": assistant_content
        })

        # 如果没有工具调用，说明任务完成
        if not tool_uses:
            print("\n任务完成！")
            break

        # 执行工具调用
        tool_results = []
        for tool_use in tool_uses:
            if tool_use.get('name') == 'bash':
                command = tool_use.get('input', {}).get('command', '')
                print(f"\n执行命令: {command}")

                try:
                    result = subprocess.run(
                        command,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )

                    output = result.stdout
                    if result.stderr:
                        output += f"\nSTDERR:\n{result.stderr}"

                    print(f"命令输出:\n{output}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.get('id'),
                        "content": output
                    })

                except subprocess.TimeoutExpired:
                    error_msg = "命令执行超时"
                    print(f"错误: {error_msg}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.get('id'),
                        "content": error_msg,
                        "is_error": True
                    })

                except Exception as e:
                    error_msg = f"命令执行失败: {str(e)}"
                    print(f"错误: {error_msg}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.get('id'),
                        "content": error_msg,
                        "is_error": True
                    })

        # 将工具结果添加到消息历史
        messages.append({
            "role": "user",
            "content": tool_results
        })

    if iteration >= max_iterations:
        print("\n警告：达到最大迭代次数")
        return False

    return True

if __name__ == "__main__":
    try:
        success = run_news_aggregator_with_claude()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n错误: {str(e)}")
        sys.exit(1)
