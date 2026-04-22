"""LangGraph 状态定义。"""

# 启用延迟类型注解。
from __future__ import annotations

# Any 用来描述灵活数据字段，
# TypedDict 用来定义字典状态结构。
from typing import Any, TypedDict

# 导入工作流状态里会出现的各种模型。
from travel_agent.app.agents.contracts import (
    CandidatePlan,
    ExecutionObservation,
    ExecutionPlan,
    FollowUpQuestion,
    GuardrailDecision,
    IntentDecision,
    KnowledgeChunk,
    RiskCheckResult,
    RouteDecision,
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
    # route_trace 是整条执行路径轨迹。
    route_trace: list[str]
    # status 是当前状态标签。
    status: str
    # guardrail 是校验节点结果。
    guardrail: GuardrailDecision
    # intent_decision 是意图识别结果。
    intent_decision: IntentDecision
    # extracted_constraints 是从 query 和结构化入参中提取的约束。
    extracted_constraints: dict[str, Any]
    # missing_info 是当前还缺失的信息字段。
    missing_info: list[str]
    # follow_up_questions 是追问列表。
    follow_up_questions: list[FollowUpQuestion]
    # interaction_action 是交互层决定的下一步动作。
    interaction_action: str
    # route_decision 是规划层路由结果。
    route_decision: RouteDecision
    # planning_constraints 是规划层归一化后的约束。
    planning_constraints: dict[str, Any]
    # retrieved_knowledge 是 RAG 检索结果。
    retrieved_knowledge: list[KnowledgeChunk]
    # tool_observations 表示规划层工具执行结果。
    tool_observations: list[ExecutionObservation]
    # candidate_plans 表示生成的候选方案列表。
    candidate_plans: list[CandidatePlan]
    # risk_checks 表示候选方案风险检查结果。
    risk_checks: list[RiskCheckResult]
    # selected_candidate_id 表示当前推荐的方案 ID。
    selected_candidate_id: str
    # candidate_retry_count 表示候选方案回退生成次数。
    candidate_retry_count: int
    # candidate_retry_needed 表示是否需要回退再生成。
    candidate_retry_needed: bool
    # error_message 用来保存错误信息。
    error_message: str
