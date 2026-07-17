# AGENTS.md

## Project

- Product name: lilsunspot.
- Chinese name: 小黑子.
- This repository is a fork of Hermes Agent.
- The goal is a desktop personal agent that normal users can install and run: the existing Windows product remains the release baseline, with private macOS arm64 and x86_64 DMGs built separately.

## Main Path

Installer/DMG -> Lilsunspot desktop -> lilsunspotd -> Hermes runtime -> Provider config -> Desktop chat -> Mode profiles -> Weixin commands -> Safety approval

## Hard Rules

- Do not rewrite Hermes core.
- New product code should live under `lilsunspot/`.
- `lilsunspotd` must bind to `127.0.0.1`.
- Every local API except `/health` must require `X-Lilsunspot-Token`.
- API keys and tokens must never appear in logs, prompts, fixtures, screenshots or diagnostics.
- Tests must use temporary data dirs.
- Do not require end users to install Python, Node, Git or Docker.
- User-facing errors must be plain Chinese.
- Do not do unrelated refactors.
- Do not add large dependencies unless explicitly required.

## How To Work

- Read `TASKS.md`.
- Work only on `Current`.
- State expected files before editing.
- Implement the smallest working version.
- Add or update tests.
- Run `scripts/check.ps1`.
- If the task changes desktop UI, `lilsunspot/desktop/src-tauri/**`, sidecar/runtime startup, installer scripts, app icons/assets used by the bundle, Weixin runtime delivery, or anything users only receive through the installed app, also run `npm run tauri:build --prefix lilsunspot/desktop` before finalizing and confirm the NSIS `setup.exe` exists. If this cannot run, document the blocker explicitly.
- Update a relevant Markdown memory file for every agent task before finalizing.
- Final response must include files changed, tests run, result, known risks, intentionally not done.

## Markdown Memory

- Every agent task must leave a small Markdown trace, even when the code change is tiny.
- Prefer updating the most relevant existing file:
  - `TASKS.md` for task status, Current/Next/Done movement, acceptance criteria, or checks.
  - `lilsunspot/README-dev.md` for developer workflow, API behavior, validation, or project status.
  - `lilsunspot/desktop/README.md` for desktop workflow or UI behavior.
  - `lilsunspot/notes/*.md` for investigation notes, decisions, risks, and historical context.
- If no existing document clearly fits, append a short entry to `lilsunspot/notes/agent-memory.md`.
- Keep entries concise: date, task, files touched, decision/result, validation, and remaining risk.
- Do not record API keys, runtime tokens, secrets, raw stack traces containing secrets, screenshots, or private user data.
- Do not update unrelated Hermes upstream docs just to satisfy the memory rule.
- If the user explicitly requests no repository changes, do not modify files; instead state that the memory update was intentionally skipped.

## Codex Local Environment

- Codex local Python work should prefer `ignored/codex-venv`.
- Before running daemon-backed desktop commands, prepend `ignored/codex-venv/Scripts` and `%USERPROFILE%/.cargo/bin` to `PATH`.
- When launching Tauri dev from this repo, set `PYTHONPATH` to the repository root so `python -m lilsunspot.daemon.launcher` resolves product-layer modules.
- Use an ignored temporary data dir such as `ignored/tauri-dev-data` for Tauri smoke tests and local daemon runs.
- Do not place real API keys or runtime tokens in `ignored/` logs, prompts, screenshots, fixtures, or committed files.

## Done Means

- Acceptance criteria pass.
- Relevant tests pass.
- No unnecessary Hermes core change.
- No secret leak.
- App skeleton still starts.
- `scripts/check.ps1` passes, or failure is documented and unrelated.
- For installer-impacting work, a fresh `setup.exe` is built and its path is reported, or the exact reason it could not be built is recorded.
- For macOS packaging work, both native-architecture DMG jobs and their installed-app smoke checks are defined; cloud-only results must not be reported as passed until GitHub Actions has actually produced the artifacts.
