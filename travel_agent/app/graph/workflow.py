"""LangGraph 工作流封装。"""

# 启用延迟类型注解。
from __future__ import annotations

# END 和 START 表示 LangGraph 的起点终点，
# StateGraph 用来定义状态机。
from langgraph.graph import END, START, StateGraph

# 导入最终工作流结果模型。
from travel_agent.app.agents.contracts import TaskResult
# 导入执行器和规划器。
from travel_agent.app.agents.executor.agent import ExecutorAgent
from travel_agent.app.agents.planner.agent import PlannerAgent
# 导入所有节点函数和条件路由函数。
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
# 导入状态类型。
from travel_agent.app.graph.state import TravelGraphState
# 导入 RAG 服务接口。
from travel_agent.app.rag.service import BaseRAGService


class TravelGraphWorkflow:
    """封装完整 Agent 工作流。"""

    def __init__(self, planner: PlannerAgent, executor: ExecutorAgent, rag_service: BaseRAGService) -> None:
        """保存依赖并编译工作流。"""
        # 保存规划器实例。
        self._planner = planner
        # 保存执行器实例。
        self._executor = executor
        # 保存 RAG 服务实例。
        self._rag_service = rag_service
        # 初始化时直接编译整张图，后续 invoke 时可直接运行。
        self._graph = self.build()

    def build(self):
        """构建整张 LangGraph 图。"""
        # 用 TravelGraphState 作为图的状态结构。
        graph = StateGraph(TravelGraphState)
        # 注册 Guardrail 节点。
        graph.add_node("guardrail", guardrail_node)
        # 注册 Planner 节点。
        graph.add_node("planner", build_planner_node(self._planner))
        # 注册城市识别节点。
        graph.add_node("city_selector", city_selector_node)
        # 注册三个专属城市分支和一个通用分支。
        graph.add_node("shanghai_branch", shanghai_branch_node)
        graph.add_node("beijing_branch", beijing_branch_node)
        graph.add_node("hangzhou_branch", hangzhou_branch_node)
        graph.add_node("other_city_branch", other_city_branch_node)
        # 注册 RAG 节点。
        graph.add_node("rag", build_rag_node(self._rag_service))
        # 注册 Executor 节点。
        graph.add_node("executor", build_executor_node(self._executor))
        # 注册 Judge 节点。
        graph.add_node("judge", judge_node)
        # 注册最终结果收敛节点。
        graph.add_node("result", result_node)

        # 起点先进入 guardrail。
        graph.add_edge(START, "guardrail")
        # Guardrail 根据结果决定去 planner 还是直接结束到 result。
        graph.add_conditional_edges(
            "guardrail",
            route_after_guardrail,
            {"planner": "planner", "result": "result"},
        )
        # Planner 完成后进入城市识别。
        graph.add_edge("planner", "city_selector")
        # 城市识别后根据城市进入不同分支。
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
        # 所有城市分支最后都进入 rag。
        graph.add_edge("shanghai_branch", "rag")
        graph.add_edge("beijing_branch", "rag")
        graph.add_edge("hangzhou_branch", "rag")
        graph.add_edge("other_city_branch", "rag")
        # RAG 后进入 executor。
        graph.add_edge("rag", "executor")
        # 执行完成后进入 judge。
        graph.add_edge("executor", "judge")
        # Judge 决定回到 planner 重规划，还是去 result 收敛。
        graph.add_conditional_edges(
            "judge",
            route_after_judge,
            {"planner": "planner", "result": "result"},
        )
        # 最终结果节点后走到 END。
        graph.add_edge("result", END)
        # 编译成可运行图对象并返回。
        return graph.compile()

    def invoke(self, initial_state: TravelGraphState) -> TaskResult:
        """执行工作流，并把最终状态收敛成 TaskResult。"""
        # 调用 LangGraph 执行整张图。
        final_state = self._graph.invoke(initial_state)
        # 把字典状态重新封装成统一的 TaskResult。
        return TaskResult(
            session_id=final_state["session_id"],
            status=final_state["status"],
            current_plan=final_state.get("current_plan"),
            observations=final_state.get("observations", []),
            final_result=final_state.get("final_result", {}),
            iteration_count=final_state.get("iteration_count", 0),
            error_message=final_state.get("error_message"),
        )
