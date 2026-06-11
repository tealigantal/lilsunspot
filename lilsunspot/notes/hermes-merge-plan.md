# Hermes 能力合并计划

日期：2026-06-11

目标：基于当前仓库已有 Hermes 能力，规划如何逐步并入小黑子产品体验；同时预留后续“自动同步 Hermes 官方更新”的功能入口和工程边界。

范围：

- 本计划只基于当前本地仓库已有代码和文档。
- 不在本文中做 Hermes 官方最新 upstream 对比。
- 不要求立即实现自动同步；但后续实现时应能直接按本文拆分落地。

## 执行状态

2026-06-11 已执行 Phase 0 的落地项：

- 新增 `lilsunspot/notes/hermes-feature-inventory.md`，完成当前仓库已有 Hermes 能力盘点。
- 新增本文，固定小黑子合并 Hermes 能力的阶段路线和产品边界。
- 新增 `scripts/hermes_upstream_check.ps1`，作为未来官方更新同步的只读检查入口。
- 新增 `lilsunspot/tests/test_hermes_upstream_check_script.py`，约束检查脚本默认不 fetch、不创建分支、不执行 merge 类操作，只生成报告。
- 运行只读检查，生成 `lilsunspot/notes/upstream-sync-reports/2026-06-11-203215.md`。

本次只读检查没有联网，也没有执行同步。它使用本地已有 `upstream/main` 和 `lilsunspot/UPSTREAM_COMMIT.txt` 计算差异：当前缓存的 upstream ref 相对记录 base 有 650 commits、1757 changed files。由于工作树已有大量未提交改动，后续真正 sync 必须等工作树干净或明确隔离变更后再做。

2026-06-11 已执行 Phase 1-7 的最小产品版落地：

- Phase 1：继续收敛微信 route 状态，兼容旧无账号 route 与带账号 route 并存时的入站落点。
- Phase 2：新增 `/diagnostics/summary` 和桌面“控制台”诊断摘要，不恢复 raw Dashboard。
- Phase 3：新增 `/conversations/search` 和聊天左栏搜索，优先搜索小黑子本地会话库和附件摘要。
- Phase 4：新增 `/providers/capabilities`，把当前 provider/model 的文字、图片、文件、微信和提醒能力映射成普通用户可读状态。
- Phase 5：新增本地提醒记录 API 和桌面管理入口；当前不包含后台调度器，也不会自动发微信。
- Phase 6：新增本地记忆记录 API 和桌面管理入口；当前不自动注入 prompt，先保证可见、可停用、可删除。
- Phase 7：新增产品层能力开关 API 和桌面开关；当前是 allowlist/审批元数据基础，未把所有未来工具调用强制接入。
- 自动同步预留：新增 `/upstream/status` 读取最近只读报告，作为以后接入官方更新检查 UI 的数据面。

## 合并总原则

1. 小黑子是普通 Windows 用户产品层，Hermes 是上游能力层。
2. 不重写 Hermes core；确实需要改上游逻辑时，优先做最小补丁并记录原因。
3. 新产品代码放在 `lilsunspot/`，上游能力通过 adapter、service 或 API wrapper 接入。
4. 默认体验只暴露普通用户能理解的中文功能；高级控制台能力进入设置、诊断或开发者入口。
5. 每个合并项都必须明确 source of truth、状态展示、错误恢复、测试方式和安装版影响。
6. 涉及桌面、Tauri、sidecar、微信运行态或安装版交付的改动，仍按 `AGENTS.md` 要求跑完整构建和 NSIS 检查。

## 目标架构

```text
Hermes upstream code
  agent/ gateway/ tools/ cron/ web/ ui-tui/ tui_gateway/ hermes_cli/
        |
        | narrow adapters, no broad fork rewrite
        v
lilsunspot integration layer
  daemon services, compatibility probes, state mappers, safety wrappers
        |
        v
lilsunspot product API
  /providers /conversations /gateway/weixin /safety /doctor /events/stream
        |
        v
Windows desktop UX
  chat, Weixin, model service, diagnostics, search, reminders, capability switches
```

核心思想：不要把 Hermes Dashboard 或 TUI 原样搬进桌面，而是把它们已经验证过的能力拆成小黑子的服务和 UI。

## 阶段计划

### Phase 0：能力清单和边界固定

状态：已落地第一步。

输入：

- `lilsunspot/notes/hermes-feature-inventory.md`
- `lilsunspot/notes/architecture.md`
- `TASKS.md`

产出：

- 维护一份“可直接复用 / 包装后复用 / 暂不开放”的能力清单。
- 每次接入 Hermes 能力前，先判断它属于上游 core、product wrapper、desktop UI 还是 installer/runtime 交付。
- 保留只读 upstream check 入口，为后续自动同步做报告和分类基础。

验收：

- 新功能任务能在开始前指出参考的 Hermes 入口。
- 不再出现“仓库里已有控制台/方案但实现时完全没参考”的情况。
- `scripts/hermes_upstream_check.ps1` 能在不联网、不修改 git 状态的情况下生成 upstream 分类报告。

### Phase 1：微信和桌面状态合并

优先级：最高。

状态：已落地最小产品版，后续继续以真实微信人工验收补强。

当前小黑子已有：

- 微信扫码、runtime 状态、入站/回复、附件、主动发回微信审批。
- 本地会话库、微信 route、桌面“微信消息进入这里”。

参考 Hermes 能力：

- `gateway/` 的 session、delivery、status、pairing。
- `tui_gateway/server.py` 的 session status 和事件边界。

合并方式：

- 保留小黑子的微信 route 作为产品层 source of truth。
- 引入更清晰的状态模型：连接状态、当前微信进入的对话、最近入站、最近回复、最近投递失败。
- 桌面和微信自然语言切换都只更新同一个 route 状态，不再产生并行状态。

优先功能：

- 微信状态摘要：已连接、等待扫码、正在回复、回复失败。
- 当前 route 可见：微信消息现在进入哪个桌面对话。
- 最近错误中文解释：模型不可用、微信未连接、附件不可读、审批未通过。

测试重点：

- 旧 route key、带 account_id route、多账号同联系人。
- 桌面设为当前后真实微信入站落点。
- 删除/归档/恢复当前微信对话。
- 用户错误编号、错误自然语言切换、重复点击。

### Phase 2：诊断中心

优先级：高。

状态：已落地最小产品版，当前提供摘要和状态聚合，不导出诊断包。

参考 Hermes 能力：

- Web Dashboard 的 status、logs、actions status、models。
- 小黑子已有 `/doctor/run`、`/runtime/info`、`/app/bootstrap`。

产品形态：

- 设置里新增或恢复“诊断中心”，但不暴露 raw Dashboard。
- 普通用户只看到中文摘要和修复按钮。
- 高级信息放到“复制诊断信息”，且必须脱敏。

建议模块：

- 模型服务：是否配置、测试是否通过、当前模型。
- 微信服务：扫码状态、runtime 状态、最后一次入站/回复时间。
- 桌面服务：daemon 是否运行、端口、安装版路径。
- 最近问题：中文错误、建议动作、是否需要重启。

验收：

- 不输出 API key、runtime token、微信 credential。
- 安装版可用。
- 诊断结果能解释常见用户问题，而不是只给技术 JSON。

### Phase 3：聊天历史和搜索

优先级：高。

状态：已落地最小产品版，当前支持本地会话消息和附件摘要搜索。

参考 Hermes 能力：

- Web Dashboard 的 sessions/search。
- `tools/session_search_tool.py`。
- TUI 的 session list/history/resume/delete。

小黑子产品形态：

- 搜索桌面和微信聊天记录。
- 按“桌面对话 / 微信联系人 / 附件 / 时间”筛选。
- 点击结果定位到对应消息。

合并方式：

- 优先基于小黑子本地会话库实现产品搜索。
- 借鉴 Hermes FTS/search 设计和结果摘要方式。
- 不直接混用 Hermes 上游 session DB，避免产品层会话 route 被打散。

验收：

- 搜索不泄露 token、key、credential。
- 大量消息时仍可接受。
- 中文搜索、附件摘要搜索、归档会话搜索行为明确。

### Phase 4：模型能力和 Provider 状态

优先级：中高。

状态：已落地最小产品版，当前以现有 provider 配置和 Hermes model metadata 兼容探测为主。

参考 Hermes 能力：

- `hermes_cli/models.py`
- `hermes_cli/model_switch.py`
- `agent/model_metadata.py`
- `providers/`
- Web Dashboard models 页面。

小黑子产品形态：

- 当前模型是否可用。
- 是否支持图片识别。
- 是否适合工具任务。
- 如何获取 API key。
- 测试失败给中文原因。

合并方式：

- 保留小黑子的简化 provider 保存和测试流程。
- 引入 Hermes model metadata 作为能力展示来源。
- 不暴露复杂 `.env` 和 raw config 编辑。

验收：

- DeepSeek、OpenAI-compatible、视觉模型的能力显示准确。
- 错误提示不含 secret。
- 安装版首启路径仍简单。

### Phase 5：提醒和自动任务

优先级：中。

状态：已落地本地提醒记录和桌面管理；完整定时调度、失败重试和自动总结仍未实现。

参考 Hermes 能力：

- `cron/`
- `tools/cronjob_tools.py`
- `hermes_cli/cron.py`
- Web Dashboard cron 页面。

小黑子产品形态：

- “提醒我明天 9 点看日报”
- “每天晚上总结今天的聊天”
- “每周五整理待办”

合并方式：

- 不把 cron 表达式作为默认入口。
- daemon 层提供 reminders/jobs API。
- 桌面提供创建、暂停、恢复、删除、立即运行。
- 微信投递必须经过明确用户选择和安全边界。

验收：

- 重启后任务仍存在。
- 时区行为明确。
- 失败任务能在诊断中心看到。
- 不因任务自动发送高风险微信消息。

### Phase 6：记忆

优先级：中。

状态：已落地本地记忆记录和桌面管理；prompt 注入、自然语言记忆抽取和联系人级策略仍未实现。

参考 Hermes 能力：

- `agent/memory_manager.py`
- `agent/memory_provider.py`
- `tools/memory_tool.py`

小黑子产品形态：

- “记住我喜欢简短回复”
- “不要再记住这件事”
- “查看小黑子记住了什么”

合并方式：

- 默认保守开启或显式询问。
- 记忆必须可见、可删除、可关闭。
- 微信联系人相关记忆要谨慎，避免误把临时聊天当长期事实。

验收：

- 用户能查看和删除记忆。
- 不记录 secret、token、credential。
- mode profile 和长期记忆边界清楚。

### Phase 7：能力开关和高级扩展

优先级：后置。

状态：已落地产品层能力开关和审批元数据；未来工具接入时仍需逐项强制执行。

参考 Hermes 能力：

- `tools/`
- `skills/`
- `plugins/`
- Web Dashboard skills/plugins/toolsets。
- TUI tools/skills 管理命令。

小黑子产品形态：

- 默认固定能力开关：联网搜索、读取文件、生成图片、定时提醒、微信主动发送。
- 高级用户再进入 plugins/skills。

合并方式：

- 先做产品层 allowlist，不直接开放全部 tools。
- 每个能力有中文说明、权限说明、审批要求。
- 高风险工具默认需要确认。

验收：

- 普通用户不会误开危险能力。
- 工具失败有中文错误和恢复建议。
- 审批链路复用统一安全模型。

## 自动同步 Hermes 官方更新的预留设计

目标：后续可以加入“检查、拉取、审计、合并 Hermes 官方更新”的功能，但不能让它绕过小黑子的产品边界和发布验证。

### 建议能力边界

自动同步不应等同于自动覆盖当前仓库。它应该分成四层：

1. 检查更新：联网读取官方 upstream 最新 commit。
2. 生成报告：列出新增文件、修改模块、依赖变化、潜在冲突。
3. 创建同步分支：自动建 `codex/hermes-sync-YYYYMMDD` 之类的分支。
4. 半自动合并：能自动合的合，冲突和产品边界问题交给 agent/开发者处理。

默认不做：

- 不在用户安装版里静默改代码。
- 不自动发布安装包。
- 不自动接受破坏小黑子产品层的 upstream 改动。
- 不把官方 Dashboard/TUI 新功能直接暴露给普通用户。

### 推荐实现入口

已新增：

```text
scripts/hermes_upstream_check.ps1
lilsunspot/notes/upstream-sync-reports/
```

后续可新增：

```text
scripts/hermes_upstream_sync.ps1
lilsunspot/daemon/upstream_status.py
lilsunspot/desktop/src/features/settings/UpstreamSettings.tsx
```

说明：

- `hermes_upstream_check.ps1`：只检查和生成报告，不改工作树；默认不联网，只有显式传入 `-Fetch` 才会更新本地 remote ref。
- `hermes_upstream_sync.ps1`：创建同步分支并执行受控 merge/cherry-pick。
- `upstream-sync-reports/`：保存每次检查报告，不记录 secret。
- daemon/desktop 入口仅适合高级诊断，不应默认展示给普通用户。

### 上游同步元数据

建议维护：

```text
UPSTREAM_COMMIT.txt
lilsunspot/notes/upstream-sync-reports/YYYY-MM-DD.md
```

报告字段：

- 当前本地 upstream base commit。
- 官方 upstream 最新 commit。
- commit 数量和摘要。
- 变更目录分类。
- 依赖变更。
- 潜在冲突。
- 建议处理方式：直接合并、需要适配、暂缓、拒绝。
- 必跑验证。

### 变更分类规则

同步工具应按目录初步分类：

| 分类 | 目录/文件 | 默认处理 |
| --- | --- | --- |
| Hermes core runtime | `agent/` | 需要测试和兼容审计 |
| Messaging gateway | `gateway/` | 微信相关必须人工复核 |
| Tools | `tools/` | 需要安全和审批审计 |
| Provider/model | `providers/`、`hermes_cli/models*`、`agent/model_metadata.py` | 倾向合并，但要更新小黑子模型展示 |
| Dashboard/TUI | `web/`、`ui-tui/`、`tui_gateway/` | 可借鉴，不默认暴露 |
| Cron/memory/skills/plugins | `cron/`、`plugins/`、skills 相关 | 需要产品化评估 |
| Packaging/deps | `pyproject.toml`、`package*.json`、Rust/Tauri 配置 | 高风险，必须完整构建 |
| lilsunspot product | `lilsunspot/` | 官方一般不应覆盖，需人工判断 |

### 同步流程

建议后续自动同步按这个流程实现：

1. 确认工作树是否干净；不干净时只允许 check，不允许 sync。
2. `git fetch` 官方 Hermes remote。
3. 读取 `UPSTREAM_COMMIT.txt`，计算本地 base 到官方 latest 的 diff。
4. 生成报告并按目录分类。
5. 如果用户确认，创建 `codex/hermes-sync-YYYYMMDD` 分支。
6. 执行受控 merge 或 cherry-pick。
7. 对冲突文件标记分类，禁止自动解决 `lilsunspot/` 产品边界冲突。
8. 跑验证：
   - daemon pytest
   - product pytest
   - secret guard
   - desktop build
   - `scripts/check.ps1`
   - 如影响安装版，跑 Tauri build 并确认 NSIS setup.exe
9. 更新 `UPSTREAM_COMMIT.txt` 和同步报告。
10. 由 agent 总结可合并项、暂缓项和风险。

### UI 形态

如果以后要在小黑子桌面里加入口，建议放在“高级诊断”里：

- “检查 Hermes 官方更新”
- “查看更新报告”
- “创建同步分支”

不要放：

- 默认首页。
- 微信页。
- 普通模型设置页。

普通用户安装版不应该看到“自动改代码”的路径。这个能力主要服务开发者和维护者。

## 每个合并任务的标准模板

后续从 Hermes 现有能力合并到小黑子时，任务应写清：

```text
目标：
参考 Hermes 入口：
小黑子产品入口：
source of truth：
需要新增/修改的文件：
不做的事：
用户错误使用场景：
需要验证：
安装版影响：
剩余风险：
```

## 当前建议的下一步

1. 当前主线继续先稳微信会话 route、真实回复状态和安装版行为。
2. 下一个产品化功能优先做“诊断中心”，因为它能直接吸收 Dashboard/status/logs 现有能力，也能帮助定位真实用户问题。
3. 再做“聊天历史搜索”，把当前本地会话库和 Hermes session/search 思路合并。
4. 自动同步 Hermes 官方更新先按本文作为预留设计，等主线稳定后再实现 `check` 脚本，最后再做 `sync` 脚本和高级 UI。
