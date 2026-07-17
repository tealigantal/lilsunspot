from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import os
import plistlib
import signal
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener


class SmokeError(RuntimeError):
    pass


def run(*args: str, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def wait_until(description: str, predicate, timeout: float = 35.0) -> Any:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except Exception as exc:  # the service may still be starting
            last_error = exc
        time.sleep(0.25)
    suffix = f": {last_error}" if last_error else ""
    raise SmokeError(f"Timed out waiting for {description}{suffix}")


def http_json(
    base_url: str,
    path: str,
    *,
    token: str | None = None,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    expected: tuple[int, ...] = (200,),
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any]]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Lilsunspot-Token"] = token
    request = Request(f"{base_url}{path}", data=body, headers=headers, method=method)
    try:
        with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
            status = response.status
            raw = response.read()
    except HTTPError as exc:
        status = exc.code
        raw = exc.read()
    parsed = json.loads(raw.decode("utf-8")) if raw else {}
    if status not in expected:
        raise SmokeError(f"{method} {path} returned HTTP {status}: {parsed}")
    return status, parsed


class OpenAICompatibleMock(BaseHTTPRequestHandler):
    server_version = "LilsunspotSmokeMock/1"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def _write_json(self, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.rstrip("/").endswith("/models"):
            self._write_json({"object": "list", "data": [{"id": "smoke-model", "object": "model"}]})
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or "0")
        request_payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        if self.path.rstrip("/").endswith("/chat/completions"):
            if request_payload.get("stream"):
                chunks = [
                    {
                        "id": "chatcmpl-macos-smoke",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "smoke-model",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": "macOS 自动烟测回复"},
                                "finish_reason": None,
                            }
                        ],
                    },
                    {
                        "id": "chatcmpl-macos-smoke",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "smoke-model",
                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                    },
                    {
                        "id": "chatcmpl-macos-smoke",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "smoke-model",
                        "choices": [],
                        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                    },
                ]
                raw = "".join(f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n" for chunk in chunks)
                raw += "data: [DONE]\n\n"
                encoded = raw.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
                return
            self._write_json(
                {
                    "id": "chatcmpl-macos-smoke",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": "smoke-model",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "macOS 自动烟测回复"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                }
            )
            return
        self.send_error(404)


@contextlib.contextmanager
def openai_mock_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), OpenAICompatibleMock)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def exact_architectures(binary: Path) -> set[str]:
    result = run("lipo", "-archs", str(binary), capture=True)
    return set(result.stdout.strip().split())


def assert_packaged_app(app_path: Path, expected_arch: str) -> tuple[Path, Path]:
    info_path = app_path / "Contents" / "Info.plist"
    with info_path.open("rb") as stream:
        info = plistlib.load(stream)
    if info.get("CFBundleIdentifier") != "com.lilsunspot.desktop":
        raise SmokeError("Unexpected macOS bundle identifier")
    if info.get("LSMinimumSystemVersion") != "15.0":
        raise SmokeError("Unexpected macOS minimum system version")

    executable_name = str(info.get("CFBundleExecutable") or "Lilsunspot")
    main_binary = app_path / "Contents" / "MacOS" / executable_name
    resources_dir = app_path / "Contents" / "Resources"
    sidecar = resources_dir / "binaries" / "lilsunspotd" / "lilsunspotd"
    for binary in (main_binary, sidecar):
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise SmokeError(f"Missing executable: {binary}")
        arches = exact_architectures(binary)
        if arches != {expected_arch}:
            raise SmokeError(f"Unexpected architectures for {binary}: {sorted(arches)}")

    sidecar_dir = sidecar.parent
    if not (sidecar_dir / "_internal").is_dir():
        raise SmokeError("PyInstaller onedir _internal directory is missing")
    required_names = {path.name for path in sidecar_dir.rglob("*")}
    for required in ("provider_registry.yaml", "UPSTREAM_COMMIT.txt"):
        if required not in required_names:
            raise SmokeError(f"Packaged sidecar resource is missing: {required}")

    run("plutil", "-lint", str(info_path))
    run("codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app_path))
    signature = run("codesign", "-dv", "--verbose=4", str(app_path), capture=True)
    signature_text = f"{signature.stdout}\n{signature.stderr}"
    if "Signature=adhoc" not in signature_text:
        raise SmokeError("The private macOS app is not ad-hoc signed")
    return main_binary, sidecar


def assert_core_api_surface(base_url: str, token: str) -> dict[str, Any]:
    paths = (
        "/app/bootstrap",
        "/providers",
        "/providers/capabilities",
        "/capability-graph",
        "/conversations",
        "/modes",
        "/modes/current",
        "/gateway/weixin/status",
        "/product/capabilities",
        "/safety/policy",
        "/safety/approvals",
        "/tasks",
        "/memory",
        "/diagnostics/summary",
    )
    responses: dict[str, Any] = {}
    for path in paths:
        _, responses[path] = http_json(base_url, path, token=token)

    graph = responses["/capability-graph"].get("by_id") or {}
    expected_capabilities = {
        "chat.text",
        "image.read",
        "file.read",
        "mode.adjust",
        "weixin.receive",
        "weixin.send_file",
    }
    if not expected_capabilities.issubset(graph):
        raise SmokeError("Packaged capability graph is incomplete")

    weixin = responses["/gateway/weixin/status"]
    capabilities = weixin.get("capabilities") or {}
    if not weixin.get("available") or not capabilities.get("qr_login"):
        raise SmokeError("Packaged Weixin adapter or QR-login requirements are unavailable")
    expected_methods = {"send", "send_document", "send_image_file", "send_video"}
    if not expected_methods.issubset(set(capabilities.get("official_adapter_media_methods") or [])):
        raise SmokeError("Packaged Weixin adapter media methods are incomplete")
    return responses


def wait_for_assistant_message(base_url: str, token: str, conversation_id: str, after_user_id: str) -> dict[str, Any]:
    def find_message() -> dict[str, Any] | None:
        _, payload = http_json(base_url, f"/conversations/{conversation_id}/messages", token=token)
        messages = payload.get("messages") or []
        seen_user = False
        for item in messages:
            if item.get("id") == after_user_id:
                seen_user = True
                continue
            if seen_user and item.get("role") == "assistant" and item.get("status") in {"sent", "complete"}:
                return item
        return None

    return wait_until("persisted assistant reply", find_message, timeout=45)


def exercise_persistent_features(base_url: str, token: str, mock_port: int) -> None:
    _, saved = http_json(
        base_url,
        "/providers/save",
        token=token,
        method="POST",
        payload={
            "provider": "ollama",
            "model": "smoke-model",
            "api_key": "",
            "base_url_override": f"http://127.0.0.1:{mock_port}/v1",
        },
    )
    if not saved.get("ok"):
        raise SmokeError("Local OpenAI-compatible model configuration was not saved")

    _, created = http_json(
        base_url,
        "/conversations",
        token=token,
        method="POST",
        payload={"title": "macOS 自动烟测", "kind": "desktop", "metadata": {}},
    )
    conversation_id = str((created.get("conversation") or {}).get("id") or "")
    if not conversation_id:
        raise SmokeError("Conversation creation did not return an id")

    _, sent = http_json(
        base_url,
        f"/conversations/{conversation_id}/messages",
        token=token,
        method="POST",
        payload={"message": "请回复这条 macOS 自动烟测消息。", "attachments": []},
        timeout=45,
    )
    user_message = sent.get("user_message") or {}
    assistant = wait_for_assistant_message(base_url, token, conversation_id, str(user_message.get("id") or ""))
    if "macOS 自动烟测回复" not in str(assistant.get("text") or ""):
        raise SmokeError("Local OpenAI-compatible chat reply was not persisted")

    attachment_bytes = b"non-sensitive macOS DMG smoke attachment"
    _, attachment_sent = http_json(
        base_url,
        f"/conversations/{conversation_id}/messages",
        token=token,
        method="POST",
        payload={
            "message": "请确认收到这个非敏感测试附件。",
            "attachments": [
                {
                    "file_name": "macos-smoke.txt",
                    "mime_type": "text/plain",
                    "data_base64": base64.b64encode(attachment_bytes).decode("ascii"),
                }
            ],
        },
        timeout=45,
    )
    attachment_user = attachment_sent.get("user_message") or {}
    attachments = attachment_user.get("attachments") or []
    if len(attachments) != 1:
        raise SmokeError("Attachment was not persisted on the conversation message")
    attachment_id = str(attachments[0].get("id") or "")
    _, attachment_payload = http_json(base_url, f"/attachments/{attachment_id}", token=token)
    attachment = attachment_payload.get("attachment") or {}
    stored_path = Path(str(attachment.get("safe_path") or ""))
    if attachment.get("file_name") != "macos-smoke.txt" or stored_path.read_bytes() != attachment_bytes:
        raise SmokeError("Attachment endpoint did not return the persisted test file")
    wait_for_assistant_message(base_url, token, conversation_id, str(attachment_user.get("id") or ""))

    _, memory = http_json(
        base_url,
        "/memory",
        token=token,
        method="POST",
        payload={"text": "macOS 自动烟测记忆", "source": "macos-ci"},
    )
    if not (memory.get("memory") or {}).get("id"):
        raise SmokeError("Memory persistence failed")

    due_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(timespec="minutes")
    _, task = http_json(
        base_url,
        "/tasks",
        token=token,
        method="POST",
        payload={
            "title": "macOS 自动烟测任务",
            "prompt": "这是本地自动烟测任务",
            "due_at": due_at,
            "kind": "reminder",
            "schedule": "once",
        },
    )
    if not (task.get("task") or {}).get("id"):
        raise SmokeError("Task persistence failed")

    _, approval = http_json(
        base_url,
        "/safety/approvals/request",
        token=token,
        method="POST",
        payload={
            "operation": "macos_ci_smoke",
            "summary": "macOS 自动烟测审批",
            "details": {"kind": "local-only"},
            "source": "macos-ci",
        },
    )
    approval_id = str((approval.get("approval") or {}).get("id") or "")
    if not approval.get("approval_required") or not approval_id:
        raise SmokeError("Safety approval request did not enter the approval queue")
    http_json(
        base_url,
        f"/safety/approvals/{approval_id}/decide",
        token=token,
        method="POST",
        payload={"decision": "rejected"},
    )

    _, conversations = http_json(base_url, "/conversations", token=token)
    if conversation_id not in {item.get("id") for item in conversations.get("conversations") or []}:
        raise SmokeError("Conversation was not persisted")


def scan_for_token(token: str, paths: list[Path]) -> None:
    token_bytes = token.encode("utf-8")
    for path in paths:
        if path.is_file() and token_bytes in path.read_bytes():
            raise SmokeError(f"Runtime token leaked into log output: {path}")
        if path.is_dir():
            for candidate in path.rglob("*.log"):
                if candidate.is_file() and token_bytes in candidate.read_bytes():
                    raise SmokeError(f"Runtime token leaked into daemon log: {candidate}")


def stop_pid(pid: int) -> None:
    if pid <= 0:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    with contextlib.suppress(ProcessLookupError):
        os.kill(pid, signal.SIGKILL)


def verify_installed_app(dmg_path: Path, expected_arch: str) -> None:
    run("hdiutil", "verify", str(dmg_path))
    with tempfile.TemporaryDirectory(prefix="lilsunspot-macos-smoke-") as temp_value:
        temp_dir = Path(temp_value)
        mount_root = temp_dir / "mount"
        install_root = temp_dir / "Applications"
        isolated_home = temp_dir / "home"
        mount_root.mkdir()
        install_root.mkdir()
        isolated_home.mkdir()

        attach = run(
            "hdiutil",
            "attach",
            "-readonly",
            "-nobrowse",
            "-plist",
            "-mountroot",
            str(mount_root),
            str(dmg_path),
            capture=True,
        )
        attach_payload = plistlib.loads(attach.stdout.encode("utf-8"))
        device = ""
        mounted_path = ""
        for entity in attach_payload.get("system-entities", []):
            device = device or str(entity.get("dev-entry") or "")
            mounted_path = mounted_path or str(entity.get("mount-point") or "")
        if not device or not mounted_path:
            raise SmokeError("DMG did not return a mounted device and path")
        try:
            apps = list(Path(mounted_path).glob("*.app"))
            if len(apps) != 1:
                raise SmokeError("DMG must contain exactly one .app bundle")
            installed_app = install_root / apps[0].name
            run("ditto", str(apps[0]), str(installed_app))
        finally:
            run("hdiutil", "detach", device)

        main_binary, _sidecar = assert_packaged_app(installed_app, expected_arch)
        data_dir = isolated_home / "Library" / "Application Support" / "Lilsunspot" / "data"
        runtime_file = data_dir / "daemon-runtime.json"
        token_file = data_dir / "runtime-token.json"
        stdout_path = temp_dir / "app.stdout.log"
        stderr_path = temp_dir / "app.stderr.log"
        env = os.environ.copy()
        env["HOME"] = str(isolated_home)
        env.pop("LILSUNSPOT_DATA_DIR", None)
        env.pop("LOCALAPPDATA", None)
        env.pop("XDG_DATA_HOME", None)
        env["NO_PROXY"] = "127.0.0.1,localhost"
        env["no_proxy"] = "127.0.0.1,localhost"
        app_process: subprocess.Popen[bytes] | None = None
        daemon_pid = 0

        with openai_mock_server() as mock_port, stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            try:
                app_process = subprocess.Popen([str(main_binary)], env=env, stdout=stdout, stderr=stderr)

                def read_runtime() -> dict[str, Any] | None:
                    if app_process and app_process.poll() is not None:
                        raise SmokeError(f"Tauri app exited early with code {app_process.returncode}")
                    if not runtime_file.is_file():
                        return None
                    return json.loads(runtime_file.read_text(encoding="utf-8"))

                runtime = wait_until("default macOS daemon runtime file", read_runtime)
                if runtime.get("host") != "127.0.0.1":
                    raise SmokeError("Daemon did not bind to 127.0.0.1")
                daemon_pid = int(runtime.get("pid") or 0)
                daemon_executable = Path(str((runtime.get("process") or {}).get("executable") or "")).resolve()
                expected_resource_root = (installed_app / "Contents" / "Resources").resolve()
                if not daemon_executable.is_relative_to(expected_resource_root):
                    raise SmokeError("Desktop did not launch the sidecar from .app/Contents/Resources")

                base_url = str(runtime.get("base_url") or "")
                _, health = http_json(base_url, "/health")
                if not health.get("ok"):
                    raise SmokeError("Daemon /health did not return ok=true")
                http_json(base_url, "/providers", expected=(403,))

                token_payload = json.loads(token_file.read_text(encoding="utf-8"))
                token = str(token_payload.get("token") or "")
                if not token:
                    raise SmokeError("Runtime token file is empty")
                assert_core_api_surface(base_url, token)
                exercise_persistent_features(base_url, token, mock_port)

                if app_process.poll() is not None:
                    raise SmokeError("Tauri window/tray process exited during the installed-app smoke")
                time.sleep(5)
                if app_process.poll() is not None:
                    raise SmokeError("Tauri window/tray process did not remain running")
                scan_for_token(token, [data_dir / "logs", stdout_path, stderr_path])
            finally:
                if app_process is not None and app_process.poll() is None:
                    app_process.terminate()
                    try:
                        app_process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        app_process.kill()
                        app_process.wait(timeout=5)
                stop_pid(daemon_pid)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and smoke-test an installed Lilsunspot macOS DMG")
    parser.add_argument("--dmg", type=Path, required=True)
    parser.add_argument("--arch", choices=("arm64", "x86_64"), required=True)
    args = parser.parse_args()

    dmg_path = args.dmg.resolve()
    if not dmg_path.is_file():
        raise SmokeError(f"DMG not found: {dmg_path}")
    verify_installed_app(dmg_path, args.arch)
    digest = hashlib.sha256(dmg_path.read_bytes()).hexdigest()
    print(f"macOS installed-app smoke passed: {dmg_path.name} arch={args.arch} sha256={digest}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SmokeError, subprocess.CalledProcessError) as exc:
        print(f"macOS installed-app smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
