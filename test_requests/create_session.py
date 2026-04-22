#!/usr/bin/env python3
"""创建测试会话的最小脚本。

这个脚本的目标非常单纯：
向本地 FastAPI 服务发送一次固定请求，
然后把服务返回的原始 JSON 打印出来。
"""

# 这句导入的作用是启用延迟类型注解解析。
from __future__ import annotations

# argparse 用来解析命令行参数。
import argparse
# json 用来把 Python 字典编码成 JSON 字符串。
import json
# sys 用来在错误时把信息打印到标准错误输出。
import sys
# urllib.error 用来捕获 HTTP 请求错误和网络错误。
import urllib.error
# urllib.request 用来发起 HTTP 请求。
import urllib.request


def main() -> int:
    """向本地服务发送创建会话请求，并打印返回体。"""
    # 创建命令行参数解析器。
    parser = argparse.ArgumentParser(description="Create a travel session.")
    # `--base-url` 允许我们在不同地址之间切换，
    # 默认仍然指向本地开发服务。
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    # 真正解析命令行参数。
    args = parser.parse_args()

    # 构造一个固定输入样例，
    # 这样每次验证时都走同一条主链路。
    payload = {
        "query": "五一从上海去杭州玩三天，预算3000，想看西湖和灵隐寺",
        "constraints": {
            "budget": 3000,
            "start_city": "上海",
            "travel_days": 3,
        },
    }
    # 把 URL、请求体、请求头和方法拼成一个 Request 对象。
    request = urllib.request.Request(
        url=f"{args.base_url}/sessions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        # 发起请求并在成功时读取响应体。
        with urllib.request.urlopen(request) as response:
            # 把字节流解码成字符串，便于直接打印。
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        # 如果服务端返回的是 HTTP 错误，
        # 这里直接打印服务端返回内容，方便调试。
        print(exc.read().decode("utf-8"), file=sys.stderr)
        # 返回非 0 表示脚本失败。
        return 1
    except urllib.error.URLError as exc:
        # 如果连不上服务或网络层报错，
        # 这里打印更通俗的错误信息。
        print(f"request failed: {exc}", file=sys.stderr)
        return 1

    # 打印原始响应体。
    print(body)
    # 返回 0 表示脚本成功执行。
    return 0


# 只有直接运行这个文件时才执行 main。
if __name__ == "__main__":
    # 用 SystemExit 包装返回码，让 shell 能正确拿到退出状态。
    raise SystemExit(main())
