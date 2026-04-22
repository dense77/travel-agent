#!/usr/bin/env python3
"""查询会话状态的最小脚本。

这个脚本不会触发任何新执行，
它只负责读取当前会话快照。
"""

# 启用延迟类型注解。
from __future__ import annotations

# 解析命令行参数。
import argparse
# 打印错误到标准错误流时要用到 sys。
import sys
# 捕获 HTTP 请求报错。
import urllib.error
# 发送 HTTP 请求。
import urllib.request


def main() -> int:
    """查询指定会话的当前状态并输出响应体。"""
    # 创建命令行参数解析器。
    parser = argparse.ArgumentParser(description="Get a travel session.")
    # 第一个位置参数是会话 ID。
    parser.add_argument("session_id", help="Session ID returned by create_session.py")
    # `--base-url` 用来覆盖默认服务地址。
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    # 执行解析。
    args = parser.parse_args()

    # 只构造一个 GET 请求，不带请求体。
    request = urllib.request.Request(
        url=f"{args.base_url}/sessions/{args.session_id}",
        method="GET",
    )

    try:
        # 发起 GET 请求并读取响应。
        with urllib.request.urlopen(request) as response:
            # 把读取到的字节转换成 UTF-8 字符串。
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        # 服务端返回错误时，直接把返回体打印出来。
        print(exc.read().decode("utf-8"), file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        # 网络层错误统一打印成一行易读信息。
        print(f"request failed: {exc}", file=sys.stderr)
        return 1

    # 打印响应原文，便于观察完整结构。
    print(body)
    return 0


# 脚本入口。
if __name__ == "__main__":
    # 交给 shell 一个明确的退出码。
    raise SystemExit(main())
