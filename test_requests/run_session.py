#!/usr/bin/env python3
"""作用：
- 向 `POST /sessions/{session_id}/run` 发请求，触发最小工作流执行。

约定：
- 这个脚本必须接收已存在的 `session_id`。
- 正常情况下会把 session 状态从 `created/running` 推进到 `finished`。
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a travel session workflow.")
    # 这里强制要求 session_id，避免误跑到一个并不存在的会话。
    parser.add_argument("session_id", help="Session ID returned by create_session.py")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    args = parser.parse_args()

    request = urllib.request.Request(
        url=f"{args.base_url}/sessions/{args.session_id}/run",
        method="POST",
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
