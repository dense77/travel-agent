"""作用：
- 封装 LangGraph 工作流的构建和调用入口。

约定：
- 当前工作流演示 LangGraph 条件分支：规划、城市识别、按城市路由、执行、结果收敛。
- `invoke` 返回内部统一的 `TaskResult`，便于存储层直接落盘或落内存。
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from travel_agent.app.agents.contracts import TaskResult
from travel_agent.app.agents.executor.agent import ExecutorAgent
from travel_agent.app.agents.planner.agent import PlannerAgent
from travel_agent.app.graph.nodes import (
    beijing_branch_node,
    build_executor_node,
    build_planner_node,
    city_selector_node,
    hangzhou_branch_node,
    other_city_branch_node,
    result_node,
    route_by_city,
    shanghai_branch_node,
)
from travel_agent.app.graph.state import TravelGraphState


class TravelGraphWorkflow:
    def __init__(self, planner: PlannerAgent, executor: ExecutorAgent) -> None:
        self._planner = planner
        self._executor = executor
        self._graph = self.build()

    def build(self):
        # 这里演示 LangGraph 的条件分支能力：先识别城市，再决定走哪条边。
        graph = StateGraph(TravelGraphState)
        graph.add_node("planner", build_planner_node(self._planner))
        graph.add_node("city_selector", city_selector_node)
        graph.add_node("shanghai_branch", shanghai_branch_node)
        graph.add_node("beijing_branch", beijing_branch_node)
        graph.add_node("hangzhou_branch", hangzhou_branch_node)
        graph.add_node("other_city_branch", other_city_branch_node)
        graph.add_node("executor", build_executor_node(self._executor))
        graph.add_node("result", result_node)
        graph.add_edge(START, "planner")
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
        graph.add_edge("shanghai_branch", "executor")
        graph.add_edge("beijing_branch", "executor")
        graph.add_edge("hangzhou_branch", "executor")
        graph.add_edge("other_city_branch", "executor")
        graph.add_edge("executor", "result")
        graph.add_edge("result", END)
        return graph.compile()

    def invoke(self, initial_state: TravelGraphState) -> TaskResult:
        # LangGraph 返回的是字典状态，这里再收口成 Pydantic 模型。
        final_state = self._graph.invoke(initial_state)
        return TaskResult(
            session_id=final_state["session_id"],
            status=final_state["status"],
            current_plan=final_state["current_plan"],
            observations=final_state.get("observations", []),
            final_result=final_state.get("final_result", {}),
        )
