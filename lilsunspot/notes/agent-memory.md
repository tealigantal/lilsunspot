# Agent Memory

## 2026-06-09

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
