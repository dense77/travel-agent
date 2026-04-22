#!/usr/bin/env python3
"""触发会话异步执行的最小脚本。

它只做一件事：
调用 `POST /sessions/{id}/run`，
然后把服务端返回的排队结果打印出来。
"""

# 启用延迟类型注解。
from __future__ import annotations

# 命令行参数解析。
import argparse
# 错误输出需要用到 sys。
import sys
# 捕获 HTTP 和 URL 层报错。
import urllib.error
# 发送 HTTP 请求。
import urllib.request


def main() -> int:
    """触发指定会话执行工作流。"""
    # 创建参数解析器。
    parser = argparse.ArgumentParser(description="Run a travel session workflow.")
    # 强制要求传入 session_id，避免误触发不存在的会话。
    parser.add_argument("session_id", help="Session ID returned by create_session.py")
    # 允许调用方自定义服务地址。
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    # 解析命令行。
    args = parser.parse_args()

    # 构造一个简单的 POST 请求，
    # 当前接口只需要 URL，不需要请求体。
    request = urllib.request.Request(
        url=f"{args.base_url}/sessions/{args.session_id}/run",
        method="POST",
    )

    try:
        # 发起请求并读取响应体。
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        # HTTP 错误时打印服务端响应。
        print(exc.read().decode("utf-8"), file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        # 网络错误时给出简洁提示。
        print(f"request failed: {exc}", file=sys.stderr)
        return 1

    # 打印原始返回结果。
    print(body)
    # 额外提醒使用者现在是异步接口，需要后续再查询状态。
    print("提示：当前 run 接口已改为异步投递，请随后调用 get_session.py 轮询状态。")
    return 0


# 脚本入口。
if __name__ == "__main__":
    # 用返回码结束脚本。
    raise SystemExit(main())
