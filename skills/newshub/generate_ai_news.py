# 兼容别名：原工作流调用 generate_ai_news.py，本文件转发到 generate.py
# 这样无需修改 .github/workflows/ai-news.yml 即可复用同一套生成逻辑。
from generate import main

if __name__ == "__main__":
    main()
