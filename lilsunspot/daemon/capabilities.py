from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from .capability_graph import build_capability_graph
from .chat_client import current_runtime_model
from .config_paths import RuntimePaths, ensure_runtime_dirs
from .hermes_runtime import read_hermes_config, write_hermes_config
from .upstream_audit import safe_upstream_capability_audit


LILSUNSPOT_PLATFORM = "lilsunspot"
DEFAULT_LILSUNSPOT_TOOLSETS = [
    "web",
    "vision",
    "terminal",
    "file",
    "todo",
    "memory",
    "session_search",
    "skills",
    "clarify",
]
REQUIRED_LILSUNSPOT_TOOLSETS = {"file"}
MODEL_CONFIG_KEYS = [
    "fallback_providers",
    "provider_routing",
    "auxiliary",
    "compression",
    "context",
    "curator",
]
SECURITY_TOOLSETS = {
    "terminal",
    "file",
    "code_execution",
    "browser",
    "computer_use",
    "cronjob",
    "messaging",
    "homeassistant",
    "spotify",
    "discord_admin",
    "skills",
}
MEDIUM_RISK_TOOLSETS = {
    "web",
    "search",
    "x_search",
    "vision",
    "video",
    "image_gen",
    "video_gen",
    "tts",
    "moa",
    "delegation",
    "session_search",
    "discord",
    "yuanbao",
}
WINDOWS_UNSUPPORTED_TOOLSETS = {"computer_use"}
THIRD_PARTY_ENV_HINTS = {
    "vision": ["Hermes vision backend：主模型原生视觉，或 auxiliary.vision 辅助视觉 provider"],
    "x_search": ["XAI_API_KEY 或 xAI OAuth"],
    "image_gen": ["图像生成 provider 凭据"],
    "video_gen": ["视频生成 provider 凭据"],
    "browser": ["agent-browser/Chromium 或云浏览器凭据"],
    "homeassistant": ["HASS_TOKEN"],
    "spotify": ["Spotify OAuth 配置"],
    "discord": ["Discord bot token"],
    "discord_admin": ["Discord bot token 和管理员权限"],
    "yuanbao": ["Yuanbao 凭据"],
}
TOOLSET_NAMES_CN = {
    "web": "网页搜索与抓取",
    "search": "网页搜索",
    "x_search": "X 搜索",
    "browser": "浏览器自动化",
    "terminal": "终端和进程",
    "file": "文件读写",
    "code_execution": "代码执行",
    "vision": "图片理解",
    "video": "视频理解",
    "image_gen": "图像生成",
    "video_gen": "视频生成",
    "moa": "多模型协作",
    "tts": "文字转语音",
    "skills": "技能",
    "todo": "任务清单",
    "memory": "长期记忆",
    "context_engine": "上下文引擎",
    "session_search": "历史会话搜索",
    "clarify": "澄清问题",
    "delegation": "子代理委托",
    "cronjob": "定时任务",
    "messaging": "跨平台消息",
    "homeassistant": "Home Assistant",
    "spotify": "Spotify",
    "discord": "Discord",
    "discord_admin": "Discord 管理",
    "yuanbao": "元宝",
    "computer_use": "桌面控制",
}
CATEGORY_NAMES = {
    "model": "模型",
    "tool": "工具",
    "automation": "自动化",
    "memory": "记忆与会话",
    "integration": "集成",
    "runtime": "运行",
    "security": "安全",
}
_CAPABILITY_PROMPT_CACHE: dict[tuple[Any, ...], str] = {}


class CapabilityError(ValueError):
    pass


def _safe_import_toolsets() -> tuple[dict[str, Any], list[tuple[str, str, str]]]:
    try:
        from toolsets import TOOLSETS
    except Exception:
        TOOLSETS = {}
    try:
        from hermes_cli.tools_config import CONFIGURABLE_TOOLSETS
    except Exception:
        CONFIGURABLE_TOOLSETS = []
    return TOOLSETS if isinstance(TOOLSETS, dict) else {}, list(CONFIGURABLE_TOOLSETS)


def _default_config() -> dict[str, Any]:
    try:
        from hermes_cli.config import DEFAULT_CONFIG

        return DEFAULT_CONFIG if isinstance(DEFAULT_CONFIG, dict) else {}
    except Exception:
        return {}


def _prepare_hermes_runtime_env(paths: RuntimePaths) -> None:
    paths.hermes_home.mkdir(parents=True, exist_ok=True)
    os.environ["HERMES_HOME"] = str(paths.hermes_home)
    try:
        from hermes_cli.env_loader import load_hermes_dotenv

        load_hermes_dotenv(
            hermes_home=paths.hermes_home,
            project_env=Path(__file__).resolve().parents[2] / ".env",
        )
    except Exception:
        pass


def _now_platform_is_windows() -> bool:
    return sys.platform == "win32"


def _toolset_category(toolset: str) -> str:
    if toolset in {"cronjob", "hermes-cron"}:
        return "automation"
    if toolset in {"memory", "session_search", "todo"}:
        return "memory"
    if (
        toolset in {"homeassistant", "spotify", "discord", "discord_admin", "yuanbao", "messaging"}
        or toolset.startswith("hermes-")
        or toolset.startswith("feishu_")
    ):
        return "integration"
    return "tool"


def _risk_for_toolset(toolset: str) -> str:
    if toolset.startswith("hermes-") and toolset not in {"hermes-cli", "hermes-api-server"}:
        return "high"
    if toolset.startswith("feishu_"):
        return "high"
    if toolset in SECURITY_TOOLSETS:
        return "high"
    if toolset in MEDIUM_RISK_TOOLSETS:
        return "medium"
    return "low"


def _status(enabled: bool, available: bool, reason: str) -> str:
    if enabled and available:
        return "enabled"
    if enabled and not available:
        return "blocked"
    if reason == "unsupported":
        return "unsupported"
    if reason == "needs_config":
        return "needs_config"
    if reason == "not_implemented":
        return "disabled"
    return "disabled"


def _status_text(enabled: bool, available: bool, reason: str) -> str:
    if enabled and available:
        return "已接入并启用。"
    if enabled and not available:
        return "已启用，但当前环境还缺少依赖或账号配置。"
    if reason == "unsupported":
        return "当前 Windows 安装版暂不支持。"
    if reason == "needs_config":
        return "能力已接入，需要先配置第三方账号或依赖。"
    if reason == "not_implemented":
        return "当前安装版还没有接入这个入口。"
    return "已接入，当前未启用。"


def _platform_toolsets(config: dict[str, Any]) -> list[str]:
    platform_toolsets = config.get("platform_toolsets") if isinstance(config.get("platform_toolsets"), dict) else {}
    raw = platform_toolsets.get(LILSUNSPOT_PLATFORM)
    if not isinstance(raw, list):
        return list(DEFAULT_LILSUNSPOT_TOOLSETS)
    toolsets = [str(item) for item in raw]
    for toolset in REQUIRED_LILSUNSPOT_TOOLSETS:
        if toolset not in toolsets:
            toolsets.append(toolset)
    return toolsets


def enabled_toolsets_for_agent(paths: RuntimePaths | None = None) -> list[str]:
    config = read_hermes_config(paths)
    return [item for item in _platform_toolsets(config) if item != "no_mcp"]


def fallback_chain_for_agent(paths: RuntimePaths | None = None) -> list[dict[str, Any]]:
    config = read_hermes_config(paths)
    raw = config.get("fallback_providers")
    if not isinstance(raw, list):
        return []
    return [
        item
        for item in raw
        if isinstance(item, dict) and str(item.get("provider") or "").strip() and str(item.get("model") or "").strip()
    ]


def _toolset_available(toolset: str, repo_root: Path, config: dict[str, Any]) -> tuple[bool, str, list[str]]:
    dependencies = list(THIRD_PARTY_ENV_HINTS.get(toolset, []))
    if _now_platform_is_windows() and toolset in WINDOWS_UNSUPPORTED_TOOLSETS:
        return False, "unsupported", dependencies
    try:
        from hermes_cli.tools_config import _toolset_needs_configuration_prompt

        if _toolset_needs_configuration_prompt(toolset, config):
            return False, "needs_config", dependencies
        return True, "", dependencies
    except Exception:
        pass
    if toolset == "browser":
        if (repo_root / "node_modules" / "agent-browser").exists() or shutil.which("agent-browser") or os.getenv("BROWSERBASE_API_KEY"):
            return True, "", dependencies
        return False, "needs_config", dependencies
    if toolset == "x_search" and not (os.getenv("XAI_API_KEY") or os.getenv("XAI_OAUTH_TOKEN")):
        return False, "needs_config", dependencies
    if toolset == "homeassistant" and not os.getenv("HASS_TOKEN"):
        return False, "needs_config", dependencies
    if toolset in {"spotify", "discord", "discord_admin", "yuanbao", "image_gen", "video_gen"}:
        return False, "needs_config", dependencies
    if toolset.startswith("hermes-") and toolset not in {"hermes-cli", "hermes-api-server"}:
        return False, "needs_config", dependencies or ["对应 Hermes 平台账号或 gateway 配置"]
    if toolset.startswith("feishu_"):
        return False, "needs_config", dependencies or ["飞书账号或应用凭据"]
    return True, "", dependencies


def _toolset_tools(toolsets: dict[str, Any], toolset_id: str) -> list[str]:
    value = toolsets.get(toolset_id)
    if isinstance(value, dict):
        return list(value.get("tools") or [])
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _toolset_description(toolsets: dict[str, Any], toolset_id: str) -> str:
    value = toolsets.get(toolset_id)
    if isinstance(value, dict):
        return str(value.get("description") or "")
    return ""


def _capability(
    *,
    capability_id: str,
    category: str,
    name: str,
    description: str,
    enabled: bool,
    available: bool = True,
    reason: str = "",
    risk: str = "low",
    dependencies: list[str] | None = None,
    config_keys: list[str] | None = None,
    tools: list[str] | None = None,
    source: str = "lilsunspot",
    source_of_truth: str = "",
    configurable: bool = True,
    registered: bool = True,
    configured: bool | None = None,
    executable: bool | None = None,
    verified: bool = False,
    last_verified_at: str = "",
) -> dict[str, Any]:
    configured_value = bool(enabled) if configured is None else bool(configured)
    executable_value = bool(enabled and available) if executable is None else bool(executable)
    return {
        "id": capability_id,
        "category": category,
        "category_label": CATEGORY_NAMES.get(category, category),
        "name": name,
        "description": description,
        "enabled": bool(enabled),
        "available": bool(available),
        "status": _status(bool(enabled), bool(available), reason),
        "status_text": _status_text(bool(enabled), bool(available), reason),
        "risk": risk,
        "dependencies": dependencies or [],
        "config_keys": config_keys or [],
        "tools": tools or [],
        "source": source,
        "source_of_truth": source_of_truth or source,
        "configurable": bool(configurable),
        "registered": bool(registered),
        "configured": configured_value,
        "executable": executable_value,
        "verified": bool(verified),
        "last_verified_at": last_verified_at,
    }


def list_capabilities(paths: RuntimePaths | None = None, *, include_upstream_audit: bool = True) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    repo_root = Path(__file__).resolve().parents[2]
    _prepare_hermes_runtime_env(runtime_paths)
    config = read_hermes_config(runtime_paths)
    default_config = _default_config()
    enabled_toolsets = set(_platform_toolsets(config))
    toolsets, configurable = _safe_import_toolsets()
    capabilities: list[dict[str, Any]] = []

    runtime_model = config.get("model") if isinstance(config.get("model"), dict) else {}
    capabilities.append(
        _capability(
            capability_id="model.main",
            category="model",
            name="主聊天模型",
            description="Hermes agent loop 使用的主 provider/model。",
            enabled=bool(runtime_model.get("provider") and runtime_model.get("default")),
            risk="medium",
            config_keys=["model.provider", "model.default", "lilsunspot.provider", "lilsunspot.model"],
            source="hermes_config",
        )
    )
    capabilities.append(
        _capability(
            capability_id="model.fallbacks",
            category="model",
            name="备用模型链",
            description="主模型连接失败、限流或不可用时的 Hermes fallback_providers。",
            enabled=bool(config.get("fallback_providers")),
            risk="medium",
            config_keys=["fallback_providers"],
            source="hermes_config",
        )
    )
    capabilities.append(
        _capability(
            capability_id="model.routing",
            category="model",
            name="模型路由",
            description="按任务或 provider 策略路由模型请求。",
            enabled=bool(config.get("provider_routing")),
            risk="medium",
            config_keys=["provider_routing"],
            source="hermes_config",
        )
    )
    auxiliary_default = default_config.get("auxiliary") if isinstance(default_config.get("auxiliary"), dict) else {}
    auxiliary_config = config.get("auxiliary") if isinstance(config.get("auxiliary"), dict) else {}
    for task in sorted(auxiliary_default):
        task_cfg = auxiliary_config.get(task) if isinstance(auxiliary_config.get(task), dict) else {}
        provider = str(task_cfg.get("provider") or "").strip()
        model = str(task_cfg.get("model") or "").strip()
        capabilities.append(
            _capability(
                capability_id=f"model.auxiliary.{task}",
                category="model",
                name=f"辅助模型：{task}",
                description="Hermes 本地已有 auxiliary model 槽位。",
                enabled=bool(provider and provider != "auto" or model),
                risk="medium",
                config_keys=[f"auxiliary.{task}"],
                source="hermes_config",
            )
        )

    for key in MODEL_CONFIG_KEYS:
        if key == "auxiliary":
            continue
        capabilities.append(
            _capability(
                capability_id=f"model.config.{key}",
                category="model",
                name=f"模型配置：{key}",
                description="Hermes DEFAULT_CONFIG 中已有的模型/上下文配置块。",
                enabled=bool(config.get(key)),
                risk="medium",
                config_keys=[key],
                source="hermes_config",
            )
        )

    seen_toolsets: set[str] = set()
    for toolset, label, description in configurable:
        toolset_id = str(toolset)
        seen_toolsets.add(toolset_id)
        tools = _toolset_tools(toolsets, toolset_id)
        available, reason, dependencies = _toolset_available(toolset_id, repo_root, config)
        capabilities.append(
            _capability(
                capability_id=f"toolset.{toolset_id}",
                category=_toolset_category(toolset_id),
                name=TOOLSET_NAMES_CN.get(toolset_id, _strip_emoji(str(label)) or toolset_id),
                description=str(description or _toolset_description(toolsets, toolset_id)),
                enabled=toolset_id in enabled_toolsets,
                available=available,
                reason=reason,
                risk=_risk_for_toolset(toolset_id),
                dependencies=dependencies,
                config_keys=[f"platform_toolsets.{LILSUNSPOT_PLATFORM}"],
                tools=tools,
                source="hermes_toolset",
            )
        )

    for toolset_id in sorted(str(item) for item in toolsets if str(item) not in seen_toolsets):
        available, reason, dependencies = _toolset_available(toolset_id, repo_root, config)
        capabilities.append(
            _capability(
                capability_id=f"toolset.{toolset_id}",
                category=_toolset_category(toolset_id),
                name=TOOLSET_NAMES_CN.get(toolset_id, toolset_id),
                description=_toolset_description(toolsets, toolset_id) or "Hermes 本地已有 toolset，当前不在普通配置向导中。",
                enabled=toolset_id in enabled_toolsets,
                available=available,
                reason=reason,
                risk=_risk_for_toolset(toolset_id),
                dependencies=dependencies,
                config_keys=[f"platform_toolsets.{LILSUNSPOT_PLATFORM}"],
                tools=_toolset_tools(toolsets, toolset_id),
                source="hermes_toolset",
                configurable=False,
            )
        )

    capabilities.extend(_runtime_capabilities(config, runtime_paths))
    result = {
        "capabilities": sorted(capabilities, key=lambda item: (item["category"], item["id"])),
        "platform": LILSUNSPOT_PLATFORM,
        "enabled_toolsets": sorted(enabled_toolsets),
        "default_toolsets": list(DEFAULT_LILSUNSPOT_TOOLSETS),
        "config_keys": MODEL_CONFIG_KEYS,
    }
    if include_upstream_audit:
        result["upstream_audit"] = safe_upstream_capability_audit(repo_root)
    return result


def _runtime_capabilities(config: dict[str, Any], paths: RuntimePaths) -> list[dict[str, Any]]:
    workflow_path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "lilsunspot-upstream-sync.yml"
    return [
        _capability(
            capability_id="integration.weixin",
            category="integration",
            name="微信网关",
            description="微信扫码、私聊同步、附件和审批发送。",
            enabled=True,
            risk="high",
            config_keys=["lilsunspot.weixin"],
            source="lilsunspot_gateway",
            source_of_truth="Hermes WeixinAdapter + lilsunspot gateway state",
            verified=False,
        ),
        _capability(
            capability_id="integration.mcp_servers",
            category="integration",
            name="MCP servers",
            description="Hermes mcp_servers 配置和 MCP 动态工具。",
            enabled=bool(config.get("mcp_servers")),
            risk="high",
            config_keys=["mcp_servers", f"platform_toolsets.{LILSUNSPOT_PLATFORM}"],
            source="hermes_config",
            source_of_truth="Hermes config.mcp_servers",
        ),
        _capability(
            capability_id="integration.plugins",
            category="integration",
            name="Hermes 插件",
            description="Hermes dashboard/plugin registry 已有的插件开关。",
            enabled=bool((config.get("plugins") or {}).get("enabled")) if isinstance(config.get("plugins"), dict) else False,
            risk="high",
            config_keys=["plugins.enabled", "plugins.disabled"],
            source="hermes_config",
            source_of_truth="Hermes plugin registry/config",
        ),
        _capability(
            capability_id="security.approvals",
            category="security",
            name="安全审批",
            description="危险命令、工具执行、微信发送和高风险配置变更审批。",
            enabled=True,
            risk="high",
            config_keys=["approvals", "command_allowlist"],
            source="hermes_approval",
            source_of_truth="Hermes tools.approval + lilsunspot audit",
            configurable=False,
        ),
        _capability(
            capability_id="security.audit",
            category="security",
            name="审计数据库",
            description="脱敏记录工具调用、审批、配置变化和诊断导出。",
            enabled=(paths.data_dir / "audit.db").exists(),
            risk="low",
            config_keys=["audit.db"],
            source="lilsunspot",
            source_of_truth="lilsunspot local audit.db",
            configurable=False,
        ),
        _capability(
            capability_id="runtime.profiles",
            category="runtime",
            name="Profiles",
            description="Hermes profiles、本地身份和运行时配置。",
            enabled=True,
            risk="medium",
            config_keys=["profiles"],
            source="hermes_runtime",
            source_of_truth="Hermes profiles/config",
        ),
        _capability(
            capability_id="runtime.sessions",
            category="runtime",
            name="Sessions",
            description="Hermes SessionDB、多轮会话和历史检索基础。",
            enabled=True,
            risk="medium",
            config_keys=["sessions"],
            source="hermes_runtime",
            source_of_truth="Hermes SessionDB",
        ),
        _capability(
            capability_id="runtime.desktop_image_upload",
            category="runtime",
            name="桌面聊天图片上传",
            description="桌面聊天输入框的本地附件上传和发送入口；图片可预览，是否识别取决于当前视觉后端。",
            enabled=True,
            risk="medium",
            config_keys=["desktop.chat.attachments"],
            source="lilsunspot_desktop",
            source_of_truth="lilsunspot desktop attachment registry",
            configurable=False,
        ),
        _capability(
            capability_id="product.reminders.crud",
            category="automation",
            name="本地提醒记录",
            description="当前只支持创建、暂停、完成和删除本地提醒记录；还没有调度执行器。",
            enabled=True,
            risk="medium",
            config_keys=["product_reminders"],
            source="lilsunspot_product",
            source_of_truth="lilsunspot product_reminders table",
            configurable=False,
            verified=False,
        ),
        _capability(
            capability_id="product.reminders.scheduler",
            category="automation",
            name="提醒调度执行",
            description="提醒调度器尚未接入；不能把本地提醒 CRUD 展示成已会自动提醒。",
            enabled=False,
            available=False,
            reason="not_implemented",
            risk="medium",
            config_keys=["product_reminders"],
            source="lilsunspot_product",
            source_of_truth="not implemented",
            configurable=False,
            configured=False,
            executable=False,
            verified=False,
        ),
        _capability(
            capability_id="product.memory.crud",
            category="memory",
            name="本地记忆记录",
            description="当前只支持本地记忆 CRUD；尚未作为小黑子产品记忆注入 Hermes prompt。",
            enabled=True,
            risk="medium",
            config_keys=["product_memories"],
            source="lilsunspot_product",
            source_of_truth="lilsunspot product_memories table",
            configurable=False,
            verified=False,
        ),
        _capability(
            capability_id="product.memory.prompt_injection",
            category="memory",
            name="产品记忆注入",
            description="小黑子产品层记忆尚未接入 Hermes prompt；不能展示为真实长期记忆已生效。",
            enabled=False,
            available=False,
            reason="not_implemented",
            risk="medium",
            config_keys=["product_memories", "memory"],
            source="lilsunspot_product",
            source_of_truth="not implemented",
            configurable=False,
            configured=False,
            executable=False,
            verified=False,
        ),
        _capability(
            capability_id="product.capability_switches",
            category="runtime",
            name="产品能力开关",
            description="产品开关只表达用户偏好和审批边界，不等于对应 Hermes tool 已真实执行。",
            enabled=True,
            risk="medium",
            config_keys=["product_capabilities"],
            source="lilsunspot_product",
            source_of_truth="lilsunspot product_capabilities table",
            configurable=False,
            verified=False,
        ),
        _capability(
            capability_id="runtime.diagnostics",
            category="runtime",
            name="诊断包导出",
            description="导出脱敏诊断 zip。",
            enabled=True,
            risk="low",
            config_keys=["doctor", "diagnostics"],
            source="lilsunspot",
            source_of_truth="lilsunspot doctor/diagnostics API",
        ),
        _capability(
            capability_id="runtime.doctor_repair",
            category="runtime",
            name="自动修复",
            description="/doctor/repair 仍是占位接口；当前不会修改系统配置，也不能展示成可执行修复。",
            enabled=False,
            available=False,
            reason="not_implemented",
            risk="high",
            config_keys=["doctor.repair"],
            source="lilsunspot",
            source_of_truth="placeholder",
            configurable=False,
            configured=False,
            executable=False,
            verified=False,
        ),
        _capability(
            capability_id="runtime.upstream_sync",
            category="runtime",
            name="上游同步",
            description="检测官方 Hermes GitHub 更新并创建草稿 PR。",
            enabled=workflow_path.exists(),
            risk="medium",
            config_keys=["lilsunspot/UPSTREAM_COMMIT.txt", ".github/workflows/lilsunspot-upstream-sync.yml"],
            source="github_actions",
            source_of_truth="GitHub Actions upstream sync workflow",
            verified=False,
        ),
    ]


def _strip_emoji(value: str) -> str:
    return re.sub(r"^[^\w\u4e00-\u9fff]+", "", value).strip()


def _file_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_mtime_ns, stat.st_size


def capability_prompt_snapshot(paths: RuntimePaths | None = None) -> str:
    runtime_paths = paths or ensure_runtime_dirs()
    cache_key = (
        str(runtime_paths.hermes_home.resolve(strict=False)),
        _file_signature(runtime_paths.hermes_home / "config.yaml"),
        _file_signature(runtime_paths.hermes_home / ".env"),
        _file_signature(runtime_paths.data_dir / "weixin-state.json"),
    )
    cached = _CAPABILITY_PROMPT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    payload = list_capabilities(runtime_paths, include_upstream_audit=False)
    current_model = current_runtime_model(runtime_paths)
    provider = str(current_model.get("provider") or "未配置")
    model = str(current_model.get("model") or "未配置")
    configured = "true" if current_model.get("configured") else "false"
    lines = [
        "当前 lilsunspot 能力状态快照（来源：Hermes toolset/model 配置与 /capabilities registry）。",
        f"当前主模型：provider={provider}；model={model}；configured={configured}。",
        "回答能力问题时只依据这份快照：只有 executable=true 且 verified=true 的能力才能说已真实验证；registered/configured/executable 但 verified=false 只能说已接入或可尝试，不能承诺真实可用。",
    ]
    graph = build_capability_graph(runtime_paths)
    for node in graph.get("nodes", []):
        if not isinstance(node, dict):
            continue
        lines.append(
            f"- product.{node.get('id')} / {node.get('label')}: status={node.get('status')}；"
            f"source={node.get('source')}；{node.get('user_message_cn')}"
        )
    for item in payload["capabilities"]:
        capability_id = str(item.get("id") or "")
        name = str(item.get("name") or capability_id)
        status = str(item.get("status") or "disabled")
        status_text = " ".join(str(item.get("status_text") or "").split())
        deps = [str(dep) for dep in item.get("dependencies") or [] if str(dep).strip()]
        dep_text = f" 依赖：{'；'.join(deps[:3])}。" if deps else ""
        truth = (
            f" registered={str(bool(item.get('registered'))).lower()}；"
            f"configured={str(bool(item.get('configured'))).lower()}；"
            f"executable={str(bool(item.get('executable'))).lower()}；"
            f"verified={str(bool(item.get('verified'))).lower()}"
        )
        lines.append(f"- {capability_id} / {name}: status={status}；{truth}；{status_text}{dep_text}")
    snapshot = "\n".join(lines)
    _CAPABILITY_PROMPT_CACHE.clear()
    _CAPABILITY_PROMPT_CACHE[cache_key] = snapshot
    return snapshot


def get_capability(capability_id: str, paths: RuntimePaths | None = None) -> dict[str, Any]:
    for item in list_capabilities(paths, include_upstream_audit=False)["capabilities"]:
        if item["id"] == capability_id:
            return item
    raise CapabilityError("没有找到这个能力。")


def update_capability(
    capability_id: str,
    *,
    enabled: bool | None = None,
    paths: RuntimePaths | None = None,
) -> dict[str, Any]:
    runtime_paths = paths or ensure_runtime_dirs()
    config = read_hermes_config(runtime_paths)
    if capability_id.startswith("toolset."):
        toolset = capability_id.split(".", 1)[1]
        known = {str(item[0]) for item in _safe_import_toolsets()[1]}
        if toolset not in known:
            raise CapabilityError("没有找到这个工具能力。")
        platform_cfg = config.setdefault("platform_toolsets", {})
        if not isinstance(platform_cfg, dict):
            platform_cfg = {}
            config["platform_toolsets"] = platform_cfg
        current = set(_platform_toolsets(config))
        if enabled is True:
            current.add(toolset)
        elif enabled is False:
            current.discard(toolset)
        else:
            raise CapabilityError("请提供 enabled。")
        platform_cfg[LILSUNSPOT_PLATFORM] = sorted(current)
        write_hermes_config(config, runtime_paths)
        return get_capability(capability_id, runtime_paths)
    if capability_id == "integration.mcp_servers":
        platform_cfg = config.setdefault("platform_toolsets", {})
        if not isinstance(platform_cfg, dict):
            platform_cfg = {}
            config["platform_toolsets"] = platform_cfg
        current = set(_platform_toolsets(config))
        if enabled is False:
            current.add("no_mcp")
        elif enabled is True:
            current.discard("no_mcp")
        else:
            raise CapabilityError("请提供 enabled。")
        platform_cfg[LILSUNSPOT_PLATFORM] = sorted(current)
        write_hermes_config(config, runtime_paths)
        return get_capability(capability_id, runtime_paths)
    raise CapabilityError("这个能力需要在对应配置页调整。")


def test_capability(capability_id: str, paths: RuntimePaths | None = None) -> dict[str, Any]:
    capability = get_capability(capability_id, paths)
    layers = [
        {
            "id": "registered",
            "label": "本地注册",
            "ok": bool(capability.get("registered")),
            "state": "registered" if capability.get("registered") else "missing",
            "message": "本地能力入口已注册。" if capability.get("registered") else "本地能力入口缺失。",
        },
        {
            "id": "configured",
            "label": "配置状态",
            "ok": bool(capability.get("configured")),
            "state": "configured" if capability.get("configured") else "needs_config",
            "message": "相关开关或配置已存在。" if capability.get("configured") else "还没有启用或配置这个能力。",
        },
        {
            "id": "executable",
            "label": "执行前检查",
            "ok": bool(capability.get("executable")),
            "state": "executable" if capability.get("executable") else str(capability.get("status") or "blocked"),
            "message": "本地依赖检查通过。" if capability.get("executable") else str(capability.get("status_text") or "依赖或配置尚未满足。"),
        },
        {
            "id": "verified",
            "label": "真实 smoke",
            "ok": bool(capability.get("verified")),
            "state": "verified" if capability.get("verified") else "unverified",
            "message": (
                f"最近一次真实验证通过：{capability.get('last_verified_at')}"
                if capability.get("verified")
                else "还没有对应账号、环境或真实调用的 smoke 记录。"
            ),
        },
    ]
    ok = all(bool(layer["ok"]) for layer in layers)
    if ok:
        message = "能力已注册、已配置、可执行，并且有真实验证记录。"
    elif capability.get("executable"):
        message = "能力已通过本地注册和执行前检查，但还没有真实 smoke 记录，不能判定为已验证。"
    else:
        message = str(capability.get("status_text") or "能力当前不可执行。")
    if not capability["available"]:
        actions = capability["dependencies"] or ["检查依赖和账号配置"]
    elif not capability.get("verified"):
        actions = ["运行真实 smoke", "检查账号或外部环境"]
    else:
        actions = []
    return {
        "ok": ok,
        "capability": capability,
        "message": message,
        "layers": layers,
        "actions": actions,
    }


def save_platform_toolsets(toolsets: list[str], paths: RuntimePaths | None = None) -> dict[str, Any]:
    local_toolsets, configurable_toolsets = _safe_import_toolsets()
    known = {str(item[0]) for item in configurable_toolsets} | {str(item) for item in local_toolsets}
    requested = [str(item).strip() for item in toolsets if str(item).strip()]
    unknown = [item for item in requested if item not in known and item != "no_mcp"]
    if unknown:
        raise CapabilityError(f"不认识的工具能力：{', '.join(unknown)}")
    runtime_paths = paths or ensure_runtime_dirs()
    config = read_hermes_config(runtime_paths)
    platform_cfg = config.setdefault("platform_toolsets", {})
    if not isinstance(platform_cfg, dict):
        platform_cfg = {}
        config["platform_toolsets"] = platform_cfg
    platform_cfg[LILSUNSPOT_PLATFORM] = sorted(set(requested) | REQUIRED_LILSUNSPOT_TOOLSETS)
    write_hermes_config(config, runtime_paths)
    return get_platform_toolsets(runtime_paths)


def get_platform_toolsets(paths: RuntimePaths | None = None) -> dict[str, Any]:
    payload = list_capabilities(paths, include_upstream_audit=False)
    toolset_caps = [item for item in payload["capabilities"] if item["id"].startswith("toolset.")]
    return {
        "platform": LILSUNSPOT_PLATFORM,
        "enabled_toolsets": payload["enabled_toolsets"],
        "available_toolsets": toolset_caps,
        "default_toolsets": payload["default_toolsets"],
    }
