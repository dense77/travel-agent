"""LangGraph 状态定义。"""

# 启用延迟类型注解。
from __future__ import annotations

# Any 用来描述灵活数据字段，
# TypedDict 用来定义字典状态结构。
from typing import Any, TypedDict

# 导入工作流状态里会出现的各种模型。
from travel_agent.app.agents.contracts import (
    ExecutionObservation,
    ExecutionPlan,
    GuardrailDecision,
    KnowledgeChunk,
    SharedContext,
)


class TravelGraphState(TypedDict, total=False):
    """整个 LangGraph 在节点间传递的状态结构。"""

    # session_id 是会话主键。
    session_id: str
    # user_query 是用户原始请求。
    user_query: str
    # shared_context 是 Planner/Executor 共享上下文。
    shared_context: SharedContext
    # current_plan 是当前计划。
    current_plan: ExecutionPlan
    # observations 是最近一轮执行结果。
    observations: list[ExecutionObservation]
    # final_result 是最终对外返回结果。
    final_result: dict[str, Any]
    # selected_city 是城市识别结果。
    selected_city: str
    # selected_branch 是路由命中的分支名。
    selected_branch: str
    # branch_message 是分支提示信息。
    branch_message: str
    # route_trace 是整条执行路径轨迹。
    route_trace: list[str]
    # status 是当前状态标签。
    status: str
    # guardrail 是校验节点结果。
    guardrail: GuardrailDecision
    # retrieved_knowledge 是 RAG 检索结果。
    retrieved_knowledge: list[KnowledgeChunk]
    # should_replan 表示 Judge 是否要求重规划。
    should_replan: bool
    # iteration_count 表示已迭代次数。
    iteration_count: int
    # max_iterations 表示最大允许迭代次数。
    max_iterations: int
    # error_message 用来保存错误信息。
    error_message: str
