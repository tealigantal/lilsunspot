# Validation

## Hermes v33 / Windows sidecar release candidate - 2026-07-26

- Scope: fixed Hermes `d9f1043c3337818b1f29224a7deb5bbb17402370`, v33 migration, dynamic extension packaging, safety boundaries, NSIS new install/upgrade, real Provider and Weixin network probes.
- Automated: `scripts/check.ps1` passed: daemon `165 passed`, secret guard passed, TypeScript/Vite build passed. Focused migration/auth/capability/audit tests: `37 passed`; Weixin packaging/login tests: `21 passed`.
- Windows installer: `npm run tauri:build --prefix lilsunspot/desktop` passed. Fresh artifact: `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`.
- Installed-app evidence: silent new install/start/token/bind/uninstall passed; installed sidecar catalog found `plugins=93`, `skills=180`, `optional_mcps=4`, `gateways=30`; seeded v32 data migrated to v33 with one restorable backup; real DeepSeek connection, save and Hermes agent-loop chat passed without recording a key or reply; actual Tencent iLink QR acquisition and Chinese pending-login response passed after packaging the official `messaging` extra.
- Security evidence: catalog requires token; catalog query is read-only; migration failure/rollback and newer-schema downgrade rejection are covered by tests; no secret-like values found. Provider and Weixin test data were in system temp paths and purged after test.
- Remaining external acceptance: no existing local Weixin credentials were present, so no person can truthfully claim account-confirmed inbound/outbound chat until the account holder scans and confirms the real QR. No QR payload, account ID, token, private text, API key or model reply was recorded.

## Hermes capability parity ledger schema - 2026-07-26

- Scenario: 将固定目标清单变成逐项可阻断的产品/安装版 parity ledger，避免源码存在被当作已集成。
- Exact Steps or Command: 从官方 toolset/tool registries、plugin manifests、skill frontmatter、MCP manifests、gateway platform keys、具体 `ProviderTransport` 子类和 config schema 生成 stable IDs；加载独立 overrides；运行 focused pytest 和严格 completion gate 单测。
- Actual Observable Result: 519 rows：57 toolsets、74 tools、93 plugins、180 skills、4 MCPs、30 gateways、4 provider transports、76 user config + 1 internal config。57 toolsets、74 tools、4 transports 已设计映射；当前 `design_mapped=135/unspecified=384/validated=0/needs_validation=519`，`mapping_complete=false/ready_complete=false`。执行 owner、安全策略、operator/cron/platform、integration read/write、Yuanbao cross-reference、browser CDP 动态 toolset 均分开记录。
- Automated Validation: audit schema 6 passed；tool mapping focused 29 passed；strict gate exit 2 with `384 mapping-unspecified rows`；`scripts/check.ps1` daemon 160 passed + secret guard passed，desktop build 因隔离 worktree 无 `node_modules` 跳过；独立只读复核确认本 slice 无 P0。
- Safety Boundary: `mapping_status` 与四态 `parity_status` 分离；缺少 bundle、installed discovery/invocation、config/safety/negative-test assessment、timestamp 或 evidence IDs 时不能 validated；最终门禁同时要求 mapping 与 validation 完成。
- Config Audit: 目标 `_config_version=33`；当前产品缺少版本门禁、schema 校验、备份/回滚、降级拒绝及 config+secret 事务写入，且 model/providers/secrets 与旧产品键存在结构漂移。因此撤回未实现的 config 批量映射，77 行保持 `unspecified`，待固定 SHA 合并后的 v33 migration 契约验证通过再接受。
- Validation Harness Finding: 冷启动单测中 Hermes plugin/models.dev 初始化可超过原先 3 秒 clarify 等待窗口；测试现等待明确 pending 或 worker 提前结束，并在失败时显示线程结果。`scripts/check.ps1` 现显式传播 pytest、secret guard 与 npm 的 native exit code，不再在 pytest 失败后误报 `lilsunspot check passed`。
- Checkpoint Revalidation: clarify + upstream audit focused `7 passed`；完整 `scripts/check.ps1` 为 daemon `160 passed`、secret guard passed，desktop build 因隔离 worktree 无 `node_modules` 跳过；`git diff --check` 仅报告 Windows LF/CRLF 转换提示。
- Remaining Risk: 519 行尚未逐项填 ownership mapping；strict completion gate 当前应失败，不能开始盲 merge。
- Evidence: `lilsunspot/notes/hermes-capability-parity/d9f1043c3337818b1f29224a7deb5bbb17402370.md`、machine manifest、schema tests、两路独立只读审计。
- Date: 2026-07-26.

## Hermes fixed Git object retry and ancestry - 2026-07-26

- Scenario: GitHub smart-HTTP 恢复后，只抓取已固定 SHA，不移动浮动 `upstream/main`。
- Exact Steps or Command: `git fetch upstream <fixed-sha> --no-tags`；持久化为 `refs/remotes/upstream/sync-d9f1043`；运行 `git cat-file`、`git merge-base`、`git merge-base --is-ancestor`、`git rev-list --left-right --count`；从官方 commit object 导出树并与已记录 tarball 按路径和换行归一化内容比较。
- Actual Observable Result: commit=`d9f1043c3337818b1f29224a7deb5bbb17402370`，subject 与时间匹配固定记录；merge base=`2b768535c9ba2a8d3b2c23fae1ee3a2f827f7f49`，ancestor exit=0，left/right=`0 / 8485`。官方 Git diff=`6162 files changed, 1347582 insertions, 118739 deletions`。官方 tree 与 tarball 均为 7,460 个路径；归一化 CRLF/LF 后内容差异为 0。
- Safety Boundary: 未移动 `upstream/main`，未 merge，未更新 `UPSTREAM_COMMIT.txt`，未 commit/push。
- Remaining Risk: Milestone 2 全量 owner/entry/config/safety/package/evidence 映射尚未完成，不能直接盲合并 6,162 文件差异。
- Date: 2026-07-26.

## Hermes fixed target and snapshot audit - 2026-07-26

- Scenario: Git smart-HTTP 持续不可用时，使用官方认证 API 固定本轮唯一目标，并从该 SHA 的官方快照开始能力盘点。
- User Intent: 继续 Hermes 官方最新同步，不用陈旧缓存 ref 或丢失 ancestry 的代替物伪称 merge 完成。
- Exact Steps or Command: `gh api repos/NousResearch/hermes-agent/git/ref/heads/main`；`gh api repos/NousResearch/hermes-agent/commits/<target>`；`gh api repos/NousResearch/hermes-agent/compare/<base>...<target>`；下载固定 SHA tarball 到 `ignored/`；把下载事实写入独立版本化 snapshot record；校验 archive SHA、唯一 tar 根目录、目标 SHA 前缀和解压树 hash；用隔离临时 Git 索引比较树；对快照运行 AST 注册表枚举逻辑。
- Expected Observable Result: 获得不浮动的官方 SHA、提交元数据、旧基线关系和可重复快照证据；同时保留“尚未 fetch Git 对象”的限制。
- Actual Observable Result: target=`d9f1043c3337818b1f29224a7deb5bbb17402370`，commit time=`2026-07-26T08:26:39Z`，release=`v2026.7.20`；compare status=`ahead`、merge base=`2b768535c9ba2a8d3b2c23fae1ee3a2f827f7f49`、ahead=`8485`、behind=`0`。快照 `77085957` bytes，SHA-256=`E12EF7FBD2A3FEA01F434430B184D20F86CD9FAAA61499A8414A548A92E01DBA`，解压树 SHA-256=`CC6ABD19FE9B5A1727FF4D57C1F850E50AD2ABFF05ADAA32D539CF8F2D313205`（7,460 files）。该证据只保证操作员记录的 GitHub 归档完整性，不证明本地存在官方 commit object。树比较为 6,202 files changed；初步 registry 差异已记录到报告。
- Automated Validation: `python -m pytest lilsunspot/daemon/tests/test_upstream_audit.py -q` -> 4 passed；capability/product/audit focused -> 27 passed；`python -m pytest lilsunspot/tests/test_hermes_upstream_check_script.py -q --timeout-method=thread` -> 3 passed；`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` -> daemon 158 passed、secret guard 通过、桌面 build 因隔离 worktree 无 `node_modules` 跳过。
- Failure and Recovery Path: 快照与临时索引均位于 `ignored/hermes-upstream-snapshot/`，可完整丢弃而不影响项目 Git 历史；当前未删除。Git 恢复后仅抓取已固定 SHA。
- Evidence: `lilsunspot/notes/upstream-sync-reports/2026-07-26-d9f1043-fixed-snapshot.md`、`lilsunspot/resources/hermes_upstream_snapshot_record.json`、GitHub API 输出、archive/tree hash、临时树 diff 与 AST 枚举输出。
- Remaining Risk: 快照不包含可本地验证的官方 Git commit ancestry；能力账本尚未 100% 完成；尚未 merge、构建或验证安装版。
- Date: 2026-07-26.

## Hermes upstream sync Milestone 0 - 2026-07-26

- Scenario: 为 `LIL-HERMES-UPSTREAM-FULL-SYNC-01` 建立不影响主工作区的可恢复同步起点。
- User Intent: 开始同步 Hermes 官方最新任务，并保留 lilsunspot 当前 Windows 产品基线。
- Preconditions: 主工作树 `develop` clean，`HEAD == origin/develop == a8880fad7094726b2c3e3ec34218e588c7d8bf19`。
- Environment: Windows；隔离 worktree `C:\Users\24179\Desktop\Personal-Agent\lilsunspot-hermes-upstream-full-sync-20260726`；分支 `codex/hermes-upstream-full-sync-20260726`。
- Exact Steps or Command: 校验目标路径/分支不存在后执行 `git worktree add -b codex/hermes-upstream-full-sync-20260726 <isolated-path> origin/develop`；在新 worktree 执行 `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`。
- Expected Observable Result: 新 worktree clean，原工作树不变，同步前失败项有可追溯记录。
- Actual Observable Result: 新 worktree 与原 `develop` 均保持 `a8880fad7094726b2c3e3ec34218e588c7d8bf19`；daemon `154 passed in 62.81s`，secret guard 通过，脚本退出码 0。桌面 build 因新 worktree 不包含未跟踪 `lilsunspot/desktop/node_modules` 而被脚本跳过。
- Failure and Recovery Path: 同步分支失败时可保留或移除该独立 worktree/分支，无需 reset 原 `develop`；本轮未执行删除。
- Evidence: `git status --short --branch`、`git worktree list --porcelain`、`git rev-parse HEAD`、`scripts/check.ps1` 输出。
- Remaining Risk: 桌面 TypeScript/Vite 基线尚未在隔离 worktree 执行；不能把本次脚本通过当作完整桌面基线。GitHub Git remote/fetch 连接四次失败，M1 尚未获得官方最新 SHA。
- Date: 2026-07-26.

## Develop workspace consolidation - 2026-07-25

- Scenario: 整理本地脏工作区，并在不触碰 `main`、不创建 PR 的前提下同步最新远端 `develop`。
- Actual Observable Result: 将变更拆为项目治理、独立生成控制、Hermes 终端与 DeepSeek 默认值、状态记录四组提交；rebase 到包含 macOS 私有 DMG 与 Hermes 同步计划的最新 `origin/develop`，手工合并 `AGENTS.md` 和 `TASKS.md`，保留双方 `agent-memory.md` 记录。
- Validation:
  - `py -3 -m pytest lilsunspot/daemon/tests -q`：154 passed。
  - `py -3 -m pytest lilsunspot/tests -q --timeout-method=thread`：52 passed；同步前发现 5 个产品测试仍断言旧 Mode 运行策略，已改为验证表达滑杆不改变生成预算后通过。
  - `pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`：daemon 154 passed、secret guard、桌面 TypeScript/Vite build 通过。
  - `npm run tauri:build --prefix lilsunspot/desktop`：通过；NSIS 为 `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`，56,737,444 bytes，时间 2026-07-25 22:49:25 +08:00。
  - `git diff --check`：通过；pytest 临时根 `.pytest-lilsunspot-daemon/` 已加入 `.gitignore`，未进入提交。
- Remaining Risk: 本次只完成仓库与构建验证，没有覆盖安装新 NSIS、真实 Provider、真实微信或 macOS 实机；这些能力沿用各自最近一次记录，不能把本次构建等同于新的现场验收。
- Date: 2026-07-25.

## LIL-GENERATION-CONTROL-01 - 2026-07-25

- Scenario: 五种生成模式真实改变下一轮请求。
- User Intent: 用普通概念控制稳定性、长度、思考和行动预算。
- Preconditions: 临时 data dir、已配置 fake/真实 Provider。
- Environment: Windows、当前 `develop`、隔离的 lilsunspot data dir。
- Representative Data: 云端模型、Ollama 本地模型、支持与不支持参数的 fake Provider。
- Exact Steps or Command: focused pytest；`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`；`npm run tauri:build --prefix lilsunspot/desktop`；安装版 smoke。
- Expected Observable Result: 三层作用域、兼容锁定、单次降级、桌面/微信一致、回复详情脱敏且安全边界不变。
- Actual Observable Result: 五种模式进入不同 AIAgent/request kwargs；global < conversation < turn 按字段生效；不支持字段省略；明确拒参只移除目标字段并重试一次；桌面/微信共用 resolver；工具与审批配置在模式间保持一致。
- Failure and Recovery Path: 记录原始失败分类但不记录秘密；不兼容参数只重试一次；构建失败保留旧安装产物并记录阻断。
- Evidence:
  - `C:\Program Files\Python311\python.exe -m pytest lilsunspot/daemon/tests`：150 passed，76.25s。
  - `powershell -ExecutionPolicy Bypass -File scripts/check.ps1`：secret guard 与桌面 TypeScript/Vite build 通过；注意脚本当前没有把外部 `python` 非零退出码提升为 PowerShell 失败，因此 daemon 测试另用上述显式命令确认。
  - 安装版云端 DeepSeek `deepseek-v4-flash`：严格模式真实回复成功；实际参数包含 `temperature=0.2`、`max_tokens=1800`、`reasoning_effort=high`、`max_iterations=40`，无自动降级。
  - 安装版本地 Ollama `llama3.2:1b`：自定义模式真实回复“本地生成控制验证通过”；实际参数包含 `temperature=0.3`、`max_tokens=1000`、`max_iterations=8`。
  - 本地候选验证也证明约束按真实能力处理：`qwen2.5:0.5b` 的 32K 上下文低于 Hermes 64K 要求，未伪造能力；`deepseek-r1:1.5b` 未形成可验收工具链回复，未计为通过。
  - `npm run tauri:build --prefix lilsunspot/desktop`：通过。最终 NSIS 为 `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`，56,766,639 bytes，时间 2026-07-25 19:16:04 +08:00。
  - 最终 NSIS 已静默覆盖安装到 `%LOCALAPPDATA%\Lilsunspot`；`/health=ready`、`/generation/current` 可用，用户原 `deepseek/deepseek-chat` 配置已恢复。
  - Windows 安装版视觉检查：最大化窗口后，生成控制标题、模式说明、当前模式摘要和表达风格说明均为亮白/青色高对比度文字，没有以灰色承载新增说明。
  - 2026-07-25 收尾：删除本轮下载的 Ollama `llama3.2:1b` 与 `qwen2.5:0.5b`，保留用户原有的 `deepseek-r1:1.5b`；安装版主模型改为 `deepseek/deepseek-v4-flash`，`/app/bootstrap=chat_ready`，真实 Hermes Agent 回复“DeepSeek接口恢复成功”。
  - 2026-07-25 DeepSeek 安装包修复：确认旧 NSIS 内置 `provider_registry.yaml` 仍以已失效的 `deepseek-chat` 为默认，且当前用户配置在 21:07 被重置为 `needs_model`。产品资源默认改为 `deepseek-v4-flash` 并增加回归断言；`test_resources_and_secret_guard.py` + `test_auth_and_provider.py` 16 passed，完整 daemon 150 passed，`scripts/check.ps1` 通过（daemon 150 passed、secret guard、桌面 build）。重新运行 `npm run tauri:build --prefix lilsunspot/desktop`，最终 NSIS 为 56,768,504 bytes、时间 2026-07-25 21:17:10 +08:00，并已覆盖安装。
  - 新安装版现场验证：`/providers` 返回 DeepSeek `default_model=deepseek-v4-flash`、官方 Base URL；从本轮本机备份只在内存中恢复 DeepSeek Key，`/providers/test=true`、`/providers/save=true`、`/app/bootstrap=chat_ready`，真实 `/chat/send` 经 `hermes_agent_loop` 返回“新版安装包DeepSeek连接正常”。未输出或记录 Key、runtime token。
- Remaining Risk: 真实 Provider/模型矩阵不可能由单次任务穷尽。
- Date: 2026-07-25.

## LIL-HERMES-TERMINAL-01 - 2026-07-25

- Scenario: Windows 安装版默认使用 Hermes 官方终端能力。
- User Intent: 让小黑子能够通过终端检查和处理本机问题，同时保留 Hermes 官方安全审批。
- Preconditions: 当前安装版保留 DeepSeek V4 Flash 配置；不输出 API Key 或 runtime token。
- Exact Steps or Command: capability/approval 定向 pytest；`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`；`npm run tauri:build --prefix lilsunspot/desktop`；静默覆盖安装；调用安装版 `/capabilities` 与真实 `/chat/send`。
- Expected Observable Result: 默认 Agent toolsets 包含 `terminal`；能力来源和实际工具均来自 Hermes；只读命令可执行；危险命令审批链未被绕过。
- Actual Observable Result: 安装版 `/capabilities` 返回 `toolset.terminal enabled=true / available=true / executable=true / source=hermes_toolset / tools=terminal,process`。DeepSeek `deepseek-v4-flash` 经 `hermes_agent_loop` 执行固定文本只读命令成功，退出码 0，生成详情记录工具迭代 5/60；测试后 pending approval 为 0。
- Evidence:
  - `python -m pytest lilsunspot/daemon/tests/test_capabilities.py lilsunspot/daemon/tests/test_safety_approvals.py -q`：17 passed。
  - `scripts/check.ps1`：daemon 151 passed、secret guard 和桌面 TypeScript/Vite build 通过。
  - `npm run tauri:build --prefix lilsunspot/desktop`：通过；NSIS 为 `lilsunspot/desktop/src-tauri/target/release/bundle/nsis/Lilsunspot_0.1.0_x64-setup.exe`，56,742,464 bytes，时间 2026-07-25 21:44:37 +08:00。
  - 安装程序退出码 0；安装目录 `Lilsunspot.exe` 与 `binaries/lilsunspotd/lilsunspotd.exe` 均更新为本轮产物。
- Security Boundary: 未修改 Hermes 核心 `tools.terminal_tool` 或 `tools.approval`；未启用 yolo/off；危险命令仍通过现有 gateway approval bridge 进入小黑子安全审批。
- Remaining Risk: 本轮真实安装版只执行无副作用只读命令；危险命令批准/拒绝由自动化测试覆盖，未在真实用户数据目录执行破坏性命令。
- Date: 2026-07-25.
