# Progress

## Active Goal

LIL-HERMES-UPSTREAM-FULL-SYNC-01：同步执行时可确认的 Hermes 官方最新版，并让 lilsunspot 安装版完整继承上游能力。

## Active ExecPlan

`docs/plans/2026-07-25-hermes-latest-full-capability-lilsunspot.md`

## Current Milestone

Milestone 1 已完成：固定目标 `d9f1043c3337818b1f29224a7deb5bbb17402370` 的真实 Git 对象已抓取并保存为 `upstream/sync-d9f1043`，本地 ancestry 为旧基线 ahead 0 / target ahead 8,485。Milestone 2 能力映射继续进行。

## Completed and Verified

- 已确认桌面与微信最终共享 `agent_runner.send_agent_message()`。
- 已确认旧 Mode 的 `max_tokens`、`reasoning_effort`、`max_iterations` 已真实进入 AIAgent，但 sampling 参数和单轮闭环缺失。
- 已新增独立 resolver、五种预设、三层作用域、模型能力过滤、拒参缓存和一次安全降级重试。
- 已把桌面、微信、coalescer、runner 和 assistant metadata 接到同一解析规则；表达风格不再改变运行参数。
- 桌面已提供基础模式、高级字段、来源/范围/默认值/降级原因、恢复模型默认值和回复执行详情；新增说明文字采用高对比度亮色。
- 自动化已通过 150 个 daemon 测试、secret guard、TypeScript/Vite build；云端 DeepSeek 与本地 Ollama `llama3.2:1b` 均完成真实安装版聊天验证。
- Hermes 原生 `terminal/process` toolset 已默认启用并通过安装版真实只读命令验证；DeepSeek 新安装默认已更新为 `deepseek-v4-flash`。
- Hermes 官方最新版同步计划已建立，并以固定官方 SHA、全能力账本、thin adapter 和安装版端到端证据作为完成门槛。
- 本地已完成的治理、generation control、terminal 和 DeepSeek 修正已拆成逻辑提交并 rebase 到最新 `origin/develop`；macOS 私有 DMG 记录与 Windows 主线内容均已保留，最终自动化和 NSIS 重建通过。
- 已从 `origin/develop@a8880fad7094726b2c3e3ec34218e588c7d8bf19` 建立 `codex/hermes-upstream-full-sync-20260726` 隔离 worktree，原 `develop` 未改动。
- 隔离 worktree 同步前基线：daemon 154 passed，secret guard 通过；桌面 build 因无未跟踪 `node_modules` 被跳过。
- 已固定 Hermes 官方目标 `d9f1043c3337818b1f29224a7deb5bbb17402370`（时间 `2026-07-26T08:26:39Z`），最新 release 观察值为 `v2026.7.20`。
- GitHub 官方 compare 证明旧基线 `2b768535...` 是 merge base，目标 ahead 8,485 commits、behind 0；固定快照报告已记录。
- 2026-07-26 重试 GitHub 成功：固定 SHA 已进入本地对象库并保存为 `refs/remotes/upstream/sync-d9f1043`；本地 `git merge-base`、`--is-ancestor` 和 `rev-list --left-right --count` 分别确认 merge base=`2b768535...`、ancestor exit=0、`0 / 8485`。
- 官方 commit tree 与 GitHub tarball 路径集合完全一致；7,285 个文本文件仅存在 Windows `git archive` CRLF 与 GitHub tarball LF 差异，换行归一化后内容差异为 0。后续合并只使用官方 Git object，不使用合成快照 commit。
- 已增强 `lilsunspot.daemon.upstream_audit` 支持固定快照与 manifest 输出，生成 `lilsunspot/resources/hermes_capability_manifest.json`；目标库存为 57 toolsets、74 静态命名工具、93 plugins、69/111 内置/optional skills、4 optional MCPs、9 个直接继承官方基类的内置 gateway adapters。静态工具扫描明确标为不完整并记录 2 个动态注册点。
- 快照完整性由独立版本化记录 `lilsunspot/resources/hermes_upstream_snapshot_record.json` 约束 archive SHA、唯一根目录、目标 SHA 前缀和解压树 hash；证据等级准确标为 operator-recorded GitHub archive，不冒充官方 Git commit 证明。新增审计单测 4 项通过；能力/产品/审计定向回归 27 项、产品同步脚本 3 项通过；完整 `scripts/check.ps1` 为 daemon 158 passed + secret guard 通过，桌面 build 因无 `node_modules` 跳过。
- 已将固定目标展开为 519 行 parity ledger：57 toolsets、74 tools、93 plugins、180 skills、4 MCPs、30 gateway platforms、4 个真实 provider transports、76+1 config surfaces。57 toolsets、74 tools 和 4 transports 均已设计映射，当前为 135 design_mapped / 384 unspecified、0 validated / 519 needs_validation。
- Ledger 将 `mapping_status=design_mapped|unspecified`、四态 `parity_status` 和安装证据分离；分别记录 `mapping_complete=false`、`ready_complete=false`。执行 owner 不再误写为 safety；integration read/write、operator/cron/platform、Yuanbao TOOLSETS cross-reference 和 browser CDP 动态 toolset/安全要求均单列。
- Toolset/tool slice 最终验证：审计 6 passed、定向 29 passed、daemon 160 passed、secret guard 通过；严格门禁按预期以 `384 mapping-unspecified rows` 拒绝完成。独立只读复核确认本 slice 无 P0 映射阻断。
- Config slice 只读审计确认 77 行暂不能标记 `design_mapped`：目标 schema 为 `_config_version=33`，当前读写路径没有版本门禁、schema 校验、原子备份/回滚或降级拒绝；目标 `model/providers/secrets` 与当前产品 dict/`.env` 形态不同，旧 `platform_toolsets`、`mcp_servers`、`provider_routing` 也没有目标迁移契约。因此配置行继续保持 `unspecified`，防止用计划中的 owner 冒充已实现 consumer。

## Implemented but Not Verified

- 真实 Provider/模型组合无法穷尽；未知组合继续按保守省略和一次拒参降级处理。

## In Progress

- 为剩余 384 行补齐设计映射；先合入固定 SHA 并实现 v33 配置迁移、备份、回滚与降级拒绝，再接受 77 个 config surfaces 的映射。全部 135 个已映射项在正式 merge 和安装版实测前保持 `blocked_not_merged + needs_validation`。

## Next Work

- 提交当前审计检查点后，从 `upstream/sync-d9f1043` 进入正式合并与 thin-adapter 冲突处理；优先实现 v33 配置迁移契约，再继续 plugins、skills、MCP、gateways、provider/runtime 和 packaging 的机器可读映射与验证。

## Blockers

- 当前无外部网络阻断。配置 consumer 依赖目标代码，故执行顺序调整为“保留审计检查点 -> 固定 SHA merge -> v33 migration -> 继续 Milestone 2 映射”，所有未实现项继续 fail closed。

## Recent Decisions

- 旧 Mode 保留为表达风格；生成参数改由独立控制系统负责。
- 不修改 Hermes core；未知/锁定参数默认省略。
- “恢复模型默认值”把字段显式设为 `null` 并在请求中省略，不回退为平衡预设。
- “拥有上游全部能力”以目标 SHA 的能力账本 100% 覆盖和安装版可达为准，不以代码存在或 `/health` 通过代替。

## Resume Instructions

读取 `AGENTS.md`、`PROJECT_GOAL.md`、本文件、active ExecPlan 与 `lilsunspot/notes/upstream-sync-reports/2026-07-26-d9f1043-fixed-snapshot.md`；继续使用已有隔离 worktree/分支。目标已固定为 `d9f1043c3337818b1f29224a7deb5bbb17402370`；继续快照能力账本，Git 恢复后只抓取该 SHA。不要运行 `scripts/hermes_upstream_sync.ps1`，不要在普通开发工作区 merge。
