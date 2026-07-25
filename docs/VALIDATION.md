# Validation

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
