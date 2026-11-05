"""Verify a deployed Streamlit URL from an external environment."""

from __future__ import annotations

import sys
import urllib.request


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("用法：python scripts/smoke_http.py https://example.streamlit.app")
    base_url = sys.argv[1].rstrip("/")
    with urllib.request.urlopen(base_url + "/_stcore/health", timeout=20) as response:
        body = response.read().decode("utf-8", errors="replace").strip()
        if response.status != 200 or body != "ok":
            raise SystemExit(f"健康检查失败：HTTP {response.status}, {body!r}")
    print(f"[PASS] {base_url} Streamlit健康检查正常")


if __name__ == "__main__":
    main()
