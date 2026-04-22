"""执行器实现。"""

# 启用延迟类型注解。
from __future__ import annotations

# 导入执行观测、执行计划、共享上下文和技能请求模型。
from travel_agent.app.agents.contracts import (
    ExecutionObservation,
    ExecutionPlan,
    SharedContext,
    SkillRequest,
)
# 导入技能注册表。
from travel_agent.app.skills.registry import SkillRegistry


class ExecutorAgent:
    """按计划调用技能并收敛 observation。"""

    def __init__(self, skill_registry: SkillRegistry) -> None:
        """保存技能注册表。"""
        self._skill_registry = skill_registry

    def execute(self, plan: ExecutionPlan, context: SharedContext) -> list[ExecutionObservation]:
        """逐步执行计划。"""
        # 先初始化一个空 observation 列表。
        observations: list[ExecutionObservation] = []

        # 逐个遍历计划步骤。
        for step in plan.steps:
            # 如果某一步没有 tool_name，
            # 说明计划不完整，这里直接记录失败 observation。
            if not step.tool_name:
                observations.append(
                    ExecutionObservation(
                        step_id=step.step_id,
                        source="executor",
                        success=False,
                        structured_output={},
                        error_message="tool_name is required.",
                    )
                )
                continue

            try:
                # 通过技能注册表按名称执行技能。
                skill_result = self._skill_registry.invoke(
                    step.tool_name,
                    SkillRequest(
                        session_id=context.session_id,
                        parameters=step.input_payload,
                        idempotency_key=f"{context.session_id}:{step.step_id}",
                    ),
                )
                # 把技能结果统一收敛成 observation。
                observations.append(
                    ExecutionObservation(
                        step_id=step.step_id,
                        source=skill_result.skill_name,
                        success=skill_result.success,
                        structured_output=skill_result.data,
                        error_message=skill_result.error_code,
                        evidence_refs=[skill_result.raw_ref] if skill_result.raw_ref else [],
                    )
                )
            except Exception as exc:  # pragma: no cover - 兜底保护
                # 如果技能调用抛异常，
                # 这里同样要收敛成标准 observation，
                # 避免整个执行链路直接崩掉。
                observations.append(
                    ExecutionObservation(
                        step_id=step.step_id,
                        source=step.tool_name,
                        success=False,
                        structured_output={},
                        error_message=str(exc),
                    )
                )

        # 返回全部 observation。
        return observations
