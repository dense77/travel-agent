"""LangGraph 工作流封装。"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from travel_agent.app.agents.contracts import TaskResult
from travel_agent.app.agents.executor.agent import ExecutorAgent
from travel_agent.app.agents.planner.agent import PlannerAgent
from travel_agent.app.graph.nodes import (
    build_candidate_generation_node,
    build_follow_up_node,
    build_missing_info_node,
    build_risk_check_node,
    build_tool_collection_node,
    constraint_analysis_node,
    constraint_extraction_node,
    guardrail_node,
    intent_recognition_node,
    planning_router_node,
    result_node,
    route_after_guardrail,
    route_after_missing_info,
    route_after_risk_check,
)
from travel_agent.app.graph.state import TravelGraphState
from travel_agent.app.rag.service import BaseRAGService


class TravelGraphWorkflow:
    """封装新的交互层 + 规划层 LangGraph 工作流。"""

    def __init__(self, planner: PlannerAgent, executor: ExecutorAgent, rag_service: BaseRAGService) -> None:
        """保存依赖并编译工作流。"""
        self._planner = planner
        self._executor = executor
        self._rag_service = rag_service
        self._graph = self.build()

    def build(self):
        """构建整张 LangGraph 图。"""
        graph = StateGraph(TravelGraphState)

        graph.add_node("guardrail", guardrail_node)
        graph.add_node("intent_recognition", intent_recognition_node)
        graph.add_node("constraint_extraction", constraint_extraction_node)
        graph.add_node("missing_info_check", build_missing_info_node(self._planner))
        graph.add_node("follow_up", build_follow_up_node(self._planner))
        graph.add_node("planning_router", planning_router_node)
        graph.add_node("constraint_analysis", constraint_analysis_node)
        graph.add_node("tool_collection", build_tool_collection_node(self._rag_service, self._executor))
        graph.add_node("candidate_generation", build_candidate_generation_node(self._planner))
        graph.add_node("risk_check", build_risk_check_node(self._planner))
        graph.add_node("result", result_node)

        graph.add_edge(START, "guardrail")
        graph.add_conditional_edges(
            "guardrail",
            route_after_guardrail,
            {"intent_recognition": "intent_recognition", "result": "result"},
        )
        graph.add_edge("intent_recognition", "constraint_extraction")
        graph.add_edge("constraint_extraction", "missing_info_check")
        graph.add_conditional_edges(
            "missing_info_check",
            route_after_missing_info,
            {"follow_up": "follow_up", "planning_router": "planning_router"},
        )
        graph.add_edge("follow_up", "result")
        graph.add_edge("planning_router", "constraint_analysis")
        graph.add_edge("constraint_analysis", "tool_collection")
        graph.add_edge("tool_collection", "candidate_generation")
        graph.add_edge("candidate_generation", "risk_check")
        graph.add_conditional_edges(
            "risk_check",
            route_after_risk_check,
            {"candidate_generation": "candidate_generation", "result": "result"},
        )
        graph.add_edge("result", END)

        return graph.compile()

    def invoke(self, initial_state: TravelGraphState) -> TaskResult:
        """执行工作流，并把最终状态收敛成 TaskResult。"""
        final_state = self._graph.invoke(initial_state)
        return TaskResult(
            session_id=final_state["session_id"],
            status=final_state["status"],
            current_plan=final_state.get("current_plan"),
            observations=final_state.get("observations", []),
            final_result=final_state.get("final_result", {}),
            iteration_count=final_state.get("candidate_retry_count", 0),
            error_message=final_state.get("error_message"),
        )
