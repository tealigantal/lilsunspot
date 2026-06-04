# AGENTS.md

## Project

- Product name: lilsunspot.
- Chinese name: 小黑子.
- This repository is a fork of Hermes Agent.
- The goal is a Windows desktop personal agent that normal users can install and run.

## Main Path

Installer -> Lilsunspot.exe -> lilsunspotd -> Hermes runtime -> Provider config -> Desktop chat -> Mode profiles -> Weixin commands -> Safety approval

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

## Done Means

- Acceptance criteria pass.
- Relevant tests pass.
- No unnecessary Hermes core change.
- No secret leak.
- App skeleton still starts.
- `scripts/check.ps1` passes, or failure is documented and unrelated.
