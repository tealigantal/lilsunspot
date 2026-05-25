from __future__ import annotations

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import Header, HTTPException, status

from .config_paths import ensure_runtime_dirs


TOKEN_HEADER = "X-Lilsunspot-Token"


def _new_token() -> str:
    return secrets.token_urlsafe(32)


def _write_token_file(path: Path, token: str) -> None:
    payload = {
        "token": token,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "type": "lilsunspot-runtime-token",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def load_or_create_token() -> str:
    paths = ensure_runtime_dirs()
    token_path = paths.token_file
    if token_path.exists():
        try:
            payload: dict[str, Any] = json.loads(token_path.read_text(encoding="utf-8"))
            token = str(payload.get("token") or "").strip()
            if token:
                return token
        except (OSError, json.JSONDecodeError):
            pass

    token = _new_token()
    _write_token_file(token_path, token)
    return token


def token_file_exists() -> bool:
    return ensure_runtime_dirs().token_file.exists()


def verify_token(candidate: str | None) -> bool:
    if not candidate:
        return False
    expected = load_or_create_token()
    return secrets.compare_digest(candidate.strip(), expected)


async def require_token(
    x_lilsunspot_token: Annotated[str | None, Header(alias=TOKEN_HEADER)] = None,
) -> None:
    if verify_token(x_lilsunspot_token):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="A valid X-Lilsunspot-Token is required for this API.",
    )
