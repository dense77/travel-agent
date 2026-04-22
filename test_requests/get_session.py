#!/usr/bin/env python3
"""作用：
- 向 `GET /sessions/{session_id}` 发请求，查看当前会话快照。

约定：
- 这个脚本通常用于闭环最后一步，确认计划、观察结果和最终答案都已写回。
- 它不会触发任何新执行，只负责读取状态。
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request


def main() -> int:
    """查询指定会话的当前状态快照，并输出原始响应体。"""
    parser = argparse.ArgumentParser(description="Get a travel session.")
    # 这里读取的 session_id 应与前两个脚本使用的是同一个。
    parser.add_argument("session_id", help="Session ID returned by create_session.py")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    args = parser.parse_args()

    request = urllib.request.Request(
        url=f"{args.base_url}/sessions/{args.session_id}",
        method="GET",
    )

    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        print(exc.read().decode("utf-8"), file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"request failed: {exc}", file=sys.stderr)
        return 1

    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
