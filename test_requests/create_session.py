#!/usr/bin/env python3
"""作用：
- 向 `POST /sessions` 发送一个固定样例请求，创建测试会话。

约定：
- 默认请求本机 `http://127.0.0.1:8000`。
- 这是演示闭环的第一步，成功后要记下返回的 `session_id`。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a travel session.")
    # 默认直连本地开发服务，避免引入额外配置成本。
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL")
    args = parser.parse_args()

    # 固定样例确保每次验证都走同一条最小路径。
    payload = {
        "query": "五一从上海去杭州玩三天，预算3000，想看西湖和灵隐寺",
        "constraints": {
            "budget": 3000,
            "start_city": "上海",
            "travel_days": 3,
        },
    }
    request = urllib.request.Request(
        url=f"{args.base_url}/sessions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        # HTTP 错误时打印服务端返回体，方便直接看到 FastAPI 的报错信息。
        print(exc.read().decode("utf-8"), file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"request failed: {exc}", file=sys.stderr)
        return 1

    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
