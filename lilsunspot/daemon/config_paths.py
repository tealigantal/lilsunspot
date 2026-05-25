from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


APP_DIR_NAME = "Lilsunspot"
DATA_DIR_NAME = "data"
HERMES_HOME_DIR_NAME = "hermes_home"
LOGS_DIR_NAME = "logs"
TOKEN_FILE_NAME = "runtime-token.json"


@dataclass(frozen=True)
class RuntimePaths:
    data_dir: Path
    hermes_home: Path
    logs_dir: Path
    token_file: Path


def get_data_dir() -> Path:
    """Return lilsunspot's user-data directory without hardcoded usernames."""
    override = os.environ.get("LILSUNSPOT_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            return Path(local_appdata) / APP_DIR_NAME / DATA_DIR_NAME
        return Path.home() / "AppData" / "Local" / APP_DIR_NAME / DATA_DIR_NAME

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / APP_DIR_NAME / DATA_DIR_NAME

    return Path.home() / ".local" / "share" / APP_DIR_NAME / DATA_DIR_NAME


def get_runtime_paths() -> RuntimePaths:
    data_dir = get_data_dir()
    return RuntimePaths(
        data_dir=data_dir,
        hermes_home=data_dir / HERMES_HOME_DIR_NAME,
        logs_dir=data_dir / LOGS_DIR_NAME,
        token_file=data_dir / TOKEN_FILE_NAME,
    )


def ensure_runtime_dirs() -> RuntimePaths:
    paths = get_runtime_paths()
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.hermes_home.mkdir(parents=True, exist_ok=True)
    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    return paths
