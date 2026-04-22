#!/usr/bin/env python3
"""触发异步工作流执行。"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a travel session workflow.")
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
    print("提示：当前 run 接口已改为异步投递，请随后调用 get_session.py 轮询状态。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
