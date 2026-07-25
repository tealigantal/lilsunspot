# LIL-GENERATION-CONTROL-01 ExecPlan

## Purpose / Big Picture

把“严谨、平衡、创意、快速、深度执行”变成真实影响 Provider 请求和 Hermes Agent 预算的生成控制；普通用户看到含义，高级用户看到实际参数、来源、支持与降级；桌面和微信使用同一解析器。

## Progress

- [x] 2026-07-25：完成只读仓库、调用链、旧 Mode、Provider transport 和治理状态盘点。
- [x] 2026-07-25：补全项目治理文档并接受 ADR 0001。
- [x] 2026-07-25：实现 resolver、三层作用域、能力、拒参记录和 execution trace。
- [x] 2026-07-25：接入桌面/微信消息、AIAgent 与回复 metadata。
- [x] 2026-07-25：完成桌面基础/高级 UI、回复详情和高对比度文字。
- [x] 2026-07-25：完成自动化、云端 DeepSeek 与本地 Ollama 安装版验证；最终 NSIS 已重建并覆盖安装。

## Surprises & Discoveries

- 旧 Mode 已真实传入 `max_tokens`、`reasoning_config` 和 `max_iterations`，但 sampling 参数未传。
- `scope=turn` 当前只返回临时结果，没有绑定真实下一轮请求。
- Hermes `request_overrides` 最后合并，若不先过滤会覆盖 Kimi 的 `OMIT_TEMPERATURE`。
- Hermes fallback 会继承同一 overrides；必须按所有可达目标求安全交集。
- `max_iterations` 是 Agent 循环/API call 预算，不等于精确工具调用数。
- 当前 DeepSeek 服务已拒绝旧 `deepseek-chat` 模型名，安装版云端验证改用服务端当前接受的 `deepseek-v4-flash`，不把模型不存在误判成生成参数失败。
- Ollama `qwen2.5:0.5b` 的真实上下文为 32K，低于 Hermes 64K 要求；最终改用 128K 上下文的 `llama3.2:1b` 完成安装版验证。

## Decision Log

- 2026-07-25：旧务实/均衡/感性只保留表达风格，不再决定运行参数。
- 2026-07-25：能力证据顺序为 Provider 锁定、运行时已拒记录、OpenRouter模型元数据/models.dev、明确产品规则、未知省略。
- 2026-07-25：单轮覆盖直接随消息提交，不实现含糊的“保存给下一轮”临时队列。
- 2026-07-25：“恢复模型默认值”保存 `null`，确保对应请求字段省略；不把平衡预设冒充模型默认。
- 2026-07-25：新增生成控制区域不用灰色说明字，统一为亮白/青色高对比度文字。

## Outcomes & Retrospective

已在 `lilsunspot/` 产品层完成生成控制闭环，没有改写 Hermes core。五种模式、三层作用域、能力过滤、Provider 拒参一次降级、桌面/微信共用解析和回复可观察性均有自动化证据；云端 DeepSeek 与本地 Ollama 均通过真实安装版回复。剩余风险是 Provider/模型矩阵无法一次穷尽，运行时拒参缓存与保守省略作为持续收敛机制。

## Context and Orientation

统一接入点是 `lilsunspot/daemon/agent_runner.py`。桌面和微信纯文本均经过 `turn_coalescer.py`，附件直接进入同一 runner。旧表达风格位于 `modes.py` 和桌面 mode 组件；assistant详情由消息 metadata 驱动。

## Plan of Work

1. 在 `lilsunspot/` 内建立预设、状态、作用域合并、模型能力、实际请求参数和 trace。
2. 扩展消息契约，使单轮覆盖随 desktop/chat API 和 coalescer 进入 runner；微信默认继承会话/全局。
3. runner 使用解析后的 `max_tokens`、`reasoning_config`、`max_iterations` 与过滤后的 `request_overrides`，并返回实际/省略/锁定/降级信息。
4. 所有 assistant 落库路径复用 trace。
5. 桌面将生成控制与表达风格分区，并提供高级参数与回复详情。

## Concrete Steps

- 新增 focused resolver/API/runner tests，先用 fake AIAgent 证明构造参数和三层优先级。
- 覆盖 Kimi temperature 锁定、DeepSeek互斥建议、Ollama/OpenRouter支持、未知参数省略、明确拒参一次降级。
- 覆盖桌面与微信入口得到同一解析结果，工具集/审批/文件安全不变。
- 运行 `python -m pytest ...`、`pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1`、`npm run tauri:build --prefix lilsunspot/desktop`。

## Validation and Acceptance

- 五个 preset 使下一轮真实 AIAgent/request kwargs 有可测试差异。
- global < conversation < turn 按字段来源解析，turn 只作用本次消息。
- 不支持字段不发送；明确拒参只移除被拒字段并重试一次。
- UI 展示当前模型是否完整支持、范围/default/锁定原因和实际 reply trace。
- 云端与本地模型各完成至少一次安装版端到端；不能执行时记录精确 blocker，不虚报完成。

## Idempotence and Recovery

状态文件采用临时文件原子替换；重复保存同一配置结果一致。拒参缓存只收紧特定 provider/model/字段。回滚代码时保留状态文件，旧客户端忽略未知 metadata。NSIS 脚本只有在新 sidecar 成功后替换 bundle。

## Artifacts and Notes

实际命令与结果进入 `docs/VALIDATION.md`；可恢复状态进入 `docs/PROGRESS.md`；任务历史简记进入最相关的现有 Markdown。

## Interfaces and Dependencies

- 仅使用现有 Python/React/Tauri/Hermes 依赖，不新增大型依赖。
- Hermes `AIAgent(max_tokens, max_iterations, reasoning_config, request_overrides)` 是运行接缝。
- models.dev、ProviderProfile 和 OpenRouter模型元数据是能力来源；安全策略、工具集、附件安全根和凭据加载保持原接口。
