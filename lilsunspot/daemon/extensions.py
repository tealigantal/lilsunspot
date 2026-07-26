from __future__ import annotations

"""Safe, read-only extension catalog exposed by the local product API."""

import json
from pathlib import Path
from typing import Any

from .bundled_runtime import bundled_extension_assets, configure_bundled_extension_assets


_EXTENSION_KINDS = {"plugin", "skill", "optional_mcp", "gateway_adapter"}


def extension_catalog() -> dict[str, Any]:
    """List delivered extensions without importing, starting, or credentialing them."""
    configured = configure_bundled_extension_assets()
    try:
        manifest_path = Path(__file__).resolve().parents[1] / "resources" / "hermes_capability_manifest.json"
        rows = json.loads(manifest_path.read_text(encoding="utf-8")).get("parity", {}).get("rows", [])
    except (OSError, json.JSONDecodeError, AttributeError):
        rows = []
    counts: dict[str, int] = {kind: 0 for kind in sorted(_EXTENSION_KINDS)}
    extensions: list[dict[str, str]] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict) or row.get("kind") not in _EXTENSION_KINDS:
            continue
        kind = str(row["kind"])
        counts[kind] += 1
        upstream = row.get("upstream") if isinstance(row.get("upstream"), dict) else {}
        extensions.append({
            "id": str(row.get("id") or ""),
            "kind": kind,
            "name": str(upstream.get("name") or upstream.get("platform") or row.get("id") or ""),
            "source": str(upstream.get("source") or ""),
            "status": "需要配置后使用",
        })
    return {
        "ok": True,
        "assets": {name: str(path) for name, path in sorted(bundled_extension_assets().items())},
        "environment": {name: configured[name] for name in sorted(configured)},
        "counts": counts,
        "extensions": extensions,
        "safety": "目录查询不会加载插件、启动 MCP、连接网关或读取凭据。实际执行仍遵循 Hermes 配置和小黑子审批边界。",
    }
