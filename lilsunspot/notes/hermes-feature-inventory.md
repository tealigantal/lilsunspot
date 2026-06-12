# Hermes 现成功能盘点与小黑子复用建议

日期：2026-06-11

任务：按当前仓库代码盘点 Hermes / lilsunspot 已有能力，整理哪些可以直接借鉴，哪些需要产品化改造，哪些暂不适合放进小黑子默认体验。

边界：

- 本文基于当前本地仓库，不代表上游最新状态。
- 本文只做功能盘点和产品化建议，不修改代码。
- 小黑子仍遵守产品层边界：不重写 Hermes core，新产品代码优先放在 `lilsunspot/`。

## 总体判断

仓库不是一个从零开始的桌面壳。它包含完整 Hermes Agent 上游能力，加上小黑子自己的 Windows 桌面产品层。

对小黑子最有价值的现成方案不是直接把 Hermes 控制台搬进桌面，而是把 Hermes 已有的运行时、会话、模型、工具、审批、状态、日志、定时任务和网关抽象，包装成普通 Windows 用户能理解的中文产品入口。

当前最值得优先参考的是三处：

1. `web/` + `hermes_cli/web_server.py`：已有 Web Dashboard / 管理控制台能力。
2. `ui-tui/` + `tui_gateway/`：已有终端对话控制台、会话、审批、slash、模型切换和工具状态事件。
3. `gateway/`：已有多平台消息网关的 session、pairing、delivery、status 抽象。

## 现有能力地图

| 领域 | 主要入口 | 已有能力 | 小黑子处理建议 |
| --- | --- | --- | --- |
| Agent 运行时 | `agent/` | 对话循环、provider adapter、工具执行、上下文压缩、记忆、错误分类、媒体路由 | 保持上游边界，产品层只包装调用和展示 |
| CLI / 控制命令 | `hermes_cli/` | `hermes`、`model`、`gateway`、`setup`、`doctor`、`cron`、`plugins`、`skills`、`logs` 等命令 | 只参考命令语义，不要求普通用户理解 CLI |
| Web Dashboard | `web/`、`hermes_cli/web_server.py` | sessions、logs、analytics、models、config、env、cron、skills、plugins、themes | 拆成小黑子的“高级诊断/服务状态/历史记录”能力 |
| TUI 控制台 | `ui-tui/`、`tui_gateway/server.py` | 流式对话、会话恢复、模型切换、审批/澄清/secret 输入、slash 补全、工具进度 | 参考交互协议和状态事件，不直接嵌入 TUI |
| Messaging Gateway | `gateway/` | 多平台适配、pairing、session、delivery、status、slash access | 复用抽象思路，微信仍保留小黑子产品层 route/token/审批 |
| Provider / 模型 | `hermes_cli/models.py`、`model_catalog.py`、`agent/model_metadata.py`、`providers/` | 多 provider、模型列表、能力元数据、模型切换、credential 探测 | 变成普通中文“模型服务”页，不暴露复杂配置 |
| 会话 / 历史 | `tui_gateway/server.py`、`web/src/lib/api.ts`、`tools/session_search_tool.py` | session list/resume/delete/history/search/usage | 可用于桌面聊天历史、微信会话搜索、问题定位 |
| 记忆 | `agent/memory_*`、`tools/memory_tool.py` | 持久记忆、用户画像、上下文注入 | 产品化为“偏好记忆/长期记住”，默认要保守 |
| 工具 / Toolsets | `tools/`、`hermes_cli/tools_config.py` | 文件、终端、浏览器、搜索、MCP、图像/视频/语音、todo、kanban、delegate 等 | 默认隐藏高级工具，只把安全可解释能力做成开关 |
| 定时任务 | `cron/`、`tools/cronjob_tools.py`、`hermes_cli/cron.py` | cron scheduler、自然语言任务、平台投递 | 产品化为“提醒/定时总结/定时检查” |
| 审批 / 安全 | `tools/approval.py`、`agent/tool_guardrails.py`、`hermes_cli/secrets_cli.py` | 危险操作审批、secret 输入、脱敏、guardrails | 小黑子应继续包装为中文安全确认，不新增平行机制 |
| Skills / Plugins | `plugins/`、`hermes_cli/skills_hub.py`、`tools/skills_*` | skills hub、插件 manifest、toolsets、dashboard plugin 扩展 | 默认不开放，后续可作为“能力商店/高级扩展” |
| 小黑子产品层 | `lilsunspot/daemon/`、`lilsunspot/desktop/` | 本地 token daemon、Windows 桌面、Provider 配置、mode、Weixin、会话库、附件、安全审批、安装包 | 继续作为普通用户唯一主入口 |

## 与小黑子当前功能重叠的部分

### 模型服务

小黑子已有 `/providers`、`/providers/test`、`/providers/save` 和桌面模型设置页。Hermes 上游已有更完整的 provider/model inventory、模型切换、credential 探测和 model options。

建议：

- 保留小黑子简化模型页。
- 借鉴 Hermes model metadata，显示“当前模型能不能看图、适合日常聊天还是工具任务、是否已连接”。
- 不直接暴露 `.env`、raw config、复杂 provider schema。

### 会话与历史

小黑子已有本地会话库、微信 route、桌面消息列表和附件。Hermes Dashboard/TUI 已经有 session list、history、resume、delete、usage、search。

建议：

- 把 Hermes 的 session/search 思路产品化为小黑子“搜索聊天记录”。
- 微信 route 继续由小黑子维护，因为它涉及桌面显示“微信消息进入这里”和真实微信入站落点一致性。
- 可参考 TUI 的 session boundary / status 事件，减少桌面状态和后端状态错位。

### 审批

小黑子已有 `/safety/approvals` 和微信主动发送审批链路。Hermes 上游已有 approval prompt、tool guardrails、secret prompt。

建议：

- 保留小黑子中文审批 UI。
- 后续接入更多工具时，尽量复用上游 guardrails 和 approval 语义。
- 不为每个新能力单独发明一套审批状态。

### 诊断与日志

小黑子已有 `/doctor/run`、`/runtime/info` 和安装版 smoke/check 记录。Hermes Dashboard 已有 logs、status、analytics、actions status。

建议：

- 做一个隐藏或设置里的“诊断中心”。
- 普通用户看到中文摘要和可执行修复，不看 raw log。
- 高级导出必须继续脱敏 runtime token、API key、微信凭据。

### 微信入口

小黑子已有真实 Weixin runtime、扫码、状态、会话 route、附件、主动发回微信审批。Hermes gateway 已有更通用的 platform/session/delivery/status 结构。

建议：

- 不替换当前微信产品层。
- 借鉴 gateway 的 session、delivery、status 命名，统一“当前微信进入哪个对话”“上一条投递结果”“是否连接”等状态。
- 微信端自然语言切换和桌面“微信消息进入这里”要继续保持同一 route source of truth。

## 不重叠但值得加入的部分

### 定时任务

Hermes 已有 cron scheduler。小黑子当前更偏聊天/微信助手，还没有把它产品化。

建议产品形态：

- “每天 9 点提醒我看日报”
- “每天晚上总结今天微信里和我有关的事情”
- “每周五帮我整理待办”

不要默认展示 cron 表达式。

### 记忆

Hermes 已有 memory/provider/user modeling 相关能力。小黑子当前 mode 和会话已经有部分个性化，但还不是明确的长期记忆产品。

建议产品形态：

- “记住我喜欢简短回复”
- “忘记关于某人的这条信息”
- “查看小黑子记住了什么”

默认应可见、可删除、可关闭。

### Skills / 能力扩展

Hermes 已有 skills hub 和 plugins。小黑子当前目标是 Windows 普通用户安装可用，不适合默认暴露复杂扩展系统。

建议产品形态：

- 先做固定能力开关，如“读文件”“联网搜索”“生成图片”“定时提醒”。
- 后续再考虑“高级能力/插件”，并且必须有清楚的权限说明。

### 工具任务面板

Hermes TUI 和 Dashboard 都有工具执行可视化、tool progress、tool result summary。

建议产品形态：

- 聊天中显示“正在读取文件 / 正在搜索 / 等待你确认”。
- 对工具结果做中文摘要。
- 对高风险动作统一走安全确认。

## 暂不建议直接加入默认体验的部分

- Web Dashboard 全量 config/env 编辑。
- 原生 TUI 或浏览器内嵌 TUI。
- raw logs 长列表。
- plugins、skills、toolsets 的完整管理界面。
- terminal backend、Docker、SSH、Modal、Daytona、Vercel Sandbox 等高级执行环境。
- slash command 作为普通用户主路径。
- 多平台 gateway 全量入口，至少在微信体验稳定前不开放。

这些能力不是没用，而是不适合小黑子的默认用户画像。它们可以作为开发者入口、隐藏诊断或后续高级模式。

## 建议优先级

### P0：先把当前微信/桌面状态做稳

- 当前微信消息进入哪个桌面对话。
- 最近一次微信入站和回复状态。
- 当前模型是否可用。
- 后台是否只有一个有效 daemon。
- 用户误操作后的中文恢复路径。

这部分直接服务当前 bug 和安装版验收。

### P1：做“小黑子诊断中心”

参考 Web Dashboard 的 status/logs/actions，但只展示普通用户能理解的信息：

- 模型服务：已连接 / 未配置 / 测试失败。
- 微信：已连接 / 等待扫码 / 掉线 / 正在回复。
- 桌面服务：运行中 / 需要重启。
- 最近错误：中文解释 + 一键修复或复制诊断信息。

### P1：做聊天历史搜索

参考 Dashboard sessions/search 和 TUI session/history：

- 搜索桌面和微信聊天记录。
- 按微信联系人或会话筛选。
- 打开结果后定位到对应消息。

### P2：做提醒和自动任务

参考 cron，但产品文案是“提醒”和“定时任务”，不暴露 cron。

### P2：做能力开关

参考 skills/toolsets，但先做固定能力：

- 联网搜索。
- 读取本地文件。
- 生成图片。
- 定时提醒。
- 微信主动发送。

每个能力要有中文说明、风险说明和审批边界。

## 后续实现原则

1. 先复用现有 Hermes 语义，再决定是否在 `lilsunspot/` 包装。
2. 不把上游高级控制台原样搬给普通用户。
3. 不新增与上游并行的审批、模型、工具、会话抽象，除非小黑子产品层确实需要隔离。
4. 所有本地 API 继续遵守 `127.0.0.1`、`X-Lilsunspot-Token` 和 secret 脱敏规则。
5. 用户可见错误继续使用普通中文。
6. 每次把上游能力产品化时，都要同步考虑安装版、真实微信、错误使用和恢复路径。
