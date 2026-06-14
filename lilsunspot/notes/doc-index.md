# lilsunspot 文档索引

## 推荐阅读顺序

1. README.lilsunspot.md
2. TASKS.md
3. lilsunspot/notes/mvp-p0-status.md
4. lilsunspot/notes/architecture.md
5. lilsunspot/notes/hermes-feature-inventory.md
6. lilsunspot/notes/hermes-merge-plan.md
7. lilsunspot/notes/model-capability-ux-plan.md
8. lilsunspot/README-dev.md
9. lilsunspot/notes/qa-checklist.md
10. lilsunspot/notes/decision-log.md
11. lilsunspot/notes/doc-inventory.md

## 主文档

- `README.lilsunspot.md`：lilsunspot 小黑子产品总入口，说明目标、当前真实状态和下一步。
- `TASKS.md`：当前任务队列入口，Current/Next/Blocked/Done 以此为准。
- `lilsunspot/notes/mvp-p0-status.md`：P0 主路径状态表，未运行或未确认的能力必须标记为未验证。
- `lilsunspot/notes/architecture.md`：产品层边界、目录职责和运行时数据流说明。
- `lilsunspot/notes/hermes-feature-inventory.md`：Hermes 现成功能盘点，记录 Web Dashboard、TUI、gateway、tools、cron、memory 等能力如何为小黑子复用或产品化。
- `lilsunspot/notes/hermes-merge-plan.md`：Hermes 能力合并路线，包含微信/诊断/搜索/模型/cron/memory/toolsets 的阶段计划，以及后续自动同步官方更新的预留设计。
- `lilsunspot/notes/model-capability-ux-plan.md`：模型能力、用户意图、辅助模型、错误解释和全链路验收的产品级规划；后续不要再用单点关键词或局部补丁替代能力编排。
- `lilsunspot/README-dev.md`：本地开发入口，记录 daemon、desktop、检查和构建命令。
- `lilsunspot/notes/qa-checklist.md`：发布前 QA 清单，未实际通过的项目保持未勾选。
- `lilsunspot/notes/decision-log.md`：关键产品和工程决策记录。
- `lilsunspot/notes/doc-inventory.md`：Markdown 文档清单和参考优先级。

## 历史文档

- `lilsunspot/notes/agent-memory.md`：历史 agent 任务记录，可作为追溯参考，不直接代表当前主线状态。
- `lilsunspot/notes/day1-status.md`：Day1 历史状态记录，部分内容已被后续任务覆盖。
- `lilsunspot/notes/weixin-feasibility.md`：Weixin 可行性调查记录，真实私聊能力仍需人工扫码验收。
- `lilsunspot/notes/upstream-sync-reports/`：Hermes upstream 只读检查报告目录；报告来自本地 git/ref 状态，不等同于已完成同步。
- `TASKS.md` 的 Done 区：历史任务记录，当前状态以 `lilsunspot/notes/mvp-p0-status.md` 为准。

## 上游 Hermes 文档

根 `README.md`、`README.zh-CN.md`、`CONTRIBUTING.md`、`RELEASE_*.md`、`website/docs/**`、`providers/README.md`、`plugins/**/README.md`、`skills/**` 和 `optional-skills/**` 主要保留上游 Hermes Agent 说明。它们可用于理解上游能力，但不作为 lilsunspot 当前任务和验收状态的主要依据。

## Codex 使用规则

- 先读 doc-index。
- 再读 mvp-p0-status。
- 再读 TASKS。
- 不要直接根据历史记录判断当前状态。
- 不要大面积修改 Hermes 核心。
- 新增代码优先放 lilsunspot/。
- 本任务不改代码。
