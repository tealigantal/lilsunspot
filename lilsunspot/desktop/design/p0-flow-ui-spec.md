# LIL-P0-FLOW-UI-01 设计规格

日期：2026-06-07

Figma MCP 本次已能认证并创建文件：<https://www.figma.com/design/k47dWzEZutMAKpoI2mCbvk>。但继续查询设计系统时触发 Starter 计划 MCP 调用上限，未能完成可编辑 Figma 画板；因此本文件仍作为 “Lilsunspot P0 Flow UI” 的仓库内等价设计交付。目标是把桌面端从开发者模块面板重构为普通 Windows 用户可完成首启、模型设置和聊天的状态驱动流程。

## 00 Flow Map

App -> BootGate -> 状态分流：

- `starting`：显示 StartingScreen，说明正在准备小黑子。
- `daemon_failed` / `repair_required`：显示 RepairScreen，主按钮为“重新检查”或“一键检查”。
- `needs_model` / `model_test_required`：进入 OnboardingFlow。
- `chat_ready`：进入 ChatHome。

首启流程：

WelcomeStep -> ChooseModelServiceStep -> ApiKeyStep -> TestAndSaveStep -> FirstChatStep -> ChatHome

设置入口：

ChatHome 右上角“设置” -> SettingsDrawer -> ModelSettings / ModeSettings / WeixinSettingsUnavailable / SafetySettingsPlaceholder / DoctorSettings

规则：

- 首屏不显示“首页 / 模型 / 聊天 / 输出风格 / 微信 / 安全 / 诊断”平铺 tab。
- 普通主文案不出现 provider、runtime、daemon、token。
- 技术详情统一折叠，并且不显示 API Key、runtime token、完整敏感路径或 traceback。

## 01 Tokens

Color tokens：

- `--color-bg`: `#f3f6fb`
- `--color-surface`: `#ffffff`
- `--color-surface-soft`: `#f8fbff`
- `--color-text`: `#17202a`
- `--color-muted`: `#617183`
- `--color-border`: `#d7e1ec`
- `--color-primary`: `#2563eb`
- `--color-primary-strong`: `#1d4ed8`
- `--color-danger`: `#c24135`
- `--color-success`: `#138a4a`
- `--color-warning`: `#a65f00`

Spacing tokens：

- `--space-1`: `4px`
- `--space-2`: `8px`
- `--space-3`: `12px`
- `--space-4`: `16px`
- `--space-5`: `20px`
- `--space-6`: `24px`
- `--space-8`: `32px`

Radius tokens：

- `--radius-control`: `7px`
- `--radius-card`: `8px`
- `--radius-panel`: `10px`

Typography：

- App font: `Inter`, `Segoe UI`, `Microsoft YaHei`, sans-serif.
- H1 24px/1.2, 700.
- H2 22px/1.25, 700.
- H3 16px/1.35, 700.
- Body 15px/1.6, 400.
- Caption 13px/1.45, 500.
- Button 15px/1, 700.

Buttons：

- Primary: 44px height, blue fill, white text.
- Secondary: 44px height, white fill, border, dark text.
- Danger outline: border danger, danger text.
- Disabled: opacity 0.55, no pointer.

Layout：

- Desktop target: 960x680.
- App shell: light background, centered max-width 1040px.
- Main panels: white surface, 1px border, subtle shadow, 8-10px radius.
- Drawer: right side, max 390px, full height on desktop; full width below 660px.

## 02 Components

- `PrimaryActionPanel`: title, message, optional checks, primary/secondary actions.
- `StepLayout`: left progress list + right step card on desktop; stacked on mobile.
- `StatusBadge`: `ok`, `warning`, `danger`, `neutral`.
- `ErrorWithAction`: human title, reason, suggestion, primary action, secondary actions, folded technical details.
- `TechnicalDetails`: `<details>` wrapper for sanitized debug payload.
- `ProviderCard`: display name, fit copy, key requirement, recommended model.
- `ModelTestResult`: success/error result with next actions.
- `ChatTranscript`: stable scroll panel with user, assistant, and error bubbles.
- `ChatComposer`: textarea + fixed-height send button.
- `ModeQuickPanel`: three presets and three sliders.
- `SettingsDrawer`: not a primary navigation surface; advanced modules live here.

## 03 Screens

### StartingScreen

960x680：顶部品牌行“Lilsunspot 小黑子”，右侧仅有“重新检查”。中央卡片标题“正在准备小黑子”，三条检查项：启动本地服务、读取模型设置、准备聊天。显示轻量进度条。

### RepairScreen

标题“本地服务没有成功启动”。说明“可能被安全软件拦截，或本地服务还没有准备好。”主按钮“重新检查”，次按钮“一键检查”。下方折叠“技术详情”。

### WelcomeStep

标题“欢迎使用小黑子”。说明“先给小黑子设置一个 AI 服务，就能开始聊天。”主按钮“开始设置”。不出现工程词。

### ChooseModelServiceStep

标题“选择 AI 服务”。推荐 DeepSeek、Kimi、通义千问、本地 Ollama 四张 ProviderCard。更多服务折叠。主按钮“下一步”。

### ApiKeyStep

标题“粘贴 API Key”。显示“打开官网获取 Key”“从剪贴板粘贴”“下一步：测试连接”。本地 Ollama 文案改为“本地模型通常不用 API Key”。

### TestAndSaveStep

可编辑“推荐模型”，高级设置折叠内可编辑 Base URL。按钮为“测试并保存”；本地 provider 文案为“检测本地服务”。失败时用 ErrorWithAction 展示 Key 不正确、网络连不上、模型不可用、额度不足、服务商错误或未知错误。

### FirstChatStep

标题“试着说第一句话”。显示一个简短输入框和发送按钮。成功后直接进入 ChatHome。

### ChatHome

顶部：当前 AI 服务/模型、当前输出模式、设置按钮。主体是 ChatTranscript，底部 ChatComposer。已配置模型时启动默认进入本屏。

### ChatBlockedState

标题“还不能聊天”。原因来自 `/app/bootstrap` blockers：未设置 AI 服务、模型测试失败或本地服务未启动。主按钮“现在设置”或“重新检查”。

### ModeQuickPanel

入口在 ChatHome 顶部。三个预设“务实 / 均衡 / 感性”；三个滑杆“表达风格 / 细节程度 / 自主程度”。保存后下一条聊天读取当前 mode。

### SettingsDrawer

右侧抽屉。入口列表：模型服务、输出模式、微信、安全审批、诊断。未完成项显示状态徽标。

### ModelSettings

普通区域显示当前 AI 服务、模型、重新测试/更换服务。高级设置折叠显示 provider id、model、base_url、hermes_provider、env_key。

### WeixinSettingsUnavailable

文案：“微信连接暂未开放，当前版本不会扫码登录或发送消息。”显示后续目标：扫码连接、`/模式`、`/资料`。

### SafetySettingsPlaceholder

文案：“安全审批基础接口存在，真实高危动作拦截仍需验证。”待审批为空时显示“暂无待审批”。

### DoctorSettings

显示“一键检查”“一键修复”。诊断包导出显示“诊断包导出待接入”，不可点击。技术详情折叠。

## 落地约束

- `App.tsx` 只挂载 AppShell。
- BootGate 是启动分流唯一入口。
- OnboardingFlow 只处理首启。
- ChatHome 只处理聊天。
- SettingsDrawer 只处理设置。
- 所有 protected API 仍从 `api.ts` 走 Tauri `daemon_request`，浏览器 dev mode 才允许手填调试 Token。
- 当前聊天引擎命名为 `lilsunspot_provider_adapter`，不冒充完整 Hermes runtime。
