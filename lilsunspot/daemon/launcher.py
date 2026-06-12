from __future__ import annotations

import argparse
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from .config_paths import RuntimePaths, ensure_runtime_dirs
from .runtime_discovery import base_url_for


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DAEMON_LOCK_FILE_NAME = "lilsunspotd.lock"


class DaemonFileLock:
    def __init__(self, path) -> None:
        self.path = path
        self._file = None

    def acquire(self, *, blocking: bool = False) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        file_obj = self.path.open("a+b")
        file_obj.seek(0, os.SEEK_END)
        if file_obj.tell() == 0:
            file_obj.write(b"\0")
            file_obj.flush()
        file_obj.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt

                mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
                msvcrt.locking(file_obj.fileno(), mode, 1)
            else:
                import fcntl

                flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
                fcntl.flock(file_obj.fileno(), flags)
        except OSError:
            file_obj.close()
            return False
        self._file = file_obj
        return True

    def release(self) -> None:
        file_obj = self._file
        self._file = None
        if file_obj is None:
            return
        try:
            file_obj.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)
        finally:
            file_obj.close()

    def __enter__(self) -> "DaemonFileLock":
        acquired = self.acquire(blocking=False)
        if not acquired:
            raise RuntimeError("小黑子本地服务正在启动，请稍后再试。")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def health_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/health"


def wait_for_health(base_url: str, timeout_seconds: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url(base_url), timeout=0.5) as response:
                body = json.loads(response.read().decode("utf-8"))
                if response.status == 200 and isinstance(body, dict) and body.get("ok") is True:
                    return True
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
            time.sleep(0.2)
    return False


def daemon_lock_path(paths: RuntimePaths | None = None):
    runtime_paths = paths or ensure_runtime_dirs()
    return runtime_paths.data_dir / DAEMON_LOCK_FILE_NAME


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    if host != DEFAULT_HOST:
        raise ValueError("lilsunspotd 只能绑定到 127.0.0.1。")

    runtime_paths = ensure_runtime_dirs()
    base_url = base_url_for(host, port)
    if wait_for_health(base_url, timeout_seconds=0.3):
        print("lilsunspotd 已在运行。")
        return

    lock = DaemonFileLock(daemon_lock_path(runtime_paths))
    if not lock.acquire(blocking=False):
        if wait_for_health(base_url, timeout_seconds=12.0):
            print("lilsunspotd 已在运行。")
            return
        raise RuntimeError("小黑子本地服务正在启动，请稍后再试。")

    try:
        if wait_for_health(base_url, timeout_seconds=0.3):
            print("lilsunspotd 已在运行。")
            return

        os.environ["LILSUNSPOT_BIND_HOST"] = host
        os.environ["LILSUNSPOT_BIND_PORT"] = str(port)

        import uvicorn

        uvicorn.run("lilsunspot.daemon.app:app", host=host, port=port, reload=False)
    finally:
        lock.release()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start local lilsunspotd.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)
    run_server(args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
