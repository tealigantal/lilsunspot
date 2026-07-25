# Architecture

## System Context

`setup.exe -> Lilsunspot.exe (Tauri/React) -> lilsunspotd -> Hermes AIAgent -> Provider/model`。微信通过 Hermes Weixin adapter 进入同一个产品会话与 Agent runner。

## Current Runtime Entry Points

- `lilsunspot/daemon/app.py`：token 保护的本地 API 与桌面消息入口。
- `lilsunspot/daemon/gateway.py`、`weixin_runtime.py`：微信入站与回传桥。
- `lilsunspot/daemon/turn_coalescer.py`：桌面/微信纯文本合并与串行。
- `lilsunspot/daemon/agent_runner.py`：统一构造 Hermes `AIAgent`。
- `lilsunspot/desktop/src/`：桌面产品界面。

## Major Components

- 产品配置与能力：Provider registry、Hermes runtime config、capability graph。
- 会话与附件：本地 SQLite 会话镜像、安全附件目录、Hermes SessionDB 映射。
- 控制层：表达风格、生成控制、安全审批、平台工具集。
- 交付层：桌面附件、微信媒体与生成文件。

## Request, Control, and Data Flows

桌面纯文本与微信纯文本均进入 `turn_coalescer`，附件路径直接进入同一个 `send_agent_message()`。`agent_runner` 负责合并对话上下文、表达风格、生成控制、工具集和回调，然后构造 Hermes Agent。assistant 结果镜像到本地消息 metadata 供 UI 展示。

## Data Ownership and Persistence

- 产品数据、token、会话、附件和生成控制状态位于 lilsunspot data dir。
- Hermes config、env、session 和 memory 位于隔离的 `hermes_home`。
- 会话级控制保存在 conversation metadata；单轮覆盖只随本次消息流动。

## External Integrations

Provider API、Ollama/兼容本地端点、Hermes Weixin、可选 Skills/MCP。lilsunspot 不持有外部协议的重复实现。

## Dependency Directions

桌面只调用产品 API；产品层可调用 Hermes 公共运行接口；Hermes core 不依赖 lilsunspot。新增产品逻辑不得反向写入上游核心。

## Security and Trust Boundaries

daemon 仅监听 `127.0.0.1`；除 `/health` 外要求 `X-Lilsunspot-Token`。生成策略永远低于工具权限、审批、文件安全根、外部发送和凭据边界。日志与回复详情只记录脱敏参数和状态。

## Current Architectural Constraints

- Provider transport 支持不一致，sampling 参数必须先过能力解析。
- Hermes fallback 可能切换模型；参数集合必须对所有可达目标保守求交集，或在请求时重新解析。
- `max_iterations` 是 Agent 模型/工具循环预算，不等于精确工具调用数；工具次数需由宿主回调单独记录。

## Known Legacy or Transitional Paths

旧 `modes.py` 的 `务实 / 均衡 / 感性` 和三滑杆曾同时控制表达与运行参数。LIL-GENERATION-CONTROL-01 将其收敛为表达风格，并建立独立生成控制。`lilsunspot/notes/architecture.md` 是历史说明，不再作为当前架构事实源。

## Target Direction

形成 `表达风格 -> Prompt overlay` 与 `生成控制 -> 能力解析后的真实请求参数` 两条独立控制面；桌面、微信、主聊天和回复详情共用同一不可变解析快照。

## Architecture Map

```text
desktop / weixin
      -> conversation + optional turn override
      -> generation resolver (global -> conversation -> turn -> compatibility)
      -> agent runner (same tools, safety, files, memory)
      -> Hermes transport -> provider/model
      -> execution trace -> assistant metadata -> desktop details
```
