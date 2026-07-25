# ExecPlan Rules

每个跨模块、跨运行层或影响真实用户主路径的任务必须在 `docs/plans/` 建立自包含 ExecPlan，并在实施期间持续维护，而不是结束时重建。

每份 ExecPlan必须包含：Purpose / Big Picture、Progress、Surprises & Discoveries、Decision Log、Outcomes & Retrospective、Context and Orientation、Plan of Work、Concrete Steps、Validation and Acceptance、Idempotence and Recovery、Artifacts and Notes、Interfaces and Dependencies。

计划必须描述可观察结果、仓库实际入口、可独立验证的里程碑、准确命令与预期观察，并明确失败恢复、重试、回滚和未完成范围。实际执行证据同步进入 `docs/VALIDATION.md`；可恢复状态同步进入 `docs/PROGRESS.md`。
