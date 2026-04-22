"""执行器实现。"""

from __future__ import annotations

from travel_agent.app.agents.contracts import (
    ExecutionObservation,
    ExecutionPlan,
    SharedContext,
    SkillRequest,
)
from travel_agent.app.skills.registry import SkillRegistry


class ExecutorAgent:
    """按计划调用技能并收敛 observation。"""

    def __init__(self, skill_registry: SkillRegistry) -> None:
        self._skill_registry = skill_registry

    def execute(self, plan: ExecutionPlan, context: SharedContext) -> list[ExecutionObservation]:
        observations: list[ExecutionObservation] = []

        for step in plan.steps:
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
                skill_result = self._skill_registry.invoke(
                    step.tool_name,
                    SkillRequest(
                        session_id=context.session_id,
                        parameters=step.input_payload,
                        idempotency_key=f"{context.session_id}:{step.step_id}",
                    ),
                )
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
                observations.append(
                    ExecutionObservation(
                        step_id=step.step_id,
                        source=step.tool_name,
                        success=False,
                        structured_output={},
                        error_message=str(exc),
                    )
                )

        return observations
