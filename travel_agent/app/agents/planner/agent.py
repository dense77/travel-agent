"""作用：
- 定义最小版本规划器，把用户需求转换成一个可执行的技能步骤列表。

约定：
- 当前规划器固定只生成 1 个步骤，并且只能调用 `mock_travel`。
- `replan` 明确不在最小闭环范围内，保留接口只是为了和架构文档对齐。
"""

from __future__ import annotations

from travel_agent.app.agents.contracts import ExecutionPlan, PlanStep, SharedContext


class PlannerAgent:
    def plan(self, context: SharedContext) -> ExecutionPlan:
        # 最小闭环先采用确定性计划，避免把复杂性提前放到规划阶段。
        return ExecutionPlan(
            goal=context.user_query,
            steps=[
                PlanStep(
                    step_id="step_1",
                    action_type="skill_invoke",
                    tool_name="mock_travel",
                    input_payload={
                        "query": context.user_query,
                        "constraints": context.hard_constraints,
                    },
                    expected_output="A structured travel suggestion.",
                    status="planned",
                )
            ],
            missing_info=[],
            need_rag=False,
            need_replan=False,
        )

    def replan(self, context: SharedContext) -> ExecutionPlan:
        # 当前实现故意失败，提醒调用方不要误以为系统已经支持 RePlan。
        raise NotImplementedError("RePlan is intentionally out of scope for the minimal runnable loop.")
