# Hermes 官方最新版同步与 lilsunspot 全能力接入 ExecPlan

日期：2026-07-25
任务编号：`LIL-HERMES-UPSTREAM-FULL-SYNC-01`
状态：执行中；Milestone 1 已完成固定目标抓取和本地 ancestry 校验；Milestone 2 能力盘点进行中
计划类型：跨上游、Agent runtime、产品适配层、桌面端、微信、数据迁移与 Windows 安装链路

## Purpose / Big Picture

把当前仓库同步到执行时可确认的 Hermes 官方 `NousResearch/hermes-agent` 最新 `main` 提交，并让 lilsunspot 在保留自身 Windows 桌面、中文产品体验、微信会话、安全审批、数据目录和安装链路的同时，完整继承该官方提交提供的全部能力。

完成后，不能只证明“上游代码已经 merge”。必须证明：官方能力被打包进 `lilsunspotd`，能从 lilsunspot 的 Agent/runtime 或相应产品入口到达，配置与状态可管理，错误可理解，安全边界仍生效，并在新安装与旧版本升级两条 Windows 路径上实际运行。

## Success Definition

“拥有上游全部能力”在本计划中按以下硬标准验收：

1. 以同步时固定的官方 commit 为唯一版本基线，不使用“最新”这种浮动描述代替 commit SHA。
2. 对该 commit 的 runtime、provider/model、tools/toolsets、skills/plugins、memory、cron、session、gateway/platform、文件与多媒体、浏览器/终端、委派/后台任务、CLI/Web/TUI 管理能力逐项盘点。
3. 每项能力必须进入能力账本，并且状态只能是：
   - `可用且已验证`：lilsunspot 安装版可直接调用；
   - `可配置后使用且已验证`：需要用户凭据、外部服务或显式启用，配置入口和真实验证均存在；
   - `平台受限且已有交付方案`：官方能力依赖非 Windows 环境时，已经提供随安装包交付的 Windows 等价路径或明确的受控运行方案；
   - `上游本身不可用`：仅当固定 commit 的官方实现、依赖或服务本身不可运行时使用，并附官方/运行证据。
4. 不允许使用“代码存在”“测试 import 成功”“Hermes CLI 里能看到”来替代 lilsunspot 用户入口验证，也不允许把未接入能力静默标为“不适合普通用户”后跳过。
5. 高级能力可以进入高级设置、自然语言 Agent 路由或受控管理入口，不要求把 Hermes Dashboard/TUI 原样塞进首页；但能力不能因为 UI 简化而消失。
6. lilsunspot 的审批、凭据保护、文件安全根和既有外部发送策略是执行边界，不是删除能力。安全策略必须包裹官方能力，不能另写一套与官方协议分叉的实现。
7. 能力账本不存在 `未盘点`、`仅代码存在`、`待接入` 或无证据行后，才允许宣布“拥有上游全部能力”。

## Non-goals

- 不重写 Hermes core。
- 不把 lilsunspot 产品代码反向放进 Hermes 上游目录。
- 不为了表面兼容保留两套并行 Agent runtime、provider resolver、gateway、tool registry 或 session truth。
- 不自动发布、推送、部署或覆盖用户正式数据。
- 不把 API Key、runtime token、微信凭据、私聊正文、附件原文或完整模型回复写入计划、日志、报告和测试夹具。
- 不把官方 Dashboard/TUI 的页面一比一复制为普通用户首页。

## Context and Orientation

仓库已经是 Hermes fork，并包含 lilsunspot Windows 产品层。当前主要链路是：

```text
setup.exe
  -> Lilsunspot.exe (Tauri + React)
  -> lilsunspotd (localhost + token)
  -> lilsunspot product adapters
  -> Hermes AIAgent / providers / tools / sessions / gateway
```

主要边界：

- Hermes 官方源：`upstream = https://github.com/NousResearch/hermes-agent.git`。
- lilsunspot 产品源：`lilsunspot/daemon/`、`lilsunspot/desktop/`、`lilsunspot/resources/`。
- 当前官方基线记录：`lilsunspot/UPSTREAM_COMMIT.txt`。
- 已有只读审计：`scripts/hermes_upstream_check.ps1`、`lilsunspot/daemon/upstream_audit.py`。
- 已有受控同步入口：`scripts/hermes_upstream_sync.ps1`。
- 已有远程同步 workflow：`.github/workflows/lilsunspot-upstream-sync.yml`。
- 当前架构真相：`docs/ARCHITECTURE.md`。
- 当前产品真相：`docs/PRODUCT.md`。
- 验证记录：`docs/VALIDATION.md`。

建立计划时观察到：

- 当前分支为 `develop`，与 `origin/develop` 对齐，但工作树包含大量未提交的在途功能变更。
- `UPSTREAM_COMMIT.txt` 当前记录 `2b768535c9ba2a8d3b2c23fae1ee3a2f827f7f49`。
- 本地缓存的 `upstream/main` 是 `f1345290edb87a5da7b28288dc39c46b0be79313`，提交时间为 2026-06-29；它不能代表 2026-07-25 官方最新状态。
- 2026-06-15 的旧报告已发现至少 `context_engine` 等能力映射缺口；该报告只能作为历史线索，不能作为本次最新能力账本。
- 已有自动同步设施偏重 merge 和基础检查，尚不能证明“上游全部能力已在 lilsunspot 安装版可达”。

## Interfaces and Dependencies

实施时优先保留以下依赖方向：

```text
lilsunspot desktop -> lilsunspot product API -> thin adapters -> Hermes public/runtime interfaces
Hermes core -X-> lilsunspot
```

需要重点审计的接口包括但不限于：

- Agent 构造、conversation loop、streaming、context engine、compression、background review。
- Provider、model metadata、auxiliary model、vision、audio/transcription、web search、Codex transport。
- Tool registry、toolsets、approval hooks、terminal/process、browser、files、MCP、delegation、媒体生成与交付。
- SessionDB、memory、user modeling、cron/jobs、checkpoints、usage/cost。
- Gateway base adapter、Weixin 及官方新增平台、媒体发送、route、delivery、status。
- Hermes config/env/credential migration、CLI setup/model switch、skills/plugins/bundles。
- PyInstaller hidden imports/data、Python/Rust/Node 依赖、Tauri sidecar、NSIS installer。

当前产品层还直接引用 `_supports_vision_override`、`_explicit_aux_vision_override`、`_toolset_needs_configuration_prompt` 等上游私有符号；实施时必须优先迁移到新版公共接口或建立窄而可测的单点 adapter，不能把这些易断引用散落到产品层。

产品适配应继续保持 thin adapter：lilsunspot 负责中文 UX、产品 route、桌面 API、安全审批和 Windows 生命周期；Hermes 官方接口负责 Agent 与能力语义。

## Progress

- [x] 2026-07-25：确认用户目标为“同步官方最新版，并让 lilsunspot 拥有上游全部能力”。
- [x] 2026-07-25：读取项目治理、现有旧计划、能力清单、同步脚本、同步报告、Git remote 与当前工作树状态。
- [x] 2026-07-25：建立本 ExecPlan。
- [x] 2026-07-26 Milestone 0：从 `origin/develop@a8880fad7094726b2c3e3ec34218e588c7d8bf19` 建立 `codex/hermes-upstream-full-sync-20260726` 隔离 worktree；daemon 154 项与 secret guard 通过，桌面 build 因隔离 worktree 无未跟踪 `node_modules` 被跳过。
- [x] Milestone 1：已通过 GitHub 官方 API 固定并抓取 `d9f1043c3337818b1f29224a7deb5bbb17402370` 到 `upstream/sync-d9f1043`；本地验证旧基线是 merge base、ancestor exit=0、left/right=`0 / 8485`，提交元数据与固定记录一致。
- [ ] Milestone 2：固定目标已展开为 519 行稳定 ID parity ledger（57 toolsets、74 tools、93 plugins、180 skills、4 optional MCPs、30 gateway platforms、4 provider transports、77 config surfaces）。57 toolsets、74 tools、4 provider transports 已设计映射；当前 135 design_mapped / 384 unspecified、0 validated / 519 needs_validation。配置审计发现目标 `_config_version=33` 与现有产品读写/凭据结构存在 P0 迁移缺口，77 个 config surfaces 在 v33 migration、备份、回滚和降级拒绝实现前保持 unspecified。严格门禁同时要求映射与验证完成。
- [ ] Milestone 3：同步 Hermes 上游历史并解决冲突。
- [ ] Milestone 4：迁移 lilsunspot thin adapters、配置与持久化。
- [ ] Milestone 5：让全部能力进入 Windows sidecar 与 lilsunspot 可达入口。
- [ ] Milestone 6：完成安全、中文错误、数据升级与回滚闭环。
- [ ] Milestone 7：完成自动、真实运行、安装版与升级矩阵验收。
- [ ] Milestone 8：更新基线、治理文档并收口远程 PR 验收。

## Plan of Work

### Milestone 0：建立干净、可恢复的同步起点

目的：不覆盖当前工作树中的用户/在途功能变更，也不让上游大合并与现有开发混在一起。

步骤：

1. 记录 `git status --short --branch`、当前 HEAD、remote URL 和所有 worktree。
2. 将当前未提交变更按来源确认并在原工作区保留；不得擅自 reset、checkout 或 stash 用户变更。
3. 从经过确认的 `origin/develop` 或包含当前已完成产品工作的明确 commit 创建独立 worktree 和 `codex/hermes-upstream-full-sync-YYYYMMDD` 分支。
4. 在同步 worktree 中复跑基线检查，确认失败项是同步前既有还是同步后新增。
5. 记录旧安装版数据目录的脱敏备份与恢复方法；不把备份提交到 Git。

退出条件：同步 worktree 干净、基线 commit 明确、当前在途工作未受影响、基线检查结果已记录。

### Milestone 1：固定真正的官方最新版

目的：把“最新”变成可审计的 SHA、时间和差异，而不是依赖陈旧的本地 remote ref。

步骤：

1. 校验 `upstream` URL 指向 `NousResearch/hermes-agent`，再执行 `git fetch upstream main --tags --prune`。
2. 记录 `upstream/main` 的完整 SHA、作者时间、提交时间、最近 release/tag，以及与 `UPSTREAM_COMMIT.txt` 的 merge-base。
3. 运行并增强 `scripts/hermes_upstream_check.ps1 -Fetch`，生成本次唯一同步报告。
4. 分类依赖、schema、配置默认值、迁移代码、runtime、gateway、tools、providers、UI/TUI/Web、打包和测试变化。
5. 在合并开始后若官方 `main` 再前进，不在中途追逐浮动 HEAD；本轮仍以已固定 SHA 为准，后续变化进入下一轮同步。

退出条件：计划与报告均记录同一官方 SHA，且该 SHA 可由 remote ref 验证。

### Milestone 2：建立“全部能力”账本

目的：先盘清官方目标 commit 实际提供什么，再判断 lilsunspot 缺什么，禁止凭旧清单猜测。

产物建议：

- `lilsunspot/notes/hermes-capability-parity/<target-sha>.md`
- `lilsunspot/resources/hermes_capability_manifest.yaml` 或等价机器可读清单
- 对应 manifest/schema 回归测试

能力账本至少覆盖：

1. Agent loop：对话、流式输出、tool loop、context/compression、后台 review、checkpoints、session resume。
2. Models：全部 provider/transport、model metadata、vision、audio、transcription、web search、auxiliary routing、credential source。
3. Tools：官方全部 registry/toolset/configurable toolset、terminal/process、文件、浏览器、搜索、MCP、媒体、todo/kanban、delegate 等。
4. Persistent capabilities：session、memory、user modeling、cron/jobs、usage/cost、history/search。
5. Gateways：官方全部 platform adapter、状态、route、入站、回复、附件/媒体交付、重试；微信必须对齐官方 adapter 接口。
6. Extension surfaces：skills、plugins、bundles、toolsets、配置/安装/更新能力。
7. Operator surfaces：CLI、Web Dashboard、TUI 中存在但 lilsunspot 尚未提供等价入口的管理能力。
8. Packaging/runtime：官方运行依赖、资源文件、动态导入和平台命令。

为避免清单随上游漂移，测试应从官方 registry、default config、CLI routes、gateway adapters 和 plugin/skill loader 自动枚举，再与 lilsunspot manifest 比较。上游新增项没有映射时测试必须失败，而不是默认忽略。

退出条件：固定 commit 的能力项 100% 有 owner、lilsunspot 入口、配置来源、安全策略、打包状态和验证方法。

2026-07-26 执行顺序修正：配置行的真实 consumer 依赖合并后的 v33 schema，不能用预期 owner 批量冒充已实现映射。先保存当前审计检查点并合入固定 SHA；随后在产品层实现显式、幂等、带备份/原子替换/回滚/降级拒绝的 v33 迁移，再接受 config mappings。其余未映射行与全部 readiness 继续 fail closed。

### Milestone 3：同步上游并保留历史

目的：把官方目标 SHA 的真实代码完整带入 fork，避免手工复制导致未来无法继续同步。

步骤：

1. 优先使用保留 ancestry 的 merge，将固定的 `upstream/main` SHA 合入同步分支。
2. 冲突按四类处理：官方 core、lilsunspot product、共享 packaging/config、测试/文档。
3. 官方 core 默认采用目标 commit 语义；若 lilsunspot 旧补丁已经被官方实现取代，删除产品层重复补丁并迁移 caller。
4. `lilsunspot/` 下的产品能力不得被上游覆盖；但所有 adapter 必须更新到官方接口。
5. 共享文件中的 lilsunspot 打包入口、Windows 依赖和 workflow 只做最小合并，不制造长期大补丁。
6. 每个无法避免的 core 偏差必须建立 ADR，写明原因、最小 diff、上游 issue/PR 可能性和移除条件。

退出条件：目标 SHA 是当前分支祖先；不存在未解决冲突；官方测试与 import/CLI smoke 能启动。

### Milestone 4：迁移 thin adapters、配置与数据契约

目的：让 lilsunspot 使用新 Hermes 的真实接口，而不是通过兼容分支继续调用旧语义。

重点：

- `agent_runner` 只构造新版官方 Agent/runtime。
- capability graph 和 provider/model 状态从官方 registry/resolver/metadata 派生。
- toolsets、skills、plugins、MCP、cron、memory、session、gateway 都有单一官方 source of truth。
- 微信 route/coalescer/session 继续由产品层维护用户体验，但发送、媒体与平台协议复用官方 adapter。
- 旧 config/env/session/memory 数据通过显式、可重试、带版本的迁移进入新版格式。
- 旧字段只在迁移器中读取，迁移完成后不保留双写或永久 fallback。

退出条件：没有旧/新 runtime 双轨；配置迁移可重复执行；失败不会破坏原数据；主要调用链均有契约测试。

### Milestone 5：完整打包并提供可达入口

目的：解决“源码有能力、安装版没有模块/资源/入口”的常见假完成。

步骤：

1. 更新 sidecar 构建的 hidden imports、datas、plugins、skills、browser/terminal 资源与动态 loader。
2. 对机器可读能力账本中的每一项执行安装包内容审计，确认模块和资源存在。
3. lilsunspot Agent 默认能按官方 toolset 配置调用全部能力；需凭据或高权限的能力提供中文配置/审批路径。
4. 普通用户常用能力进入聊天或设置；高级能力进入“高级能力/扩展/诊断”入口，或可由自然语言可靠触发并查看执行状态。
5. 对官方只在 CLI/Web/TUI 提供的操作能力，在 lilsunspot 中提供等价 API/管理入口；可以重新设计中文 UX，但不能只要求用户安装 Python 后运行 Hermes CLI。
6. Windows 上缺少原生命令的官方能力必须在安装包中提供等价实现或受控运行方案，普通用户不能被要求另装 Python、Node、Git 或 Docker。

退出条件：manifest 每项都能映射到安装版中的模块、配置入口和运行入口；不依赖开发仓库才能使用。

### Milestone 6：安全、错误、升级与恢复

目的：上游扩展能力不能绕过 lilsunspot 的真实用户安全边界，也不能让升级损坏用户数据。

步骤：

1. 所有 `/health` 之外本地 API 继续要求 `X-Lilsunspot-Token`，daemon 继续只监听 `127.0.0.1`。
2. 新增/变化的 tools、gateways、plugins、MCP、终端和外部发送逐项做权限、审批、文件范围、网络与 secret 审计。
3. 对配置、session、memory、cron、skills/plugins 状态做旧版升级、失败回滚、重复启动与降级拒绝测试。
4. 新版不能读取的数据必须保留原副本并用普通中文说明，不能静默清空或重建。
5. 所有用户可见错误使用中文；诊断只保存脱敏分类和状态。
6. 记录同步前安装包/数据恢复路径；禁止以回退二进制配合已不可逆升级的数据 schema。

退出条件：安全回归通过，数据迁移可恢复，旧数据升级和新数据重启均通过。

### Milestone 7：分层验收

目的：用真实证据同时证明官方语义、产品集成和安装版交付。

验证层次：

1. **上游层**：运行目标 commit 要求的 lint、unit、integration、Windows footgun、lockfile/schema 检查；记录因外部服务不能执行的官方测试及替代证据。
2. **产品层**：运行全部 lilsunspot daemon/product tests、能力 manifest parity、secret guard、desktop build 和 `scripts/check.ps1`。
3. **并行对照层**：相同临时数据、provider 和输入下，对 Hermes 官方入口与 lilsunspot 入口执行代表性能力用例，比较实际 tool/provider/session/gateway 行为，而不是只比较文本回复。
4. **全能力矩阵层**：机器可读 manifest 的每一行至少有自动测试或明确的真实 smoke evidence；需外部账号的项目在隔离测试账号上执行。
5. **安装版层**：重新执行 `npm run tauri:build --prefix lilsunspot/desktop`，确认 NSIS `setup.exe`；在干净临时数据目录和旧版数据副本上分别安装/升级。
6. **真实主路径层**：至少覆盖首启、模型配置、真实 Agent chat、工具调用、文件/图片/音频、终端/浏览器、memory、cron、skills/plugins/MCP、会话恢复、微信入站/回复/媒体、安全审批、关闭重开。
7. **负面层**：无凭据、模型不支持、工具拒绝、审批拒绝、网络断开、任务重启、插件错误、数据迁移中断均有中文反馈且不泄密。

最低必跑命令以同步后官方文档和仓库实际命令为准，并至少包含：

```powershell
python -m pytest lilsunspot/daemon/tests
python -m pytest lilsunspot/tests --timeout-method=thread
python scripts/guard_no_secrets.py
npm run build --prefix lilsunspot/desktop
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
npm run tauri:build --prefix lilsunspot/desktop
```

上述命令只是最低门槛，不能替代目标 commit 的官方检查和全能力 manifest 验收。

退出条件：全部验收层通过；NSIS 产物存在；安装版新装、升级、真实 Agent、微信与能力矩阵均有证据。

### Milestone 8：固定新基线并收口

步骤：

1. 只有 Milestone 7 通过后才更新 `lilsunspot/UPSTREAM_COMMIT.txt` 为目标 SHA。
2. 更新 `docs/ARCHITECTURE.md`、`docs/PRODUCT.md`、`docs/VALIDATION.md`、`docs/PROGRESS.md`、`TASKS.md` 和本计划实际状态。
3. 更新能力账本，确保无 `未盘点`、`待接入` 和无证据项。
4. 更新/加固 `.github/workflows/lilsunspot-upstream-sync.yml`，让以后每次官方新增 registry/config/gateway/toolset 项时 parity 检查自动失败。
5. 创建 draft PR 前复核 diff、依赖、secret guard、安装包证据和 remaining risks；推送/PR 必须由用户明确授权。

退出条件：新基线记录等于实际验证 SHA；文档与代码一致；远程检查能阻止后续能力漂移。

## Concrete Steps

实际执行时按以下顺序推进，并在每个里程碑后更新本计划：

```powershell
git status --short --branch
git remote -v
git worktree list
git fetch upstream main --tags --prune
git rev-parse upstream/main
git show -s --format=fuller upstream/main
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/hermes_upstream_check.ps1 -Fetch
```

创建隔离 worktree/分支、执行 merge、安装依赖或覆盖安装前，必须先确认准确路径和目标。不得在当前脏工作树上直接 merge。

每个 milestone 的预期观察：

- M0：独立 worktree 为 clean，原工作树状态不变。
- M1：报告中的 target SHA 与 `git rev-parse upstream/main` 一致。
- M2：机器清单与官方 registry 自动枚举集合相等，无漏项。
- M3：`git merge-base --is-ancestor <target-sha> HEAD` 成功。
- M4：所有 lilsunspot adapter 指向新版官方接口，没有永久兼容双轨。
- M5：安装版能力清单与源码清单相等，动态模块和资源均可加载。
- M6：旧数据升级成功或安全回滚，安全边界不回退。
- M7：全能力矩阵、真实主路径和 NSIS 验收通过。
- M8：`UPSTREAM_COMMIT.txt` 与已验证 SHA 一致。

## Validation and Acceptance

最终验收必须同时满足：

- 官方目标 SHA 已完整进入 Git ancestry。
- Hermes 官方测试与 lilsunspot 全量检查通过，或有明确、与本实现无关且被复核的外部阻塞。
- 能力账本覆盖率 100%，零静默缺失，零仅源码存在项。
- 安装版无需 Python、Node、Git、Docker即可启动和使用已配置能力。
- 新安装和旧数据升级均通过。
- 桌面和微信共享同一个 Hermes Agent 能力、会话和安全边界。
- 真实 provider chat 与代表性 tool loop 通过。
- 需凭据/服务的能力提供配置入口、状态与明确中文错误。
- API/secret/文件/审批边界保持不变或更严格。
- `setup.exe` 已重新生成且路径、大小、时间和安装 smoke 已记录。
- `UPSTREAM_COMMIT.txt` 仅在以上条件满足后更新。

以下情况一律不能宣称完成：

- 只完成 `git merge`。
- 只通过 `/health`。
- 只跑 lilsunspot 的少量 focused tests。
- 能力存在于 Hermes CLI/Dashboard，但安装版用户无法到达。
- capability graph 宣称可用，但真实调用失败或未打包。
- 用 fallback、模板响应或旧 adapter 掩盖新版接口未接入。

## Idempotence and Recovery

- 上游检查可重复运行；每次报告必须记录 SHA，不覆盖历史证据。
- 同步只能在独立 clean worktree 进行；失败时删除该 worktree/分支即可恢复，不触碰原脏工作区。
- config/data migration 使用版本号、备份、临时文件和原子替换；重复启动不得重复迁移或丢数据。
- sidecar 和 NSIS 只在新构建成功后替换旧产物。
- 若 merge 冲突无法安全解决，保留同步分支和报告，回到已验证基线；不更新 `UPSTREAM_COMMIT.txt`。
- 若新二进制需不可逆数据迁移，必须先设计向前修复方案和备份恢复路径，再允许安装版升级测试。
- 官方 main 在实施期间前进时不重写当前 target；新 SHA 进入下一次计划/同步。

## Risks and Gates

1. **当前工作树脏**：最高优先级风险。未隔离前禁止同步。
2. **基线跨度大**：旧报告已有数百 commits、上千文件变化；必须分能力域审查，不能一次 merge 后凭测试绿灯收口。
3. **动态能力漏打包**：plugins/skills/providers/tools 常通过动态 import 或资源发现，PyInstaller 容易漏项。
4. **产品层重复实现**：旧 adapter 可能遮蔽官方新增能力，必须按 source of truth 逐项去重。
5. **Windows 平台差异**：终端、浏览器、系统命令和后台服务需要真实 Windows 安装版证据。
6. **安全面扩大**：全部 tools/gateways/plugins 接入会扩大网络、文件、命令和外部发送面；审批与权限审计是强制门槛。
7. **持久化漂移**：config/session/memory/cron schema 变化可能影响现有用户数据，禁止无备份覆盖。
8. **“全部能力”口径漂移**：能力清单必须由目标 SHA 自动枚举，不能靠人工旧文档维持。
9. **外部服务依赖**：需要账号、硬件或第三方服务的能力必须区分“未配置”与“未接入”，不能用缺凭据掩盖集成缺口。

需要用户再次授权的事项：推送、创建 PR、发布、部署、覆盖正式用户数据、不可逆迁移、新增有显著成本/风险的生产依赖。普通代码同步、计划内测试和隔离临时数据验证不需要额外确认。

## Surprises & Discoveries

- 2026-07-25：仓库已有 upstream check/sync/workflow，不需要从零设计 Git 同步；真正缺口是固定最新版后的完整能力 parity 与安装版证据。
- 2026-07-25：旧 `hermes-merge-plan.md` 明确不做官方最新 upstream 对比，因此不能直接作为本任务执行计划。
- 2026-07-25：当前本地 `upstream/main` 晚于旧同步报告，但仍比当前日期早近一个月；实施第一步必须联网 fetch 后重新固定 SHA。
- 2026-07-25：工作树包含其他未提交功能，真实同步必须使用隔离 worktree，不能直接在当前目录 merge。
- 2026-07-26：当前主工作树实际已 clean 并与 `origin/develop` 对齐，隔离 worktree 可以直接以 `a8880fad7094726b2c3e3ec34218e588c7d8bf19` 为 fork 同步起点；计划建立时的“脏工作树”风险已由 2026-07-25 收口消除。
- 2026-07-26：`git fetch upstream main --tags --prune`、强制 HTTP/1.1 的 main-only fetch、最小 `git ls-remote` 和 filtered fetch 四次分别因 `Recv failure: Connection was reset`、无法连接 GitHub 443 与再次连接重置失败。PowerShell HTTPS HEAD 一度返回 200，但 GitHub API 又返回 rate limit 403，不足以取代 Git 对象校验。这是 M1 的外部网络阻断；本地缓存 `upstream/main@f1345290edb87a5da7b28288dc39c46b0be79313` 仅保留为 fetch 前证据。
- 2026-07-26：既有 `scripts/hermes_upstream_sync.ps1` 会直接 merge 浮动 `upstream/main`、提前更新 `UPSTREAM_COMMIT.txt` 并 amend，与本计划 M2/M7/M8 门槛冲突，本轮不直接执行该脚本。
- 2026-07-26：认证 GitHub API 可用，已固定 target `d9f1043c3337818b1f29224a7deb5bbb17402370`；官方 compare 返回旧基线为 merge base、ahead 8,485、behind 0。按 SHA 下载的官方 tarball 可用于只读能力盘点，但不代替 Git ancestry 或 merge 证据。
- 2026-07-26：旧基线到目标快照是 6,202 个文件的巨大变化；初步 AST 审计发现目标新增 `coding/context_engine/project` toolsets，而当前产品仍有目标已移除/迁移的 `messaging/moa` 可配置项。不能仅做新增项补齐，还必须处理官方所有权迁移。
- 2026-07-26：GitHub 重试成功，固定 SHA 已持久化为 `upstream/sync-d9f1043`。本地 Git 对象验证 merge base=`2b768535...`、left/right=`0 / 8485`；官方 Git diff 为 6,162 files changed、1,347,582 insertions、118,739 deletions。官方 tree 与快照路径集合一致，CRLF/LF 归一化后 7,460 个文件内容差异为 0；合并来源仍只允许官方 Git object。

## Decision Log

- 2026-07-25：采用“保留上游 Git ancestry 的 merge + lilsunspot thin adapter”路线，不复制或重写 Hermes core。
- 2026-07-25：将“全部能力”定义为目标 commit 能力账本 100% 覆盖和安装版可达，不以 UI 页面数量或源码存在判断。
- 2026-07-25：官方 CLI/Web/TUI 的能力语义必须保留，但允许在 lilsunspot 中用中文桌面、API 或自然语言入口重新呈现。
- 2026-07-25：`UPSTREAM_COMMIT.txt` 是完成标记，不是开始同步时提前修改的目标指针。
- 2026-07-25：安全审批和权限限制包裹能力执行，但不得被当作删除上游能力的理由。
- 2026-07-25：本轮同步固定一个 SHA；实施过程中不无限追逐上游移动中的 `main`。

## Artifacts and Notes

计划实施预计会维护或新增：

- `lilsunspot/UPSTREAM_COMMIT.txt`
- `lilsunspot/notes/upstream-sync-reports/`
- `lilsunspot/notes/hermes-capability-parity/`
- 一份机器可读的 Hermes capability manifest 及 parity tests
- `scripts/hermes_upstream_check.ps1`
- `scripts/hermes_upstream_sync.ps1`
- `.github/workflows/lilsunspot-upstream-sync.yml`
- `docs/ARCHITECTURE.md`
- `docs/PRODUCT.md`
- `docs/VALIDATION.md`
- `docs/PROGRESS.md`
- `TASKS.md`

具体源码文件要在 Milestone 1 和 2 完成后由真实 diff/能力账本决定，计划阶段不预造文件清单。

## Outcomes & Retrospective

同步尚未执行。2026-07-25 的计划编写校验结果：`git diff --check` 通过，secret guard 通过，桌面 TypeScript/Vite build 通过，本机系统 Python 补跑 daemon tests 为 `151 passed`。`scripts/check.ps1` 本身返回成功，但其首选 `ignored/codex-venv` 缺少 `pytest`，所以不能把该脚本的返回码单独当作 daemon 测试证据；已用补跑结果填补本次计划任务的验证缺口。

最终在这里记录：实际同步的官方 SHA、合并方式、能力覆盖数字、安装版路径、真实验收结果、未解决风险和后续同步成本。

## Outcomes & Retrospective - 2026-07-26 execution update

固定官方 Git object `d9f1043c3337818b1f29224a7deb5bbb17402370` 已通过现有同步分支进入 ancestry。v33 契约在产品层实现为 sidecar startup 前迁移：对 config/env/auth/provider cache 生成哈希备份，官方迁移后做 schema 校验，失败恢复原字节，较新版本拒绝降级。机器账本现在是 519/519 `design_mapped`，没有 unspecified 行；安装版 token-protected catalog 实测发现 93 plugins、180 skills、4 optional MCPs、30 gateway adapters。PyInstaller 同时收集动态代码、四类资产和官方 `messaging` extra；真实 Weixin probe 因而能从安装版获取 iLink QR。

验证已超出 health：`scripts/check.ps1` 为 165 daemon tests + secret guard + desktop build；新装、v32 升级、真实 DeepSeek provider save/chat、真实 iLink QR 与 NSIS 安装卸载均通过。没有本机既有微信登录态，且扫码确认是账号持有人的外部操作；因此只记录 QR/中文待确认链路通过，不伪称已完成账号收发。`UPSTREAM_COMMIT.txt` 必须保持为最终动作，随后才提交、推送和 PR 验收。
