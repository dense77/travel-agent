"""作用：
- 执行规划结果，把每个计划步骤转换成技能调用，并沉淀为观察结果。

约定：
- 执行器只关心“按计划执行”，不负责决定计划是否合理。
- 当前执行器串行执行所有步骤，且默认每一步都依赖 `tool_name`。
"""

from __future__ import annotations

from travel_agent.app.agents.contracts import ExecutionObservation, ExecutionPlan, SharedContext, SkillResult
from travel_agent.app.skills.registry import SkillRegistry


class ExecutorAgent:
    def __init__(self, skill_registry: SkillRegistry) -> None:
        self._skill_registry = skill_registry

    def execute(self, plan: ExecutionPlan, context: SharedContext) -> list[ExecutionObservation]:
        observations: list[ExecutionObservation] = []

        for step in plan.steps:
            if not step.tool_name:
                # 最小闭环要求每一步都能直接映射到一个技能。
                observations.append(
                    ExecutionObservation(
                        step_id=step.step_id,
                        source="executor",
                        success=False,
                        structured_output={},
                        error_message="tool_name is required for the minimal loop.",
                    )
                )
                continue

            tool = self._skill_registry.get_tool(step.tool_name)
            # `idempotency_key` 约定使用 step_id，方便未来接真实外部服务时防重。
            raw_result = tool.invoke(
                {
                    "session_id": context.session_id,
                    "parameters": step.input_payload,
                    "idempotency_key": step.step_id,
                }
            )
            # 技能层返回字典，执行器在这里重新收敛成内部统一模型。
            skill_result = SkillResult.model_validate(raw_result)

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

        return observations
