# Agent Memory

## 2026-06-30 - screenshot-level full UI acceptance plan only

- Task: run screenshot-level acceptance across the current desktop UI and record issues only as the next plan.
- Files touched: `TASKS.md` and this memory file. Temporary screenshot harness and artifacts stayed under ignored `ignored/ui-acceptance/`.
- Decision/result: no product code was changed. Vite + headless Chrome/CDP with a mock daemon captured 22 screenshots covering onboarding, chat, Weixin, tasks, history, all settings tabs, and 390px mobile views. The plan now records the remaining UI issues: stale "未配置" status after model save, hidden primary save action on the model-save step, overly tall settings category navigation, and mobile chat prioritizing conversation list over the actual chat/input.
- Validation: screenshot run produced `ignored/ui-acceptance/results.json` and `contact_sheet.png`; metrics found no horizontal overflow. The only console error in onboarding was the dev-server favicon 404. No real API Key, runtime token, Weixin credential, private message, QR payload, attachment original, or model reply was recorded.
- Remaining risk: this was Vite/mock screenshot acceptance, not installed-app WebView, real daemon, real provider, or live Weixin acceptance.

## 2026-06-29 - Weixin file send without approval

- Task: remove the extra safety approval step for user-clicked Weixin file/message sending after the UI showed `weixin_runtime+safety.approval` and the user asked for automatic sending.
- Files touched: `lilsunspot/daemon/gateway.py`, `lilsunspot/daemon/weixin_runtime.py`, `lilsunspot/daemon/app.py`, `lilsunspot/daemon/capability_graph.py`, `lilsunspot/daemon/product_features.py`, `lilsunspot/resources/default_safety_policy.yaml`, focused pytest files, desktop API/types/chat transcript, and this memory file.
- Decision/result: `/gateway/weixin/send` now directly sends through the active Weixin runtime and returns delivery status; it no longer creates a pending `send_weixin_message` approval. The direct path still validates token protection, explicit recipient/message or attachment, connected Weixin runtime, safe attachment paths, and deliverable file format. `weixin.send_file` now reports `ready` when connected and `requires_approval=false`; the product capability migration updates existing local capability rows without overwriting user-enabled state. Generic safety approvals and Hermes tool approvals remain available for other high-risk operations.
- Validation: `python -m pytest lilsunspot/daemon/tests/test_safety_approvals.py lilsunspot/daemon/tests/test_conversation_sync.py lilsunspot/daemon/tests/test_product_features.py -q` passed with 72 tests; `npm run build --prefix lilsunspot/desktop` passed; `git diff --check` passed with only LF/CRLF warnings; `python scripts/guard_no_secrets.py` passed; `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` passed with daemon 144 tests, secret guard, and desktop build; `npm run tauri:build --prefix lilsunspot/desktop` produced the NSIS setup.exe at 56,721,876 bytes.
- Remaining risk: installed-app click-through and live Weixin file-send confirmation were not run in this pass.

## 2026-06-29 - complete task scheduler, branch attachments, and guarded advanced actions

- Task: close the remaining limitations from the Hermes UI productization slice: make tasks run in the background, preserve attachments when branching conversations, and make Advanced more than read-only without exposing dangerous raw controls.
- Files touched: `lilsunspot/daemon/product_features.py`, `lilsunspot/daemon/product_task_scheduler.py`, `lilsunspot/daemon/app.py`, `lilsunspot/daemon/tests/test_product_features.py`, desktop API/types, `TasksPage`, `AdvancedSettings`, CSS, and this memory file.
- Decision/result: `/tasks` now requires parseable date-time input and supports `once` or `daily` schedules. The daemon starts a product task scheduler in FastAPI lifespan; due tasks create local system messages, write run history, complete one-shot tasks, and reschedule daily tasks. Branching a conversation creates new attachment records that point to the existing safe attachment path and record `copied_from_attachment_id`. Advanced now supports guarded capability toggles, redacted config export, and safe product-config import; plugin install, raw env editing, terminal tools, API keys, runtime tokens, Weixin credentials, chat text, and attachment contents remain excluded.
- Validation so far: `python -m pytest lilsunspot/daemon/tests/test_product_features.py -q` passed with 11 tests; `python -m pytest lilsunspot/daemon/tests/test_product_features.py lilsunspot/daemon/tests/test_conversation_sync.py -q` passed with 67 tests; `npm run build --prefix lilsunspot/desktop` passed.
- Remaining risk: installed-app/manual click-through and final NSIS rebuild are still pending for this follow-up pass.

## 2026-06-29 - Hermes missing UI productization slice

- Task: implement the planned UI integration for Hermes official UI gaps without copying the raw Dashboard into the normal-user product.
- Files touched: product API wrappers in `lilsunspot/daemon/app.py` and `product_features.py`, focused product tests, desktop API/types, AppShell/BootGate/ChatHome, new Tasks/History/Memory/Profile/Advanced UI components, `DoctorSettings`, `SettingsDrawer`, CSS, and this memory file.
- Decision/result: main navigation now exposes Chat, Weixin, Tasks, and History. Settings now groups Model, Capabilities, Memory and Style, Safety, Diagnostics, Advanced, and Update. Added token-protected wrappers for `/ui/overview`, `/sessions/search`, `/tasks`, `/usage/summary`, `/profiles`, `/advanced/extensions`, and conversation turn actions for stop/retry/undo/branch/save-summary. Tasks are productized local jobs with pause/resume/manual-run records; the background scheduler and silent Weixin delivery remain explicitly not enabled.
- Validation: `python -m pytest lilsunspot/daemon/tests/test_product_features.py lilsunspot/daemon/tests/test_conversation_sync.py -q` passed with 65 tests; `npm run build --prefix lilsunspot/desktop` passed; `git diff --check` passed with only LF/CRLF warnings; `python scripts/guard_no_secrets.py` passed; `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` passed with daemon 142 tests, secret guard, and desktop build; `npm run tauri:build --prefix lilsunspot/desktop` produced the NSIS setup.exe.
- Remaining risk: installed-app/manual click-through was not run in this pass. Follow-up work on the same date added a real product scheduler, branch attachment records, and guarded Advanced import/export.

## 2026-06-22 - generated Office format hardening

- Task: implement the first `LIL-WEIXIN-FILE-FORMAT-HARDENING` slice so generated files cannot be pure text with fake Office/PDF extensions.
- Files touched: `TASKS.md`, `lilsunspot/daemon/delivery_actions.py`, `lilsunspot/daemon/delivery_tools.py`, `lilsunspot/daemon/media_delivery.py`, `lilsunspot/daemon/weixin_runtime.py`, `lilsunspot/daemon/tests/test_conversation_sync.py`, and this memory file.
- Decision/result: `lilsunspot_create_deliverable_file` now tells the agent to use `.csv` for ordinary tables and `.xlsx` only for explicit Excel requests. Text content for `.xlsx` is converted into a real workbook; text content for `.docx` becomes a minimal real OpenXML document; text content for `.pdf` is rejected instead of being renamed. Delivery actions, same-channel Weixin delivery, and approved Weixin sends all validate `.xlsx/.docx/.pdf` before registering or sending, so fake Office/PDF bytes fail closed with a plain Chinese reason.
- Validation: `python -m pytest lilsunspot/daemon/tests/test_conversation_sync.py -q` passed with 56 tests.
- Remaining risk: this was local automated coverage only. A rebuilt installed app still needs live Weixin verification for real `.csv/.xlsx/.docx/.pdf` generation, phone-side opening/preview behavior, and approval-to-Weixin delivery.

## 2026-06-21 - desktop Enter-to-send shortcut and installer memory boundary

- Task: add a desktop chat shortcut so Enter sends a message while Shift+Enter keeps multiline input, and answer whether user memory is bundled into `setup.exe`.
- Files touched: `lilsunspot/desktop/src/features/chat/ChatComposer.tsx`, `lilsunspot/desktop/src/features/chat/ChatHome.tsx`, and this memory file.
- Decision/result: the main desktop chat composer now sends on Enter unless the user is composing IME text or holding Shift. The placeholder no longer advertises a keyboard shortcut. Installer memory boundary was rechecked: Tauri bundles `binaries/lilsunspotd`, while runtime data and `product_memories` live under the per-user data dir such as `%LOCALAPPDATA%\Lilsunspot\data`, so another user receiving only the installer gets a fresh local data directory without this machine's memories.
- Remaining risk: existing users reinstalling over their own `%LOCALAPPDATA%\Lilsunspot\data` keep their local data unless they explicitly reset or uninstall/remove data.

## 2026-06-21 - memory reset truthfulness issue

- Task: inspect the latest installed-app conversation after a user-requested memory reset and add the issue to the next plan without changing code.
- Files touched: `TASKS.md`, `lilsunspot/notes/mode-hermes-automation-status.md`, and this memory file.
- Decision/result: the latest sanitized message check matched the screenshot: after a user asked to delete a specific topic from memory and then confirm local cleanup, the assistant claimed cleanup while exposing internal tool names and environment assumptions. This is a product truthfulness and privacy-boundary problem, not only a wording issue. Memory reset must distinguish product local memory, Hermes agent memory, conversation history, Weixin route/session context, and installed-app local files.
- Implementation note: record the user's preferred fix as part of the plan. The installed build should include the local search dependency used for filesystem verification, such as `ripgrep`/`rg`, and release smoke should confirm it is available in the packaged app. This supports verification, but the actual reset must still call structured memory/session cleanup paths instead of treating search as the deletion mechanism.
- Validation: documentation-only change. The conversation inspection recorded only message lengths, roles, timestamps, statuses, metadata keys, and boolean flags for internal-tool exposure or deletion claims; no private names, Weixin credentials, runtime tokens, private message text, QR data, screenshots, or attachment contents were written to repo docs.
- Remaining risk: until implemented, the app should not promise verified memory deletion or local cleanup from chat alone; it needs a real clear/reset path with a Chinese confirmation summary and a clear "cannot verify" response when the boundary is incomplete.

## 2026-06-21 - Weixin new account memory carryover issue

- Task: inspect the latest installed-app Weixin conversation state and record the user's concern without changing product code.
- Files touched: `TASKS.md`, `lilsunspot/notes/mode-hermes-automation-status.md`, and this memory file.
- Decision/result: the latest sanitized local inspection found one active Weixin conversation and Hermes state still organized around shared local session/message storage, while the local Weixin accounts directory can retain more than one account credential/sync file. The user observed that logging in with a new Weixin account can still carry over past memory/context. Until account-scoped credentials, routes, conversations, Hermes sessions, Mode state, and memory are isolated end to end, the initial product scope should not promise multiple Weixin accounts.
- Validation: documentation-only change; no code was modified. The inspection intentionally recorded only counts, timestamps, metadata keys, message lengths, and hashed route/account identifiers, not Weixin credentials, runtime tokens, private message text, QR data, screenshots, or attachment contents.
- Remaining risk: single-account Weixin still needs live disconnect/reconnect, QR expiry, same-account multi-contact route, deletion race, file/media, and installed-app recovery QA.

## 2026-06-20 - installed Weixin file and image transfer live QA

- Task: verify installed-app Weixin file and image transfer after Mode/Hermes Stage 6.
- Files touched: `lilsunspot/notes/mode-hermes-automation-status.md` and this memory file.
- Decision/result: rebuilt the latest `develop` NSIS installer, silently installed it to `%LOCALAPPDATA%\Lilsunspot`, launched the installed app, and verified `/health` ready with Weixin runtime connected. Real Weixin text roundtrip passed. A Weixin request to generate and send a text file returned a safe `text/plain` attachment and the user confirmed receipt. A Weixin image upload was stored as `image/jpeg`, recognized, and a later request returned the same image to Weixin; the user confirmed receipt.
- Decision/result: the transfer channel works, but Office generation is not yet correct. A requested spreadsheet was sent with `.xlsx` extension and Excel MIME type, but local bytes were plain UTF-8 text (`文件传输测试通过`) and only 24 bytes, so Weixin native preview could not open it. This is a product generation/format-validation issue, not a Weixin transport failure.
- Validation: installed app process and onedir sidecar ran from `%LOCALAPPDATA%\Lilsunspot`; `/gateway/weixin/status` reported connected/running with no runtime error; txt delivery had `delivery.status=delivered`; image inbound stored one `image/jpeg` attachment with recognized summary, and image return had `delivery.status=delivered`.
- Remaining risk: generated Office formats need a guard or real writer path so `.xlsx`/`.docx`/`.pdf` cannot be created from plain text bytes with a fake extension; broader Weixin stability cases such as disconnect/reconnect, QR expiry, multi-route, and large files still need live QA. Follow-up testing is now tracked in `TASKS.md` Next under `LIL-WEIXIN-FILE-FORMAT-HARDENING`, `LIL-HERMES-FULL-01-INSTALL-QA`, and `LIL-WEIXIN-MEDIA-STABILITY-QA`.

## 2026-06-16 - generated file delivery acceptance recheck

- Task: rerun acceptance-level validation for generated file/image delivery and the fresh setup.exe.
- Files touched: this memory file only after validation.
- Decision/result: no product code changes were needed during acceptance. The NSIS build script moved the previous installer into `stale/`, generated a new current setup.exe, and the installed-app smoke used that setup.exe to install into an isolated temp app directory, launch repository-external `Lilsunspot.exe`, verify the packaged sidecar, and uninstall.
- Validation: focused conversation sync pytest 50 passed, focused agent/compat pytest 7 passed, `scripts/check.ps1` passed with daemon 124 passed plus secret guard and desktop build, `python scripts/guard_no_secrets.py` passed, `git diff --check` passed, `npm run tauri:build --prefix lilsunspot/desktop` produced fresh NSIS `Lilsunspot_0.1.0_x64-setup.exe` at 56,660,042 bytes with timestamp 2026-06-16 03:50:41 +08:00, and `scripts/smoke_lilsunspot_installed_app.ps1` passed against that installer.
- Remaining risk: this acceptance still did not perform a live Weixin scan/send or a real installed-app LLM generated-file chat with a provider key.

## 2026-06-16 - generated file delivery recheck

- Task: rerun validation for the generated file/image delivery tool chain and confirm the current NSIS installer is fresh.
- Files touched: this memory file only after validation.
- Decision/result: no product code changes were needed during the recheck. The local NSIS build script moved the previous installer into `stale/` and generated a new current `Lilsunspot_0.1.0_x64-setup.exe`.
- Validation: focused conversation sync pytest 50 passed, `scripts/check.ps1` passed with daemon 124 passed plus secret guard and desktop build, `python scripts/guard_no_secrets.py` passed, `git diff --check` passed, and `npm run tauri:build --prefix lilsunspot/desktop` produced a fresh setup.exe at 56,659,946 bytes, timestamp 2026-06-16 03:43:12 +08:00.
- Remaining risk: this recheck did not perform a live Weixin scan/send or installed-app live LLM file-generation chat.

## 2026-06-16 - generated file delivery tool chain

- Task: implement product-layer generation and delivery for new files/images, not just returning existing `att_...` attachments.
- Files touched: `lilsunspot/daemon/agent_runner.py`, `capabilities.py`, `delivery_actions.py`, `delivery_tools.py`, `media_delivery.py`, `test_conversation_sync.py`, `lilsunspot/desktop/src/features/chat/ChatTranscript.tsx`, and this memory file.
- Decision/result: enabled Hermes `file` toolset for lilsunspot agent turns, scoped writes with `HERMES_WRITE_SAFE_ROOT` to `hermes_home/cache/documents/<conversation_id>/<turn_id>/`, and added product tools `lilsunspot_deliver_file` plus `lilsunspot_create_deliverable_file`. Backend turn results keep safe paths only internally; model-visible tool JSON and desktop messages stay path-free. Desktop registers generated files as assistant attachments, while Weixin same-route delivery continues through `send_image_file` or `send_document`.
- Validation: focused conversation sync pytest 50 passed, capabilities pytest 11 passed, agent runner pytest 3 passed, Hermes compatibility pytest 4 passed, product features pytest 7 passed, `scripts/check.ps1` passed with daemon 124 passed plus secret guard and desktop build, `python scripts/guard_no_secrets.py` passed, `git diff --check` passed, and `npm run tauri:build --prefix lilsunspot/desktop` produced fresh NSIS `Lilsunspot_0.1.0_x64-setup.exe` at 56,659,534 bytes, timestamp 2026-06-16 03:33:50 +08:00.
- Remaining risk: Weixin generated-file sending is fake-adapter tested only; no live Weixin scan/send was performed. The full Hermes `write_file` implementation still depends on the upstream shell backend on Windows, so the reliable local generation path is the new product `lilsunspot_create_deliverable_file` tool.

## 2026-06-16 - installer overwrite locked sidecar dll fix

- Task: diagnose the NSIS overwrite error where `VCRUNTIME140.dll` under the installed `lilsunspotd` sidecar directory could not be written during setup.
- Files touched: `lilsunspot/desktop/src-tauri/nsis/installer-hooks.nsh`, `lilsunspot/tests/test_lilsunspot_updater_release_plan.py`, and this memory file.
- Decision/result: the installed `Lilsunspot.exe` and `lilsunspotd.exe` can remain running during a user-initiated reinstall, keeping sidecar DLLs locked. The installer hook now stops the current main app name as well as legacy names and sidecars, uses `taskkill /F /T` as a fallback, and verifies the processes are gone before overwrite.
- Validation: focused updater/release pytest passed, fresh `npm run tauri:build --prefix lilsunspot/desktop` produced a new `Lilsunspot_0.1.0_x64-setup.exe`, overwrite-install smoke passed while both installed `Lilsunspot.exe` and `lilsunspotd.exe` were running, `scripts/check.ps1` passed, `python scripts/guard_no_secrets.py` passed, and `git diff --check` passed.
- Remaining risk: the installer intentionally stops the running desktop app during upgrade; users must reopen 小黑子 after a manual reinstall if the installer does not auto-launch it.

## 2026-06-16 - attachment return installed-app screenshot verification

- Task: complete screenshot-level verification for the attachment-return redesign and prepare the validated branch for PR.
- Files touched: delivery product-layer code/tests, desktop Tauri config/build scripts, updater-release scripts/tests, desktop update UI files, `lilsunspot/desktop/src-tauri/tauri.conf.json`, and this memory file.
- Decision/result: verified that existing attachment return is driven by the LLM calling `lilsunspot_return_attachment`, while the backend performs real attachment delivery through sanitized `assistant_message.attachments`. The visible assistant text came from the model; no `MEDIA:` or `lilsunspot-attachment://` text was accepted as a successful attachment return.
- Decision/result: local updater artifacts remain disabled for default NSIS builds, so `setup.exe` can be rebuilt without a Tauri updater signing key. The desktop window now records a minimum configured size matching the designed desktop viewport.
- Validation: live installed daemon chat succeeded with the stored local provider config; live desktop image upload/return produced one delivered assistant attachment and no internal URI leak; CDP screenshot verification captured the assistant return card at `ignored/visual-qa/screenshots/20260616-010548/dev-qa-assistant-return-card-1200x820.png`; fresh installed-app screenshot captured `ignored/visual-qa/screenshots/20260616-011642/installed-fresh-960x680.png`; the temporary QA conversation was deleted after screenshots.
- Validation: focused pytest 20 passed, `scripts/check.ps1` passed with daemon 119 passed plus secret guard and desktop build, `python scripts/guard_no_secrets.py` passed, `git diff --check` passed, and `npm run tauri:build --prefix lilsunspot/desktop` produced `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe` at 56,646,965 bytes with no `.sig` or `latest.json`.
- Remaining risk: Weixin was validated through fake-adapter tests only; no live Weixin scan/contact send was performed in this pass. Programmatic Win32 `SetWindowPos` can still force any size and is not used as the manual resize acceptance signal.

## 2026-06-16 - local setup build isolated from updater artifacts

- Task: disable updater artifacts for the default local NSIS build so current-code `setup.exe` does not require Tauri updater signing key.
- Files touched: `lilsunspot/desktop/src-tauri/tauri.conf.json`, `scripts/build_lilsunspot_desktop_nsis.ps1`, `scripts/check_release.ps1`, updater/release static tests, and this memory file.
- Decision/result: default Tauri config now sets `bundle.createUpdaterArtifacts=false`. The NSIS build script still moves stale installers out of the current output directory, but only requires `TAURI_SIGNING_PRIVATE_KEY` / `.sig` when updater artifacts are explicitly enabled. Release check now reports updater artifacts disabled instead of failing on missing `.sig`.
- Validation: focused updater/release static pytest passed, secret guard passed, `git diff --check` passed, `npm run tauri:build --prefix lilsunspot/desktop` passed without updater key, and `scripts/check.ps1` passed with daemon 119 passed plus desktop build.
- Resulting installer: fresh local setup exists at `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`, timestamp 2026-06-16 00:30:19 +08:00, size 56,646,075 bytes. No updater `.sig` is expected for this local build.

## 2026-06-16 - stale setup artifact cleanup on failed NSIS build

- Task: fix the unsafe state where a failed fresh `tauri:build` could leave an older `Lilsunspot_*_x64-setup.exe` in the NSIS output directory.
- Files touched: `scripts/build_lilsunspot_desktop_nsis.ps1`, `lilsunspot/tests/test_lilsunspot_updater_release_plan.py`, and this memory file.
- Decision/result: the NSIS build script now clears stale `Lilsunspot_*_x64-setup.exe` and `.sig` artifacts inside the repository output directory before checking updater signing env or starting Tauri. If signing env is missing, the build still fails, but there is no old installer left to mistake for a current deliverable.
- Validation: ran `npm run tauri:build --prefix lilsunspot/desktop` with signing env cleared and confirmed the expected signing failure removed the old installer; `Test-Path` for `Lilsunspot_0.1.0_x64-setup.exe` returned false. Focused updater/release pytest passed with `--timeout-method=thread`; secret guard and `git diff --check` passed.
- Remaining risk: no fresh setup.exe exists until `TAURI_SIGNING_PRIVATE_KEY` or `TAURI_SIGNING_PRIVATE_KEY_PATH` is supplied and the installer build succeeds.

## 2026-06-15 - attachment return tool-action redesign

- Task: implement v2 attachment return redesign so existing附件返还 is a structured product-layer tool action, not model正文 `MEDIA:` / `lilsunspot-attachment://` parsing.
- Files touched: `lilsunspot/daemon/delivery_actions.py`, `delivery_tools.py`, `agent_runner.py`, `media_delivery.py`, `app.py`, `gateway.py`, `turn_coalescer.py`, `weixin_runtime.py`, daemon test fixtures/tests, and this memory file.
- Decision/result: added the internal `lilsunspot_delivery` toolset and `lilsunspot_return_attachment` handler with per-turn context, conversation/path validation, duplicate action handling, and redacted action output. Prompts now expose only structured attachment fields; desktop and Weixin收口 consume delivery actions; internal attachment URI output is stripped and recorded as `invalid_delivery_output` without返还成功. Generated safe local `MEDIA:<path>` files still use the existing Hermes-compatible path delivery.
- Validation: focused conversation delivery tests passed, Hermes compatibility tests passed, `scripts/check.ps1` passed with daemon 119 passed plus secret guard and desktop web build, `python scripts/guard_no_secrets.py` passed, and `git diff --check` passed.
- Remaining risk: fresh `npm run tauri:build --prefix lilsunspot/desktop` is blocked by the current updater-signing gate requiring `TAURI_SIGNING_PRIVATE_KEY` or `TAURI_SIGNING_PRIVATE_KEY_PATH`; an older `Lilsunspot_0.1.0_x64-setup.exe` exists but was not rebuilt for this task.

## 2026-06-15 - attachment return markdown URI parsing

- Task: fix assistant attachment return when the model wraps `lilsunspot-attachment://` as a Markdown image/link, and ensure the Weixin same-channel path can return images.
- Files touched: `lilsunspot/daemon/media_delivery.py`, `lilsunspot/daemon/tests/test_conversation_sync.py`, and this memory file.
- Decision/result: extended the canonical backend delivery parser to accept Markdown image/link wrappers around `lilsunspot-attachment://att_*` and still route through the existing same-conversation safety validation, visible-text cleanup, assistant attachment-card registration, and Weixin outbound `MEDIA:<safe_path>` generation. No frontend fallback was added.
- Validation: focused desktop attachment return and Weixin image return tests passed; `scripts/check.ps1` passed with daemon 115 passed, secret guard, and desktop build. Rebuilt NSIS with updater artifacts, silently installed it to `%LOCALAPPDATA%\Lilsunspot`, and installed-app smoke passed with an isolated data dir.
- Remaining risk: manual verification should still confirm the returned image card renders in the real desktop conversation and the Weixin adapter sends the generated image through the live account. The local staging updater private key used only for rebuilding this installer was removed after the build.

## 2026-06-15 - Tauri updater and Hermes sync release scaffolding

- Task: implement the Hermes core sync and Tauri updater plan for the Windows product line.
- Files touched: Tauri config/Cargo/Rust entry, desktop update API/types/settings/AppShell/CSS, `scripts/hermes_upstream_sync.ps1`, release/build scripts, release workflow, script/config tests, and this memory file.
- Decision/result: added Tauri updater configuration with fixed manifest endpoint `https://updates.lilsunspot.com/lilsunspot/windows/latest.json`, NSIS updater artifacts, passive install mode, Rust commands for check/download-install/dismiss, local-only dismissed-version persistence, and a Chinese app update card in startup/settings. Added a dirty-tree-refusing maintainer sync wrapper that creates `codex/upstream-sync-YYYYMMDD`, generates reports, merges `upstream/main`, updates `lilsunspot/UPSTREAM_COMMIT.txt`, and reruns the upstream gap report.
- Decision/result: added `scripts/build_lilsunspot_release.ps1` plus `.github/workflows/lilsunspot-release.yml` to produce `setup.exe`, `.sig`, SHA256, `latest.json`, and mirror-upload-ready artifacts. Production release is blocked unless Authenticode is valid; staging builds can proceed without Authenticode but still require Tauri updater signing key material.
- Validation: focused updater/release static pytest passed, cargo check/test passed, desktop build passed, Tauri NSIS build passed and produced `Lilsunspot_0.1.0_x64-setup.exe` plus `.sig`, release script smoke produced `latest.json` and SHA256, secret guard passed, `git diff --check` passed, `scripts/check.ps1` passed, and `scripts/check_release.ps1` passed with updater signing env configured.
- Remaining risk: production CDN/DNS/upload credentials and Windows Authenticode certificate signing are not configured in the repository; the committed updater pubkey is a staging key and must be replaced to match the CI private key secret before a public release. The temporary local staging private key used for validation was removed after the build. Installed-app update install/ restart flow still needs manual old-to-new version acceptance.

## 2026-06-15 - capability truth audit and upstream gap report

- Task: implement the first Hermes capability真实性 slice from the new audit plan.
- Files touched: `lilsunspot/daemon/capabilities.py`, `lilsunspot/daemon/product_features.py`, new `lilsunspot/daemon/upstream_audit.py`, `scripts/hermes_upstream_check.ps1`, focused tests, `lilsunspot/notes/upstream-sync-reports/2026-06-15-041744.md`, and this memory file.
- Decision/result: `/capabilities` now keeps existing status fields but adds `registered/configured/executable/verified/source_of_truth/last_verified_at`; `/capabilities/{id}/test` returns layered checks instead of generic success. Doctor repair, reminder scheduling, product memory prompt injection, and product capability switches are explicitly represented as placeholder/CRUD/unverified rather than real executable Hermes capabilities.
- Decision/result: the upstream audit helper compares cached `upstream/main` against the local worktree without fetch or merge. The generated report confirms latest upstream `32899279a744805350be891ccf3ae08289efc702`, recorded base `2b768535c9ba2a8d3b2c23fae1ee3a2f827f7f49`, missing `context_engine`, and missing DEFAULT_CONFIG keys `gateway`, `tools`, and `paste_collapse_*`.
- Validation: helper CLI and `py_compile` passed; focused capability/product/upstream pytest passed; script smoke generated the upstream report; `git diff --check`, secret guard, `scripts/check.ps1`, desktop build, sidecar build, and NSIS build passed.
- Remaining risk: this did not sync Hermes core, update `UPSTREAM_COMMIT.txt`, add a controlled sync branch script, or implement the Tauri updater. Installed-app UI clicking and live capability smoke remain manual acceptance items.

## 2026-06-14 - save-success onboarding refresh is non-blocking

- Task: re-locate and fix the first-start error shown after saving the main AI service.
- Files touched: `lilsunspot/desktop/src/features/onboarding/OnboardingFlow.tsx`, `lilsunspot/desktop/src/features/onboarding/ApiKeyStep.tsx`, `lilsunspot/desktop/src/features/model/ModelReconfigurePanel.tsx`, `lilsunspot/desktop/src/api.ts`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: local log evidence showed `provider saved provider=deepseek model=deepseek-chat`, so the save itself succeeded. The user-visible failure came from post-save capability/UI refresh being rendered as the blocking `当前步骤没有完成` error. First-start save now treats capability refresh and later UI refresh as non-blocking after `saveProvider()` succeeds; it shows an inline notice and continues to the next step. Reconfigure save now behaves the same way. Tauri string errors are no longer collapsed into generic `请求失败，请稍后再试。`.
- Validation: desktop build passed, focused auth/provider pytest 9 passed, `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` passed with daemon 110 passed plus secret guard and desktop build, and `npm run tauri:build --prefix lilsunspot/desktop` produced the NSIS setup.exe at 55,805,640 bytes.
- Remaining risk: the fixed installer was built but not installed and clicked through in the live app during this pass.

## 2026-06-14 - vision provider key-page matching

- Task: fix the image-recognition settings UI so its key-page jump matches the selected vision provider independently from the main chat provider.
- Files touched: `lilsunspot/desktop/src/features/model/VisionModelPanel.tsx`, `lilsunspot/desktop/src/App.css`, `lilsunspot/daemon/app.py`, `lilsunspot/daemon/tests/test_auth_and_provider.py`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: the vision panel now shows a provider-specific key/help button and calls `openProviderKeyUrl(selectedVisionProvider.id)` only for the currently selected image-recognition service. The helper text states it will not jump to the main chat model provider. The backend `/providers/open-key-url` no longer falls back to `detect_url`, so an API Base URL cannot be opened as a mistaken website.
- Validation: focused auth/provider pytest 9 passed, desktop build passed, `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` passed with daemon 110 passed plus secret guard and desktop build, and `npm run tauri:build --prefix lilsunspot/desktop` produced the NSIS setup.exe at 55,800,847 bytes.
- Remaining risk: the new button was not manually clicked in the installed app after the NSIS build; visual screenshot-level acceptance for 390px width was not rerun.

## 2026-06-14 - local AI key reset button

- Task: add a user-facing way to clear saved local AI keys and return directly to the first-start setup flow.
- Files touched: `lilsunspot/daemon/hermes_runtime.py`, `lilsunspot/daemon/app.py`, `lilsunspot/daemon/tests/test_auth_and_provider.py`, desktop API/types/app/settings/model files, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: added token-protected `POST /providers/reset-local`, which removes known provider registry env keys from Hermes `.env`, clears main model/fallback/routing/auxiliary vision/capability verification config, and returns sanitized bootstrap state. The model settings page now shows `清除本机 AI Key` for configured installs; after confirmation it calls the reset endpoint, closes settings, refreshes bootstrap, and opens the first-start onboarding from the beginning. Chat records, attachments, runtime token, Weixin credentials, and non-model local data are intentionally left intact.
- Validation: focused auth/provider pytest 8 passed, related auth/capability/product pytest 25 passed, `npm run build --prefix lilsunspot/desktop` passed, `python scripts/guard_no_secrets.py` passed, `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` passed with daemon 109 passed, `git diff --check` had only LF/CRLF warnings, and `npm run tauri:build --prefix lilsunspot/desktop` produced `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe` at 55,806,149 bytes.
- Remaining risk: this was not manually clicked in the installed app after building; real user data reset should still be tested once in the UI before relying on it for repeated first-start rehearsals.

## 2026-06-14 - Current full-chain media delivery and onboarding merge

- Task: implement the Current full-chain refactor slice for service configuration, capability-driven image setup, desktop attachment return, Weixin media delivery, and front-end false-failure handling.
- Files touched: `lilsunspot/daemon/media_delivery.py`, daemon app/gateway/coalescer/agent/attachment/conversation modules and tests, desktop API/chat/onboarding/CSS files, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: added a product-layer media delivery service that parses Hermes `MEDIA:` plus `MEDIA:lilsunspot-attachment://<attachment_id>`, strips internal markers from visible assistant text, validates conversation ownership and safe paths, registers assistant attachment cards, and records only sanitized `delivery.status/count/reason_code` metadata. Weixin route turns now keep Hermes `weixin` platform context and return safe `MEDIA:/...` strings only to the official adapter path. First-run model setup now keeps image recognition configuration in the same service page, and chat sends use a longer timeout without creating unreconcilable local assistant failure bubbles.
- Validation: focused conversation tests passed, focused capability/product/chat tests passed, daemon test suite passed, product tests passed, desktop build passed, secret guard passed, `scripts/check.ps1` passed, and `npm run tauri:build --prefix lilsunspot/desktop` produced the NSIS setup.exe. No API Key, runtime token, Weixin credential, private chat body, attachment original content, or full model reply was recorded.
- Remaining risk: installed-app smoke and screenshot-level responsive UI verification have not been automated in this pass.

## 2026-06-13 - Windows desktop shortcut icon overlay investigation

- Task: diagnose the user's desktop screenshot where many desktop shortcuts show the same unexpected overlay/icon.
- Files touched: `lilsunspot/notes/agent-memory.md`.
- Decision/result: local read-only checks found no `Shell Icons\29` override in HKCU/HKLM, and `.lnk` still uses the default Windows icon handler `{00021401-0000-0000-C000-000000000046}`. The lilsunspot installer hook only recreates its own shortcut and does not write global Shell Icons or overlay-handler registry values. The visible pattern affects shortcut rendering more than actual application/file associations, so the likely cause is Explorer icon/overlay cache corruption or a third-party overlay cache issue, not a project code change.
- Validation: read-only registry queries, shortcut metadata summary, and repository search for global shell icon/overlay writes. No system settings were changed.
- Remaining risk: the fix was not applied in this task because rebuilding the icon cache requires restarting Explorer and briefly disrupting the desktop.

## 2026-06-13 - LIL-CAPABILITY-ORCHESTRATION-01A capability graph and auxiliary vision loop

- Task: implement the first capability-orchestration slice so model settings, onboarding, chat attachments, Weixin image ingress, and diagnostics share one product capability state while the image path can use a real auxiliary vision model when the main chat model is text-only.
- Files touched: `TASKS.md`, new `lilsunspot/daemon/capability_graph.py`, daemon API/product/capability/chat/attachment/conversation modules, focused daemon tests, desktop API/types/chat/settings/model/CSS files, and this memory file.
- Decision/result: added a token-protected `/capability-graph` and extended `/providers/capabilities` with graph-derived image fields while keeping legacy fields. `chat.text`, `image.read`, `file.read`, `mode.adjust`, `weixin.receive`, and `weixin.send_file` now expose `status`, `source`, `blocking_reason`, `user_message_cn`, `next_actions`, and `last_verified_at`. Image uploads now prefer native main-model vision, otherwise call configured `auxiliary.vision` for a Chinese summary before the main chat answer. Attachment metadata records only sanitized recognition backend/stage/error code; successful recognition marks `recognized`, failures remain `preview_only`.
- Validation: focused graph/image tests passed, daemon tests passed, product tests passed, desktop build passed, `python scripts/guard_no_secrets.py` passed, `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` passed, and `git diff --check` passed. A targeted live smoke reached the real DeepSeek text-model plus Qwen auxiliary-vision path without logging secrets, attachment content, private text, or full model replies, but the available DashScope key was classified as `invalid_key`.
- Remaining risk: `npm run tauri:build --prefix lilsunspot/desktop` and direct sidecar rebuild are blocked by repeated PyPI TLS handshake EOF while `uv` fetches PyInstaller dependencies, so no fresh NSIS setup was produced in this pass. A real `recognized` live smoke still needs a valid vision provider key, and screenshot-level UI acceptance was not rerun in this pass.

## 2026-06-13 - record attachment composer clearing expectation

- Task: record the user's feedback that after sending an image, the attachment composer should not keep the sent image around.
- Files touched: `TASKS.md`, `lilsunspot/notes/model-capability-ux-plan.md`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: added attachment composer clearing to the capability orchestration task and UX plan. The expected behavior is: once a send request is accepted, the input/composer attachment queue clears; the sent message keeps its attachment card in history; if sending fails, pending attachments may be restored so the user can retry. This prevents duplicate sends and avoids confusing users into thinking the image is still unsent.
- Validation: documentation-only change; no product code, screenshot file, API key, runtime token, Weixin credential, private message text, or attachment content was recorded.
- Remaining risk: the UI behavior still needs implementation and visual acceptance.

## 2026-06-13 - holistic model capability UX plan

- Task: record the user's feedback that future work must plan across all models and all user-facing chains instead of narrow patches or brittle keyword triggers.
- Files touched: `TASKS.md`, `lilsunspot/notes/model-capability-ux-plan.md`, `lilsunspot/notes/doc-index.md`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: added a product-level model capability and UX plan covering user behavior assumptions, unified capability graph, structured intent routing, model orchestration, proactive onboarding, error taxonomy, validation matrix, and phased delivery. `TASKS.md` now points to `LIL-CAPABILITY-ORCHESTRATION-01` as the next top-priority task, with the vision-provider issue treated as the first slice of a broader capability orchestration fix. The plan explicitly rejects keyword-based mode handling and single-page patching as sufficient.
- Validation: documentation-only change; no product code, screenshot file, API key, runtime token, Weixin credential, private message text, or attachment content was recorded.
- Remaining risk: the plan still needs implementation and live validation with safe test credentials across providers, desktop, Weixin, and installed-app flows.

## 2026-06-13 - record vision save versus recognition mismatch

- Task: analyze the user's screenshots showing an unexplained chat failure and a saved Qwen vision model that still does not recognize uploaded images, then record the findings as a follow-up task without changing product code.
- Files touched: `TASKS.md` and `lilsunspot/notes/agent-memory.md`.
- Decision/result: local code inspection indicates two likely product issues. First, the settings/capabilities path treats `auxiliary.vision` as image recognition available, so the UI can show “图片识别已可用”. Second, the actual attachment recognition path calls `describe_image_data_url()`, which currently rejects non-native main models via `image_supports_native` and then only sends `image_url` to the main chat model. That explains the mismatch where `qwen-vl-max` is saved but the chat answer still says `qwen-plus` cannot understand images. The generic failure bubble also hides the failing stage and error code, so users cannot tell whether the problem is Key, quota, model name, Base URL, provider HTTP, auxiliary vision, or agent loop.
- Validation: documentation-only change after local source inspection; no product code, screenshot file, API key, runtime token, or private data was recorded.
- Remaining risk: this is a code-path analysis, not a live provider repro. The next implementation task should verify with safe test credentials and visual acceptance.

## 2026-06-13 - record vision provider guide follow-up

- Task: record the user's screenshot feedback as the next task instead of implementing it immediately.
- Files touched: `TASKS.md` and `lilsunspot/notes/agent-memory.md`.
- Decision/result: added `LIL-VISION-PROVIDER-GUIDE-01` at the top of `Next` to improve the image-recognition model setup UX. The task asks for official provider links, plain guidance for getting keys and choosing models, Base URL explanation, safe saved-key handling, and acceptance coverage for Qwen/DashScope, misclicks, repeat saves, continue-text-chat, and 390x760 mobile layout.
- Validation: documentation-only change; no product code, screenshot file, API key, runtime token, or private data was recorded.
- Remaining risk: official links and provider-specific wording still need implementation and current-source verification when the task is picked up.

## 2026-06-12 - LIL-VISION-ONBOARDING-01 model vision onboarding

- Task: start the next Current/Next task and improve the model-selection experience from a normal-user perspective, including visual acceptance and user misclick testing.
- Files touched: `TASKS.md`, `lilsunspot/resources/provider_registry.yaml`, `lilsunspot/daemon/hermes_runtime.py`, `product_features.py`, capability/product tests, desktop model/onboarding API/types/CSS files, new `VisionModelPanel.tsx`, new `VisionOnboardingStep.tsx`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: after saving the main chat model, onboarding now reuses `/providers/capabilities` and Hermes image-routing status to decide whether image recognition is available. Text-only main models show “当前模型不能直接识别图片” before chat, with clear paths to continue text chat or add a separate image-recognition model through Hermes `auxiliary.vision`. The shared vision-model panel is reused in onboarding and settings, preserves existing auxiliary config when saving main provider settings, redacts keys, and rejects empty/misclicked saves with plain Chinese errors.
- Validation: focused capabilities/product pytest 12 passed, daemon pytest 98 passed, product pytest 38 passed, `npm run build --prefix lilsunspot/desktop`, `python scripts/guard_no_secrets.py`, `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`, `git diff --check`, local Chrome/CDP visual acceptance at 960x680 and 390x760 including double-click continue, empty save, and missing cloud API key, and `npm run tauri:build --prefix lilsunspot/desktop` passed. NSIS setup exists at `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`.
- Remaining risk: no real vision-provider API call or freshly installed NSIS click-through was run in this pass. Visual screenshots and mock daemon data stayed under ignored temporary directories. No API key, runtime token, Weixin credential, private message text, screenshot, or attachment content was recorded in repo memory.

## 2026-06-12 - auxiliary vision model desktop settings

- Task: expose the Hermes official auxiliary vision-model path so users can configure image recognition separately when the main chat model is text-only.
- Files touched: `lilsunspot/daemon/hermes_runtime.py`, `app.py`, capability/product tests, desktop model settings API/types/CSS, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: lilsunspot now saves image recognition settings into Hermes `auxiliary.vision`, while preserving the user's lilsunspot provider id under `lilsunspot.auxiliary.vision` for UI display. Cloud vision providers require an API key the first time; provider base URLs and Hermes provider ids are normalized through the existing provider registry. The desktop model settings drawer now has a "图片识别模型" panel for OpenRouter, OpenAI-compatible, Qwen, and local Ollama/LLaVA-style services, plus a clear action to return to no separate vision model. Hermes core was not rewritten.
- Validation: focused auxiliary-vision pytest passed, related daemon/product/API pytest 22 passed, and desktop TypeScript/Vite build passed before the full check/build stage.
- Remaining risk: no real provider API call or installed-app image upload smoke test was run with live credentials in this automated pass. No API key, runtime token, Weixin credential, private message text, screenshot, or attachment content was recorded.

## 2026-06-12 - capability registry prompt alignment and desktop uploads

- Task: replace the image-specific ability prompt with a generic Hermes-backed capability snapshot for chat answers, then add desktop attachment upload for images and other files.
- Files touched: `lilsunspot/daemon/chat_client.py`, `agent_runner.py`, `capabilities.py`, `product_features.py`, `app.py`, `attachments.py`, desktop chat API/UI/CSS files, daemon/product tests, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: confirmed Hermes already has official model/tool/image-routing sources (`tools_config`, `models_dev`, `image_routing`, and `vision_analyze`). Removed the lilsunspot image-only system prompt and model-name heuristic; agent turns now receive a generic snapshot generated from the same `/capabilities` registry, with current provider/model and the desktop upload entry represented as an enabled product runtime capability. Desktop chat can now upload up to 5 local attachments, stores them under the safe attachment directory, summarizes supported file types, and runs existing image recognition only when the configured vision backend supports it. Hermes core was not rewritten.
- Validation: focused upload/capability pytest passed, broader focused daemon/product pytest passed, `python -m pytest lilsunspot/tests --timeout-method=thread --basetemp .tmp-pytest-product-full` passed with 38 tests, `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` passed, `git diff --check` returned only CRLF warnings, sidecar rebuild passed, and `npm run tauri:build --prefix lilsunspot/desktop` produced the NSIS setup artifact at 55,764,782 bytes.
- Remaining risk: browser screenshot QA was not available through the Browser plugin in this session, so the installed app still needs one manual upload smoke test with real local files and the user's configured model credentials. No API key, runtime token, Weixin credential, private message text, screenshot, or attachment content was recorded.

- Task: prepare the local Hermes capability work for PR after `develop` was already in a merge with `origin/develop`.
- Files touched: conflict resolution in `TASKS.md`, `lilsunspot/daemon/app.py`, `lilsunspot/daemon/tests/conftest.py`, `lilsunspot/desktop/src/App.css`, `lilsunspot/desktop/src/api.ts`, `SettingsDrawer.tsx`, `types.ts`, `scripts/guard_no_secrets.py`, and this memory file.
- Decision/result: resolved conflicts with local Hermes full-capability behavior as the primary source. Kept `/capabilities` for the Hermes capability center and moved the lightweight product-control capability toggles to `/product/capabilities`; kept independent settings pages for Hermes capability center, safety audit/approval, diagnostics export, and the upstream control center.
- Validation: focused capability/product/safety pytest 14 passed, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` passed with daemon pytest 93 passed plus secret guard and desktop build, product pytest 38 passed with `--timeout-method=thread`, Tauri Rust tests 2 passed, `cargo check` passed, and `npm run tauri:build --prefix lilsunspot/desktop` produced the NSIS setup artifact. No API key, runtime token, Weixin credential, private message text, QR, or attachment content was recorded.

## 2026-06-12 - LIL-HERMES-FULL-01 screenshot-level frontend QA retry

- Task: rerun screenshot-level frontend acceptance for the integrated Hermes capability work and fix rendered UI bugs found during Browser IAB validation.
- Files touched: `TASKS.md`, `lilsunspot/desktop/src/app/AppShell.tsx`, `lilsunspot/desktop/src/App.css`, `lilsunspot/desktop/src/api.ts`, `lilsunspot/desktop/src/features/settings/CapabilitySettings.tsx`, and this memory file.
- Decision/result: fixed the capability center crash on partial/older capability payloads by normalizing optional string lists and fallback source labels; preserved capability test messages after reload; fixed duplicate dependency keys; allowed browser dev runs to target an isolated daemon URL without touching production Tauri discovery; hid the development token panel after successful dev connection; and changed mobile capability cards to stack action buttons below content.
- Validation: Browser IAB covered 960x680 and 390x760 ability center, ability test, diagnostics export, and safety audit flows with 84 capability cards and 84 check buttons, no framework overlay, no current-run console errors or warnings, and no horizontal overflow. `npm run build --prefix lilsunspot/desktop`, `python -m pytest lilsunspot/daemon/tests -q`, `python scripts/guard_no_secrets.py`, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`, `git diff --check`, and `npm run tauri:build --prefix lilsunspot/desktop` passed. Final NSIS setup artifact exists at 62,262,130 bytes.
- Remaining risk: automated screenshot QA used the Vite dev UI against an isolated local daemon, not a freshly installed NSIS app click-through with real credentials or Weixin media. Screenshots were not committed or recorded in repository memory, and no API key, runtime token, Weixin credential, private message text, QR, or attachment content was recorded.

## 2026-06-12 - LIL-HERMES-FULL-01 Hermes local capability integration

- Task: expose local Hermes capabilities through lilsunspot as one integrated capability center, with config bridge, audit, diagnostics, and upstream sync strategy.
- Files touched: `TASKS.md`, daemon capability/audit/diagnostics/runtime/API modules, desktop settings/API/types/CSS, focused daemon tests, safety approval tests, secret guard, GitHub upstream-sync workflow, PR template, and this memory file.
- Decision/result: lilsunspot now has a product-layer capability registry over local Hermes `TOOLSETS`, configurable toolsets, and config surfaces; protected APIs for capability/model/toolset/MCP config; `audit.db`; diagnostics zip export; explicit agent-loop toolset/fallback loading; desktop capability UI; and a scheduled/manual upstream sync PR workflow. Audit, approval, diagnostics, and public config views share stronger redaction for sensitive fields and inline command/header/token argument forms. Hermes core was not rewritten.
- Validation: focused capabilities/safety pytest 9 passed, daemon pytest 67 passed, product pytest 35 passed, secret guard passed, `pwsh -NoProfile -File scripts/check.ps1` passed, `git diff --check` returned only CRLF warnings, sidecar build passed, and `npm run tauri:build --prefix lilsunspot/desktop` produced `Lilsunspot_0.1.0_x64-setup.exe` at 62,251,338 bytes.
- Remaining risk: high-risk tool execution uses Hermes approval surfaces plus lilsunspot audit/approval bridges, but real external-provider/tool/manual installed-app acceptance still depends on configured credentials and local dependencies. GitHub Actions upstream-sync still needs a first remote `workflow_dispatch` run. No secrets, runtime token, Weixin credentials, private message text, screenshots, or attachment contents were recorded.

## 2026-06-10

- Task: re-check code and prepare the Weixin multi-conversation work for PR.
- Files touched: `lilsunspot/notes/agent-memory.md` plus the existing task scope for conversation sync, Weixin runtime, desktop chat, mode/attachment support, tests, and packaging.
- Decision/result: local review confirmed the PR scope is the current `develop` worktree feature set rather than only the final small route-key patch, because `gateway.py`, `ChatHome.tsx`, and the new conversation store depend on earlier uncommitted LIL-P2 changes. CodeRabbit CLI was not installed, and the required install command timed out after 184 seconds, so external CodeRabbit review was not available.
- Validation: route/account-id and explicit Weixin active-conversation paths were re-inspected with `rg`; `pwsh -NoProfile -File scripts/check.ps1` passed with daemon pytest 63 passed, secret guard, and desktop build; `npm run tauri:build --prefix lilsunspot/desktop` passed and regenerated `Lilsunspot_0.1.0_x64-setup.exe` at 62,219,830 bytes.
- Remaining risk: PR review will still need human inspection for the broad combined feature diff. No API Key, runtime token, Weixin credential, QR, screenshot, or private message content was recorded.

- Task: implement explicit Weixin-to-conversation binding for multi-conversation desktop chat.
- Files touched: `TASKS.md`, `lilsunspot/daemon/conversations.py`, `gateway.py`, `weixin_runtime.py`, `lilsunspot/daemon/tests/test_conversation_sync.py`, desktop `features/chat/ChatHome.tsx`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: desktop "新建" now remains desktop-only and cannot steal the Weixin inbound route. Weixin private messages keep routing to the active Weixin conversation for that route; users must explicitly use "新开此微信对话" or "设为当前" to change where future Weixin messages land. Weixin route keys now include `account_id` when available, while old no-account route keys still work.
- Validation: preferred `ignored/codex-venv` lacked `pytest`, so validation used system Python 3.11 via `py -3`. Focused conversation pytest 22 passed, daemon pytest 63 passed, product pytest 35 passed, desktop TypeScript/Vite build passed, secret guard passed, `pwsh -NoProfile -File scripts/check.ps1` passed, `git diff --check` returned only CRLF warnings, and `npm run tauri:build --prefix lilsunspot/desktop` produced `Lilsunspot_0.1.0_x64-setup.exe` at 62,214,241 bytes.
- Remaining risk: automated checks use fake Weixin events and mocked agent replies; a real installed-app click-through should still verify switching active Weixin conversations while a live Weixin account is connected. No API Key, runtime token, Weixin credential, QR, screenshot, or private message content was recorded.

- Task: rebuild the Hermes agent boundary and add desktop multi-conversation support.
- Files touched: `lilsunspot/daemon/agent_runner.py`, `conversations.py`, `app.py`, `gateway.py`, `safety.py`, `hermes_compat.py`, `default_safety_policy.yaml`, sidecar packaging script, daemon/product tests, desktop `api.ts`, `features/chat/ChatHome.tsx`, and `App.css`.
- Decision/result: normal desktop chat, `/chat/send`, and real Weixin private-message replies now route through in-process Hermes `AIAgent.run_conversation()` with one Hermes `SessionDB` session per lilsunspot conversation. The old provider adapter is left for low-level provider/recognition checks instead of user chat. Added conversation CRUD/archive/delete APIs, compact desktop conversation management, Weixin active-thread routing per contact, Hermes tool-approval bridging into existing lilsunspot approvals, and packaged the required Hermes agent-loop modules into the sidecar.
- Validation: focused agent/chat/compat/safety/conversation pytest 39 passed, daemon pytest 61 passed, product pytest 35 passed, desktop TypeScript/Vite build passed, secret guard passed, `git diff --check` returned only CRLF warnings, `pwsh -NoProfile -File scripts/check.ps1` passed, `npm run tauri:build --prefix lilsunspot/desktop` produced `Lilsunspot_0.1.0_x64-setup.exe`, packaged sidecar smoke passed `/health` and Hermes compatibility on an isolated port, and CDP mock UI checks at 960x680 plus 390x760 showed no horizontal overflow.
- Remaining risk: CDP visual QA used mocked daemon responses, not a clean installed-app click-through with real user data; live real-provider multi-turn memory and real Weixin active-thread behavior still need manual acceptance after installation. No API Key, runtime token, Weixin credential, QR, screenshot, or private message content was recorded.

- Task: rebuild mode as fixed presets plus custom and remove the standalone MD UI.
- Files touched: `TASKS.md`, `lilsunspot/resources/default_mode_profiles.yaml`, `lilsunspot/daemon/modes.py`, `mode_intents.py`, `prompt_compiler.py`, `chat_client.py`, mode/conversation tests, desktop `AppShell.tsx`, `ChatHome.tsx`, `ModeQuickPanel.tsx`, `SettingsDrawer.tsx`, `App.css`, deleted `ModeSettings.tsx`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: mode is now an isolated parameter layer with four choices: `pragmatic`, `balanced`, `emotional`, and `custom`. Fixed presets use their configured defaults; any manual slider change or semantic slider intent saves as `custom`, and old mismatched fixed-mode state reads as `custom`. Removed the left-side `MD 模式` page, the settings-drawer output-mode tab, the old safety mini panel/runtime line from the chat sidebar, and replaced that area with the real-time preview card.
- Validation: focused mode/conversation pytest 29 passed, daemon pytest 58 passed, product pytest 35 passed, desktop build passed, headless Chrome/CDP mock Tauri screenshot verified four mode buttons, no MD nav, no safety mini panel/runtime line, and no horizontal overflow; secret guard passed, `pwsh -NoProfile -File scripts/check.ps1` passed, `git diff --check` returned only CRLF warnings, and `npm run tauri:build --prefix lilsunspot/desktop` produced `Lilsunspot_0.1.0_x64-setup.exe`.
- Remaining risk: CDP visual verification used mocked local API responses, not a real installed-app click session with the user's live daemon state; the chat engine is still `lilsunspot_provider_adapter`, not the full Hermes agent loop.

- Task: remove product-layer file/attachment text interception from chat paths.
- Files touched: `TASKS.md`, `lilsunspot/daemon/app.py`, `lilsunspot/daemon/gateway.py`, `lilsunspot/daemon/hermes_compat.py`, `lilsunspot/daemon/tests/test_hermes_compat.py`, `lilsunspot/daemon/tests/test_conversation_sync.py`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: mode routing remains the only pre-chat semantic product layer, and it only decides whether to adjust mode state. Attachment capability questions, "send this Word to me", and "generate a Word document and send it" no longer use keyword-based product interception or create approvals from plain chat text; if they do not trigger mode, they fall through to normal chat. Explicit Weixin sending still uses `/gateway/weixin/send` to create a `send_weixin_message` approval, and approval delivery still calls official Hermes adapter methods.
- Validation: focused Hermes/conversation pytest 6 passed, daemon pytest 57 passed, product pytest 34 passed, desktop build passed, grep found no remaining old file-interception router symbols in product/test/desktop code, secret guard passed, `pwsh -NoProfile -File scripts/check.ps1` passed, `git diff --check` returned only CRLF warnings, and `npm run tauri:build --prefix lilsunspot/desktop` produced `Lilsunspot_0.1.0_x64-setup.exe`.
- Remaining risk: normal chat is still the current `lilsunspot_provider_adapter`, not the full Hermes agent loop; this correction intentionally removes product-layer natural-language file-send routing rather than implementing one-shot artifact generation.

- Task: fix user-reported mode UI desync and wrong Weixin create-and-send file reply.
- Files touched: `TASKS.md`, `lilsunspot/daemon/mode_intents.py`, `lilsunspot/daemon/app.py`, `lilsunspot/daemon/gateway.py`, `lilsunspot/daemon/tests/test_conversation_sync.py`, desktop `features/chat/ChatHome.tsx`, `features/mode/ModeQuickPanel.tsx`, `types.ts`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: natural-language mode switches now reset sliders to the target profile defaults instead of carrying stale values from the previous mode; desktop chat responses include mode-intent state and trigger a shared mode reload so the right-side mode bars catch up even if an event is missed. Fixed the three visible slider labels to product vocabulary. A later correction removed the attempted Weixin create-and-send text interception so file-related chat returns to the normal chat path.
- Validation: focused conversation sync pytest 3 passed, daemon pytest 58 passed, product pytest 34 passed, desktop build passed, built JS label check passed, secret guard passed, `pwsh -NoProfile -File scripts/check.ps1` passed, `git diff --check` returned only CRLF warnings, and `npm run tauri:build --prefix lilsunspot/desktop` produced `Lilsunspot_0.1.0_x64-setup.exe`.
- Remaining risk: automated checks cover the backend state contract, frontend compile output, and text labels; exact installed-app click-through with the user's live daemon/window still needs manual confirmation. This task intentionally did not implement one-shot Word/Excel/PDF generation plus Weixin sending.

- Task: audit lilsunspot/Hermes official interface compatibility and fix attachment capability routing.
- Files touched: `TASKS.md`, `lilsunspot/daemon/hermes_compat.py`, `lilsunspot/daemon/app.py`, `lilsunspot/daemon/doctor.py`, `lilsunspot/daemon/gateway.py`, daemon compat/conversation tests, `lilsunspot/daemon/tests/conftest.py`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: added a product-layer Hermes compatibility report covering provider config shape, official Weixin/BasePlatformAdapter send methods, attachment registry boundaries, mode prompt wrapping, safety approval gating, and doctor/runtime checks. Desktop and Weixin chat now answer attachment capability questions truthfully in product code, while actual file sending still requires safety approval and then calls official adapter methods (`send_image_file()` for images, `send_document()` for documents). Review tightened the capability detector so normal file tasks such as “这个文件可以帮我总结吗” still fall through to chat.
- Validation: focused Hermes compat pytest 5 passed, focused Weixin approval/send pytest 5 passed, daemon pytest 56 passed, product pytest 34 passed, desktop build passed, secret guard passed, `pwsh -NoProfile -File scripts/check.ps1` passed, `git diff --check` returned only CRLF warnings, and `npm run tauri:build --prefix lilsunspot/desktop` produced `Lilsunspot_0.1.0_x64-setup.exe`.
- Remaining risk: compatibility checks prove official interfaces are importable and shaped as expected; they do not replace real installed-app Weixin media/file send acceptance or upstream sync PR review. No API Key, runtime token, Weixin credential, QR, screenshot, or real private message content was recorded.

## 2026-06-09

- Task: fix P0 mode switching when users describe mode changes naturally.
- Files touched: `lilsunspot/daemon/mode_intents.py`, `lilsunspot/daemon/gateway.py`, `lilsunspot/daemon/app.py`, `lilsunspot/daemon/tests/test_conversation_sync.py`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: replaced the natural-language mode switch keyword path with a short-input semantic router that asks the configured provider for structured `chat/query/mode/slider` intent. Weixin and desktop chat now both try this router before normal chat; on a valid route they call the real `select_mode()`, persist mode state, emit `mode.changed`, and return a visible mode reply instead of letting the model merely claim it switched. Invalid JSON, low confidence, provider errors, long input, slash commands, and normal task requests fall through without changing mode.
- Validation: focused conversation sync pytest 13 passed, full daemon pytest 49 passed, product pytest 34 passed, desktop build passed, Tauri `cargo check` passed, secret guard passed, `pwsh -NoProfile -File scripts/check.ps1` passed, `git diff --check` passed with CRLF warnings only, and `npm run tauri:build --prefix lilsunspot/desktop` produced `Lilsunspot_0.1.0_x64-setup.exe` at 2026-06-10 00:09:48 +08:00.
- Remaining risk: the semantic router depends on the currently configured model responding with valid structured JSON; if it fails, the request safely does not change mode. This task intentionally did not change slider labels, adapter-name display, or visual styling.

- Task: move completed Current tasks into Done and verify setup.exe artifact.
- Files touched: `TASKS.md` and `lilsunspot/notes/agent-memory.md`.
- Decision/result: moved completed `LIL-P0-FLOW-UI-01`, `LIL-P0-01`, `LIL-P0-03`, `LIL-P1-01`, and `LIL-P2-01` from Current into a Done subsection. Kept `LIL-P2-02 + LIL-P2-03` in Current because its installed-app Weixin media/file send and tray checks remain listed for manual acceptance. Confirmed NSIS setup artifact exists at `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`, size 62,087,161 bytes, last written 2026-06-09 23:04:18 +08:00.
- Validation: `git diff --check` passed with CRLF warnings only. Documentation/status-only update; no code tests or rebuild were required.
- Remaining risk: setup.exe was verified as present from the earlier build, not rebuilt again during this documentation-only task.

- Task: fix Mode synchronization, truthful image recognition state, and Weixin recent-file send intent.
- Files touched: `TASKS.md`, `lilsunspot/daemon/chat_client.py`, `attachments.py`, `conversations.py`, `gateway.py`, `lilsunspot/daemon/tests/test_conversation_sync.py`, desktop `App.tsx`, `App.css`, `app/AppShell.tsx`, `app/BootGate.tsx`, mode/chat/settings components, `types.ts`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: added a shared desktop `ModeProvider/useModeState` that listens for `mode.changed`; image attachments now distinguish `preview_only` from `recognized`, with optional OpenAI-compatible `image_url` visual summaries and explicit DeepSeek/text-model no-vision copy; Weixin inbound messages persist only `chat_id/user_id/chat_type` routing metadata; "把这个 Word/文件发给我" finds the latest generated safe attachment and creates a `send_weixin_message` approval instead of sending directly or asking the model.
- Validation: focused conversation/media/mode/approval pytest 10 passed, full daemon pytest 46 passed, product pytest 34 passed, desktop TypeScript/Vite build passed, Tauri `cargo check` passed, secret guard passed, `git diff --check` passed with CRLF warnings only, `pwsh -NoProfile -File scripts/check.ps1` passed, `npm run tauri:build --prefix lilsunspot/desktop` produced `Lilsunspot_0.1.0_x64-setup.exe`, and Browser IAB rendered the Vite dev shell in default desktop plus 390x844 mobile screenshots.
- Remaining risk: exact 960x680/390x760 Browser IAB batch screenshots timed out and the follow-up viewport reset call also timed out; CodeRabbit CLI was not installed and the plugin-required install command timed out after 124 seconds, so no CodeRabbit review result was produced; real installed-app Weixin media/file send still needs manual validation. No API Key, runtime token, Weixin credential, QR, or real private message content was recorded.

- Task: diagnose Browser IAB unavailability and complete Weixin refresh fallback UI validation.
- Files touched: `lilsunspot/notes/agent-memory.md`.
- Decision/result: Browser MCP registry only exposed a Chrome extension instance; `agent.browsers.get("iab")` returned `Browser is not available: iab`, so this was not a call-limit failure. Used temporary headless Chromium/CDP request interception against the Vite dev page instead of IAB, leaving the real `127.0.0.1:8765` installed daemon untouched and not recording any real Weixin QR, runtime token, or credential data.
- Validation: CDP smoke loaded the desktop dev UI through mocked local API responses; rapid Weixin refresh validation clicked the refresh button 20 times while mocked Weixin requests were delayed 1.25 seconds. Result: 5 total Weixin requests, `max_concurrent=1`, queued refresh feedback observed, final page remained on the scan view with "等待扫码", and no console errors were captured.
- Remaining risk: this validates browser-rendered dev UI behavior with mocked Weixin responses, not a real installed-app window drag/click session or a live Weixin QR scan.

- Task: fix Weixin scan refresh hang after repeated refresh clicks.
- Files touched: `lilsunspot/daemon/gateway.py`, `lilsunspot/daemon/tests/test_weixin_gateway_login.py`, `lilsunspot/desktop/src/api.ts`, `lilsunspot/desktop/src/features/settings/WeixinSettings.tsx`, `lilsunspot/desktop/src-tauri/src/main.rs`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: Weixin QR requests now use a product-layer 9 second timeout instead of Hermes' longer QR timeout; desktop API calls have per-request timeouts; Tauri `daemon_request` runs through an async blocking task with configurable read timeout; the Weixin UI now skips overlapping poll requests and keeps only one queued manual refresh while preserving stale-response version guards.
- Validation: focused Weixin login pytest 10 passed, desktop TypeScript/Vite build passed, Tauri `cargo check` passed, secret guard passed, `git diff --check` returned only CRLF warnings, `pwsh -NoProfile -File scripts/check.ps1` passed with daemon pytest 43 passed, and `npm run tauri:build --prefix lilsunspot/desktop` produced the NSIS setup.exe.
- Remaining risk: rapid-click behavior still needs installed-app manual acceptance because Browser IAB returned unavailable in this run and no real QR screenshot was captured.

- Task: review and validate `LIL-P2-02 + LIL-P2-03` merged delivery after implementation.
- Files touched: `lilsunspot/daemon/conversations.py`, `lilsunspot/daemon/tests/test_conversation_sync.py`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: aligned attachment event names with the delivery plan by emitting `attachment_registered` and `attachment_summary_updated`, then added focused test assertions for those stored event names. No token or credential fields were added to responses, logs, or fixtures.
- Validation: focused conversation sync pytest 5 passed; full daemon pytest 38 passed; product pytest 34 passed; `npm run build --prefix lilsunspot/desktop` passed; `cargo check --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml` passed; `python scripts/guard_no_secrets.py` passed; `pwsh -NoProfile -File scripts/check.ps1` passed; `git diff --check` returned only CRLF warnings; `npm run tauri:build --prefix lilsunspot/desktop` rebuilt sidecar and NSIS setup.exe; temp installed-app smoke passed with 6 providers.
- Remaining risk: Browser IAB still reports unavailable, so no automated screenshot proof for 960x680/390x760 was captured. Real Weixin media/file sync, approval-to-Weixin file send, and tray close/open/quit still need manual installed-app acceptance.

- Task: implement `LIL-P2-02 + LIL-P2-03` Weixin conversation sync, attachments, natural-language mode UX, Tauri SSE, and tray behavior.
- Files touched: `TASKS.md`, `pyproject.toml`, `uv.lock`, `scripts/build_lilsunspotd_sidecar.ps1`, `lilsunspot/daemon/app.py`, `gateway.py`, `conversations.py`, `attachments.py`, `mode_intents.py`, `modes.py`, `safety.py`, `weixin_runtime.py`, daemon tests, desktop Tauri Rust/Cargo files, desktop chat/API/types/CSS/Weixin UI files, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: added the product SQLite conversation/event/attachment store, token-protected conversation/SSE/attachment APIs, Weixin media registration and summaries, natural-language mode changes with hidden slash compatibility, approval-gated Weixin text/file sending, Tauri SSE header-token bridge, safe attachment opening, and tray close/open/quit behavior. Follow-up review tightened attachment source roots so Weixin credential files are not acceptable attachment inputs, fixed CSV structured summaries when MIME is `text/plain`, improved cross-thread SSE wakeups, and made the Tauri SSE loop rediscover endpoint/token after reconnect failures.
- Validation: focused conversation/media/mode/approval pytest 5 passed, full daemon pytest 38 passed, full product pytest 34 passed, desktop build passed, Rust `cargo check` passed, secret guard passed, `scripts/check.ps1` returned success, `git diff --check` returned only CRLF warnings, Tauri NSIS build passed, and a temporary installed-app smoke passed for setup.exe install, installed sidecar, `127.0.0.1`, `/health`, token-protected `/providers`, and token log guard.
- Remaining risk: Browser IAB was unavailable, so no screenshot-level 960x680/390x760 UI proof was captured. Real Weixin image/PDF/docx/xlsx/csv sync, approval-to-Weixin file send, and tray close/open/quit still need manual installed-app acceptance. `cargo fmt --check` could not run because `rustfmt` is not installed for the local stable toolchain.

- Task: record `LIL-P2-01` manual acceptance.
- Files touched: `TASKS.md`, `lilsunspot/notes/qa-checklist.md`, `lilsunspot/notes/weixin-feasibility.md`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: 用户补充确认 P2-01 安装版 UI 人工校验成功；Markdown 状态已收敛为真实桌面聊天、微信扫码登录、微信端登录、私聊文本回复、`/help`、`/mode` 和安装版 UI 点击均通过。`TASKS.md` 不再把 P2-01 剩余手工验收列入 Next，`qa-checklist.md` 勾选 P2-01 已通过的微信人工项，`weixin-feasibility.md` 从早期“尚未封装真实扫码/私聊”更新为 P2-01 已完成最小真实私聊闭环。
- Validation: documentation-only update; no code, tests, build, or setup.exe run was required.
- Remaining risk: 断线重连、二维码真实过期、微信媒体/文件和命令 UX 小白化仍未实现或未补验，后续分别进入稳定性验证、LIL-P2-02 和 LIL-P2-03。

- Task: research whether Weixin sync/files/PDF should reuse official Hermes gateway strategy.
- Files touched: `lilsunspot/notes/architecture.md`, `TASKS.md`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: 联网和本地源码核对后，判断方向合理：后续不应继续扩展 lilsunspot 的手写微信文字桥，而应转向官方 Hermes gateway-first。官方 `gateway/platforms/weixin.py` 已有 `MessageEvent(media_urls/media_types)`、媒体下载缓存、`send_document()`、`send_image_file()` 和 `MEDIA:<path>` artifact 交付相关能力；lilsunspot 产品层应负责本地会话同步、桌面 UI、审批、脱敏、配置和 setup.exe 打包。
- Validation: research/documentation-only update; no product code implementation was performed. Remaining validation is future setup.exe installed-app smoke with real Weixin file/PDF flows.
- Remaining risk: 不能直接搬官方 CLI 交互；需要设计产品层会话库、artifact/document pipeline 和安全审批，且 iLink 媒体/文件能力必须真机验收。

- Task: fix installed setup.exe Weixin QR scan usability after user feedback.
- Files touched: `lilsunspot/daemon/gateway.py`, `lilsunspot/daemon/tests/test_weixin_gateway_login.py`, `lilsunspot/desktop/src/features/settings/WeixinSettings.tsx`, `lilsunspot/desktop/src/App.css`, `TASKS.md`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: 联网核对 Hermes 官方 Weixin adapter 后确认 `qrcode_img_content` 是完整可扫码 liteapp URL，`qrcode` 只应用于登录状态轮询；后端不再用 `qrcode` fallback 生成误导性二维码，缺少或格式异常时返回中文错误。桌面微信页进入后自动生成真实二维码，真实二维码未返回前只显示空状态，不再画假 QR；命令贴纸改为自然换行，避免安装版窗口里重叠。
- Decision/result: after user confirmed scanning could start but the UI overlapped, split the real QR image box from the scan instruction/actions. The QR container now only renders the QR image or empty state; scan instructions and helper buttons live in a separate metadata panel with low-height sizing rules.
- Decision/result: after user pointed out the right panel was meaningless, removed the developer-facing status timeline and command-sticker block from the Weixin page. The panel now shows a plain current-status card, the next action, and the small set of message forms a user can send after scanning.
- Validation: focused Weixin pytest 7 passed, desktop build passed, Tauri NSIS setup.exe rebuild passed, setup.exe 静默重装到 `%LOCALAPPDATA%\Lilsunspot` passed, installed-app smoke passed, installed Weixin login/start returned `qr_pending` with URL payload host `liteapp.weixin.qq.com` and SVG data URL present without `token/account_id`, secret guard passed, `git diff --check` had only CRLF warnings, and `scripts/check.ps1` passed with daemon pytest 33 passed.
- Validation: UI-overlap and right-panel follow-ups reran focused Weixin pytest 7 passed, desktop build passed, Tauri NSIS setup.exe rebuild passed, and setup.exe was reinstalled to `%LOCALAPPDATA%\Lilsunspot`; the installed Weixin page was opened for user visual recheck without logging QR contents.
- Remaining risk: 真实手机扫码确认、iLink 私聊 `/help`/`/mode`/普通文本闭环、二维码过期和断线重连仍需要用户现场验收；真实二维码不能写入截图、日志或聊天记录。

- Task: record standing project operating rules from the user.
- Files touched: `lilsunspot/notes/agent-memory.md`.
- Decision/result: 后续默认用中文回复；本项目必须把 `setup.exe -> 安装版 Lilsunspot.exe -> 安装版 lilsunspotd.exe` 作为主要使用和验收链路，不能只验证源码开发态或 `dist` 产物。
- Validation: memory-only update; no code validation required.
- Remaining risk: setup.exe 链路仍需要在每次生成安装包后实际安装或 smoke 验证，尤其是微信接入、模型配置和首次启动流程。

- Task: implement `LIL-P2-01` Weixin QR login and real private-chat runtime path.
- Files touched: `TASKS.md`, `pyproject.toml`, `uv.lock`, `scripts/build_lilsunspotd_sidecar.ps1`, `lilsunspot/daemon/app.py`, `gateway.py`, `weixin_runtime.py`, `sidecar_main.py`, daemon/product Weixin and sidecar tests, desktop Weixin UI/API/types/CSS, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: added token-protected Weixin QR login start/status/disconnect APIs, generated backend SVG QR data URLs, persisted confirmed iLink credentials under lilsunspot's isolated Hermes home, and returned redacted status/capability/runtime fields without token/account IDs. Added a lilsunspot Weixin runtime manager that constructs Hermes `WeixinAdapter`, handles private text through the existing command/chat path, starts after scan confirmation, and only auto-restores on daemon startup when a model is configured.
- Decision/result: kept proactive Weixin sends behind safety approval, updated the desktop Weixin panel for QR display/polling/disconnect/runtime status, added sidecar Weixin hidden imports/dependencies without using the full messaging extra, and fixed windowed PyInstaller stdio so packaged `lilsunspotd` starts without a console.
- Validation: focused Weixin/API tests passed with 10 tests, full daemon pytest passed with 32 tests, product pytest passed with 34 tests, desktop build passed through `scripts/check.ps1`, `python scripts/guard_no_secrets.py` passed, `pwsh -NoProfile -File scripts/check.ps1` passed, `git diff --check` passed with CRLF warnings only, sidecar build passed, and packaged windowed sidecar smoke reached `/health` plus token-protected `/gateway/weixin/status` without leaking runtime token or Weixin credential fields.
- Remaining risk: no real phone Weixin QR scan or iLink private-chat send/receive was performed; QR expiry, reconnect, and installed-app UI clicks still need manual acceptance. Browser IAB was not used for screenshot-level Weixin UI validation in this run.

## 2026-06-08

- Task: sync local `develop` to the latest `origin/develop`.
- Files touched: `lilsunspot/notes/agent-memory.md`.
- Decision/result: fetched `origin/develop` and fast-forwarded local `develop` from `53ab94822` to `80a0554af`; the branch now contains PR #16 / `LIL-P1-01` prompt compiler changes.
- Validation: `pwsh scripts/check.ps1` passed after the sync; `git status --short --branch` showed `develop` aligned with `origin/develop` before this memory note was added.
- Remaining risk: this task did not run installer, sidecar, real provider, or visual acceptance checks; the memory note leaves one local uncommitted Markdown change by design.

- Task: complete `LIL-P1-01` output mode prompt compilation.
- Files touched: `TASKS.md`, `lilsunspot/daemon/prompt_compiler.py`, `lilsunspot/daemon/modes.py`, `lilsunspot/daemon/chat_client.py`, `lilsunspot/daemon/providers.py`, `lilsunspot/resources/default_mode_prompt.yaml`, daemon/product tests, desktop mode UI/types/CSS, `lilsunspot/notes/architecture.md`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: added product-layer prompt compilation with fixed `product_baseline + mode_profile + slider_overrides` ordering. `/modes/current` and `/modes/select` now return structured prompt metadata while keeping `profile.system_hint` as the compiled compatibility value, and `/chat/send` uses the compiled prompt for the provider system message. Desktop mode UI shows prompt layers and the live slider summary; the 390px Mode page now uses a single-column mixer layout to avoid page-level horizontal overflow.
- Validation: focused chat tests passed with 6 tests, focused daemon skeleton/resource tests passed with 5 tests, full daemon pytest passed with 25 tests, full product pytest passed with 33 tests, desktop build passed, `python scripts/guard_no_secrets.py` passed, `pwsh -NoProfile -File scripts/check.ps1` passed, and `git diff --check` passed with CRLF warnings only. Browser IAB returned unavailable, so the retry used headless Chrome/CDP against a temporary repo daemon data dir; Chat compact panel and Mode page screenshots at 960x680 and 390x760 passed with no page-level horizontal overflow and visible prompt layer/slider summaries. Screenshots stayed under `%TEMP%\lilsunspot-p1-ui-recheck-20260608-225323`.
- Remaining risk: screenshot QA used headless Chrome/CDP instead of the in-app Browser because Browser IAB was unavailable; real provider chat with the compiled prompt still depends on the configured provider outside this UI-only retry.

- Task: run real installed-app UI visual acceptance for `LIL-P0-FLOW-UI-01`.
- Files touched: `lilsunspot/desktop/src/App.css`, `lilsunspot/desktop/src/features/model/ProviderCard.tsx`, `lilsunspot/desktop/src/shared/components/StepLayout.tsx`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: rebuilt and reinstalled the current NSIS package into `%LOCALAPPDATA%\Lilsunspot`, then used Windows UI Automation and DWM screenshots at a 1365x768 window to inspect Chat, Mode, Weixin, Safety, Doctor, and Provider selection against `lilsunspot/lilsunspot_ui_v3_reference`. Fixed low-height/high-DPI visual issues: Weixin QR/status no longer clips, native scrollbars match the dark theme, Provider selection resets scroll on step changes, and compact Provider cards no longer break words or show half-cards. Screenshots stayed in `%TEMP%` and were not committed.
- Validation: `npm run build --prefix lilsunspot/desktop`, `npm run tauri:build --prefix lilsunspot/desktop`, `git diff --check`, `python scripts/guard_no_secrets.py`, and `pwsh scripts/check.ps1` passed. Final visual evidence is in `%TEMP%\lilsunspot-ui-visual-final-20260608-202018`.
- Remaining risk: acceptance used this development machine's installed app rather than a clean Windows VM; real Weixin private chat, real high-risk action interception, diagnostics export, and full Hermes agent-loop behavior remain out of scope.

- Task: run multi-round, multi-capability, and installed-app visual QA for `LIL-P0-03`.
- Files touched: `lilsunspot/desktop/src/App.css`, `TASKS.md`, `lilsunspot/README-dev.md`, `lilsunspot/notes/mvp-p0-status.md`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: used the installed `%LOCALAPPDATA%\Lilsunspot\Lilsunspot.exe` and sidecar with the DeepSeek API Key read from environment only in memory. Consecutive chat calls succeeded, but the product adapter reports `conversation_id_supported=false`, so cross-turn memory was not treated as implemented. Verified mode profile/sliders, Weixin command skeleton, Safety approval queue, and Doctor APIs. Installed-app screenshots found the chat composer below the first viewport on narrow windows; adjusted AppShell/ChatHome/transcript/composer sizing so the composer remains visible.
- Validation: desktop build passed, Tauri NSIS build passed, the rebuilt installer was installed into `%LOCALAPPDATA%\Lilsunspot`, final DWM screenshots at 960x680 and 390x760 showed the composer visible with no obvious overlap or horizontal overflow, installed process count was one `Lilsunspot.exe` plus one same-directory `lilsunspotd.exe`, `python -m pytest lilsunspot/tests/test_installed_app_smoke_script.py --timeout-method=thread --basetemp .tmp-pytest-lilsunspot` passed with 4 tests, `python scripts/guard_no_secrets.py` passed, and `git diff --check` passed with CRLF warnings only. API Key, runtime token, and chat reply bodies were not recorded.
- Remaining risk: visual QA used local installed-app screenshots rather than a clean Windows VM; real Weixin private chat, high-risk action interception, diagnostics export, and full Hermes agent-loop behavior remain out of scope.

- Task: start `LIL-P0-03` installed-app clean Windows smoke preparation.
- Files touched: `scripts/smoke_lilsunspot_installed_app.ps1`, `lilsunspot/tests/test_installed_app_smoke_script.py`, `TASKS.md`, `lilsunspot/README-dev.md`, `lilsunspot/notes/mvp-p0-status.md`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: added a reusable installed-app smoke script that can silently install the NSIS setup into an isolated path, run the installed `Lilsunspot.exe` with an isolated `LILSUNSPOT_DATA_DIR`, verify the installed `lilsunspotd.exe` process, check `127.0.0.1` runtime discovery, `/health`, token-protected `/providers`, and ensure daemon logs do not contain the runtime token. Ran the script locally against the current-user installed app with `-SkipInstall`; after user approval, also ran the real silent install path into `%TEMP%\lilsunspot-installed-app-smoke\app`, verified the installed app and sidecar, then restored the current-user install under `%LOCALAPPDATA%\Lilsunspot`. After the user asked to direct-install on the local machine, installed again into `%LOCALAPPDATA%\Lilsunspot` and verified the real installed environment directly.
- Validation: PowerShell parse passed, `python -m pytest lilsunspot/tests/test_installed_app_smoke_script.py --timeout-method=thread --basetemp .tmp-pytest-lilsunspot` passed with 4 tests, `-SkipInstall` installed-app smoke passed with 6 providers discovered, non-`-SkipInstall` real installer smoke passed with 6 providers discovered and silent uninstall, restored current-user install has uninstall registry and desktop/start-menu shortcuts, direct local install to `%LOCALAPPDATA%\Lilsunspot` launched `Lilsunspot.exe` and `lilsunspotd.exe`, `/health` passed, `/providers` returned 6 providers, and `/app/bootstrap` returned `chat_ready`; one extra non-listening sidecar process was cleaned up and `/health` still passed with one installed sidecar left running. User-provided environment DeepSeek validation then passed: `/providers/test`, `/providers/save`, and `/chat/send` all succeeded with `deepseek/deepseek-chat`; API Key, runtime token, and reply body were not recorded. `python -m pytest lilsunspot/tests --timeout-method=thread --basetemp .tmp-pytest-lilsunspot` passed with 32 tests, `pwsh -NoProfile -File scripts/check.ps1` passed with daemon tests 25 passed plus secret guard and desktop build, and `git diff --check` passed.
- Remaining risk: clean Windows VM was not executed, but per user direction LIL-P0-03 is accepted against the direct local installed environment.

## 2026-06-07

- Task: publish the P0 API Key flow and visual QA changes as a GitHub PR.
- Files touched: `lilsunspot/notes/agent-memory.md`.
- Decision/result: preparing a dedicated PR branch from `develop` for the current P0 flow/UI diff, targeting `tealigantal/lilsunspot` base `develop` rather than the Hermes upstream remote.
- Validation: publish prerequisites checked with `gh --version`, `gh auth status`, repository/remote inspection, prior desktop build, secret guard, `scripts/check.ps1`, and visual QA evidence.
- Remaining risk: final PR URL and remote checks are reported in the chat response after push/create succeeds.

- Task: run visual acceptance and try Figma-backed UI adjustment for `LIL-P0-FLOW-UI-01`.
- Files touched: `TASKS.md`, `lilsunspot/desktop/src/App.css`, `lilsunspot/desktop/src/features/settings/SettingsDrawer.tsx`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: created a Figma design file for visual QA, but both webpage capture and direct canvas write were blocked by the Starter plan MCP tool-call limit. Continued with local visual QA using a temporary daemon and headless Edge; tightened mobile header actions, changed mobile setup progress into a horizontal rail, widened the settings drawer, styled settings badges, shortened the chat transcript minimum height, and locked body scrolling while the drawer is open.
- Validation: desktop build passed, secret guard passed, `scripts/check.ps1` passed, and headless Edge screenshots/metrics covered API Key, ChatHome, SettingsDrawer, and mobile API/chat states at 960x680 and 390x760 with no horizontal overflow.
- Remaining risk: the Figma file exists but could not receive the editable UI adjustment board until MCP quota/access is available; production installed-app visual QA and real provider chat remain manual checks.

- Task: accept the API Key save/reconfiguration fix end to end.
- Files touched: `TASKS.md`, `lilsunspot/notes/agent-memory.md`, rebuilt desktop/sidecar/NSIS generated artifacts, and existing frontend/product files from the fix.
- Decision/result: accepted the current flow with automated checks, rebuilt sidecar and NSIS installer, then used headless Edge against the real Vite UI with a mocked local daemon contract. The UI flow saved a placeholder API Key on first run, reached the first-chat step, skipped into ChatHome, reopened model settings, saved a second placeholder API Key, and returned to ChatHome. Desktop 960x680 and narrow 390x760 screenshots were visually checked for horizontal overflow. A newly built sidecar in a temporary data directory verified `/app/bootstrap` changed from `needs_model` to `chat_ready` after both first save and re-save.
- Validation: `python -m pytest lilsunspot/tests --timeout-method=thread --basetemp .tmp-pytest-lilsunspot`, `python -m pytest lilsunspot/daemon/tests`, `python scripts/guard_no_secrets.py`, `npm run build --prefix lilsunspot/desktop`, `pwsh scripts/check.ps1`, `pwsh scripts/build_lilsunspotd_sidecar.ps1`, `npm run tauri:build --prefix lilsunspot/desktop`, headless Edge CDP UI acceptance, and temporary sidecar API acceptance all passed. Sidecar logs did not contain the placeholder API Key or runtime token.
- Remaining risk: this did not use a real provider API Key, did not test the complete Hermes agent loop, did not run on a clean Windows VM, and did not update Figma because MCP remains blocked by the Starter plan call limit.

- Task: fix API Key reconfiguration save loop and responsive setup sizing.
- Files touched: `TASKS.md`, `lilsunspot/desktop/README.md`, desktop onboarding/model/AppShell/CSS files, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: settings-driven model reconfiguration now opens the API Key/model save form for an already configured provider, saves without requiring a provider test, exits forced onboarding after save, and returns to ChatHome. First-run save now advances to the first-chat step without refreshing BootGate out from under the step, with a skip action so users are not trapped if the real provider is temporarily unavailable. The API Key form no longer duplicates model inputs, and setup/chat containers gained bounded scrolling and button wrapping for 960x680 and narrow layouts.
- Validation: `npm run build --prefix lilsunspot/desktop`, `python -m pytest lilsunspot/tests --timeout-method=thread --basetemp .tmp-pytest-lilsunspot`, `python -m pytest lilsunspot/daemon/tests`, `git diff --check`, and `python scripts/guard_no_secrets.py` passed. The existing installed `lilsunspotd.exe` occupied port 8765, so no temporary live daemon was bound there.
- Remaining risk: Browser IAB returned `Browser is not available: iab`, so rendered click-through screenshots and responsive visual proof were not captured. Figma MCP still hit the Starter plan call limit, so no editable Figma screen was updated in this run.

- Task: perform real setup.exe installed-app API Key save validation and uninstall afterward.
- Files touched: `lilsunspot/desktop/src/api.ts`, `TASKS.md`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: real current-user setup.exe validation found the installed WebView still showed local service failure because `/health` used browser `fetch` while protected requests used the Tauri daemon proxy. Changed the desktop API layer so every installed-app daemon request, including `/health`, goes through the Tauri command proxy. Rebuilt and reinstalled the NSIS setup, then verified installed `Lilsunspot.exe` launched the installed sidecar, entered onboarding, saved provider/model/API Key settings with an isolated placeholder key, reached ChatHome, and reopened directly to ChatHome from the saved local config. The installed app was uninstalled after validation.
- Validation: `npm run build --prefix lilsunspot/desktop` passed, `python -m pytest lilsunspot/tests/test_provider_api.py --timeout-method=thread --basetemp .tmp-pytest-lilsunspot-installed` passed, `npm run tauri:build --prefix lilsunspot/desktop` produced `Lilsunspot_0.1.0_x64-setup.exe`, silent install passed, installed-app save/reopen smoke passed, and silent uninstall removed the app binaries, uninstall entry, and running processes.
- Remaining risk: this used a placeholder key and isolated data dir to avoid touching real secrets; real provider test/chat and a clean Windows VM install are still not covered.

- Task: fix installed setup.exe first-run API Key setup structure.
- Files touched: `TASKS.md`, `lilsunspot/desktop/src/api.ts`, onboarding/model desktop components, `lilsunspot/desktop/design/p0-flow-ui-spec.md`, `lilsunspot/desktop/README.md`, `lilsunspot/tests/test_provider_api.py`, and `lilsunspot/notes/agent-memory.md`.
- Decision/result: decoupled saving model credentials from provider live testing; users can now save API Key/model/Base URL first and run connection testing as optional validation, so setup.exe first launch is not blocked by network, quota, model, or provider transient failures. Tauri runtime detection now also accepts `__TAURI__`, `tauri:` protocol, and `tauri.localhost`.
- Validation: desktop TypeScript/Vite build passed; product test added to verify save does not require a successful `/providers/test`; `scripts/check.ps1` passed. Browser IAB invocation returned `Browser is not available: iab`, so rendered interaction QA could not be completed in Codex.
- Remaining risk: clean installed-app UI verification with a real API Key still needs manual acceptance after rebuilding the installer.

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
# 2026-07-17 LIL-MACOS-DMG-01

- 任务：在保持现有 Windows setup.exe 链路不变的前提下增加 macOS 15+ arm64/x86_64 私用 DMG。
- 涉及：Mac Tauri 平台配置、PyInstaller onedir/icon shell 脚本、Rust/Python 数据目录与资源定位、Mac updater 隔离、双架构 Artifact workflow、安装后功能面烟测及项目文档。
- 决策：不改 Hermes core、不做功能裁剪；两个原生 runner 分别构建，无 Developer ID/公证/Release/自动更新，Windows 关键配置和脚本由 PR regression job 强制保持不变。
- 验证：本机 `scripts/check.ps1`（daemon 147 passed、secret guard、desktop build）、产品测试 51 passed、Rust 测试 4 passed、Mac 定向测试和 Windows release/安装版 smoke 通过。GitHub Actions run `29576626648` 在 `bcc110603` 上完成 arm64/x86_64 DMG 安装后功能面 smoke 与 Windows regression；Artifact 已下载到 `ignored/macos-artifacts/run-29576626648/`。arm64 SHA-256 为 `F70537166D09FE18B12BDC5F327B29E2DA2589C18C0C2F3937F640C32EA38EB0`，x86_64 SHA-256 为 `0C53F97675A5B242617F8DAB4B4F829A1430174B036B2AE6FA923CA979A2EC7D`。真实 Mac 微信、真实模型、Finder 和托盘人工项目尚未执行，不记为通过。
