# Research Log

## 2026-07-25 - Generation parameter capability sources

- Question: 如何在不盲发参数的前提下控制不同 Provider/模型？
- Checked Date: 2026-07-25.
- Applicable Version: 当前 `develop` 与当日公开 API 文档。
- Official Sources: DeepSeek Chat Completion API、Ollama OpenAI compatibility、OpenRouter Models/Parameters API。
- Open-source Implementations Compared: 仓库内 Hermes `ProviderProfile`、`models.dev` snapshot、Chat Completions/Responses transports。
- Maintenance and Release Status: Hermes 与公开 Provider 文档均在活跃变化，运行时拒参记录必须按 provider/model 隔离并允许未来刷新。
- License: 仓库 Hermes 为 MIT；外部文档仅作为接口依据。
- Relevant Architecture or Pattern: 能力元数据 + Provider 锁定规则 + 已拒参数缓存 + 安全省略。
- Limitations: `models.dev` 只直接给出部分能力；OpenRouter 可给每模型 `supported_parameters`；任意兼容端点仍可能与声明不一致。
- Applicability to This Repository: 新 resolver 只位于 `lilsunspot/`，通过 Hermes 现有 `request_overrides` 与构造参数接入。
- Decision or Follow-up: 未知参数默认省略；明确拒参后只移除被拒字段并安全重试一次；Kimi 的固定/省略 temperature 必须优先于用户模式。
