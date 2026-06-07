# TASKS.md

## Current

- LIL-P0-FLOW-UI-01：产品流程重构 + UI 重排 + P0 主路径修复。
  - 2026-06-07：桌面主导航从开发者模块 tab 改为 BootGate 状态驱动流程；未配置模型进入首启向导，已配置模型进入聊天主界面，本地服务失败进入修复/诊断入口。
  - 新增 `/app/bootstrap` 作为前端启动状态契约；`/app/state` 保留兼容；当前聊天引擎如实命名为 `lilsunspot_provider_adapter`，不再假称完整 Hermes runtime。
  - 模型设置支持可编辑 model 和安全校验后的 `base_url_override`；本地 Ollama 允许空 API Key；输出模式支持三滑杆并写入下一条 chat system hint。
  - Weixin/Safety/Doctor 移入设置抽屉，并明确标记“暂未开放 / 待验证 / 骨架”，不再作为首屏主流程误导用户。
  - 2026-06-07：安装包首启 API Key 设置结构调整；保存 API Key / 模型配置成为主路径，连接测试改为可选验证，避免网络、额度或服务商临时错误阻断本机保存；同时增强 Tauri 运行环境识别。
  - 2026-06-07：真实 setup.exe 当前用户安装验证复现安装版 `/health` 仍走 WebView fetch 的阻断；已改为安装版所有 daemon 请求都走 Tauri 命令代理。重建并静默安装后，仓库外 `Lilsunspot.exe` 能启动安装目录 sidecar，首启进入向导，保存占位 API Key 后进入聊天页，关闭重开后直达聊天页；验证结束后已卸载。
  - 2026-06-07：继续修复从设置入口更换 API Key 的保存流程；已配置模型时重新设置会直接进入保存表单，保存后退出强制向导并回到聊天主界面；首启保存后进入第一句聊天，同时提供“稍后再聊”避免真实 provider 暂时不可用时卡住。Figma MCP 仍受 Starter 计划调用上限阻断，本次沿用仓库内 P0 规格。
  - 2026-06-07：完成本机验收；重建 sidecar 和 NSIS 安装包，headless Edge 用 mock daemon 跑通首启保存、跳过第一句聊天进入 ChatHome、设置抽屉再次保存 API Key 后回 ChatHome，并检查 960x680 / 390x760 无水平溢出；新构建 sidecar 在临时数据目录验证 `/app/bootstrap` 从 `needs_model` 到两次保存后的 `chat_ready`，日志不含占位 Key 或 runtime token。
  - 2026-06-07：完成视觉验收和小范围 UI 调整；Figma 新建设计文件 `https://www.figma.com/design/75o6t0GKbEVYkzHcnwVFHz` 成功，但 `generate_figma_design` / `use_figma` 写入继续受 Starter 计划 MCP 调用上限阻断。headless Edge + 临时 daemon 复验桌面 960x680 和移动 390x760：移动端步骤栏改为横向进度，聊天顶栏按钮更紧凑，设置抽屉加宽到 440px 并锁定背景滚动，所有复验状态无水平溢出。
  - 验证已跑：`git diff --check`、`python scripts/guard_no_secrets.py`、daemon pytest 25 passed、product pytest 25 passed、desktop build、`pwsh scripts/check.ps1`、sidecar build、Tauri NSIS build、headless Edge frontend acceptance、headless Edge visual acceptance、临时 sidecar API acceptance、当前用户 setup.exe 安装/启动/保存/重开/卸载。
  - 仍未覆盖：干净 Windows VM 安装、真实 API Key provider 测试/聊天、完整 Hermes agent loop、真实安装版 UI 人工点击验收；Figma 文件已创建但可编辑 UI 调整稿仍被 MCP Starter 调用上限阻断。

- LIL-P0-01：收敛 `release/mvp-p0` 分支，验证安装、首启、provider、桌面聊天。
  - 2026-06-06：本地自动验证已覆盖 daemon/product tests、secret guard、desktop build、`scripts/check.ps1`、sidecar build、NSIS build、sidecar `/health` 和 token-protected `/providers` smoke。
  - 2026-06-07：按 `lilsunspot/feed_back/feed_back07-06-2026` 插入并完成 LIL-P0-02A 首启体验修复；覆盖黑窗构建配置、首启模型向导、API Key 保存提示、聊天输入清空、Mode 横向选择和安装包图标。
  - 2026-06-07：继续修正 setup.exe 产物；安装包现在安装 `Lilsunspot.exe`，升级时关闭并清理旧 `lilsunspot_desktop.exe`，静默安装后快捷方式和注册表均指向 `Lilsunspot.exe`。
  - 2026-06-07：当前用户 setup.exe 安装版已验证仓库外 `Lilsunspot.exe` 首启、保存占位 API Key、关闭重开直达聊天页，并在验证后卸载。
  - 仍未覆盖：干净 Windows VM 安装、真实 API Key provider 测试/聊天、真实桌面 UI 聊天闭环。

## Next

1. LIL-P0-02：新增发布级 check_release.ps1，不允许静默跳过 desktop build。
2. LIL-P0-03：干净 Windows 安装冒烟，验证仓库外 Lilsunspot.exe 启动 lilsunspotd。
3. LIL-P1-01：输出模式三滑杆、三层合并和 prompt 编译。
4. LIL-P2-01：Weixin gateway 二维码、状态和真实私聊。
5. LIL-P3-01：真实高危动作审批拦截和 audit.db。
6. LIL-P4-01：诊断包导出和脱敏。

## Blocked / Unknown

- Windows 干净 VM 安装未验证；当前开发机用户级 setup.exe 安装/启动/保存/重开/卸载已验证。
- NSIS installer 可在仓库外启动已验证于当前开发机；干净 VM 仍未验证。
- 桌面聊天是否等同完整 Hermes agent loop 未验证。
- Mode 三滑杆未完成或未验证。
- Weixin 私聊真实闭环未验证。
- Safety 是否拦截真实高危动作未验证。
- Diagnostics export 未完成或未验证。

## Done

以下为历史任务记录，是否完全代表当前主线状态需以 lilsunspot/notes/mvp-p0-status.md 为准。

### LIL-P0-02A: 安装后首启体验修复。

Goal:
根据 `feed_back07-06-2026` 修复安装包测试阶段暴露的首启体验问题，先于发布级 check 和干净 Windows 冒烟处理真实用户阻断。

Result:
Windows release 桌面进程改为无控制台子系统，sidecar PyInstaller 改为 `--noconsole`；setup.exe 安装的主程序改为 `Lilsunspot.exe`，并在升级时处理旧 `lilsunspot_desktop.exe`；桌面端首启未配置 provider 时直接进入模型设置；Provider 向导补充 API Key 获取/保存说明；测试保存成功后清空前端 Key；聊天页改为消息流并在发送后清空输入；Mode 页自动加载并使用横向选择卡；安装包/快捷方式图标改用反馈图片。

Check:
```powershell
python -m pytest lilsunspot/daemon/tests
python -m pytest lilsunspot/tests --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
python scripts/guard_no_secrets.py
npm run build --prefix lilsunspot/desktop
pwsh scripts/check.ps1
pwsh scripts/build_lilsunspotd_sidecar.ps1
npm run tauri:build --prefix lilsunspot/desktop
.\lilsunspot\desktop\src-tauri\target\release\bundle\nsis\Lilsunspot_0.1.0_x64-setup.exe /S
```

### LIL-DOC-01: 按仓库现有 MD 架构整理 lilsunspot 项目文档。

Goal:
把 lilsunspot 当前状态、开发入口、文档索引和历史任务关系收敛到产品层 Markdown，不修改 Hermes upstream 文档作为任务记忆。

Result:
建立 `README.lilsunspot.md`、`lilsunspot/notes/doc-index.md`、`lilsunspot/notes/doc-inventory.md`、`lilsunspot/notes/mvp-p0-status.md` 等当前状态入口；后续任务以 `mvp-p0-status.md` 为准。

### LIL-00-07: Windows 安装包与 daemon sidecar 最小闭环。

Goal:
让普通 Windows 用户安装后打开 `Lilsunspot.exe`，不需要 Python、Node、Git 或 Docker，也能自动启动并连接 `lilsunspotd`。

Allowed files:
- TASKS.md
- lilsunspot/**
- scripts/**

Do not touch:
- Hermes core business code
- SOUL.md

Acceptance:
1. Windows daemon sidecar 构建脚本能生成 `lilsunspotd-x86_64-pc-windows-msvc.exe`。
2. sidecar 入口等价于 `python -m lilsunspot.daemon.launcher`。
3. sidecar 打包必须包含 `lilsunspot/resources/*.yaml`，不能依赖仓库源码路径。
4. Tauri bundle 使用 `externalBin` 接入 daemon sidecar。
5. Windows bundle target 固定为 `nsis`，避免 `targets: all` 触发 MSI/WiX 下载失败。
6. 桌面端启动 daemon 时优先查找打包 sidecar；debug 构建下仍保留 Python fallback。
7. 安装包构建命令能生成可安装 `.exe`。
8. sidecar 首次启动能创建 lilsunspot 独立数据目录、runtime token、discovery file 和 logs。
9. 桌面端能通过 Tauri token 代理访问 `/app/state` 和 `/providers`。
10. API Key、runtime token 不得进入日志、响应、prompt fixture、截图或诊断文本。
11. `scripts/check.ps1` 可以运行。
12. 不修改 Hermes 核心。

Check:
```powershell
python -m pytest lilsunspot/daemon/tests
python -m pytest lilsunspot/tests --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
python scripts/guard_no_secrets.py
pwsh scripts/check.ps1
pwsh scripts/build_lilsunspotd_sidecar.ps1
npm run tauri:build --prefix lilsunspot/desktop -- --bundles nsis
```

### LIL-00-06: 微信命令意图与安全审批队列最小闭环。

Goal:
在不触碰 Hermes 微信 adapter 的前提下，先完成 lilsunspot 产品层的微信命令解析/处理入口和本地安全审批队列，让高风险微信发送动作只能进入审批流程，不能直接发送。

Allowed files:
- TASKS.md
- lilsunspot/**
- scripts/**

Do not touch:
- Hermes core business code
- SOUL.md

Acceptance:
1. `/gateway/weixin/*` 和 `/safety/*` 除 `/health` 外继续要求 `X-Lilsunspot-Token`。
2. 微信状态必须明确说明当前不会扫码登录或真实发送消息。
3. `/gateway/weixin/commands` 暴露 `/help`、`/mode`、`/approve`、`/reject` 的产品层命令。
4. 微信命令处理接口能解析 `/help`、`/mode <id>`、`/approve <id>`、`/reject <id>`，用户可见错误保持普通中文。
5. `send_weixin_message` 必须按安全策略创建 pending approval，不得直接发送。
6. 审批队列必须保存在 lilsunspot 独立数据目录，不写入 Hermes home。
7. 审批支持 approve/reject 后从 pending 列表移除，并保留状态记录。
8. API Key、runtime token 不得进入日志、响应、prompt fixture、截图或诊断文本。
9. daemon pytest 最小测试通过。
10. `scripts/check.ps1` 可以运行。
11. 不修改 Hermes 核心。
12. 不修改 SOUL.md。

Check:
```powershell
python -m pytest lilsunspot/daemon/tests
python scripts/guard_no_secrets.py
pwsh scripts/check.ps1
```

### LIL-00-05: 接入 mode profiles 到真实聊天行为。

Goal:
让已选择的 mode profile 影响真实聊天请求的系统提示、输出风格和默认行为，同时继续避免泄露 API Key 或 runtime token。

Allowed files:
- TASKS.md
- lilsunspot/**
- scripts/**

Do not touch:
- Hermes core business code
- SOUL.md

Acceptance:
1. `/chat/send` 继续要求 `X-Lilsunspot-Token`。
2. 当前 mode profile 必须从 lilsunspot 独立数据目录读取。
3. mode profile 的 `system_hint` 必须进入真实聊天请求。
4. 未选择 mode 时使用默认 profile。
5. 用户可见错误保持普通中文。
6. API Key、runtime token 不得进入日志、响应、prompt fixture、截图或诊断文本。
7. daemon pytest 最小测试通过。
8. chat/mode 产品层补充测试通过。
9. desktop TypeScript build 通过。
10. `scripts/check.ps1` 可以运行。
11. 不修改 Hermes 核心。
12. 不修改 SOUL.md。

Check:
```powershell
python -m pytest lilsunspot/daemon/tests
python -m pytest lilsunspot/tests/test_chat_api.py --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
python scripts/guard_no_secrets.py
pwsh scripts/check.ps1
```

- LIL-00-04: 实现桌面聊天到 Hermes runtime 的真实桥接。本机 `DEEPSEEK_API_KEY` 已通过 `/providers/test` 和 `/chat/send` 真实通讯验证；未记录 API Key、runtime token 或回复正文。
- LIL-00-01: 创建 lilsunspot 完整开发骨架。
- LIL-00-02: 打通 lilsunspotd 启动器和桌面端自动发现。
- LIL-00-03: 实现真实 Provider 配置验证。
