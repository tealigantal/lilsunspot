# lilsunspot 架构说明

## 边界原则

lilsunspot 是产品层，优先新增在 `lilsunspot/`，不大面积修改 Hermes 核心。

## 目录职责

- `lilsunspot/daemon`：`lilsunspotd` 本地 daemon，包含本地 API、runtime token、provider、chat、mode、Weixin 骨架、安全审批和 doctor 入口。
- `lilsunspot/desktop`：Tauri + React 桌面端，包含 provider、chat、mode、Weixin、Safety、Doctor 页面和 daemon 访问代理。
- `lilsunspot/resources`：provider registry、默认 mode profiles、安全策略等产品层资源。
- `lilsunspot/installer`：占位，安装器主链路当前主要由 desktop/Tauri 和 scripts 构建脚本承载。
- `lilsunspot/plugins`：占位，当前未验证具体插件机制。
- `lilsunspot/profile_card`：占位，当前未验证资料卡实现。
- `lilsunspot/notes`：lilsunspot 状态、决策、历史和验收文档。
- `scripts/`：包含 lilsunspot sidecar、NSIS 和检查脚本，也包含大量上游 Hermes 脚本。

## 运行时数据

- `%LOCALAPPDATA%/Lilsunspot/data`：计划/当前默认产品数据目录。
- `~/Library/Application Support/Lilsunspot/data`：macOS 默认产品数据目录；Rust 桌面壳启动 sidecar 时显式传递同一路径。
- `hermes_home`：lilsunspot 独立 Hermes home，计划避免污染用户原 `~/.hermes`。
- `runtime-token.json`：本地 API runtime token 文件。
- `daemon-runtime.json`：daemon discovery 文件，记录本机 base URL、端口和 token 文件路径，不应包含 token 明文。
- `logs`：daemon 日志目录，secret 脱敏必须贯穿日志和诊断包。

## Provider 配置流

desktop
-> lilsunspotd
-> provider_registry.yaml
-> provider test
-> hermes_home/.env
-> hermes_home/config.yaml

## Product Bootstrap 流

desktop
-> BootGate
-> `/app/bootstrap`
-> `starting | daemon_failed | needs_model | model_test_required | chat_ready | repair_required`
-> 首启向导或聊天主界面
-> 设置抽屉

`/app/bootstrap` 是桌面端新的产品启动状态契约。它只返回普通用户可理解的标题、说明、下一步按钮、简化 checks、runtime 是否已配置、provider/model 标识和用户可见 blockers；不得返回 API Key、runtime token、完整敏感路径、traceback 或大段技术 JSON。

旧 `/app/state` 继续保留兼容，但桌面端优先读取 `/app/bootstrap`。BootGate 是启动后进入首启、聊天或修复页的唯一分流入口。

## Chat 请求流

当前仓库显示 `/chat/send` 由 `lilsunspot/daemon/chat_client.py` 读取 `hermes_home/config.yaml`、`hermes_home/.env`、保存的安全 `base_url_override` 和当前 mode profile，再调用 OpenAI-compatible `chat/completions`。这仍是单轮 `lilsunspot_provider_adapter`，不等同完整 Hermes agent loop。`conversation_id` 当前不实现多轮会话，返回中明确标记 unsupported。

## Mode 计划流

mode profile
-> prompt 编译
-> chat 前注入
-> 桌面滑杆/微信命令共用

LIL-P1-01 后，mode prompt 编译在 lilsunspot 产品层完成，不修改 `SOUL.md` 或 Hermes core。编译顺序固定为“产品基线 + 模式预设 + 三滑杆覆盖”：产品基线来自 `default_mode_prompt.yaml`，模式预设来自 `default_mode_profiles.yaml`，滑杆值来自 lilsunspot 独立数据目录中的 `mode-profile.json`，缺失滑杆使用所选 profile 默认值。`/modes/current` 和 `/modes/select` 返回 `prompt.system_hint`、`prompt.layers[]` 和 `prompt.slider_summary`；`profile.system_hint` 保留为编译后 prompt 的兼容字段。`/chat/send` 只读取编译后的 `prompt.system_hint` 注入 OpenAI-compatible system message。

## Weixin 计划流

复用 Hermes Weixin gateway，不新写微信机器人。

当前 lilsunspot 层已经接入 Weixin 扫码登录和 Hermes `WeixinAdapter.connect()`，但运行时仍是产品层文字桥：只读取 `event.text`，普通文本走 `lilsunspot_provider_adapter`，非文字会被提示为“当前微信入口只支持文字私聊”。这还不等同官方 Hermes gateway 的完整处理链路。

后续 Weixin 同步、PDF 阅读、文件收发和生成文件发送，优先采用“官方 Hermes gateway-first”策略：

- 以官方 `gateway/platforms/weixin.py` 为消息适配层来源，保留其 `MessageEvent(media_urls/media_types)`、媒体下载缓存、`send_document()`、`send_image_file()`、`MEDIA:<path>` 交付和 iLink 长轮询逻辑，不在 lilsunspot 里重新实现微信文件协议。
- lilsunspot 增加产品桥接层，把官方 Hermes 处理后的入站/出站消息写入本地会话库，再由桌面端读取，实现微信和电脑端同一会话同步。
- PDF/文件能力通过官方 Weixin adapter 下载到本地缓存后进入统一 artifact/document pipeline；桌面端展示文件、引用和下载入口，微信端发送文件必须先经过安全审批。
- 生成文件发送优先复用 Hermes 的 native upload/deliverable 机制；lilsunspot 只做普通用户 UI、审批、脱敏和安装包打包，不改 Hermes core。
- 该方向的官方依据包括 Hermes Weixin 文档和官方 `WeixinAdapter` 源码，源码里已有媒体下载、`MessageEvent` 媒体字段、`send_document()` 和 `MEDIA` artifact 交付相关实现。

风险边界：不能简单把整个 Hermes CLI 交互搬进桌面；必须把配置、日志、会话库、审批和 token 脱敏留在 lilsunspot 产品层。iLink 私聊、媒体下载、文件上传仍需要真实微信账号和 setup.exe 安装版验收。

## Safety 计划流

高危动作
-> 审批队列
-> 桌面允许/拒绝
-> audit.db

当前仓库有审批队列 API 和测试迹象；真实高危动作拦截、桌面完整允许/拒绝和 `audit.db` 未验证，按部分实现处理。

桌面端不再把 Safety 放在首屏主导航；它位于设置抽屉，文案明确说明基础接口存在但真实高危动作拦截仍需验证。

## Diagnostics 计划流

doctor checks
-> repair
-> redacted logs export

当前仓库有 doctor/repair 入口；诊断包导出未实现/未验证。

桌面端 Doctor 位于设置抽屉；一键检查和一键修复可触发现有接口，诊断包导出标记为待接入，不提供可点击假按钮。

## 当前架构风险

1. main/develop 或当前分支状态可能不一致。
2. 文档可能混有历史状态。
3. 桌面聊天可能尚未等同完整 Hermes agent loop。
4. Weixin 真实私聊需要人工扫码验收。
5. 安装包必须在干净 Windows 验证。
6. secret 脱敏必须贯穿日志和诊断包。

## macOS 私用包壳层

Mac 不复制或裁剪产品运行时：React 前端、Python daemon、Hermes runtime、微信 iLink adapter、会话、附件、模式、安全审批、任务和记忆仍走同一套代码。平台差异仅位于：

- `tauri.macos.conf.json` 覆盖普通前端构建命令、DMG、macOS 15 下限、独立 `icon.icns` 和 ad-hoc 签名。
- 原生 runner 用 PyInstaller 6.16.0 `onedir` 生成无扩展名的 `lilsunspotd`，完整复用 Windows hidden imports、Hermes collect-submodules 与产品资源。
- `.app` 中 daemon 固定从 `Contents/Resources/binaries/lilsunspotd/lilsunspotd` 发现；`LILSUNSPOT_DATA_DIR` 仍优先于平台默认值。
- Mac 更新入口保留，但只返回“私用 DMG 不提供自动更新”，不会访问 Windows 更新源。

Windows 主 `tauri.conf.json`、NSIS hooks、PowerShell sidecar/installer/release 脚本、npm `tauri:build` 和 Windows release workflow 仍是独立且受保护的原链路。
