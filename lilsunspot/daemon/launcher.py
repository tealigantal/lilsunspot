from __future__ import annotations

import argparse
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from .runtime_discovery import base_url_for, write_runtime_descriptor


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def health_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/health"


def wait_for_health(base_url: str, timeout_seconds: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url(base_url), timeout=0.5) as response:
                body = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and body == {"ok": True}:
                    return True
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            time.sleep(0.2)
    return False


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    if host != DEFAULT_HOST:
        raise ValueError("lilsunspotd 只能绑定到 127.0.0.1。")

    base_url = base_url_for(host, port)
    if wait_for_health(base_url, timeout_seconds=0.3):
        write_runtime_descriptor(host, port)
        print("lilsunspotd 已在运行。")
        return

    os.environ["LILSUNSPOT_BIND_HOST"] = host
    os.environ["LILSUNSPOT_BIND_PORT"] = str(port)

    import uvicorn

    uvicorn.run("lilsunspot.daemon.app:app", host=host, port=port, reload=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start local lilsunspotd.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    run_server(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
