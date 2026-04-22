"""规划器实现。"""

from __future__ import annotations

from travel_agent.app.agents.contracts import ExecutionPlan, PlanStep, SharedContext


class PlannerAgent:
    """最小可运行的规划器。

    说明：
    - 继续保持确定性输出，保证当前仓库易于调试。
    - 同时为 RAG、重规划和多轮执行预留结构化字段。
    """

    def __init__(self, default_tool_name: str = "mock_travel") -> None:
        self._default_tool_name = default_tool_name

    def plan(self, context: SharedContext) -> ExecutionPlan:
        """生成初始计划。"""
        return ExecutionPlan(
            goal=context.user_query,
            steps=[
                PlanStep(
                    step_id="step_1",
                    action_type="skill_invoke",
                    tool_name=self._default_tool_name,
                    input_payload={
                        "query": context.user_query,
                        "constraints": context.hard_constraints,
                        "memory_summary": context.memory_summary,
                        "knowledge_chunks": [item.model_dump() for item in context.retrieved_knowledge],
                    },
                    expected_output="A structured travel suggestion.",
                )
            ],
            missing_info=self._missing_info(context),
            need_rag=self._needs_rag(context),
            need_replan=False,
            strategy="plan-execute",
            iteration_index=0,
        )

    def replan(self, context: SharedContext) -> ExecutionPlan:
        """根据已有观测重规划。"""
        failure_reasons = [item.error_message for item in context.latest_observations if item.error_message]
        return ExecutionPlan(
            goal=context.user_query,
            steps=[
                PlanStep(
                    step_id="step_retry_1",
                    action_type="skill_invoke",
                    tool_name=self._default_tool_name,
                    input_payload={
                        "query": context.user_query,
                        "constraints": context.hard_constraints,
                        "knowledge_chunks": [item.model_dump() for item in context.retrieved_knowledge],
                        "fallback_mode": True,
                        "retry_reasons": failure_reasons,
                    },
                    expected_output="A fallback but structured travel suggestion.",
                )
            ],
            missing_info=self._missing_info(context),
            need_rag=False,
            need_replan=False,
            strategy="replan-after-observation",
            iteration_index=context.current_plan.iteration_index + 1 if context.current_plan else 1,
        )

    def _needs_rag(self, context: SharedContext) -> bool:
        query = context.user_query
        if context.retrieved_knowledge:
            return False
        keywords = ("攻略", "推荐", "玩法", "景点", "美食", "注意事项", "寺", "西湖")
        return any(keyword in query for keyword in keywords)

    def _missing_info(self, context: SharedContext) -> list[str]:
        missing: list[str] = []
        if "travel_days" not in context.hard_constraints:
            missing.append("travel_days")
        if "budget" not in context.hard_constraints:
            missing.append("budget")
        return missing
