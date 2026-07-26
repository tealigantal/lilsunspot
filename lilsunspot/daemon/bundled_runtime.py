from __future__ import annotations

"""Locate Hermes extension assets in both source and Windows sidecar runs."""

import os
import sys
from pathlib import Path


_ASSET_ENV = {
    "plugins": "HERMES_BUNDLED_PLUGINS",
    "skills": "HERMES_BUNDLED_SKILLS",
    "optional-skills": "HERMES_OPTIONAL_SKILLS",
    "optional-mcps": "HERMES_OPTIONAL_MCPS",
}


def bundled_asset_root() -> Path:
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root)
    return Path(__file__).resolve().parents[2]


def configure_bundled_extension_assets() -> dict[str, str]:
    """Point Hermes discovery at read-only assets delivered with the sidecar."""
    root = bundled_asset_root()
    configured: dict[str, str] = {}
    for directory, variable in _ASSET_ENV.items():
        path = root / directory
        if not path.is_dir():
            continue
        if not os.environ.get(variable, "").strip():
            os.environ[variable] = str(path)
        configured[directory] = os.environ[variable]
    return configured


def bundled_extension_assets() -> dict[str, Path]:
    root = bundled_asset_root()
    return {directory: root / directory for directory in _ASSET_ENV if (root / directory).is_dir()}
