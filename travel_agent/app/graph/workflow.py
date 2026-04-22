"""LangGraph 工作流封装。"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from travel_agent.app.agents.contracts import TaskResult
from travel_agent.app.agents.executor.agent import ExecutorAgent
from travel_agent.app.agents.planner.agent import PlannerAgent
from travel_agent.app.graph.nodes import (
    beijing_branch_node,
    build_executor_node,
    build_planner_node,
    build_rag_node,
    city_selector_node,
    guardrail_node,
    hangzhou_branch_node,
    judge_node,
    other_city_branch_node,
    result_node,
    route_after_guardrail,
    route_after_judge,
    route_by_city,
    shanghai_branch_node,
)
from travel_agent.app.graph.state import TravelGraphState
from travel_agent.app.rag.service import BaseRAGService


class TravelGraphWorkflow:
    """封装高一层的 Agent 工作流。"""

    def __init__(self, planner: PlannerAgent, executor: ExecutorAgent, rag_service: BaseRAGService) -> None:
        self._planner = planner
        self._executor = executor
        self._rag_service = rag_service
        self._graph = self.build()

    def build(self):
        graph = StateGraph(TravelGraphState)
        graph.add_node("guardrail", guardrail_node)
        graph.add_node("planner", build_planner_node(self._planner))
        graph.add_node("city_selector", city_selector_node)
        graph.add_node("shanghai_branch", shanghai_branch_node)
        graph.add_node("beijing_branch", beijing_branch_node)
        graph.add_node("hangzhou_branch", hangzhou_branch_node)
        graph.add_node("other_city_branch", other_city_branch_node)
        graph.add_node("rag", build_rag_node(self._rag_service))
        graph.add_node("executor", build_executor_node(self._executor))
        graph.add_node("judge", judge_node)
        graph.add_node("result", result_node)

        graph.add_edge(START, "guardrail")
        graph.add_conditional_edges(
            "guardrail",
            route_after_guardrail,
            {"planner": "planner", "result": "result"},
        )
        graph.add_edge("planner", "city_selector")
        graph.add_conditional_edges(
            "city_selector",
            route_by_city,
            {
                "shanghai_branch": "shanghai_branch",
                "beijing_branch": "beijing_branch",
                "hangzhou_branch": "hangzhou_branch",
                "other_city_branch": "other_city_branch",
            },
        )
        graph.add_edge("shanghai_branch", "rag")
        graph.add_edge("beijing_branch", "rag")
        graph.add_edge("hangzhou_branch", "rag")
        graph.add_edge("other_city_branch", "rag")
        graph.add_edge("rag", "executor")
        graph.add_edge("executor", "judge")
        graph.add_conditional_edges(
            "judge",
            route_after_judge,
            {"planner": "planner", "result": "result"},
        )
        graph.add_edge("result", END)
        return graph.compile()

    def invoke(self, initial_state: TravelGraphState) -> TaskResult:
        final_state = self._graph.invoke(initial_state)
        return TaskResult(
            session_id=final_state["session_id"],
            status=final_state["status"],
            current_plan=final_state.get("current_plan"),
            observations=final_state.get("observations", []),
            final_result=final_state.get("final_result", {}),
            iteration_count=final_state.get("iteration_count", 0),
            error_message=final_state.get("error_message"),
        )
