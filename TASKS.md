# TASKS.md

## Current

- LIL-P2-02 + LIL-P2-03：微信私聊同步、文件附件、自然语言模式 UX 合并交付。
  - 2026-06-09：新增 lilsunspot SQLite 会话库、事件表、附件表和审批动作表；`/conversations`、`/conversations/{id}/messages`、`/events/stream`、`/attachments/{id}` 全部继续要求 `X-Lilsunspot-Token`，`/chat/send` 兼容路径改为写入稳定 `personal` 会话。
  - 2026-06-09：微信 `MessageEvent(media_urls/media_types)` 入站后登记附件、复制到 `data_dir/attachments/YYYYMM`、生成图片/PDF/txt/md/csv/docx/xlsx 摘要或中文不可读原因，并把附件摘要拼入 AI 回复 prompt；附件来源只允许 `data_dir/attachments` 和 Hermes 媒体缓存目录，不允许 Weixin credential 目录。
  - 2026-06-09：桌面端聊天改为会话数据源，启动加载最近消息并通过 Tauri `subscribe_events` 接收 daemon SSE；Tauri 用 header token 连接 `/events/stream`，token 不进入 URL/前端 state，并新增受控 `open_attachment`。Tauri core 增加托盘：关窗隐藏到后台，“打开小黑子”恢复窗口，“退出”真实退出。
  - 2026-06-09：微信模式入口支持普通自然语言：务实/平衡/温柔、详细/简短、主动/谨慎和当前风格查询；未知 slash command 返回中文提示，`/help`、`/mode` 保留为隐藏高级兼容路径。mode 变化落库为 system message 并广播 `mode.changed`。
  - 2026-06-09：主动微信发送仍走安全审批；审批通过后才调用 Weixin adapter 的 `send`、`send_document` 或 `send_image_file`，拒绝不会发送。
  - 2026-06-09 收尾复核：修复 CSV 被通用 `text/*` 提前解析的问题；SSE 等待改为跨线程 condition，避免非当前 asyncio loop 落库事件只能等 keepalive；Tauri SSE 重连会重新发现 endpoint 并在 401/403 后重读 token。
  - 验证已跑：focused conversation/media/mode/approval pytest 5 passed、daemon pytest 38 passed、product pytest 34 passed、`npm run build --prefix lilsunspot/desktop`、`cargo check --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check`、`npm run tauri:build --prefix lilsunspot/desktop`、临时目录安装版 smoke 通过；NSIS 产物为 `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`。
  - 2026-06-09：中断续跑收尾复核并补小修复：Weixin runtime 文本入站统一走事件入口，保留真实 `message_id`；审批通过发送微信文件前先验证所有附件存在且位于安全附件目录，避免文本已发送但附件失败的半完成状态。新增对应回归测试，更新 runtime fake event 测试入口。验证：focused conversation/safety pytest 11 passed、daemon pytest 40 passed、product pytest 34 passed、`npm run build --prefix lilsunspot/desktop`、`cargo check --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check` 仅 CRLF warnings、`pwsh -NoProfile -File scripts/build_lilsunspotd_sidecar.ps1`、`npm run tauri:build --prefix lilsunspot/desktop`、临时目录安装版 smoke 通过；NSIS 产物已确认存在。
  - 2026-06-09：按“小白用户误点”视角修复微信扫码页卡顿体感：刷新请求进行中再次点击会排队一次并在二维码说明区给反馈；断开按钮不再被慢刷新禁用，二次确认后可抢占旧刷新；后端扫码登录增加 generation，断开或新刷新后旧的 `/login/start` / `/login/status` 慢响应不能重新写回扫码会话。顺手修复会话消息列表按随机 id 排序导致同一时间戳消息偶发倒序的问题，改为 SQLite 写入顺序。验证：focused Weixin pytest 8 passed、daemon pytest 41 passed、product pytest 34 passed、`npm run build --prefix lilsunspot/desktop`、`cargo check --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check` 仅 CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop`；最新 setup.exe 已覆盖安装到 `%LOCALAPPDATA%\Lilsunspot`，随后 `scripts/smoke_lilsunspot_installed_app.ps1 -SkipInstall -InstallDir %LOCALAPPDATA%\Lilsunspot` 通过。
  - 2026-06-09：继续修复 Mode 同步、图片识别状态和微信附件基础链路。桌面新增统一 ModeProvider/useModeState，顶部状态、聊天右栏、模式页和设置抽屉共用同一份 mode state 并监听 `mode.changed`；图片附件区分 `preview_only` 和 `recognized`，支持 `image_url` 的 OpenAI/Qwen-VL 类模型可写入视觉摘要，DeepSeek 文本模型明确显示只能预览不能识别；微信私聊消息 metadata 记录脱敏 `chat_id/user_id` 路由；显式 `/gateway/weixin/send` 可携带安全 attachment ids 创建 `send_weixin_message` 审批，不直接发送；聊天右侧安全摘要增加进入审批的按钮。
  - 验证新增已跑：focused conversation/media/mode/approval pytest 10 passed、daemon pytest 46 passed、product pytest 34 passed、`npm run build --prefix lilsunspot/desktop`、`cargo check --manifest-path lilsunspot/desktop/src-tauri/Cargo.toml`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check`、`npm run tauri:build --prefix lilsunspot/desktop` 通过；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`。Browser IAB 打开 Vite dev UI 后，默认桌面截图和 390x844 移动截图显示基础壳正常渲染。
  - 未覆盖：Browser IAB 精确 960x680/390x760 批量截图调用超时，后续 viewport reset 调用也超时；CodeRabbit CLI 未安装，按插件技能通过 `bash -lc "curl -fsSL https://cli.coderabbit.ai/install.sh | sh"` 安装时 124 秒超时，未取得 CodeRabbit review 结果；真实微信发图片/PDF/docx/xlsx/csv 后桌面实时显示、审批后发回微信文件、关窗托盘/托盘打开/托盘退出仍需人工安装版验收。`cargo fmt --check` 未运行，因为本机 Rust toolchain 缺少 `rustfmt` 组件。
  - 2026-06-10：新增 Hermes 官方接口兼容审计边界：`hermes_compat` 记录 provider、Weixin、attachment、mode、safety、doctor/runtime 的官方接口来源和产品层包装理由；Doctor 和 `/runtime/info` 暴露 Hermes 版本、upstream commit 与关键接口探测。显式微信发送仍创建 `send_weixin_message` 审批，审批通过后调用官方 `WeixinAdapter` / `BasePlatformAdapter` 的 `send()`、`send_image_file()`、`send_document()`；不安全附件路径和未连接微信都不会发送。验证：focused Hermes compat pytest 5 passed、focused approval/send pytest 5 passed、daemon pytest 56 passed、product pytest 34 passed、`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check` 仅 CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop` 通过；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`。
  - 2026-06-10：按用户截图修复模式/对话真实状态错位。自然语言切换到目标 mode 时不再继承上一模式 sliders，而是写入目标 profile 默认值，避免后端 `current=balanced` 但 UI 仍显示感性滑杆；桌面 `/chat/send` 语义模式响应带回最新 mode，前端在收到 `mode_intent` 后主动重载共享 mode state，降低 SSE/Tauri 事件漏收时右侧展示条不同步的风险。Mode 面板三条滑杆标签从错误的“唱/RAP/篮球”修正为“风格/表达、长度/细节、确认/自主”。用户指出文件/附件判断不应混入产品层文本拦截后，已删除桌面和微信普通聊天路径上的附件能力/发送文件关键词拦截；mode 层只做 LLM 语义判断是否调整参数，未命中 mode 的消息回到正常聊天。验证：focused conversation/hermes compat pytest 6 passed、daemon pytest 57 passed、product pytest 34 passed、`npm run build --prefix lilsunspot/desktop`、旧拦截符号扫描、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check` 仅 CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop` 通过；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`。
  - 2026-06-10：按“预设 + 自定义”重做 mode 边界。`default_mode_profiles.yaml` 仅保留 `pragmatic/balanced/emotional/custom` 四个模式，`balanced` 是默认；固定预设不再保存任意 sliders，API 或旧状态里出现“固定预设 + 非预设滑杆”会读取/保存为 `custom`，自然语言 slider 调整也落到 `custom`。桌面端删除左侧 `MD 模式` 页面、设置抽屉输出模式 tab 和 `ModeSettings.tsx`，聊天右侧改为四个模式按钮、滑杆、实时预览卡，移除原安全审批 mini panel 和 runtime line。验证：focused mode/conversation pytest 29 passed、daemon pytest 58 passed、product pytest 35 passed、`npm run build --prefix lilsunspot/desktop`、headless Chrome/CDP mock Tauri 截图检查四模式/无 MD/无安全 mini panel/无横向溢出、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check` 仅 CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop` 通过；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`。
  - 2026-06-10：落实“微信连接 != 当前桌面对话”的多对话边界。普通桌面“新建”只创建桌面对话，不抢微信入站 route；微信私聊按 active Weixin conversation 落库，只有“新开此微信对话”或“设为当前”会切换同一微信 route 的入站落点；Weixin route key 增加 `account_id` 维度，兼容旧的无账号 route，真实 runtime handler 会把当前 adapter account id 注入事件 metadata。验证：focused conversation pytest 22 passed、daemon pytest 63 passed、product pytest 35 passed、`npm run build --prefix lilsunspot/desktop`、`py -3 scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check` 仅 CRLF warnings、`npm run tauri:build --prefix lilsunspot/desktop` 通过；NSIS 产物确认存在：`lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`，大小 62,214,241 bytes，时间 2026-06-10 14:34:45 +08:00。

## Next

1. LIL-P2-02/P2-03 安装版人工验收：真实微信发图片/PDF/docx/xlsx/csv 后桌面实时显示；生成文件经审批发送回微信；960x680 和 390x760 附件卡无重叠/横向溢出；关窗进托盘、托盘打开、托盘退出。
2. LIL-P3-01：真实高危动作审批拦截和 audit.db。
3. LIL-P4-01：诊断包导出和脱敏。
4. LIL-UPSTREAM-01：Hermes 官方仓库同步自动化。配置 GitHub Action 定时/手动 `fetch upstream`，检测 `upstream/main` 新提交后创建同步 PR，不自动合并；PR 跑 `scripts/check.ps1`、secret guard、desktop build，涉及桌面/sidecar/installer 时跑 Tauri NSIS build；记录 upstream commit，冲突人工处理，暂不改 git submodule/subtree。

## Blocked / Unknown

- 当前开发机用户级 setup.exe 安装/启动/保存/重开/卸载已验证；2026-06-08 追加本机真实安装目录 `%LOCALAPPDATA%\Lilsunspot` 直接安装和运行验证，以及 DeepSeek 真实 provider test/save/chat 验证。
- NSIS installer 可在仓库外启动已验证于当前开发机；2026-06-08 新增可复用 installed-app smoke 脚本，并已验证当前已安装 exe 的 `-SkipInstall` 路径、真实静默安装到临时目录路径、当前用户真实安装目录路径。
- 桌面聊天是否等同完整 Hermes agent loop 未验证；当前验证覆盖的是 `lilsunspot_provider_adapter` 单轮真实 DeepSeek 聊天。
- Mode 三滑杆和 prompt 编译已在本地 API/test/build 路径完成；Browser IAB 不可用，但已用 headless Chrome/CDP 完成 960x680 / 390x760 截图级复验。
- Weixin 扫码登录产品层 API、二维码 data URL、runtime manager、普通私聊文本到 chat adapter、`/help` 和 `/mode` 命令已通过自动测试；packaged sidecar 可启动并返回脱敏 Weixin 状态；2026-06-09 用户人工确认真实桌面聊天、真实微信扫码登录、微信端登录、私聊文本回复、`/help`、`/mode` 和安装版 UI 点击均已跑通，P2-01 人工校验成功。
- Weixin 后续能力方向已记录为官方 Hermes gateway-first：官方 adapter 已有媒体/文件下载、`MessageEvent` 媒体字段、`send_document()` 和 artifact 交付相关实现；lilsunspot 仍需补本地会话库、桌面同步 UI、PDF/artifact pipeline、审批和安装版验收。
- Safety approval 队列 create/reject 已验证；是否拦截真实高危动作未验证。
- Doctor API 已在安装版返回 10 项检查；Diagnostics export 未完成或未验证。

## Done

以下为历史任务记录，是否完全代表当前主线状态需以 lilsunspot/notes/mvp-p0-status.md 为准。

### Moved From Current 2026-06-09

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
  - 2026-06-08：按 `lilsunspot/lilsunspot_ui_v3_reference` 完成桌面 UI v3 整体整改；主外壳改为深蓝黑控制台、72px 侧栏、顶部状态栏，ChatHome 增加任务示例卡和右侧模式/安全摘要，输出模式改为调音台页面，首启 Provider 改为出场卡，Weixin/Safety/Doctor 改为同一套深色玻璃面板。前端仅补已有 `/safety/approvals/{id}/decide` 的 API 包装；未新增后端协议，二维码和诊断包导出仍按未接入能力展示。验证：`npm run build --prefix lilsunspot/desktop`、`git diff --check`、`python scripts/guard_no_secrets.py`、`pwsh scripts/check.ps1` 通过；headless Chrome CDP 截图覆盖 1365x768 的 Chat/Mode/Onboarding/Weixin/Safety/Doctor 和 390x760 Chat，均无水平溢出，移动聊天输入框首屏可见。
  - 验证已跑：`git diff --check`、`python scripts/guard_no_secrets.py`、daemon pytest 25 passed、product pytest 25 passed、desktop build、`pwsh scripts/check.ps1`、sidecar build、Tauri NSIS build、headless Edge frontend acceptance、headless Edge visual acceptance、临时 sidecar API acceptance、当前用户 setup.exe 安装/启动/保存/重开/卸载。
  - 仍未覆盖：干净 Windows VM 安装、真实 API Key provider 测试/聊天、完整 Hermes agent loop、真实安装版 UI 人工点击验收；Figma 文件已创建但可编辑 UI 调整稿仍被 MCP Starter 调用上限阻断。

- LIL-P0-01：收敛 `release/mvp-p0` 分支，验证安装、首启、provider、桌面聊天。
  - 2026-06-06：本地自动验证已覆盖 daemon/product tests、secret guard、desktop build、`scripts/check.ps1`、sidecar build、NSIS build、sidecar `/health` 和 token-protected `/providers` smoke。
  - 2026-06-07：按 `lilsunspot/feed_back/feed_back07-06-2026` 插入并完成 LIL-P0-02A 首启体验修复；覆盖黑窗构建配置、首启模型向导、API Key 保存提示、聊天输入清空、Mode 横向选择和安装包图标。
  - 2026-06-07：继续修正 setup.exe 产物；安装包现在安装 `Lilsunspot.exe`，升级时关闭并清理旧 `lilsunspot_desktop.exe`，静默安装后快捷方式和注册表均指向 `Lilsunspot.exe`。
  - 2026-06-07：当前用户 setup.exe 安装版已验证仓库外 `Lilsunspot.exe` 首启、保存占位 API Key、关闭重开直达聊天页，并在验证后卸载。
  - 2026-06-08：用户确认除干净 Windows 安装以外，LIL-P0-01 其余人工验收已完成；clean Windows 安装保留给 LIL-P0-03。
  - 仍未覆盖：干净 Windows VM 安装。

- LIL-P0-03：干净 Windows 安装冒烟，验证仓库外 Lilsunspot.exe 启动 lilsunspotd。
  - 2026-06-08：新增 `scripts/smoke_lilsunspot_installed_app.ps1`，固定安装版 smoke 路径：可静默安装 NSIS、使用隔离 `LILSUNSPOT_DATA_DIR`、启动仓库外 `Lilsunspot.exe`、验证同目录 `lilsunspotd.exe` 进程、`127.0.0.1` runtime discovery、`/health`、带 token 的 `/providers`，并检查 daemon 日志不含 runtime token。
  - 2026-06-08：本机已用当前用户已安装的仓库外 `%LOCALAPPDATA%\Lilsunspot\Lilsunspot.exe` 跑通 `-SkipInstall` smoke；临时数据目录为 `ignored\installed-app-smoke\data`，`/providers` 返回 6 个 provider，未打印 runtime token。
  - 2026-06-08：经用户允许后跑通真实安装路径：`scripts/smoke_lilsunspot_installed_app.ps1` 静默安装到 `%TEMP%\lilsunspot-installed-app-smoke\app`，仓库外安装版启动同目录 sidecar，`/health` 和带 token 的 `/providers` 通过，随后自动静默卸载；为恢复本机当前用户安装状态，已用同一安装包重装回 `%LOCALAPPDATA%\Lilsunspot`，卸载注册表项和桌面/开始菜单快捷方式存在。
  - 2026-06-08：按用户要求直接在本机安装环境验证：静默安装到 `%LOCALAPPDATA%\Lilsunspot`，启动真实安装版 `Lilsunspot.exe`，确认同目录 `lilsunspotd.exe` 进程、`http://127.0.0.1:8765`、真实数据目录 `%LOCALAPPDATA%\Lilsunspot\data`、`/health`、带 token 的 `/providers` 6 个 provider、`/app/bootstrap` stage=`chat_ready`；未打印 runtime token。
  - 2026-06-08：按用户要求使用系统环境中的 DeepSeek API Key 验证真实 provider 主路径；从环境变量读取 Key 到内存，`/providers/test` 通过，`/providers/save` 保存 `deepseek/deepseek-chat`，`/chat/send` 真实返回 4 字回复，`/app/bootstrap` 仍为 `chat_ready`；未打印或记录 API Key、runtime token、回复正文。
  - 2026-06-08：追加多轮/多能力/视觉验证：真实安装版连续 3 次 DeepSeek chat 成功，当前 `/chat/send` 明确 `conversation_id_supported=false`，跨轮记忆未作为已实现能力验收；mode default/pragmatic/balanced 与三滑杆保存后 chat 均通过并恢复原 mode；Weixin `/help`、`/mode pragmatic` 骨架命令通过；Safety approval create/reject 后 pending 归零；Doctor 返回 10 项检查；DWM 截图发现窄屏聊天输入框首屏不可见后，已调整 ChatHome/AppShell CSS、重建并重装，最终 960x680 和 390x760 安装版截图中输入框可见且未见重叠/横向溢出。
  - 本轮结论：LIL-P0-03 本机直接安装验收完成；clean Windows VM 不再作为当前阻断项。

- LIL-P1-01：输出模式三滑杆、三层合并和 prompt 编译。
  - 2026-06-08：完成后端 prompt compiler，固定按“产品基线 + 模式预设 + 三滑杆覆盖”三层合并；新增 `default_mode_prompt.yaml`，`/modes/current` 和 `/modes/select` 返回 `prompt.system_hint`、三层 `prompt.layers[]` 和 `prompt.slider_summary`，并保留 `profile.system_hint` 作为编译后 prompt 兼容字段。
  - `/chat/send` 现在只读取编译后的 `prompt.system_hint` 作为 OpenAI-compatible system message；缺失滑杆时使用所选 mode profile 默认值，保存滑杆继续 clamp 到 `0..100`。
  - 桌面输出模式页读取新 `prompt` 结构，展示三层合并摘要和当前滑杆效果；未新增生产依赖，未修改 Hermes core。
  - 验证已跑：daemon pytest 25 passed、product pytest 33 passed、`test_chat_api.py` 6 passed、`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check` 通过。Browser IAB 当前返回 unavailable；2026-06-08 重试改用 headless Chrome/CDP 截图复验 Chat compact panel 和 Mode page 的 960x680 / 390x760，均无页面级横向溢出，三层 prompt 摘要和滑杆效果可见。截图位于 `%TEMP%\lilsunspot-p1-ui-recheck-20260608-225323`，未包含 API Key 或 runtime token。

- LIL-P2-01：Weixin gateway 二维码、状态和真实私聊。
  - 2026-06-09：新增 lilsunspot 产品层 Weixin 扫码登录状态机和 API：`/gateway/weixin/status` 返回 `not_configured/qr_pending/scanned/qr_expired/connected/credential_expired/error`、能力 flags 和无需微信官方付费/材料标记；新增 `/gateway/weixin/login/start`、`/gateway/weixin/login/status`、`/gateway/weixin/disconnect`，所有接口继续要求 `X-Lilsunspot-Token`。
  - 扫码确认后复用 Hermes Weixin iLink helper 保存凭据到 lilsunspot 独立 `hermes_home/weixin/accounts`，产品状态写入 `weixin-state.json`；响应不返回 token 或 account_id，主动 `/gateway/weixin/send` 仍只创建安全审批，不直接发送微信。
  - `/gateway/weixin/commands/handle` 现在把普通私聊文本复用当前 `lilsunspot_provider_adapter` 生成回复，`/help`、`/mode`、`/approve`、`/reject` 命令继续走产品层处理。
  - 2026-06-09：补齐真实运行态：新增 lilsunspot Weixin runtime manager，读取已保存凭据后构造 Hermes `WeixinAdapter`，通过 `set_message_handler()` 接入私聊文字；扫码确认后自动启动，daemon 启动时仅在已有凭据且模型已配置时自动恢复监听。`/gateway/weixin/status` 增加脱敏 runtime 状态、入站/回复时间和错误摘要。
  - 二维码响应增加后端生成的 SVG `qr_image_data_url`；桌面 Weixin 页直接显示二维码、轮询扫码状态、显示 runtime 状态并支持断开清理。sidecar 构建加入 Weixin 运行依赖和 hidden imports，并修复 windowed PyInstaller stdio，避免无控制台启动时 uvicorn/logging 早退。
  - 桌面 Weixin 页接入开始扫码、状态轮询、断开清理、扫码链接/载荷操作和新状态时间线；未新增前端依赖，仍不接公众号、小程序或开放平台材料流程。
  - 2026-06-09：联网核对 Hermes 官方 Weixin adapter 后确认 `qrcode_img_content` 是完整可扫码 liteapp URL，`qrcode` 只用于轮询状态；后端已禁止在缺少 `qrcode_img_content` 时退回用 `qrcode` 生成二维码，前端进入微信页后自动请求真实二维码，并且真实二维码未返回前不再展示可误扫的假 QR 占位。
  - 2026-06-09：按 setup.exe 主链路重建并重装到 `%LOCALAPPDATA%\Lilsunspot`，安装版 `/gateway/weixin/login/start` 返回 `qr_pending`、`qr_payload_kind=url`、host=`liteapp.weixin.qq.com`、`qr_image_data_url` 存在且响应不含 `token/account_id`；真实二维码只在安装版窗口里给用户现场查看，不写入截图或聊天。
  - 2026-06-09：按用户反馈修复真实二维码状态下的 UI 重叠：二维码容器只承载二维码图像，扫码说明和“打开扫码链接/复制扫码载荷”移动到独立说明面板；低高度窗口同步收紧说明区，避免说明文字、按钮和二维码互相覆盖。
  - 2026-06-09：按用户反馈移除右侧开发者式 `qr_pending/scanned/credential_expired/runtime` 状态时间线和“命令贴纸”，改为普通用户可理解的当前状态、下一步说明，以及扫码后可发送的三类内容。
  - 验证已跑：微信/API 相关 pytest 10 passed、daemon pytest 32 passed、product pytest 34 passed、`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`git diff --check`、`pwsh -NoProfile -File scripts/build_lilsunspotd_sidecar.ps1`、packaged windowed sidecar `/health` + token-protected `/gateway/weixin/status` smoke 通过；status smoke 未泄漏 runtime token 或 Weixin credential 字段。Browser IAB 未用于本轮截图级 UI 验收。
  - 2026-06-09 追加验证：`python -m pytest lilsunspot/daemon/tests/test_weixin_gateway_login.py` 7 passed、`npm run build --prefix lilsunspot/desktop` 通过、`npm run tauri:build --prefix lilsunspot/desktop` 通过、setup.exe 静默重装通过、安装版基础 smoke 通过、`python scripts/guard_no_secrets.py` 通过、`git diff --check` 仅 CRLF warnings、`pwsh -NoProfile -File scripts/check.ps1` 通过且 daemon pytest 33 passed。UI 重叠和右侧无意义面板修复后再次完成 focused Weixin pytest、desktop build、NSIS rebuild 和 setup.exe 覆盖安装，安装版微信页已打开供人工复验。
  - 2026-06-09：用户确认微信文字对话人工测试通过后，补齐 lilsunspot 默认 bot 资料：后端 `/gateway/weixin/status` 和扫码启动响应返回 `bot_profile.nickname=小黑子`、`avatar_asset=lilsunspot-icon.png`；桌面聊天助手气泡和微信设置页统一使用项目头像。腾讯 `@tencent-weixin/openclaw-weixin@2.4.4` 源码仅暴露 `get_bot_qrcode?bot_type=...`，本次未猜测 iLink 服务端头像/昵称参数。验证：focused Weixin pytest 7 passed、`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`git diff --check` 仅 CRLF warnings、`pwsh -NoProfile -File scripts/check.ps1` 通过；Browser 渲染未跑，因为当前安装版占用 `127.0.0.1:8765` 且避免截图/记录真实微信二维码或 runtime token。
  - 2026-06-09：补做 setup.exe 构建并加强 agent 约束：`AGENTS.md` 新增安装版影响触发规则，凡桌面 UI、Tauri、sidecar/runtime、安装脚本、bundle 图标/资产、Weixin runtime delivery 或只能通过安装版交付的变更，收尾必须跑 `npm run tauri:build --prefix lilsunspot/desktop` 并确认 NSIS `setup.exe` 产物。已补跑 `pwsh -NoProfile -File scripts/check.ps1`、`python scripts/guard_no_secrets.py`、`npm run tauri:build --prefix lilsunspot/desktop`，生成 `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`。
  - 2026-06-09：按用户确认用最新 `setup.exe` 覆盖安装到 `%LOCALAPPDATA%\Lilsunspot`，确认安装目录下 `Lilsunspot.exe` 和 `lilsunspotd.exe` 来自本次构建；随后运行 `scripts/smoke_lilsunspot_installed_app.ps1 -SkipInstall -InstallDir %LOCALAPPDATA%\Lilsunspot`，安装版 smoke 通过，验证安装目录 sidecar、`127.0.0.1` runtime discovery、`/health`、带 `X-Lilsunspot-Token` 的 `/providers`，且未输出 runtime token 或 API Key。
  - 2026-06-09：复核微信端无法显示“小黑子”头像/昵称的问题：当前 iLink/ClawBot 协议和腾讯 `openclaw-weixin` 插件只公开 QR 登录、消息收发、上传、配置和 typing 等接口；`get_bot_qrcode` 只接收 `bot_type`，登录确认只返回 `ilink_bot_id/bot_token/baseurl/ilink_user_id`，消息 API 类型里没有 bot 昵称或头像字段。结论：本地只能设置 lilsunspot 桌面端展示资料，微信客户端里的 ClawBot/iLink bot identity 展示资料由微信服务端控制；除非腾讯后续开放 profile API 或管理台配置，否则不应在本地伪造参数。
  - 2026-06-09：按用户截图反馈精简微信扫码面板：底部三个操作收敛为唯一“刷新”按钮，刷新按状态执行读取状态/拉取扫码状态/重新生成二维码；移除“读取中”“正在生成二维码”“这里不会显示可扫描的假二维码”“复制扫码载荷”等用户无意义文案或控件。验证：`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`npm run tauri:build --prefix lilsunspot/desktop`、setup.exe 覆盖安装到 `%LOCALAPPDATA%\Lilsunspot`、安装版 smoke 通过。Browser IAB 本轮返回不可用，未做截图级自动验收。
  - 2026-06-09：按用户补充要求恢复独立强制断开入口：微信扫码面板保留“刷新”主操作，另增单独“断开”按钮，直接调用 `/gateway/weixin/disconnect` 清理连接或扫码状态，不再把断开语义混入刷新。验证：`npm run build --prefix lilsunspot/desktop`、`python scripts/guard_no_secrets.py`、`pwsh -NoProfile -File scripts/check.ps1`、`npm run tauri:build --prefix lilsunspot/desktop`、setup.exe 覆盖安装到 `%LOCALAPPDATA%\Lilsunspot`、安装版 smoke 通过；Browser IAB 仍返回不可用，未做截图级自动验收。
  - 2026-06-09：用户人工确认真实桌面端聊天、微信扫码登录、微信端成功登录、微信私聊文本回复、`/help` 和 `/mode` 均已跑通。先不实现但需记录的产品风险：`/help`、`/mode` 这类 slash command/命令式调整路径不适合本产品目标用户，绝大多数用户是代码小白，后续应改成自然语言、按钮/菜单、快捷卡或低门槛引导，不应要求用户理解类似代码的命令格式。
  - 2026-06-09：用户补充确认 P2-01 安装版 UI 人工校验成功；P2-01 以真实桌面聊天、扫码登录、微信端登录、私聊文本回复、`/help`、`/mode` 和安装版 UI 点击验收通过收尾。
  - 后续稳定性风险：断线重连、二维码真实过期仍需在后续 Weixin 能力迭代中补验，不再作为 P2-01 当前阻断项。

### LIL-P0-02: 发布级 check_release.ps1。

Goal:
新增发布候选强校验入口，避免发布前因为缺少 npm 或 desktop 依赖而静默跳过桌面构建。

Result:
新增 `scripts/check_release.ps1`，固定执行 git diff check、daemon pytest、product pytest、secret guard、desktop build、sidecar build、NSIS build，并检查 sidecar exe 和 NSIS setup.exe 产物存在；缺少 `git`、`python`、`npm`、`uv` 或 `lilsunspot/desktop/node_modules` 时直接失败。新增脚本约束测试，防止 release check 回退到跳过 desktop build。

Check:
```powershell
python -m pytest lilsunspot/tests/test_release_check_script.py --timeout-method=thread --basetemp .tmp-pytest-lilsunspot
pwsh scripts/check_release.ps1
pwsh scripts/check.ps1
```

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
