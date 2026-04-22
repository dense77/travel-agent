"""规划器实现。"""

# 启用延迟类型注解。
from __future__ import annotations

# 导入计划模型、步骤模型和共享上下文模型。
from travel_agent.app.agents.contracts import ExecutionPlan, PlanStep, SharedContext


class PlannerAgent:
    """最小可运行的规划器。"""

    def __init__(self, default_tool_name: str = "mock_travel") -> None:
        """初始化规划器。"""
        # 保存默认工具名，后续生成计划时会使用它。
        self._default_tool_name = default_tool_name

    def plan(self, context: SharedContext) -> ExecutionPlan:
        """根据上下文生成初始计划。"""
        # 直接构造一个单步计划，
        # 让当前仓库继续保持简单可运行。
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
        """根据已有 observation 生成一份回退计划。"""
        # 收集最近观测里的错误原因。
        failure_reasons = [item.error_message for item in context.latest_observations if item.error_message]
        # 返回一份以 fallback_mode 为标识的重规划结果。
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
        """判断当前问题是否值得先做知识检索。"""
        # 先把 query 拿出来，后面要多次判断。
        query = context.user_query
        # 如果上下文里已经有检索知识，就不需要重复检索。
        if context.retrieved_knowledge:
            return False
        # 用关键词做一个简单启发式判断。
        keywords = ("攻略", "推荐", "玩法", "景点", "美食", "注意事项", "寺", "西湖")
        return any(keyword in query for keyword in keywords)

    def _missing_info(self, context: SharedContext) -> list[str]:
        """判断当前还缺哪些关键约束。"""
        # 初始化缺失字段列表。
        missing: list[str] = []
        # 如果没有 travel_days，就记为缺失。
        if "travel_days" not in context.hard_constraints:
            missing.append("travel_days")
        # 如果没有 budget，也记为缺失。
        if "budget" not in context.hard_constraints:
            missing.append("budget")
        # 返回缺失字段列表。
        return missing
