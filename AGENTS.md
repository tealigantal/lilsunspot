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
- Final response must include files changed, tests run, result, known risks, intentionally not done.

## Done Means

- Acceptance criteria pass.
- Relevant tests pass.
- No unnecessary Hermes core change.
- No secret leak.
- App skeleton still starts.
- `scripts/check.ps1` passes, or failure is documented and unrelated.
