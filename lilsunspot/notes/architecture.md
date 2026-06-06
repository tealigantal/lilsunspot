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

## Chat 请求流

当前仓库显示 `/chat/send` 由 `lilsunspot/daemon/chat_client.py` 读取 `hermes_home/config.yaml`、`hermes_home/.env` 和当前 mode profile，再调用 provider registry 指向的 OpenAI-compatible `chat/completions`。这更接近 provider adapter chat；本任务未验证它等同完整 Hermes agent loop。

## Mode 计划流

mode profile
-> prompt 编译
-> chat 前注入
-> 桌面滑杆/微信命令共用

当前仓库已有 mode profile API 和 chat 前 system hint 注入迹象，三滑杆和完整 prompt 编译链路按部分实现记录。

## Weixin 计划流

复用 Hermes Weixin gateway，不新写微信机器人。

当前 lilsunspot 层有 Weixin 状态和命令骨架；真实扫码、联系人、私聊收发未验证，按骨架/未验证处理。

## Safety 计划流

高危动作
-> 审批队列
-> 桌面允许/拒绝
-> audit.db

当前仓库有审批队列 API 和测试迹象；真实高危动作拦截、桌面完整允许/拒绝和 `audit.db` 未验证，按部分实现处理。

## Diagnostics 计划流

doctor checks
-> repair
-> redacted logs export

当前仓库有 doctor/repair 入口；诊断包导出未实现/未验证。

## 当前架构风险

1. main/develop 或当前分支状态可能不一致。
2. 文档可能混有历史状态。
3. 桌面聊天可能尚未等同完整 Hermes agent loop。
4. Weixin 真实私聊需要人工扫码验收。
5. 安装包必须在干净 Windows 验证。
6. secret 脱敏必须贯穿日志和诊断包。
