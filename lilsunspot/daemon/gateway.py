from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any
import base64

from . import conversations, turn_coalescer
from .agent_host import submit_clarify_answer
from .attachments import (
    AttachmentError,
    attachment_summaries_for_prompt,
    recognize_image_attachments,
    register_message_attachments,
)
from .config_paths import RuntimePaths, ensure_runtime_dirs
from .media_delivery import add_delivery_context_to_prompt, prepare_assistant_delivery, register_prepared_delivery
from .mode_intents import apply_mode_intent, slash_command_hint

WEIXIN_COMMANDS: list[dict[str, Any]] = [
    {
        "name": "/help",
        "enabled": True,
        "description": "显示小黑子微信命令帮助。",
        "approval_required": False,
    },
    {
        "name": "/mode",
        "enabled": True,
        "description": "查看或切换输出模式，例如 /mode pragmatic。",
        "approval_required": False,
    },
]

WEIXIN_STATE_FILE_NAME = "weixin-state.json"
WEIXIN_LOGIN_TIMEOUT_SECONDS = 480
WEIXIN_SCANNED_CONFIRM_WARNING_SECONDS = 75
WEIXIN_QR_REQUEST_TIMEOUT_MS = 9_000
WEIXIN_ILINK_BASE_URL = "https://ilinkai.weixin.qq.com"
WEIXIN_QR_ENDPOINT = "ilink/bot/get_bot_qrcode"
WEIXIN_QR_STATUS_ENDPOINT = "ilink/bot/get_qrcode_status"
WEIXIN_DEFAULT_BOT_NICKNAME = "小黑子"
WEIXIN_DEFAULT_BOT_AVATAR_ASSET = "lilsunspot-icon.png"


@dataclass
class WeixinLoginSession:
    qrcode: str
    qr_payload: str
    base_url: str
    status: str
    generation: int
    started_at: float
    expires_at: float
    message: str
    scanned_at: float = 0.0
    poll_warning: str = ""
    risk_flags: list[str] = field(default_factory=list)


_active_login: WeixinLoginSession | None = None
_login_generation = 0
_weixin_switch_menus: dict[str, dict[str, Any]] = {}
WEIXIN_SWITCH_MENU_TTL_SECONDS = 300


class WeixinGatewayError(RuntimeError):
    """User-visible Weixin gateway failure with plain Chinese text."""


def default_weixin_bot_profile() -> dict[str, str]:
    return {
        "nickname": WEIXIN_DEFAULT_BOT_NICKNAME,
        "avatar_asset": WEIXIN_DEFAULT_BOT_AVATAR_ASSET,
        "avatar_alt": "小黑子头像",
    }


def _dedupe_flags(flags: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for flag in flags:
        value = flag.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _login_risk_flags(session: WeixinLoginSession | None) -> list[str]:
    if session is None:
        return []
    flags = list(session.risk_flags)
    if (
        session.status == "scanned"
        and session.scanned_at > 0
        and time.time() - session.scanned_at >= WEIXIN_SCANNED_CONFIRM_WARNING_SECONDS
    ):
        flags.append("user_confirmation_delayed")
    return _dedupe_flags(flags)


def _login_verification_payload(
    *,
    state: str,
    message: str,
    risk_flags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "state": state,
        "risk_flags": _dedupe_flags(risk_flags or []),
        "message": message,
    }


def _weixin_login_verification_status(
    *,
    connected: bool,
    status: str,
    message: str,
    active_login: WeixinLoginSession | None,
) -> dict[str, Any]:
    if connected:
        return _login_verification_payload(
            state="verified",
            message="微信登录已通过同步验证。",
        )
    if active_login is not None and status in {"qr_pending", "scanned"}:
        risks = _login_risk_flags(active_login)
        if "user_confirmation_delayed" in risks:
            return _login_verification_payload(
                state="attention",
                risk_flags=risks,
                message="已扫码但长时间没有确认，可能是在手机上点了取消、扫错二维码，或确认页被切走。",
            )
        if "user_scan_cancelled_or_wrong_qr" in risks:
            return _login_verification_payload(
                state="attention",
                risk_flags=risks,
                message="刚才的扫码没有完成，可能是误扫、取消确认或扫了旧二维码。",
            )
        return _login_verification_payload(
            state="pending",
            risk_flags=risks,
            message="正在等待手机微信完成确认。",
        )
    if status in {"error", "credential_expired"}:
        return _login_verification_payload(
            state="failed",
            risk_flags=_login_risk_flags(active_login),
            message=message,
        )
    return _login_verification_payload(
        state="not_started",
        message="微信尚未开始登录验证。",
    )


def _weixin_login_qr_endpoint(bot_type: str = "3") -> str:
    return f"{WEIXIN_QR_ENDPOINT}?bot_type={bot_type}"


def _weixin_state_path(paths: RuntimePaths) -> Path:
    return paths.data_dir / WEIXIN_STATE_FILE_NAME


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _iso_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _bump_login_generation() -> int:
    global _login_generation
    _login_generation += 1
    return _login_generation


def _safe_account_file(paths: RuntimePaths, account_id: str) -> Path | None:
    account_value = account_id.strip()
    if not account_value or any(part in account_value for part in ("\\", "/", "..")):
        return None
    return paths.hermes_home / "weixin" / "accounts" / f"{account_value}.json"


def load_weixin_credentials(paths: RuntimePaths | None = None) -> dict[str, str] | None:
    runtime_paths = paths or ensure_runtime_dirs()
    state = _read_json(_weixin_state_path(runtime_paths))
    account_id = str(state.get("account_id") or "").strip()
    if account_id:
        account_file = _safe_account_file(runtime_paths, account_id)
        account_payload = _read_json(account_file) if account_file and account_file.exists() else {}
        token = str(account_payload.get("token") or "").strip()
        if token:
            return {
                "account_id": account_id,
                "token": token,
                "user_id": str(state.get("user_id") or account_payload.get("user_id") or ""),
                "base_url": str(state.get("base_url") or account_payload.get("base_url") or WEIXIN_ILINK_BASE_URL),
                "connected_at": str(state.get("connected_at") or account_payload.get("saved_at") or ""),
            }
        return None

    account_dir = runtime_paths.hermes_home / "weixin" / "accounts"
    if not account_dir.exists():
        return None
    for account_file in sorted(account_dir.glob("*.json")):
        account_payload = _read_json(account_file)
        token = str(account_payload.get("token") or "").strip()
        if token:
            return {
                "account_id": account_file.stem,
                "token": token,
                "user_id": str(account_payload.get("user_id") or ""),
                "base_url": str(account_payload.get("base_url") or WEIXIN_ILINK_BASE_URL),
                "connected_at": str(account_payload.get("saved_at") or ""),
            }
    return None


def _load_connection_state(paths: RuntimePaths | None = None) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    state = _read_json(_weixin_state_path(runtime_paths))
    account_id = str(state.get("account_id") or "").strip()
    if account_id:
        credentials = load_weixin_credentials(runtime_paths)
        if credentials:
            return {
                "configured": True,
                "account_id": credentials["account_id"],
                "user_id": credentials.get("user_id", ""),
                "connected_at": credentials.get("connected_at", ""),
            }
        return {"configured": False, "expired": True}

    credentials = load_weixin_credentials(runtime_paths)
    if credentials:
        return {
            "configured": True,
            "account_id": credentials["account_id"],
            "user_id": credentials.get("user_id", ""),
            "connected_at": credentials.get("connected_at", ""),
        }
    return {"configured": False}


def _clear_connection_state(paths: RuntimePaths | None = None) -> None:
    runtime_paths = paths or ensure_runtime_dirs()
    state = _read_json(_weixin_state_path(runtime_paths))
    account_id = str(state.get("account_id") or "").strip()
    if account_id:
        account_file = _safe_account_file(runtime_paths, account_id)
        if account_file and account_file.exists():
            account_file.unlink()
    else:
        account_dir = runtime_paths.hermes_home / "weixin" / "accounts"
        if account_dir.exists():
            for account_file in account_dir.glob("*.json"):
                account_file.unlink()
    state_path = _weixin_state_path(runtime_paths)
    if state_path.exists():
        state_path.unlink()


def _weixin_requirements_available() -> bool:
    try:
        from gateway.platforms.weixin import check_weixin_requirements
    except Exception:
        return False
    return bool(check_weixin_requirements())


async def _weixin_api_get(*, base_url: str, endpoint: str) -> dict[str, Any]:
    try:
        from gateway.platforms import weixin as hermes_weixin
    except Exception as exc:
        raise WeixinGatewayError("微信网关组件加载失败，请重新安装小黑子。") from exc
    if not hermes_weixin.check_weixin_requirements():
        raise WeixinGatewayError("微信网关缺少运行组件，请重新安装小黑子。")
    async with hermes_weixin.aiohttp.ClientSession(
        trust_env=True,
        connector=hermes_weixin._make_ssl_connector(),
    ) as session:
        return await hermes_weixin._api_get(
            session,
            base_url=base_url,
            endpoint=endpoint,
            timeout_ms=WEIXIN_QR_REQUEST_TIMEOUT_MS,
        )


def _save_weixin_credentials(credentials: dict[str, Any], paths: RuntimePaths | None = None) -> None:
    runtime_paths = paths or ensure_runtime_dirs()
    account_id = str(credentials.get("account_id") or "").strip()
    token = str(credentials.get("token") or "").strip()
    base_url = str(credentials.get("base_url") or WEIXIN_ILINK_BASE_URL).strip()
    user_id = str(credentials.get("user_id") or "").strip()
    if not account_id or not token:
        raise WeixinGatewayError("微信扫码成功，但返回凭据不完整，请重新扫码。")
    try:
        from gateway.platforms.weixin import save_weixin_account
    except Exception as exc:
        raise WeixinGatewayError("微信凭据保存组件加载失败，请重新安装小黑子。") from exc
    save_weixin_account(
        str(runtime_paths.hermes_home),
        account_id=account_id,
        token=token,
        base_url=base_url,
        user_id=user_id,
    )
    _write_json(
        _weixin_state_path(runtime_paths),
        {
            "account_id": account_id,
            "user_id": user_id,
            "base_url": base_url,
            "connected_at": _iso_now(),
        },
    )


def _credentials_from_confirmed_status(status_resp: dict[str, Any]) -> dict[str, str]:
    credentials = {
        "account_id": str(status_resp.get("ilink_bot_id") or "").strip(),
        "token": str(status_resp.get("bot_token") or "").strip(),
        "base_url": str(status_resp.get("baseurl") or WEIXIN_ILINK_BASE_URL).strip(),
        "user_id": str(status_resp.get("ilink_user_id") or "").strip(),
    }
    missing = [
        label
        for key, label in (
            ("account_id", "账号标识"),
            ("token", "登录凭据"),
            ("base_url", "服务地址"),
            ("user_id", "用户标识"),
        )
        if not credentials[key]
    ]
    if missing:
        missing_text = "、".join(missing)
        raise WeixinGatewayError(f"检测到这次微信登录没有通过验证，缺少{missing_text}，请刷新二维码后重新扫码。")
    if not credentials["base_url"].startswith(("http://", "https://")):
        raise WeixinGatewayError("检测到这次微信登录返回的服务地址异常，请刷新二维码后重新扫码。")
    return credentials


def fail_weixin_login_verification(message: str, paths: RuntimePaths | None = None) -> dict[str, Any]:
    global _active_login

    _bump_login_generation()
    _clear_connection_state(paths)
    now = time.time()
    _active_login = WeixinLoginSession(
        qrcode="",
        qr_payload="",
        base_url=WEIXIN_ILINK_BASE_URL,
        status="error",
        generation=_login_generation,
        started_at=now,
        expires_at=now,
        message=message,
        risk_flags=["fake_login_verification_failed"],
    )
    status = weixin_status()
    return {"ok": False, **status, "message": message}


def _make_qr_image_data_url(qr_payload: str) -> str:
    try:
        import qrcode
        from qrcode.image.svg import SvgPathImage
    except Exception:
        return ""

    try:
        qr = qrcode.QRCode(border=2)
        qr.add_data(qr_payload)
        qr.make(fit=True)
        image = qr.make_image(image_factory=SvgPathImage)
        output = BytesIO()
        image.save(output)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:image/svg+xml;base64,{encoded}"
    except Exception:
        return ""


def _redacted_login_payload(session: WeixinLoginSession | None) -> dict[str, Any] | None:
    if session is None:
        return None
    qr_payload = session.qr_payload if session.status in {"qr_pending", "scanned"} else ""
    risk_flags = _login_risk_flags(session)
    if "user_confirmation_delayed" in risk_flags:
        session.poll_warning = "已扫码但长时间没有确认，可能是误点取消、扫错二维码，或手机确认页被切走。"
    return {
        "status": session.status,
        "display_status": session.status,
        "qr_payload": qr_payload,
        "qr_payload_kind": "url" if session.qr_payload.startswith(("http://", "https://")) else "text",
        "qr_image_data_url": _make_qr_image_data_url(qr_payload) if qr_payload else "",
        "expires_at": int(session.expires_at),
        "message": session.message,
        "poll_warning": session.poll_warning,
        "risk_flags": risk_flags,
    }


def weixin_status() -> dict[str, Any]:
    global _active_login
    connection = _load_connection_state()
    available = _weixin_requirements_available()
    active_login = _active_login
    if connection.get("configured"):
        if active_login is not None:
            _active_login = None
        status = "connected"
        connected = True
        message = "微信已扫码连接；直接在微信私聊里发消息，或在桌面查看对应对话。"
        login = None
    elif active_login and active_login.status in {"qr_pending", "scanned", "qr_expired", "error"}:
        status = active_login.status
        connected = False
        message = active_login.message
        login = _redacted_login_payload(active_login)
    elif connection.get("expired"):
        status = "credential_expired"
        connected = False
        message = "微信凭据已失效，请重新扫码连接。"
        login = None
    elif not available:
        status = "error"
        connected = False
        message = "微信网关缺少运行组件，请重新安装小黑子。"
        login = None
    else:
        status = "not_configured"
        connected = False
        message = "微信尚未连接。点击扫码连接后，用手机微信确认登录。"
        login = None
    return {
        "gateway": "weixin",
        "available": available,
        "connected": connected,
        "status": status,
        "display_status": status,
        "commands_available": True,
        "bot_profile": default_weixin_bot_profile(),
        "login": login,
        "login_verification": _weixin_login_verification_status(
            connected=connected,
            status=status,
            message=message,
            active_login=active_login,
        ),
        "capabilities": {
            "qr_login": available,
            "private_chat": connected,
            "commands": True,
            "attachments": True,
            "attachment_send_requires_approval": False,
            "official_adapter_media_methods": ["send", "send_document", "send_image_file", "send_video"],
            "active_send_requires_approval": False,
            "official_payment_or_materials_required": False,
        },
        "message": message,
    }


def weixin_commands() -> dict[str, Any]:
    return {
        "gateway": "weixin",
        "commands": WEIXIN_COMMANDS,
        "message": "这些命令可用于微信私聊入口。",
    }


async def start_weixin_login() -> dict[str, Any]:
    global _active_login
    if not _weixin_requirements_available():
        raise WeixinGatewayError("微信网关缺少运行组件，请重新安装小黑子。")
    generation = _bump_login_generation()
    try:
        qr_resp = await _weixin_api_get(
            base_url=WEIXIN_ILINK_BASE_URL,
            endpoint=_weixin_login_qr_endpoint(),
        )
    except WeixinGatewayError:
        raise
    except Exception as exc:
        raise WeixinGatewayError("微信二维码获取失败，请检查网络后重试。") from exc

    qrcode = str(qr_resp.get("qrcode") or "").strip()
    qr_payload = str(qr_resp.get("qrcode_img_content") or "").strip()
    if not qrcode:
        raise WeixinGatewayError("微信二维码数据不完整，请稍后重试。")
    if not qr_payload:
        raise WeixinGatewayError("微信二维码内容缺失，请重新生成二维码。")
    if not qr_payload.startswith(("http://", "https://")):
        raise WeixinGatewayError("微信二维码格式异常，请重新生成二维码。")
    if generation != _login_generation:
        status = weixin_status()
        return {"ok": False, **status, "message": "本次刷新已被新的操作取代。"}

    now = time.time()
    _active_login = WeixinLoginSession(
        qrcode=qrcode,
        qr_payload=qr_payload,
        base_url=WEIXIN_ILINK_BASE_URL,
        status="qr_pending",
        generation=generation,
        started_at=now,
        expires_at=now + WEIXIN_LOGIN_TIMEOUT_SECONDS,
        message="请使用手机微信扫码，并在手机上确认登录。",
    )
    status = weixin_status()
    return {"ok": True, **status}


async def poll_weixin_login_status() -> dict[str, Any]:
    global _active_login
    session = _active_login
    if session is None:
        status = weixin_status()
        return {"ok": True, **status}
    if time.time() >= session.expires_at:
        session.status = "qr_expired"
        session.message = "微信二维码已过期，请重新生成。"
        status = weixin_status()
        return {"ok": False, **status}

    try:
        status_resp = await _weixin_api_get(
            base_url=session.base_url,
            endpoint=f"{WEIXIN_QR_STATUS_ENDPOINT}?qrcode={session.qrcode}",
        )
    except Exception:
        if _active_login is not session or session.generation != _login_generation:
            status = weixin_status()
            return {"ok": False, **status, "message": "本次扫码状态已被新的操作取代。"}
        if session.status not in {"qr_pending", "scanned"}:
            session.status = "qr_pending"
        session.poll_warning = "微信扫码状态读取失败，正在确认，稍后自动重试。"
        session.message = "正在确认，稍后自动重试。"
        status = weixin_status()
        return {"ok": True, **status}
    if _active_login is not session or session.generation != _login_generation:
        status = weixin_status()
        return {"ok": False, **status, "message": "本次扫码状态已被新的操作取代。"}

    session.poll_warning = ""
    raw_status = str(status_resp.get("status") or "wait").strip()
    if raw_status == "wait":
        if session.status == "scanned" or "user_scan_cancelled_or_wrong_qr" in session.risk_flags:
            session.risk_flags = _dedupe_flags([*session.risk_flags, "user_scan_cancelled_or_wrong_qr"])
            session.poll_warning = "刚才的扫码没有完成，可能是误点取消、扫错二维码，或扫了旧二维码。"
        session.status = "qr_pending"
        session.message = session.poll_warning or "请使用手机微信扫码，并在手机上确认登录。"
    elif raw_status == "scaned":
        session.risk_flags = [flag for flag in session.risk_flags if flag != "user_scan_cancelled_or_wrong_qr"]
        if session.scanned_at <= 0:
            session.scanned_at = time.time()
        session.status = "scanned"
        session.message = "已扫码，请在手机微信里确认登录。"
    elif raw_status == "scaned_but_redirect":
        redirect_host = str(status_resp.get("redirect_host") or "").strip()
        if redirect_host:
            session.base_url = f"https://{redirect_host}"
        session.risk_flags = [flag for flag in session.risk_flags if flag != "user_scan_cancelled_or_wrong_qr"]
        if session.scanned_at <= 0:
            session.scanned_at = time.time()
        session.status = "scanned"
        session.message = "已扫码，正在等待微信确认。"
    elif raw_status == "expired":
        session.status = "qr_expired"
        session.message = "微信二维码已过期，请重新生成。"
    elif raw_status == "confirmed":
        try:
            credentials = _credentials_from_confirmed_status(status_resp)
            _save_weixin_credentials(credentials)
        except WeixinGatewayError as exc:
            session.status = "error"
            session.message = str(exc)
            session.risk_flags = _dedupe_flags([*session.risk_flags, "fake_login_incomplete_credentials"])
        else:
            _active_login = None
    else:
        session.status = "error"
        session.message = "微信返回了未知状态，请重新扫码。"

    status = weixin_status()
    return {"ok": bool(status["connected"] or status["status"] in {"qr_pending", "scanned"}), **status}


def disconnect_weixin() -> dict[str, Any]:
    global _active_login
    _bump_login_generation()
    _active_login = None
    _clear_connection_state()
    status = weixin_status()
    return {"ok": True, **status, "message": "微信连接已清理。需要使用时请重新扫码。"}


def parse_weixin_command(text: str) -> dict[str, Any]:
    raw_text = text.strip()
    if not raw_text:
        return {
            "ok": False,
            "kind": "empty",
            "message": "微信命令不能为空。",
        }
    if not raw_text.startswith("/"):
        return {
            "ok": True,
            "kind": "chat_message",
            "message": "准备作为微信私聊消息处理。",
        }

    command, _, raw_argument = raw_text.partition(" ")
    command = command.lower()
    argument = raw_argument.strip()

    if command == "/help":
        return {
            "ok": True,
            "kind": "help",
            "message": "可用命令：/help、/mode <模式>。也可以直接用自然语言告诉我想要的回答风格。",
        }
    if command == "/mode":
        if not argument:
            return {
                "ok": True,
                "kind": "list_modes",
                "message": "请使用 /mode <模式> 切换输出风格。",
            }
        return {
            "ok": True,
            "kind": "select_mode",
            "mode": argument.split()[0],
            "message": "准备切换输出风格。",
        }
    if command in {"/approve", "/reject"}:
        if not argument:
            return {
                "ok": False,
                "kind": "approval_decision",
                "message": f"请提供审批编号，例如 {command} approval_xxx。",
            }
        return {
            "ok": True,
            "kind": "approval_decision",
            "approval_id": argument.split()[0],
            "decision": "approved" if command == "/approve" else "rejected",
            "message": "准备处理安全审批。",
        }

    return {
        "ok": False,
        "kind": "unknown_command",
        "message": slash_command_hint(),
    }


def _weixin_route_from_event(event: Any) -> dict[str, str]:
    source = getattr(event, "source", None)
    account_id = str(
        getattr(source, "account_id", "")
        or getattr(source, "accountId", "")
        or getattr(event, "account_id", "")
        or getattr(event, "accountId", "")
        or "",
    ).strip()
    chat_id = str(getattr(source, "chat_id", "") or getattr(event, "chat_id", "") or "").strip()
    user_id = str(getattr(source, "user_id", "") or getattr(event, "user_id", "") or "").strip()
    chat_type = str(getattr(source, "chat_type", "") or "dm").strip() or "dm"
    route: dict[str, str] = {"chat_type": chat_type}
    if account_id:
        route["account_id"] = account_id
    if chat_id:
        route["chat_id"] = chat_id
    if user_id:
        route["user_id"] = user_id
    return route


def _normalize_weixin_switch_text(text: str) -> str:
    return "".join(ch for ch in text.strip() if not ch.isspace() and ch not in "。.!！?？，,；;：:")


def _route_recent_conversations(
    route: dict[str, str] | None,
    paths: RuntimePaths,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if not route:
        return []
    return conversations.recent_weixin_conversations(route, paths=paths, limit=limit)


def _format_weixin_switch_menu(items: list[dict[str, Any]]) -> str:
    if not items:
        return "这个微信联系人还没有可切换的本地对话。"
    lines = ["最近的微信对话："]
    for index, conversation in enumerate(items, start=1):
        metadata = conversation.get("metadata") if isinstance(conversation.get("metadata"), dict) else {}
        marker = "（当前）" if metadata.get("weixin_route_active") else ""
        lines.append(f"{index}. {conversation.get('title') or '微信私聊'}{marker}")
    lines.append("回复编号即可切换。")
    return "\n".join(lines)


def _remember_weixin_switch_menu(route_key: str, items: list[dict[str, Any]]) -> None:
    _weixin_switch_menus[route_key] = {
        "conversation_ids": [str(item["id"]) for item in items],
        "created_at": time.time(),
    }


def _pending_weixin_switch_menu(route_key: str) -> list[str]:
    menu = _weixin_switch_menus.get(route_key)
    if not menu:
        return []
    if time.time() - float(menu.get("created_at") or 0) > WEIXIN_SWITCH_MENU_TTL_SECONDS:
        _weixin_switch_menus.pop(route_key, None)
        return []
    return [str(item) for item in menu.get("conversation_ids", []) if str(item).strip()]


def _weixin_switch_result(
    *,
    kind: str,
    message: str,
    conversation: dict[str, Any] | None = None,
    conversations_list: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "kind": kind,
        "message": message,
        "conversation": conversation,
        "conversations": conversations_list or [],
    }


def _maybe_handle_weixin_conversation_switch(
    text: str,
    *,
    route: dict[str, str] | None,
    paths: RuntimePaths,
) -> dict[str, Any] | None:
    route_key = conversations.weixin_route_key(route)
    if not route_key:
        return None

    normalized = _normalize_weixin_switch_text(text)
    if not normalized:
        return None

    pending_ids = _pending_weixin_switch_menu(route_key)
    if pending_ids and normalized.isdigit():
        index = int(normalized) - 1
        if index < 0 or index >= len(pending_ids):
            return _weixin_switch_result(kind="conversation_switch_error", message="没有这个编号，请重新发送“切换对话”。")
        conversation = conversations.set_weixin_conversation_active(pending_ids[index], paths=paths)
        _weixin_switch_menus.pop(route_key, None)
        if conversation is None:
            return _weixin_switch_result(kind="conversation_switch_error", message="这个对话已经不存在，请重新发送“切换对话”。")
        return _weixin_switch_result(
            kind="conversation_switch_selected",
            message=f"已切到：{conversation['title']}，之后微信消息会进入这个对话。",
            conversation=conversation,
        )

    if normalized in {"新开一个对话", "新开对话", "开新对话", "新建微信对话", "新建对话"}:
        conversation = conversations.create_weixin_conversation(route or {}, title="微信私聊 新对话", paths=paths)
        _weixin_switch_menus.pop(route_key, None)
        return _weixin_switch_result(
            kind="conversation_switch_new",
            message=f"已新开：{conversation['title']}，之后微信消息会进入这个对话。",
            conversation=conversation,
        )

    if normalized in {"切回上一个对话", "回到上一个对话", "上一个对话"}:
        active = conversations.active_weixin_conversation(route or {}, paths=paths)
        for conversation in _route_recent_conversations(route, paths, limit=8):
            if active and conversation["id"] == active["id"]:
                continue
            updated = conversations.set_weixin_conversation_active(conversation["id"], paths=paths)
            if updated is not None:
                _weixin_switch_menus.pop(route_key, None)
                return _weixin_switch_result(
                    kind="conversation_switch_previous",
                    message=f"已切回：{updated['title']}，之后微信消息会进入这个对话。",
                    conversation=updated,
                )
        return _weixin_switch_result(kind="conversation_switch_error", message="没有找到上一个可切换的微信对话。")

    if normalized in {"切换对话", "最近对话", "切换本地对话", "选择对话"}:
        items = _route_recent_conversations(route, paths, limit=5)
        _remember_weixin_switch_menu(route_key, items)
        return _weixin_switch_result(
            kind="conversation_switch_menu",
            message=_format_weixin_switch_menu(items),
            conversations_list=items,
        )

    return None


def _store_weixin_reply(
    text: str,
    metadata: dict[str, Any] | None = None,
    paths: RuntimePaths | None = None,
    *,
    conversation_id: str = conversations.PERSONAL_CONVERSATION_ID,
) -> dict[str, Any]:
    return conversations.create_message(
        conversation_id=conversation_id,
        source="weixin",
        role="assistant",
        text=text,
        status="sent",
        metadata=metadata or {},
        paths=paths,
    )


def _finish_weixin_reply(
    text: str,
    metadata: dict[str, Any] | None = None,
    paths: RuntimePaths | None = None,
    *,
    conversation_id: str = conversations.PERSONAL_CONVERSATION_ID,
    reply_message_id: str | None = None,
    status: str = "sent",
) -> dict[str, Any] | None:
    if reply_message_id:
        return conversations.update_message(
            reply_message_id,
            text=text,
            status=status,
            metadata_patch=metadata or {},
            paths=paths,
        )
    return _store_weixin_reply(text, metadata, paths, conversation_id=conversation_id)


def _mark_weixin_control_message(
    message_id: str | None,
    *,
    kind: str,
    paths: RuntimePaths | None = None,
) -> None:
    if not message_id:
        return
    conversations.update_message(
        message_id,
        metadata_patch={"kind": kind, "control_event": True},
        paths=paths,
    )


def _weixin_reply_cancelled() -> dict[str, Any]:
    return {
        "ok": False,
        "suppressed": True,
        "message": "",
        "error_code": "conversation_deleted",
    }


def _chat_prompt_with_attachments(text: str, attachments: list[dict[str, Any]]) -> str:
    base = text.strip() or "用户发来了附件，请根据附件处理结果回复。"
    summaries = attachment_summaries_for_prompt(attachments)
    prompt = f"{base}\n\n以下是用户发来的附件处理结果：\n{summaries}" if summaries else base
    conversation_id = str(attachments[0].get("conversation_id") or conversations.PERSONAL_CONVERSATION_ID) if attachments else conversations.PERSONAL_CONVERSATION_ID
    return add_delivery_context_to_prompt(prompt, attachments=attachments, conversation_id=conversation_id)


async def _handle_weixin_after_store(
    text: str,
    *,
    conversation_id: str = conversations.PERSONAL_CONVERSATION_ID,
    current_message_id: str | None = None,
    reply_message_id: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
    route: dict[str, str] | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    from .agent_runner import send_agent_message
    from .modes import load_mode_profiles, select_mode
    from .safety import ApprovalNotFoundError, decide_approval

    runtime_paths = paths or ensure_runtime_dirs()
    attachments = attachments or []
    if text.strip() and not attachments:
        clarify_result = submit_clarify_answer(
            conversation_id,
            text,
            message_id=current_message_id,
            paths=runtime_paths,
        )
        if clarify_result is not None:
            return {
                "ok": True,
                "intent": {"kind": "clarify_answer"},
                "message": "已收到，我继续处理。",
                "assistant_message": clarify_result.get("assistant_message"),
            }

    switch_intent = _maybe_handle_weixin_conversation_switch(text, route=route, paths=runtime_paths)
    if switch_intent is not None:
        reply = _finish_weixin_reply(
            switch_intent["message"],
            {"kind": switch_intent["kind"]},
            runtime_paths,
            conversation_id=conversation_id,
            reply_message_id=reply_message_id,
        )
        if reply is None:
            return _weixin_reply_cancelled()
        return {
            "ok": True,
            "intent": {"kind": switch_intent["kind"]},
            "message": switch_intent["message"],
            "conversation": switch_intent.get("conversation"),
            "conversations": switch_intent.get("conversations") or [],
        }

    mode_intent = await apply_mode_intent(text, runtime_paths, conversation_id=conversation_id, scope="conversation")
    if mode_intent is not None:
        _mark_weixin_control_message(current_message_id, kind="mode_intent_user", paths=runtime_paths)
        reply = _finish_weixin_reply(
            mode_intent["message"],
            {"kind": "mode_intent", "changed": mode_intent["changed"], "control_event": True},
            runtime_paths,
            conversation_id=conversation_id,
            reply_message_id=reply_message_id,
        )
        if reply is None:
            return _weixin_reply_cancelled()
        return mode_intent

    intent = {"ok": True, "kind": "chat_message", "message": "准备作为微信私聊消息处理。"} if attachments and not text.strip() else parse_weixin_command(text)
    if not intent.get("ok"):
        reply = _finish_weixin_reply(
            intent["message"],
            {"kind": intent.get("kind", "unknown_command")},
            runtime_paths,
            conversation_id=conversation_id,
            reply_message_id=reply_message_id,
        )
        if reply is None:
            return _weixin_reply_cancelled()
        return {"ok": False, "intent": intent, "message": intent["message"]}

    kind = intent.get("kind")
    if kind == "help":
        reply = _finish_weixin_reply(
            intent["message"],
            {"kind": "help"},
            runtime_paths,
            conversation_id=conversation_id,
            reply_message_id=reply_message_id,
        )
        if reply is None:
            return _weixin_reply_cancelled()
        return {"ok": True, "intent": intent, "message": intent["message"], "commands": weixin_commands()["commands"]}
    if kind == "list_modes":
        _mark_weixin_control_message(current_message_id, kind="list_modes_user", paths=runtime_paths)
        reply = _finish_weixin_reply(
            intent["message"],
            {"kind": "list_modes"},
            runtime_paths,
            conversation_id=conversation_id,
            reply_message_id=reply_message_id,
        )
        if reply is None:
            return _weixin_reply_cancelled()
        return {"ok": True, "intent": intent, "message": intent["message"], "modes": load_mode_profiles()}
    if kind == "select_mode":
        _mark_weixin_control_message(current_message_id, kind="select_mode_user", paths=runtime_paths)
        try:
            result = select_mode(str(intent["mode"]), runtime_paths, conversation_id=conversation_id, scope="conversation")
        except ValueError as exc:
            reply = _finish_weixin_reply(
                str(exc),
                {"kind": "select_mode_error", "control_event": True},
                runtime_paths,
                conversation_id=conversation_id,
                reply_message_id=reply_message_id,
                status="error",
            )
            if reply is None:
                return _weixin_reply_cancelled()
            return {"ok": False, "intent": intent, "message": str(exc)}
        message = "输出风格已切换。"
        reply = _finish_weixin_reply(
            message,
            {"kind": "select_mode", "mode": result.get("current"), "control_event": True},
            runtime_paths,
            conversation_id=conversation_id,
            reply_message_id=reply_message_id,
        )
        if reply is None:
            return _weixin_reply_cancelled()
        return {"ok": True, "intent": intent, "message": message, "mode": result}
    if kind == "approval_decision":
        try:
            result = decide_approval(str(intent["approval_id"]), str(intent["decision"]))
        except ApprovalNotFoundError as exc:
            reply = _finish_weixin_reply(
                str(exc),
                {"kind": "approval_error"},
                runtime_paths,
                conversation_id=conversation_id,
                reply_message_id=reply_message_id,
                status="error",
            )
            if reply is None:
                return _weixin_reply_cancelled()
            return {"ok": False, "intent": intent, "message": str(exc)}
        except ValueError as exc:
            reply = _finish_weixin_reply(
                str(exc),
                {"kind": "approval_error"},
                runtime_paths,
                conversation_id=conversation_id,
                reply_message_id=reply_message_id,
                status="error",
            )
            if reply is None:
                return _weixin_reply_cancelled()
            return {"ok": False, "intent": intent, "message": str(exc)}
        if result["approval"]["status"] == "approved":
            from .weixin_runtime import send_approved_weixin_action

            delivery = await send_approved_weixin_action(result["approval"])
            result["delivery"] = delivery
            if not delivery.get("ok"):
                result["message"] = delivery.get("message") or result["message"]
        reply = _finish_weixin_reply(
            result["message"],
            {"kind": "approval_decision", "approval_id": intent["approval_id"]},
            runtime_paths,
            conversation_id=conversation_id,
            reply_message_id=reply_message_id,
            status="sent" if result.get("ok", True) else "error",
        )
        if reply is None:
            return _weixin_reply_cancelled()
        return {"ok": True, "intent": intent, "message": result["message"], "approval": result["approval"]}
    if kind == "chat_message":
        if not attachments:
            result = await turn_coalescer.enqueue_text_turn(
                key=turn_coalescer.key_for_weixin(route, conversation_id),
                conversation_id=conversation_id,
                text=text,
                current_message_id=current_message_id,
                assistant_source="weixin",
                paths=runtime_paths,
                route=route,
                wait_for_reply=True,
            )
            if result.get("cancelled"):
                return _weixin_reply_cancelled()
            result["intent"] = intent
            return result

        assistant_placeholder = conversations.create_message(
            conversation_id=conversation_id,
            source="weixin",
            role="assistant",
            text="正在回复...",
            status="generating",
            metadata={
                "kind": "weixin_reply_pending",
                "in_reply_to": current_message_id,
                "weixin_route": route,
            },
            paths=runtime_paths,
        )
        reply_message_id = assistant_placeholder["id"]
        prompt_text = _chat_prompt_with_attachments(text, attachments)
        result = await send_agent_message(
            prompt_text,
            conversation_id,
            runtime_paths,
            current_message_id=current_message_id,
            host_message_id=reply_message_id,
            route=route,
            require_existing_conversation=True,
        )
        if result.get("cancelled"):
            return _weixin_reply_cancelled()
        if not result.get("ok"):
            reply = _finish_weixin_reply(
                result.get("message", "微信私聊暂时不能回复。"),
                {
                    "kind": "chat_error",
                    "error_code": result.get("error_code"),
                    "generation_execution": result.get("generation_execution"),
                },
                runtime_paths,
                conversation_id=conversation_id,
                reply_message_id=reply_message_id,
                status="error",
            )
            if reply is None:
                return _weixin_reply_cancelled()
            return {"ok": False, "intent": intent, "message": result.get("message", "微信私聊暂时不能回复。"), "chat": result}
        if conversations.get_conversation(conversation_id, runtime_paths) is None:
            return _weixin_reply_cancelled()
        prepared = prepare_assistant_delivery(
            str(result.get("reply") or ""),
            conversation_id=conversation_id,
            paths=runtime_paths,
            delivery_actions=result.get("delivery_actions") if isinstance(result.get("delivery_actions"), list) else [],
            include_outbound_media=True,
        )
        reply = _finish_weixin_reply(
            prepared.visible_text,
            {
                "kind": "chat_reply",
                "engine": result.get("engine"),
                "provider": result.get("provider"),
                "model": result.get("model"),
                "generation_execution": result.get("generation_execution"),
                "delivery": prepared.metadata(),
                "source_message_ids": [current_message_id],
                "source_message_count": 1,
                "visible_reply": prepared.visible_text,
            },
            runtime_paths,
            conversation_id=conversation_id,
            reply_message_id=reply_message_id,
        )
        if reply is None:
            return _weixin_reply_cancelled()
        try:
            register_prepared_delivery(
                prepared,
                message_id=reply_message_id,
                conversation_id=conversation_id,
                source="assistant_delivery",
                paths=runtime_paths,
            )
        except AttachmentError:
            reply = conversations.update_message(
                reply_message_id,
                metadata_patch={
                    "delivery": {
                        "status": "rejected",
                        "delivered_count": 0,
                        "rejected_count": max(1, prepared.rejected_count),
                        "reason_code": "unsafe_path",
                    }
                },
                paths=runtime_paths,
            ) or reply
            prepared.outbound_text = prepared.visible_text
            prepared.media_paths = []
            prepared.media_items = []
        reply = conversations.get_message(reply_message_id, paths=runtime_paths) or reply
        next_chat = {
            **result,
            "reply": prepared.visible_text,
            "visible_reply": prepared.visible_text,
            "_delivery_media": list(prepared.media_items),
            "_delivery_media_paths": list(prepared.media_paths),
        }
        next_chat.pop("delivery_actions", None)
        return {
            "ok": True,
            "intent": intent,
            "message": "微信私聊回复已生成。",
            "assistant_message": reply,
            "chat": next_chat,
        }

    return {"ok": False, "intent": intent, "message": "这个微信命令暂时不能处理。"}


async def handle_weixin_message_event(event: Any, paths: RuntimePaths | None = None) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    text = str(getattr(event, "text", "") or "").strip()
    media_urls = [str(item) for item in (getattr(event, "media_urls", None) or []) if str(item).strip()]
    media_types = [str(item) for item in (getattr(event, "media_types", None) or []) if str(item).strip()]
    route = _weixin_route_from_event(event)
    if conversations.weixin_route_key(route):
        active_conversation = conversations.ensure_active_weixin_conversation(route, paths=runtime_paths)
        conversation_id = active_conversation["id"]
    else:
        conversation_id = conversations.PERSONAL_CONVERSATION_ID

    user_message = conversations.create_message(
        conversation_id=conversation_id,
        source="weixin",
        role="user",
        text=text or "（收到附件）",
        status="received",
        metadata={
            "message_id": str(getattr(event, "message_id", "") or ""),
            "media_count": len(media_urls),
            "weixin_route": route,
        },
        emit_event=False,
        paths=runtime_paths,
    )
    attachments: list[dict[str, Any]] = []
    if media_urls:
        try:
            attachments = register_message_attachments(
                message_id=user_message["id"],
                conversation_id=user_message["conversation_id"],
                media_urls=media_urls,
                media_types=media_types,
                paths=runtime_paths,
            )
            attachments = await recognize_image_attachments(attachments, paths=runtime_paths)
        except AttachmentError as exc:
            conversations.create_system_message(
                str(exc),
                conversation_id=conversation_id,
                metadata={"kind": "attachment_error", "message_id": user_message["id"]},
                paths=runtime_paths,
            )
    conversations.record_message_event(user_message["id"], paths=runtime_paths)
    return await _handle_weixin_after_store(
        text,
        conversation_id=conversation_id,
        current_message_id=user_message["id"],
        reply_message_id=None,
        attachments=attachments,
        route=route,
        paths=runtime_paths,
    )


async def handle_weixin_command_text(text: str) -> dict[str, Any]:
    class TextOnlyEvent:
        media_urls: list[str] = []
        media_types: list[str] = []
        message_id = None

        def __init__(self, value: str) -> None:
            self.text = value

    return await handle_weixin_message_event(TextOnlyEvent(text))


def request_weixin_send_approval(
    recipient: str,
    message: str,
    attachment_ids: list[str] | None = None,
) -> dict[str, Any]:
    from .safety import request_safety_approval

    recipient_value = recipient.strip()
    message_value = message.strip()
    if not recipient_value:
        raise ValueError("微信联系人不能为空。")
    if not message_value:
        raise ValueError("微信消息不能为空。")

    preview = message_value[:80]
    if len(message_value) > 80:
        preview = f"{preview}..."

    approval_result = request_safety_approval(
        "send_weixin_message",
        f"发送微信消息给 {recipient_value}",
        {
            "recipient": recipient_value,
            "message": message_value,
            "message_preview": preview,
            "message_length": len(message_value),
            "attachment_ids": attachment_ids or [],
        },
        "weixin",
    )
    return {
        "ok": False,
        "gateway": "weixin",
        "status": "approval_required" if approval_result.get("approval_required") else "unavailable",
        "approval_required": bool(approval_result.get("approval_required")),
        "approval": approval_result.get("approval"),
        "message": "微信发送需要安全审批，通过后才会发送。",
    }


async def send_weixin_message_direct(
    recipient: str,
    message: str,
    attachment_ids: list[str] | None = None,
) -> dict[str, Any]:
    recipient_value = recipient.strip()
    message_value = message.strip()
    if not recipient_value:
        raise ValueError("微信联系人不能为空。")
    if not message_value and not attachment_ids:
        raise ValueError("微信消息或附件不能为空。")

    from .weixin_runtime import send_weixin_message_now

    delivery = await send_weixin_message_now(recipient_value, message_value, attachment_ids or [])
    return {
        "ok": bool(delivery.get("ok")),
        "gateway": "weixin",
        "status": "sent" if delivery.get("ok") else "failed",
        "approval_required": False,
        "approval": None,
        "delivery": delivery,
        "message": str(delivery.get("message") or ("微信发送已完成。" if delivery.get("ok") else "微信发送失败。")),
    }
