# Progress

## Active Goal

LIL-HERMES-UPSTREAM-FULL-SYNC-01：同步执行时可确认的 Hermes 官方最新版，并让 lilsunspot 安装版完整继承上游能力。

## Active ExecPlan

`docs/plans/2026-07-25-hermes-latest-full-capability-lilsunspot.md`

## Current Milestone

执行计划已建立；在正式 Hermes 同步前先完成本地 `develop` 工作区收口并与 `origin/develop` 对齐。

## Completed and Verified

- 已确认桌面与微信最终共享 `agent_runner.send_agent_message()`。
- 已确认旧 Mode 的 `max_tokens`、`reasoning_effort`、`max_iterations` 已真实进入 AIAgent，但 sampling 参数和单轮闭环缺失。
- 已新增独立 resolver、五种预设、三层作用域、模型能力过滤、拒参缓存和一次安全降级重试。
- 已把桌面、微信、coalescer、runner 和 assistant metadata 接到同一解析规则；表达风格不再改变运行参数。
- 桌面已提供基础模式、高级字段、来源/范围/默认值/降级原因、恢复模型默认值和回复执行详情；新增说明文字采用高对比度亮色。
- 自动化已通过 150 个 daemon 测试、secret guard、TypeScript/Vite build；云端 DeepSeek 与本地 Ollama `llama3.2:1b` 均完成真实安装版聊天验证。
- Hermes 原生 `terminal/process` toolset 已默认启用并通过安装版真实只读命令验证；DeepSeek 新安装默认已更新为 `deepseek-v4-flash`。
- Hermes 官方最新版同步计划已建立，并以固定官方 SHA、全能力账本、thin adapter 和安装版端到端证据作为完成门槛。

## Implemented but Not Verified

- 真实 Provider/模型组合无法穷尽；未知组合继续按保守省略和一次拒参降级处理。

## In Progress

- 正在把已完成的 generation control、terminal、DeepSeek 默认值和治理文档按逻辑提交收口，并同步到远端 `develop`。

## Next Work

- 工作区干净并与 `origin/develop` 对齐后，按 active ExecPlan 进入 Milestone 0：建立隔离的 Hermes upstream 同步 worktree。

## Blockers

- 无。

## Recent Decisions

- 旧 Mode 保留为表达风格；生成参数改由独立控制系统负责。
- 不修改 Hermes core；未知/锁定参数默认省略。
- “恢复模型默认值”把字段显式设为 `null` 并在请求中省略，不回退为平衡预设。
- “拥有上游全部能力”以目标 SHA 的能力账本 100% 覆盖和安装版可达为准，不以代码存在或 `/health` 通过代替。

## Resume Instructions

读取 `AGENTS.md`、`PROJECT_GOAL.md`、本文件与 active ExecPlan；确认本地 `develop` 与 `origin/develop` 对齐且工作树干净，再从固定基线创建隔离 upstream 同步 worktree。不要在普通开发工作区直接 merge Hermes upstream。
