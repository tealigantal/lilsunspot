# LIL-MACOS-DMG-01 执行计划

<!-- codex-important-project -->

## 目标

从干净 `origin/develop` 的独立 worktree 构建 macOS 15+ Apple Silicon 与 Intel 私用 DMG，同时保持现有 Windows `setup.exe` 的配置、脚本、行为和发布链路不变。安装后的 Mac 产品继续提供同一套聊天、模型配置、会话、附件、模式、微信、安全审批、任务、记忆、本地 daemon 和托盘能力。

## 边界

- 不改 Hermes core，不裁剪或隐藏功能。
- Mac 使用独立 Tauri 平台配置、sidecar shell 脚本和 Artifact workflow。
- 不做 Developer ID 签名、公证、App Store、Release、自动更新或 universal2。
- Mac 自动更新入口保留，但明确返回中文“私用 DMG 不提供自动更新”。
- Windows NSIS 配置、PowerShell 构建脚本、installer hooks、Windows release workflow 和 npm `tauri:build` 入口必须保持原样。

## 里程碑

- [x] 从 `origin/develop@3935c02df` 创建 `codex/macos-private-dmg` 独立 worktree。
- [x] 增加 macOS 数据目录、`.app/Contents/Resources` sidecar 定位和 updater 隔离。
- [x] 增加原生 PyInstaller onedir sidecar、Mac 图标和 DMG 平台配置。
- [x] 增加 arm64/x86_64 GitHub Actions Artifact 构建、安装后烟测和 Windows 回归 job。
- [x] 完成本机 Python、前端、Rust、secret、Windows sidecar/NSIS/安装版回归。
- [x] 独立审查 Windows 受保护文件未变、Hermes core 未变、Mac 能力面无隐藏。

## 当前证据

- 现有微信 adapter 使用 iLink 网络接口，没有 Win32 或本地微信客户端依赖。
- React 功能入口、Tauri 托盘、关窗隐藏和附件 `open -R` 已是跨平台路径。
- 已确认的 Mac 启动阻断是默认数据目录、App Bundle 资源定位、sidecar 构建与 Windows updater 隔离。
- GitHub Actions run `29576626648` 在提交 `bcc110603` 上全部通过：`macos-15` arm64、`macos-15-intel` x86_64 和 Windows regression 均为 success。两个 Mac job 都完成 DMG 构建、挂载复制、Info.plist、ad-hoc 签名、单一架构、默认数据目录、Resources sidecar 启动、`127.0.0.1`/token、核心 API、mock 聊天、会话、附件、微信 adapter、审批、任务和记忆验证。
- 两个 Artifact 已同步到本 worktree 的 `ignored/macos-artifacts/run-29576626648/`。arm64 DMG 为 56,306,534 bytes，SHA-256 `F70537166D09FE18B12BDC5F327B29E2DA2589C18C0C2F3937F640C32EA38EB0`；x86_64 DMG 为 58,724,891 bytes，SHA-256 `0C53F97675A5B242617F8DAB4B4F829A1430174B036B2AE6FA923CA979A2EC7D`。
- 本机 `scripts/check.ps1` 通过（daemon 147 passed、secret guard、desktop build）；产品测试 51 passed，Rust 测试 4 passed，Mac 定向测试 7 passed，shell 语法、workflow YAML、`py_compile`、Mac Tauri override/no-bundle build 与 `git diff --check` 均通过。
- `scripts/check_release.ps1` 完成 Windows sidecar、NSIS 与安装版 smoke；新产物 `Lilsunspot_0.1.0_x64-setup.exe` 为 39,325,311 bytes，SHA-256 为 `8F686A1C95FE62D949AE86FE2395CB28DE2006095884303CC6717BEE5F6F15D5`。安装版验证了 onedir sidecar、`127.0.0.1`、`/health`、token 代理、6 个 provider 和日志不含 runtime token。
- 独立只读审查修正了 clean checkout 中 sidecar/icon 必须早于 Rust 测试生成的 workflow 顺序，并确认修正后没有剩余必然阻断 DMG job 或造成功能裁剪的问题；Windows 受保护链和 Hermes core 相对 `origin/develop` 均为零差异。

## 恢复点

当前分支：`codex/macos-private-dmg`；worktree：`C:\Users\24179\Desktop\Personal-Agent\lilsunspot-macos-private-dmg`。原 `develop` 工作区未提交内容未被带入或修改。
