# Agent Memory

Use this file only when no more specific Markdown file fits the task.

## 2026-06-04

- Task: add a prompt-level rule that every future agent task updates a relevant Markdown memory file.
- Files touched: `AGENTS.md`, `lilsunspot/notes/agent-memory.md`.
- Decision/result: future work should update `TASKS.md`, component README files, task notes, or this fallback memory file before finalizing.
- Validation: documentation-only change; run secret guard after edit.
- Remaining risk: forced Markdown updates can add noise, so entries should stay short and task-relevant.

- Task: complete `LIL-00-04` desktop chat bridge to the saved runtime configuration.
- Files touched: `TASKS.md`, `lilsunspot/daemon/chat_client.py`, chat/provider tests, desktop Chat UI files, and lilsunspot README files.
- Decision/result: `/chat/send` now reads the isolated `hermes_home` provider/model/API key config and calls an OpenAI-compatible minimal runtime adapter with `engine: hermes_runtime_adapter`; desktop Chat shows loading, success, error, and disabled states.
- Validation: daemon pytest, provider/chat product tests, secret guard, desktop build, Browser DOM QA, `pwsh scripts/check.ps1`, and a real local-env DeepSeek `/providers/test` + `/chat/send` run using `DEEPSEEK_API_KEY`.
- Remaining risk: Browser screenshot capture timed out in the in-app browser, so visual QA relied on DOM/state/console checks; GitHub publishing is blocked until `gh auth login` succeeds.
