from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ModeRuntimePolicy:
    style_axis: int
    detail_level: int
    autonomy_level: int
    target_answer_tokens: int
    max_iterations: int
    clarification_policy: str
    proactive_tool_policy: str
    reasoning_effort: str | None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _slider(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 0
    return max(0, min(100, number))


def _target_answer_tokens(detail_level: int) -> int:
    if detail_level <= 20:
        return 300
    if detail_level <= 40:
        return 600
    if detail_level <= 60:
        return 1000
    if detail_level <= 80:
        return 1800
    return 3000


def _max_iterations(autonomy_level: int) -> int:
    if autonomy_level <= 20:
        return 8
    if autonomy_level <= 40:
        return 16
    if autonomy_level <= 60:
        return 30
    if autonomy_level <= 80:
        return 50
    return 75


def _clarification_policy(autonomy_level: int) -> str:
    if autonomy_level <= 20:
        return "非明确任务先询问用户，避免自行扩展范围。"
    if autonomy_level <= 40:
        return "多步骤或含糊任务先给方案，等用户确认后推进高影响步骤。"
    if autonomy_level <= 60:
        return "明确且可逆的步骤可直接完成；真正含糊或阻断时再询问。"
    if autonomy_level <= 80:
        return "主动完成安全、可逆步骤并验证结果；风险动作仍先确认。"
    return "在安全边界内完成完整任务链，只在真正阻断、风险动作或缺少权限时询问。"


def _proactive_tool_policy(autonomy_level: int) -> str:
    if autonomy_level <= 20:
        return "没有明确指令时不主动调用工具。"
    if autonomy_level <= 40:
        return "先说明计划，再执行用户明确同意或低风险的工具步骤。"
    if autonomy_level <= 60:
        return "对明确任务主动使用安全工具，完成后报告验证结果。"
    if autonomy_level <= 80:
        return "主动使用安全工具推进并复核结果，不扩大工具集。"
    return "主动串联安全工具完成端到端任务，保留审批、文件和外部发送边界。"


def _reasoning_effort(detail_level: int, autonomy_level: int) -> str | None:
    if detail_level <= 40 and autonomy_level <= 40:
        return "low"
    if detail_level >= 80 or autonomy_level >= 80:
        return "high"
    return "medium"


def compile_mode_runtime_policy(profile: dict[str, Any] | None) -> ModeRuntimePolicy:
    payload = profile if isinstance(profile, dict) else {}
    style_axis = _slider(payload.get("style_axis", 45))
    detail_level = _slider(payload.get("detail_level", 60))
    autonomy_level = _slider(payload.get("autonomy_level", 60))
    return ModeRuntimePolicy(
        style_axis=style_axis,
        detail_level=detail_level,
        autonomy_level=autonomy_level,
        target_answer_tokens=_target_answer_tokens(detail_level),
        max_iterations=_max_iterations(autonomy_level),
        clarification_policy=_clarification_policy(autonomy_level),
        proactive_tool_policy=_proactive_tool_policy(autonomy_level),
        reasoning_effort=_reasoning_effort(detail_level, autonomy_level),
    )


def runtime_policy_prompt(policy: ModeRuntimePolicy) -> str:
    reasoning = policy.reasoning_effort or "默认"
    return "\n".join(
        [
            "当前 Mode 运行策略：",
            f"- 输出预算：目标约 {policy.target_answer_tokens} tokens；不要为了预算机械截断完整答案。",
            f"- 迭代预算：本轮最多 {policy.max_iterations} 次 Hermes 工具/模型迭代。",
            f"- 确认策略：{policy.clarification_policy}",
            f"- 主动推进：{policy.proactive_tool_policy}",
            f"- 推理强度：{reasoning}。",
            "硬约束：不得绕过审批，不得扩大工具集，不得突破文件安全范围，不得自动发送外部消息，不得修改凭据权限。",
        ]
    )
