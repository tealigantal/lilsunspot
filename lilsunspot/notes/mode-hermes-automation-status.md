# Mode/Hermes 自动化实施状态

| 阶段 | 状态 | 分支/PR | 测试 | 未验证项 |
| --- | --- | --- | --- | --- |
| 1 Prompt | in_progress | codex/mode-hermes-stage-1-prompt | focused 18 passed；daemon 125 passed；product 44 passed；secret guard passed；desktop build passed；check.ps1 passed；git diff --check passed | PR 未创建；真实 Provider smoke 未运行；安装包/NSIS 不在本阶段范围 |
| 2 Scope | pending | | | |
| 3 Tools | pending | | | |
| 4 Policy | pending | | | |
| 5 Host | pending | | | |
| 6 Parity | pending | | | |

## 2026-06-19 Stage 1 记录

- 任务：按 `mode-hermes-parity-plan.md` 阶段 A 拆分产品 Prompt layers，并让个人对话通过 Hermes `AIAgent` 加载 SOUL 身份。
- 范围：只处理 Prompt 分层、Mode overlay、Agent runner 组合和回归测试；不处理会话级 Mode、Mode 工具、三滑杆运行策略、宿主回调或 parity 收口。
- 结果：新增产品 Prompt layers；Mode compiler 只输出 Mode overlay；Agent runner 统一组合产品基线、动态能力快照、Mode overlay 和文件交付 overlay；个人对话显式 `load_soul_identity=True`，继续 `skip_memory=False`。
- 验证：`python -m pytest lilsunspot/daemon/tests/test_agent_runner.py lilsunspot/daemon/tests/test_api_skeleton.py lilsunspot/daemon/tests/test_chat_runtime.py lilsunspot/tests/test_chat_api.py --timeout-method=thread --basetemp .tmp-pytest-mode-stage1-focused` 18 passed；`python -m pytest lilsunspot/daemon/tests --timeout-method=thread --basetemp .tmp-pytest-lilsunspot-daemon` 125 passed；`python -m pytest lilsunspot/tests --timeout-method=thread --basetemp .tmp-pytest-lilsunspot` 44 passed；`python scripts/guard_no_secrets.py` passed；`npm run build --prefix lilsunspot/desktop` passed；`git diff --check` passed with LF/CRLF working-copy warnings only；`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1` passed。
- 未验证：未运行真实 Provider smoke；未运行安装包/NSIS 构建，因为本阶段不修改桌面 UI、Tauri、sidecar、installer 或安装版交付链路。
