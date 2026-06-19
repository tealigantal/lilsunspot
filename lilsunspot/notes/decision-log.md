# Decision Log

| 日期 | 决策 | 原因 | 影响 | 后续动作 |
| --- | --- | --- | --- | --- |
| 2026-06-19 | Mode 定义为 Hermes 之上的会话级输出与执行策略覆盖层，不再作为独立 Agent 控制面。 | 保留 Lilsunspot 的差异化 Mode 功能，同时避免 Prompt、工具、记忆、会话和 Provider 路径与 Hermes 原生能力分叉。 | 正常聊天继续以 Hermes `AIAgent` 为唯一执行真相；Mode 只影响表达、细节、主动推进和运行预算，不得扩大权限、工具集或绕过审批。 | 按 `lilsunspot/notes/mode-hermes-parity-plan.md` 分阶段完成 Prompt 分层、会话级 Mode、Mode 工具、滑杆策略和 parity 测试。 |
| 2026-06-19 | Mode 的动态能力描述不再写入静态 Mode 资源。 | 具体能力状态会随仓库和运行环境变化，静态文案容易压制已接入能力或产生错误承诺。 | 产品基线保持稳定；真实能力由 capability graph/runtime snapshot 提供。 | 清理 `default_mode_prompt.yaml` 中会过期的能力判断，并建立统一 Prompt layers。 |
| 2026-06-19 | 普通聊天不得为了识别 Mode 意图额外直连 provider。 | 隐藏 Mode Router 会增加费用和延迟，并绕开 Hermes transport、fallback、SessionDB 与工具历史。 | 高置信命令本地解析；模糊风格请求由 Hermes 正常回合中的 Mode 工具处理。 | 收敛 `mode_intents.py`，注册 `lilsunspot_get_mode` / `lilsunspot_set_mode`。 |
| 2026-06-06 | lilsunspot 作为 Hermes 的产品层，不大面积修改 Hermes 核心。 | 降低 fork 维护成本，保留上游可合并性。 | 产品能力集中在 lilsunspot 层演进。 | 代码任务继续优先检查是否能在产品层完成。 |
| 2026-06-06 | 新增代码优先放 `lilsunspot/`。 | 明确产品边界。 | 减少对 Hermes core 的侵入。 | 后续任务保持目录约束。 |
| 2026-06-06 | `lilsunspotd` 只监听 `127.0.0.1`。 | 本地桌面 agent 不应暴露局域网服务。 | daemon/API 设计默认 loopback。 | 验证安装包和运行时绑定地址。 |
| 2026-06-06 | 本地 API 使用 runtime token。 | 防止同机网页或进程直接调用受保护 API。 | `/health` 外接口需要 `X-Lilsunspot-Token`。 | 持续测试 token 鉴权和脱敏。 |
| 2026-06-06 | 用户数据目录使用 `%LOCALAPPDATA%/Lilsunspot/data`。 | 符合 Windows 普通用户安装和运行预期。 | 数据、token、logs、Hermes home 放在产品目录。 | 干净 Windows 验证目录创建和权限。 |
| 2026-06-06 | lilsunspot 使用独立 `hermes_home`，避免污染用户原 `~/.hermes`。 | 产品化运行不应改动用户已有 Hermes 配置。 | Provider 保存写入独立 home。 | 验证 provider 保存和关闭重开读取。 |
| 2026-06-06 | P0 先保安装、首启、provider、桌面聊天。 | 主路径可用优先于扩展体验。 | UI 打磨、微信、安全和诊断后置。 | 执行 LIL-P0-01。 |
| 2026-06-06 | P1/P2 再做模式滑杆、Weixin、安全审批。 | 这些能力依赖 P0 主路径稳定。 | 先记录计划，不写成已完成。 | P0 验证后拆任务推进。 |
| 2026-06-06 | 文档整理阶段不删除历史 MD，只建立索引。 | 历史记录仍有参考价值，但不能代表当前状态。 | 新增 doc-index/doc-inventory 作为入口。 | 后续 Codex 先读索引。 |
| 2026-06-06 | 未验证能力不得写成已完成。 | 防止文档误导验收和发布判断。 | 当前状态表采用已实现/部分实现/未实现/未验证/阻断。 | 每次验证后更新状态和 QA。 |