# Lilsunspot Desktop

React + Tauri desktop for `lilsunspot` / `小黑子`.

## Start

From `lilsunspot/desktop`:

```powershell
npm install
npm run dev
```

In another terminal, start the daemon from the repository root:

```powershell
python -m lilsunspot.daemon.launcher
```

The app auto-discovers `lilsunspotd` from the local `daemon-runtime.json` file and falls back to `http://127.0.0.1:8765`.

## Product Flow

LIL-P0-FLOW-UI-01 后，桌面端不再使用“首页 / Provider / Chat / Mode / Weixin / Safety / Doctor”的首屏平铺 tab。主流程改为状态驱动：

```text
App -> BootGate -> 启动检查 -> 首启设置流程 -> 第一句聊天 -> 日常聊天主界面 -> 设置抽屉
```

状态规则：

- 未配置 AI 服务：直接进入首启设置流程。
- 已配置 AI 服务：直接进入 ChatHome。
- 本地服务失败：进入修复/诊断说明页。
- 聊天不可用：显示 ChatBlockedState，必须给出原因和主操作按钮。
- 微信、安全、诊断、输出模式不作为首屏主导航；它们位于设置抽屉。

首启模型流程：

```text
WelcomeStep -> ChooseModelServiceStep -> ApiKeyStep -> FirstChatStep
```

Model 设置支持普通用户可见的 AI 服务、推荐模型和 API Key。API Key 保存是主路径，连接测试是保存前后的可选验证，避免安装包首启时因为网络、额度或服务商临时错误而无法完成设置。高级设置折叠后可编辑 `model` 和 `base_url_override`。本地 Ollama 允许空 API Key。云 provider 的 base URL override 必须是 https，本地 provider 只允许 `http://127.0.0.1:port/v1`。

从设置抽屉进入“模型服务”重新配置时，已配置用户会直接进入保存 API Key / 模型表单；保存成功后退出强制设置流程并回到聊天主界面。首启用户保存后进入“第一句聊天”，如果真实服务商暂时不可用，也可以选择稍后再聊进入主界面，避免被连接测试或首次聊天阻断。

Chat 当前仍是 `lilsunspot_provider_adapter`：它调用 OpenAI-compatible provider adapter，不等同完整 Hermes agent loop；`conversation_id` 多轮会话后续再接入。

Weixin/Safety/Doctor 状态：

- Weixin：微信连接暂未开放，当前版本不会扫码登录或发送消息。
- Safety：安全审批基础接口存在，真实高危动作拦截仍需验证。
- Doctor：一键检查/修复使用现有接口，诊断包导出待接入，不显示可点击假按钮。

## Protected APIs

`/health` is public. All other daemon APIs require `X-Lilsunspot-Token`.

Tauri command `daemon_request` keeps protected API calls behind the desktop proxy so runtime token is not exposed to the Web UI. Browser dev mode can still use manual token entry and is clearly marked as development-only.

`/app/bootstrap` is the primary desktop startup contract. `/app/state` remains for compatibility.

## Build

```powershell
npm run build
```

Tauri packaging uses a bundled `lilsunspotd` sidecar for Windows. From the repository root:

```powershell
pwsh scripts/build_lilsunspotd_sidecar.ps1
npm run tauri:build --prefix lilsunspot/desktop -- --bundles nsis
```

The NSIS installer is written under `src-tauri/target/release/bundle/nsis/`. Do not use `targets: all` for the Windows build path; MSI/WiX is not part of the current minimum installer loop.

### Private macOS DMGs

Mac builds run only on native macOS 15 runners. They do not change the Windows commands above:

```bash
bash scripts/build_lilsunspotd_sidecar_macos.sh arm64   # or x86_64 on an Intel runner
bash scripts/prepare_lilsunspot_macos_icon.sh
cd lilsunspot/desktop
npx tauri build --bundles dmg --target aarch64-apple-darwin
```

Tauri automatically merges `src-tauri/tauri.macos.conf.json`. The private package uses an ad-hoc signature (`-`) only for bundle integrity; it has no Developer ID certificate or notarization. On first launch the user may need to allow it in macOS “隐私与安全”. The app supports macOS 15 and later, and its default data directory is `~/Library/Application Support/Lilsunspot/data`.

`.github/workflows/lilsunspot-macos-artifacts.yml` builds arm64 on `macos-15` and x86_64 on `macos-15-intel`, verifies and installs each DMG into a temporary directory, launches the packaged desktop/daemon chain with an isolated `HOME`, exercises the complete local API surface plus mock-model chat and attachment persistence, then uploads a DMG and SHA-256 for 14 days. It creates no GitHub Release and reads no signing or release secrets.

The Mac update UI remains visible but reports that private DMGs do not support automatic updates. Download a newer DMG and replace the app manually.

## LIL-P0-FLOW-UI-01 Validation

Validated locally on 2026-06-07:

```powershell
git diff --check
python scripts/guard_no_secrets.py
python -m pytest lilsunspot/daemon/tests
python -m pytest lilsunspot/tests --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
npm run build --prefix lilsunspot/desktop
pwsh scripts/check.ps1
pwsh scripts/build_lilsunspotd_sidecar.ps1
npm run tauri:build --prefix lilsunspot/desktop
```

Still requires manual acceptance on a clean Windows install with a real API Key: first launch, test/save, close and reopen into ChatHome, real chat send, and visual review of 960x680 plus narrow responsive layout.

This task also checked that the local Vite page responds over HTTP. Browser IAB was unavailable in the Codex environment and local Playwright/puppeteer were not installed, so screenshot-level visual QA remains manual.

On 2026-06-07, the API Key reconfiguration path was rechecked locally with TypeScript/Vite build, daemon/product pytest, `git diff --check`, and secret guard. Figma MCP remained blocked by the Starter plan rate limit, so the in-repo P0 design spec remains the source of truth until Figma access is available.
