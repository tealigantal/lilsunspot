from __future__ import annotations

import json
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
import base64

from .config_paths import RuntimePaths, ensure_runtime_dirs
from .safety import request_safety_approval


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
    {
        "name": "/approve",
        "enabled": True,
        "description": "批准安全审批请求，例如 /approve approval_xxx。",
        "approval_required": False,
    },
    {
        "name": "/reject",
        "enabled": True,
        "description": "拒绝安全审批请求，例如 /reject approval_xxx。",
        "approval_required": False,
    },
]

WEIXIN_STATE_FILE_NAME = "weixin-state.json"
WEIXIN_LOGIN_TIMEOUT_SECONDS = 480
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
    started_at: float
    expires_at: float
    message: str


_active_login: WeixinLoginSession | None = None


class WeixinGatewayError(RuntimeError):
    """User-visible Weixin gateway failure with plain Chinese text."""


def default_weixin_bot_profile() -> dict[str, str]:
    return {
        "nickname": WEIXIN_DEFAULT_BOT_NICKNAME,
        "avatar_asset": WEIXIN_DEFAULT_BOT_AVATAR_ASSET,
        "avatar_alt": "小黑子头像",
    }


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
            timeout_ms=hermes_weixin.QR_TIMEOUT_MS,
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
    return {
        "status": session.status,
        "qr_payload": qr_payload,
        "qr_payload_kind": "url" if session.qr_payload.startswith(("http://", "https://")) else "text",
        "qr_image_data_url": _make_qr_image_data_url(qr_payload) if qr_payload else "",
        "expires_at": int(session.expires_at),
        "message": session.message,
    }


def weixin_status() -> dict[str, Any]:
    connection = _load_connection_state()
    available = _weixin_requirements_available()
    active_login = _active_login
    if active_login and active_login.status in {"qr_pending", "scanned", "qr_expired", "error"}:
        status = active_login.status
        connected = False
        message = active_login.message
        login = _redacted_login_payload(active_login)
    elif connection.get("configured"):
        status = "connected"
        connected = True
        message = "微信已扫码连接；请用真实私聊发送 /help 或 /mode 做人工验收。"
        login = None
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
        "commands_available": True,
        "bot_profile": default_weixin_bot_profile(),
        "login": login,
        "capabilities": {
            "qr_login": available,
            "private_chat": connected,
            "commands": True,
            "active_send_requires_approval": True,
            "official_payment_or_materials_required": False,
        },
        "message": message,
    }


def weixin_commands() -> dict[str, Any]:
    return {
        "gateway": "weixin",
        "commands": WEIXIN_COMMANDS,
        "message": "这些命令可用于微信私聊入口；主动发送微信消息仍需要安全审批。",
    }


async def start_weixin_login() -> dict[str, Any]:
    global _active_login
    if not _weixin_requirements_available():
        raise WeixinGatewayError("微信网关缺少运行组件，请重新安装小黑子。")
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

    now = time.time()
    _active_login = WeixinLoginSession(
        qrcode=qrcode,
        qr_payload=qr_payload,
        base_url=WEIXIN_ILINK_BASE_URL,
        status="qr_pending",
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
        session.status = "error"
        session.message = "微信扫码状态读取失败，请稍后再试。"
        status = weixin_status()
        return {"ok": False, **status}

    raw_status = str(status_resp.get("status") or "wait").strip()
    if raw_status == "wait":
        session.status = "qr_pending"
        session.message = "请使用手机微信扫码，并在手机上确认登录。"
    elif raw_status == "scaned":
        session.status = "scanned"
        session.message = "已扫码，请在手机微信里确认登录。"
    elif raw_status == "scaned_but_redirect":
        redirect_host = str(status_resp.get("redirect_host") or "").strip()
        if redirect_host:
            session.base_url = f"https://{redirect_host}"
        session.status = "scanned"
        session.message = "已扫码，正在等待微信确认。"
    elif raw_status == "expired":
        session.status = "qr_expired"
        session.message = "微信二维码已过期，请重新生成。"
    elif raw_status == "confirmed":
        credentials = {
            "account_id": status_resp.get("ilink_bot_id"),
            "token": status_resp.get("bot_token"),
            "base_url": status_resp.get("baseurl") or WEIXIN_ILINK_BASE_URL,
            "user_id": status_resp.get("ilink_user_id"),
        }
        try:
            _save_weixin_credentials(credentials)
        except WeixinGatewayError as exc:
            session.status = "error"
            session.message = str(exc)
        else:
            _active_login = None
    else:
        session.status = "error"
        session.message = "微信返回了未知状态，请重新扫码。"

    status = weixin_status()
    return {"ok": bool(status["connected"] or status["status"] in {"qr_pending", "scanned"}), **status}


def disconnect_weixin() -> dict[str, Any]:
    global _active_login
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
            "message": "可用命令：/help、/mode <模式>、/approve <审批编号>、/reject <审批编号>。",
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
        "message": "没有识别这个微信命令。请发送 /help 查看可用命令。",
    }


async def handle_weixin_command_text(text: str) -> dict[str, Any]:
    from .chat_client import send_chat_message
    from .modes import load_mode_profiles, select_mode
    from .safety import ApprovalNotFoundError, decide_approval

    intent = parse_weixin_command(text)
    if not intent.get("ok"):
        return {"ok": False, "intent": intent, "message": intent["message"]}

    kind = intent.get("kind")
    if kind == "help":
        return {"ok": True, "intent": intent, "message": intent["message"], "commands": weixin_commands()["commands"]}
    if kind == "list_modes":
        return {"ok": True, "intent": intent, "message": intent["message"], "modes": load_mode_profiles()}
    if kind == "select_mode":
        try:
            result = select_mode(str(intent["mode"]))
        except ValueError as exc:
            return {"ok": False, "intent": intent, "message": str(exc)}
        return {"ok": True, "intent": intent, "message": "输出风格已切换。", "mode": result}
    if kind == "approval_decision":
        try:
            result = decide_approval(str(intent["approval_id"]), str(intent["decision"]))
        except ApprovalNotFoundError as exc:
            return {"ok": False, "intent": intent, "message": str(exc)}
        except ValueError as exc:
            return {"ok": False, "intent": intent, "message": str(exc)}
        return {"ok": True, "intent": intent, "message": result["message"], "approval": result["approval"]}
    if kind == "chat_message":
        result = await send_chat_message(text)
        if not result.get("ok"):
            return {"ok": False, "intent": intent, "message": result.get("message", "微信私聊暂时不能回复。"), "chat": result}
        return {"ok": True, "intent": intent, "message": "微信私聊回复已生成。", "chat": result}

    return {"ok": False, "intent": intent, "message": "这个微信命令暂时不能处理。"}


def request_weixin_send_approval(recipient: str, message: str) -> dict[str, Any]:
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
            "message_preview": preview,
            "message_length": len(message_value),
        },
        "weixin",
    )
    return {
        "ok": False,
        "gateway": "weixin",
        "status": "approval_required" if approval_result.get("approval_required") else "unavailable",
        "approval_required": bool(approval_result.get("approval_required")),
        "approval": approval_result.get("approval"),
        "message": "微信发送需要安全审批，当前版本不会直接发送消息。",
    }
