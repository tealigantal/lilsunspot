# Agent Memory

## 2026-06-06

- Task: complete `LIL-00-07` Windows installer and daemon sidecar minimum loop.
- Files touched: `TASKS.md`, `scripts/build_lilsunspotd_sidecar.ps1`, `scripts/build_lilsunspot_desktop_nsis.ps1`, `lilsunspot/daemon/sidecar_main.py`, Tauri desktop config/Rust/package scripts, and lilsunspot desktop/dev docs.
- Decision/result: added a PyInstaller sidecar build through `uv run --extra web --with pyinstaller==6.16.0`, fixed Tauri to bundle NSIS with `externalBin`, and made desktop startup prefer packaged sidecar paths before PATH/debug Python fallback.
- Validation: daemon pytest, product pytest, secret guard, `scripts/check.ps1`, Windows PowerShell sidecar build, NSIS Tauri build, and release sidecar `/health` plus token-protected `/providers` smoke passed.
- Remaining risk: the NSIS installer was built but not installed on a clean Windows account; signing, auto-update, and real installed-app startup remain manual/release validation items.

- Task: sync local `develop` with latest `origin/develop` and finish an in-progress merge.
- Files touched: `AGENTS.md`, `TASKS.md`, `lilsunspot/README-dev.md`, `lilsunspot/daemon/chat_client.py`, related chat tests, desktop README/UI/types, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: fetched `origin/develop`, resolved conflicts by keeping the latest remote LIL-00-05/LIL-00-06 code and tests, while preserving local Markdown Memory and Codex environment instructions in `AGENTS.md`.
- Validation: `python -m pytest lilsunspot/daemon/tests`, `python -m pytest lilsunspot/tests/test_chat_api.py --timeout-method=thread --basetemp .tmp-pytest-lilsunspot`, `python scripts/guard_no_secrets.py`, and `pwsh scripts/check.ps1` passed with system Python 3.11.8; the preferred `ignored/codex-venv` was not used because it lacks `pytest`.
- Remaining risk: local branch remains ahead of `origin/develop` until these existing local commits and the merge commit are pushed.

- Task: verify the merged `LIL-00-05` mode-profile chat behavior with a real local provider key.
- Files touched: `lilsunspot/notes/agent-memory.md`.
- Decision/result: `origin/develop` already contained PR #7 for `LIL-00-05`; no code changes were needed. A live temporary daemon selected `pragmatic` mode, saved `deepseek/deepseek-chat`, and completed `/chat/send` through the real provider.
- Validation: `python -m pytest lilsunspot/daemon/tests`, `python -m pytest lilsunspot/tests/test_chat_api.py --timeout-method=thread --basetemp .tmp-pytest-lilsunspot`, `python scripts/guard_no_secrets.py`, `pwsh scripts/check.ps1`, and a live `DEEPSEEK_API_KEY` provider/chat run passed.
- Remaining risk: the provider reply body, API Key, and runtime token were intentionally not recorded; live validation only spot-checked one selected profile and one provider.

## 2026-06-04

- Task: complete `LIL-00-05` by connecting mode profiles to real chat behavior.
- Files touched: `TASKS.md`, `lilsunspot/daemon/chat_client.py`, daemon/chat tests, and `lilsunspot/README-dev.md`.
- Decision/result: `/chat/send` now reads the selected mode from the lilsunspot data dir and sends the profile `system_hint` as the OpenAI-compatible system message before user input; missing selection falls back to the default profile.
- Validation: daemon pytest, chat product tests, secret guard, desktop build, and `scripts/check.ps1` passed.
- Remaining risk: runtime providers may interpret system prompts differently, so real provider behavior still needs spot-checking after provider configuration.

- Task: close `LIL-00-04` after real local-environment chat validation.
- Files touched: `TASKS.md`, `lilsunspot/notes/agent-memory.md`.
- Decision/result: `LIL-00-04` moved to Done and `LIL-00-05` is now Current.
- Validation: using local environment variable `DEEPSEEK_API_KEY`, `/providers/test` passed for `deepseek/deepseek-chat`, and `/chat/send` returned a real `hermes_runtime_adapter` response with 39 characters. `python scripts/guard_no_secrets.py` and `pwsh scripts/check.ps1` passed locally.
- Remaining risk: no API Key, runtime token, or reply body was recorded; GitHub PR creation still requires local `gh auth login`.
