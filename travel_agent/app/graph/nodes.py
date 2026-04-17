"""作用：
- 定义 LangGraph 的节点函数，把 Planner、条件路由、Executor 和结果收敛串起来。

约定：
- 节点函数接收 `TravelGraphState`，返回“本节点更新后的局部状态”。
- 当前演示使用“按城市条件分支”的方式展示 LangGraph 路由能力。
"""

from __future__ import annotations

from typing import Any

from travel_agent.app.agents.contracts import SharedContext
from travel_agent.app.agents.executor.agent import ExecutorAgent
from travel_agent.app.agents.planner.agent import PlannerAgent
from travel_agent.app.graph.state import TravelGraphState


def _append_route_trace(state: TravelGraphState, message: str) -> list[str]:
    route_trace = list(state.get("route_trace", []))
    route_trace.append(message)
    return route_trace


def _print_step(message: str) -> None:
    print(f"[LangGraph Demo] {message}")


def _guess_city(user_query: str, constraints: dict[str, Any]) -> str:
    candidate_fields = (
        "destination_city",
        "target_city",
        "city",
        "start_city",
    )
    for field in candidate_fields:
        value = str(constraints.get(field, "")).strip()
        if value:
            return value

    query = user_query.strip()
    for city in ("上海", "北京", "杭州", "深圳", "广州"):
        if city in query:
            return city
    return "其他城市"


def city_selector_node(state: TravelGraphState) -> TravelGraphState:
    context = state["shared_context"]
    selected_city = _guess_city(state["user_query"], context.hard_constraints)
    trace_message = f"city_selector -> 识别到城市：{selected_city}"
    _print_step(trace_message)
    return {
        "selected_city": selected_city,
        "route_trace": _append_route_trace(state, trace_message),
        "status": "city_selected",
    }


def route_by_city(state: TravelGraphState) -> str:
    selected_city = state.get("selected_city", "其他城市")
    if selected_city == "上海":
        branch = "shanghai_branch"
    elif selected_city == "北京":
        branch = "beijing_branch"
    elif selected_city == "杭州":
        branch = "hangzhou_branch"
    else:
        branch = "other_city_branch"

    _print_step(f"route_by_city -> selected_city={selected_city}，命中分支：{branch}")
    return branch


def _build_branch_update(
    state: TravelGraphState,
    branch_name: str,
    branch_message: str,
) -> TravelGraphState:
    current_plan = state["current_plan"]
    updated_steps = []

    for step in current_plan.steps:
        updated_payload = dict(step.input_payload)
        updated_payload["selected_city"] = state.get("selected_city", "其他城市")
        updated_payload["selected_branch"] = branch_name
        updated_payload["branch_message"] = branch_message
        updated_steps.append(step.model_copy(update={"input_payload": updated_payload}))

    updated_plan = current_plan.model_copy(update={"steps": updated_steps})
    updated_context = state["shared_context"].model_copy(update={"current_plan": updated_plan})
    trace_message = f"{branch_name} -> {branch_message}"
    _print_step(trace_message)

    return {
        "current_plan": updated_plan,
        "shared_context": updated_context,
        "selected_branch": branch_name,
        "branch_message": branch_message,
        "route_trace": _append_route_trace(state, trace_message),
        "status": "branch_selected",
    }


def shanghai_branch_node(state: TravelGraphState) -> TravelGraphState:
    return _build_branch_update(
        state=state,
        branch_name="shanghai_branch",
        branch_message="进入上海分支，准备生成上海城市玩法建议。",
    )


def beijing_branch_node(state: TravelGraphState) -> TravelGraphState:
    return _build_branch_update(
        state=state,
        branch_name="beijing_branch",
        branch_message="进入北京分支，准备生成北京城市玩法建议。",
    )


def hangzhou_branch_node(state: TravelGraphState) -> TravelGraphState:
    return _build_branch_update(
        state=state,
        branch_name="hangzhou_branch",
        branch_message="进入杭州分支，准备生成杭州城市玩法建议。",
    )


def other_city_branch_node(state: TravelGraphState) -> TravelGraphState:
    selected_city = state.get("selected_city", "其他城市")
    return _build_branch_update(
        state=state,
        branch_name="other_city_branch",
        branch_message=f"进入通用分支，当前城市是 {selected_city}。",
    )


def build_planner_node(planner: PlannerAgent):
    def planner_node(state: TravelGraphState) -> TravelGraphState:
        context = state["shared_context"]
        plan = planner.plan(context)
        # `shared_context` 会跟随计划一起更新，供后续节点读取一致视图。
        updated_context = context.model_copy(update={"current_plan": plan})
        trace_message = "planner -> 已生成基础旅行计划"
        _print_step(trace_message)
        return {
            "current_plan": plan,
            "shared_context": updated_context,
            "route_trace": _append_route_trace(state, trace_message),
            "status": "planned",
        }

    return planner_node


def build_executor_node(executor: ExecutorAgent):
    def executor_node(state: TravelGraphState) -> TravelGraphState:
        plan = state["current_plan"]
        context = state["shared_context"]
        selected_branch = state.get("selected_branch", "no_branch")
        trace_message = f"executor -> 开始执行计划，当前分支：{selected_branch}"
        _print_step(trace_message)
        observations = executor.execute(plan, context)
        # 执行结果只回写最新观察，最小闭环里还没有长期记忆合并逻辑。
        updated_context = context.model_copy(update={"latest_observations": observations})
        return {
            "observations": observations,
            "shared_context": updated_context,
            "route_trace": _append_route_trace(state, trace_message),
            "status": "executed",
        }

    return executor_node


def result_node(state: TravelGraphState) -> TravelGraphState:
    plan = state["current_plan"]
    observations = state.get("observations", [])
    # 当前约定“最后一个 observation 的结构化输出”就是最终答案主体。
    latest = observations[-1].structured_output if observations else {}
    trace_message = f"result -> 汇总完成，最终分支：{state.get('selected_branch', 'no_branch')}"
    _print_step(trace_message)
    route_trace = _append_route_trace(state, trace_message)

    return {
        "final_result": {
            "goal": plan.goal,
            "selected_city": state.get("selected_city", ""),
            "selected_branch": state.get("selected_branch", ""),
            "branch_message": state.get("branch_message", ""),
            "route_trace": route_trace,
            "steps": [step.model_dump() for step in plan.steps],
            "observations": [item.model_dump() for item in observations],
            "answer": latest,
        },
        "route_trace": route_trace,
        "status": "finished",
    }
