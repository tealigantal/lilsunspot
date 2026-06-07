# Agent Memory

## 2026-06-07

- Task: check Figma before publishing `LIL-P0-FLOW-UI-01`.
- Files touched: `lilsunspot/desktop/design/p0-flow-ui-spec.md` and `lilsunspot/notes/agent-memory.md`.
- Decision/result: Figma authenticated and created `https://www.figma.com/design/k47dWzEZutMAKpoI2mCbvk`, but Starter plan MCP rate limits blocked continued design-system lookup and canvas work; per user instruction, proceeded toward PR submission instead of attempting more Figma writes.
- Validation: Figma `whoami`, `create_new_file`, metadata, library lookup, and first design-system search ran; subsequent Figma searches returned the plan-limit error.
- Remaining risk: the Figma file exists but does not contain the redesigned editable frontend screens; the repository spec remains the design source until Figma MCP quota/access is available.

- Task: complete `LIL-P0-FLOW-UI-01` product flow refactor, UI rearrangement, design fallback, and P0 main-path repair.
- Files touched: `TASKS.md`, `lilsunspot/daemon/app.py`, `chat_client.py`, `hermes_runtime.py`, `modes.py`, `provider_client.py`, daemon/product tests, `lilsunspot/desktop/design/p0-flow-ui-spec.md`, `lilsunspot/desktop/src/App.tsx`, `App.css`, `api.ts`, `types.ts`, new `app/`, `features/`, and `shared/` frontend modules, `lilsunspot/desktop/README.md`, `lilsunspot/notes/architecture.md`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: Figma MCP was unavailable, so the design was delivered as an in-repo spec; desktop flow now uses BootGate and `/app/bootstrap` instead of a flat developer tab homepage; unconfigured users enter onboarding, configured users enter ChatHome, repair states show reasons/actions, and Weixin/Safety/Doctor moved into a clearly marked settings drawer.
- Decision/result: provider setup now supports editable model and validated `base_url_override`; local provider empty API Key remains allowed; mode sliders are saved in lilsunspot data and appended to the next chat system hint; chat engine is truthfully reported as `lilsunspot_provider_adapter`.
- Validation: `git diff --check` passed, secret guard passed, daemon pytest 25 passed, product pytest 24 passed, desktop TypeScript/Vite build passed, `scripts/check.ps1` passed, sidecar build passed, Tauri NSIS build produced the Windows installer, and a local Vite HTTP smoke returned 200.
- Remaining risk: Browser IAB was unavailable and local Playwright/puppeteer were not installed, so visual QA was not automated; clean Windows install, repository-external installed-app close/reopen into ChatHome, real API Key provider test/save/chat, and manual visual QA still need to be performed; current chat is still not a full Hermes agent loop.

- Task: complete `LIL-P0-02A` installation first-run feedback fix from `feed_back07-06-2026`.
- Files touched: `TASKS.md`, `scripts/build_lilsunspotd_sidecar.ps1`, `lilsunspot/desktop/src/App.tsx`, `lilsunspot/desktop/src/App.css`, desktop Tauri config/Rust entry, desktop icon assets, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: fixed Windows release console-window risk with the Tauri Windows subsystem attribute and PyInstaller `--noconsole`; replaced the package icon from the feedback image; routed unconfigured first launch to the provider wizard; made API Key save status explicit and cleared the in-memory key after save; replaced chat output with a message transcript that clears the composer after send; and changed Mode into auto-loaded horizontal selection cards.
- Validation: daemon pytest 23 passed, product pytest 20 passed, secret guard passed, desktop TypeScript/Vite build passed, `scripts/check.ps1` passed, sidecar build passed with the windowed PyInstaller bootloader, NSIS build produced `Lilsunspot_0.1.0_x64-setup.exe`, and Chrome headless screenshots checked Provider step 1/2, Chat, Mode desktop, and Mode mobile render states.
- Remaining risk: clean Windows install, repository-external installed-app launch, real API Key provider save/test/chat, and actual post-install no-black-window behavior still require manual installed-app verification.

- Task: continue `LIL-P0-02A` validation after handoff.
- Files touched: `lilsunspot/notes/agent-memory.md`.
- Decision/result: kept the product code unchanged after review; reused the locally running installed daemon only for read-only desktop dev smoke checks.
- Validation: reran daemon pytest 23 passed, product pytest 20 passed, secret guard passed, desktop build passed, `scripts/check.ps1` passed, sidecar build passed, NSIS build produced `Lilsunspot_0.1.0_x64-setup.exe`, and Browser extension smoke verified Provider, Mode, and Chat DOM states with no console errors.
- Remaining risk: in-app browser `iab` was unavailable and the Chrome extension screenshot API timed out, so this continuation did not add new screenshot evidence; clean install, real API Key save/test/chat, and post-install no-black-window behavior remain manual checks.

- Task: fix the setup.exe product issue instead of only validating the UI patch.
- Files touched: `lilsunspot/desktop/src-tauri/Cargo.toml`, `lilsunspot/desktop/src-tauri/nsis/installer-hooks.nsh`, `TASKS.md`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: made the packaged Windows main binary install as `Lilsunspot.exe`; added NSIS upgrade hooks to close and remove stale `lilsunspot_desktop.exe`; kept shortcut recreation pointed at the installed app exe icon.
- Validation: rebuilt NSIS setup.exe, confirmed generated `installer.nsi` uses `MAINBINARYNAME "Lilsunspot"`, ran `Lilsunspot_0.1.0_x64-setup.exe /S`, verified install dir contains `Lilsunspot.exe`, `lilsunspotd.exe`, and `uninstall.exe` without old `lilsunspot_desktop.exe`, verified desktop/start menu shortcuts and uninstall registry target `Lilsunspot.exe`, confirmed setup/app/sidecar PE subsystem is Windows GUI, and launched installed `Lilsunspot.exe` to `/health` ok.
- Remaining risk: this was an in-place current-user install smoke on the development Windows machine, not a clean Windows VM test with a real user provider/chat loop.

## 2026-06-06

- Task: start `LIL-P0-01` and converge the local `release/mvp-p0` candidate branch.
- Files touched: `.gitignore`, removed tracked `.tmp-lilsunspot-data/*` runtime artifacts, `TASKS.md`, `README.lilsunspot.md`, `lilsunspot/README-dev.md`, `lilsunspot/notes/mvp-p0-status.md`, `lilsunspot/notes/qa-checklist.md`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: no product code changes were needed; the branch records the automated MVP P0 evidence separately from clean-install and real-provider manual risks, and removes tracked temporary runtime files from the release candidate.
- Validation: daemon pytest 23 passed, product pytest 20 passed, secret guard passed, desktop build passed, `scripts/check.ps1` passed, sidecar build passed, NSIS build produced `Lilsunspot_0.1.0_x64-setup.exe`, and release sidecar smoke passed for `/health`, token-protected `/providers`, `127.0.0.1` binding, runtime file creation, and token log leak check.
- Remaining risk: clean Windows install, repository-external installed-app launch, real API Key provider save/test/chat, and desktop UI chat were not verified in this task.

- Task: complete `LIL-DOC-01` Markdown documentation entry cleanup.
- Files touched: `README.lilsunspot.md`, `README.md`, `TASKS.md`, `lilsunspot/README-dev.md`, and lilsunspot notes for doc index, inventory, P0 status, architecture, QA, and decisions.
- Decision/result: created an executable lilsunspot documentation entry path and marked historical Day1/Weixin/status notes as reference material instead of current truth.
- Validation: repository location, branch, recent log, remotes, Markdown scans, `git diff --check`, and `python scripts/guard_no_secrets.py`.
- Remaining risk: this task did not run pytest, npm build, Tauri build, provider calls, daemon startup, or clean Windows installation checks.

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
