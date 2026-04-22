"""LangGraph 状态定义。"""

from __future__ import annotations

from typing import Any, TypedDict

from travel_agent.app.agents.contracts import (
    ExecutionObservation,
    ExecutionPlan,
    GuardrailDecision,
    KnowledgeChunk,
    SharedContext,
)


class TravelGraphState(TypedDict, total=False):
    session_id: str
    user_query: str
    shared_context: SharedContext
    current_plan: ExecutionPlan
    observations: list[ExecutionObservation]
    final_result: dict[str, Any]
    selected_city: str
    selected_branch: str
    branch_message: str
    route_trace: list[str]
    status: str
    guardrail: GuardrailDecision
    retrieved_knowledge: list[KnowledgeChunk]
    should_replan: bool
    iteration_count: int
    max_iterations: int
    error_message: str
