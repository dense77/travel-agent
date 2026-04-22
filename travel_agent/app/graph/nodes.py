"""LangGraph 节点定义。"""

from __future__ import annotations

from typing import Any

from travel_agent.app.agents.contracts import GuardrailDecision, SharedContext
from travel_agent.app.agents.executor.agent import ExecutorAgent
from travel_agent.app.agents.planner.agent import PlannerAgent
from travel_agent.app.graph.state import TravelGraphState
from travel_agent.app.rag.service import BaseRAGService


def _append_route_trace(state: TravelGraphState, message: str) -> list[str]:
    route_trace = list(state.get("route_trace", []))
    route_trace.append(message)
    return route_trace


def _print_step(message: str) -> None:
    print(f"[LangGraph Demo] {message}")


def _guess_city(user_query: str, constraints: dict[str, Any]) -> str:
    candidate_fields = ("destination_city", "target_city", "city", "start_city")
    for field in candidate_fields:
        value = str(constraints.get(field, "")).strip()
        if value:
            return value

    query = user_query.strip()
    for city in ("上海", "北京", "杭州", "深圳", "广州"):
        if city in query:
            return city
    return "其他城市"


def _resolve_branch_name(selected_city: str) -> str:
    if selected_city == "上海":
        return "shanghai_branch"
    if selected_city == "北京":
        return "beijing_branch"
    if selected_city == "杭州":
        return "hangzhou_branch"
    return "other_city_branch"


def _update_plan_payload(state: TravelGraphState, extra_payload: dict[str, Any]) -> tuple[Any, SharedContext]:
    current_plan = state["current_plan"]
    updated_steps = []

    for step in current_plan.steps:
        updated_payload = dict(step.input_payload)
        updated_payload.update(extra_payload)
        updated_steps.append(step.model_copy(update={"input_payload": updated_payload}))

    updated_plan = current_plan.model_copy(update={"steps": updated_steps})
    updated_context = state["shared_context"].model_copy(update={"current_plan": updated_plan})
    return updated_plan, updated_context


def guardrail_node(state: TravelGraphState) -> TravelGraphState:
    query = state["user_query"].strip()
    constraints = state["shared_context"].hard_constraints
    reasons: list[str] = []

    if not query:
        reasons.append("user_query is empty")

    travel_days = constraints.get("travel_days")
    if travel_days is not None and int(travel_days) <= 0:
        reasons.append("travel_days must be positive")

    budget = constraints.get("budget")
    if budget is not None and float(budget) < 0:
        reasons.append("budget must not be negative")

    allowed = not reasons
    trace_message = "guardrail -> 请求通过校验" if allowed else f"guardrail -> 拒绝请求: {', '.join(reasons)}"
    _print_step(trace_message)
    return {
        "guardrail": GuardrailDecision(allowed=allowed, reasons=reasons),
        "route_trace": _append_route_trace(state, trace_message),
        "status": "guardrail_passed" if allowed else "rejected",
        "error_message": "; ".join(reasons) if reasons else "",
    }


def route_after_guardrail(state: TravelGraphState) -> str:
    guardrail = state["guardrail"]
    return "planner" if guardrail.allowed else "result"


def city_selector_node(state: TravelGraphState) -> TravelGraphState:
    context = state["shared_context"]
    selected_city = _guess_city(state["user_query"], context.hard_constraints)
    selected_branch = _resolve_branch_name(selected_city)
    trace_message = f"city_selector -> 识别到城市：{selected_city}，准备路由到：{selected_branch}"
    _print_step(trace_message)
    return {
        "selected_city": selected_city,
        "selected_branch": selected_branch,
        "route_trace": _append_route_trace(state, trace_message),
        "status": "city_selected",
    }


def route_by_city(state: TravelGraphState) -> str:
    selected_city = state.get("selected_city", "其他城市")
    branch = _resolve_branch_name(selected_city)
    _print_step(f"route_by_city -> selected_city={selected_city}，命中分支：{branch}")
    return branch


def _build_branch_update(state: TravelGraphState, branch_name: str, branch_message: str) -> TravelGraphState:
    updated_plan, updated_context = _update_plan_payload(
        state=state,
        extra_payload={
            "selected_city": state.get("selected_city", "其他城市"),
            "selected_branch": branch_name,
            "branch_message": branch_message,
        },
    )
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
    return _build_branch_update(state, "shanghai_branch", "进入上海分支，准备生成上海城市玩法建议。")


def beijing_branch_node(state: TravelGraphState) -> TravelGraphState:
    return _build_branch_update(state, "beijing_branch", "进入北京分支，准备生成北京城市玩法建议。")


def hangzhou_branch_node(state: TravelGraphState) -> TravelGraphState:
    return _build_branch_update(state, "hangzhou_branch", "进入杭州分支，准备生成杭州城市玩法建议。")


def other_city_branch_node(state: TravelGraphState) -> TravelGraphState:
    selected_city = state.get("selected_city", "其他城市")
    return _build_branch_update(
        state,
        "other_city_branch",
        f"进入通用分支，当前城市是 {selected_city}。",
    )


def build_planner_node(planner: PlannerAgent):
    def planner_node(state: TravelGraphState) -> TravelGraphState:
        context = state["shared_context"]
        is_replan = state.get("iteration_count", 0) > 0 and context.latest_observations
        plan = planner.replan(context) if is_replan else planner.plan(context)
        updated_context = context.model_copy(update={"current_plan": plan})
        trace_message = "planner -> 已生成重规划计划" if is_replan else "planner -> 已生成基础旅行计划"
        _print_step(trace_message)
        return {
            "current_plan": plan,
            "shared_context": updated_context,
            "route_trace": _append_route_trace(state, trace_message),
            "status": "planned",
        }

    return planner_node


def build_rag_node(rag_service: BaseRAGService):
    def rag_node(state: TravelGraphState) -> TravelGraphState:
        current_plan = state["current_plan"]
        if not current_plan.need_rag:
            trace_message = "rag -> 当前计划不需要检索，跳过。"
            _print_step(trace_message)
            return {
                "retrieved_knowledge": [],
                "route_trace": _append_route_trace(state, trace_message),
                "status": "rag_skipped",
            }

        context = state["shared_context"]
        knowledge_chunks = rag_service.retrieve(state["user_query"], context)
        updated_plan, updated_context = _update_plan_payload(
            state=state,
            extra_payload={"knowledge_chunks": [item.model_dump() for item in knowledge_chunks]},
        )
        updated_context = updated_context.model_copy(update={"retrieved_knowledge": knowledge_chunks})
        trace_message = f"rag -> 已检索到 {len(knowledge_chunks)} 条知识片段"
        _print_step(trace_message)
        return {
            "current_plan": updated_plan,
            "shared_context": updated_context,
            "retrieved_knowledge": knowledge_chunks,
            "route_trace": _append_route_trace(state, trace_message),
            "status": "rag_retrieved",
        }

    return rag_node


def build_executor_node(executor: ExecutorAgent):
    def executor_node(state: TravelGraphState) -> TravelGraphState:
        plan = state["current_plan"]
        context = state["shared_context"]
        selected_branch = state.get("selected_branch", "no_branch")
        trace_message = f"executor -> 开始执行计划，当前分支：{selected_branch}"
        _print_step(trace_message)
        observations = executor.execute(plan, context)
        updated_context = context.model_copy(update={"latest_observations": observations})
        return {
            "observations": observations,
            "shared_context": updated_context,
            "route_trace": _append_route_trace(state, trace_message),
            "status": "executed",
        }

    return executor_node


def judge_node(state: TravelGraphState) -> TravelGraphState:
    observations = state.get("observations", [])
    iteration_count = state.get("iteration_count", 0) + 1
    max_iterations = state.get("max_iterations", 1)
    any_failed = any(not item.success for item in observations)
    should_replan = any_failed and iteration_count < max_iterations

    trace_message = (
        f"judge -> 存在失败 observation，准备进入第 {iteration_count} 次重规划。"
        if should_replan
        else f"judge -> 当前结果可收敛，iteration_count={iteration_count}。"
    )
    _print_step(trace_message)
    return {
        "iteration_count": iteration_count,
        "should_replan": should_replan,
        "route_trace": _append_route_trace(state, trace_message),
        "status": "replanning" if should_replan else "judged",
    }


def route_after_judge(state: TravelGraphState) -> str:
    return "planner" if state.get("should_replan", False) else "result"


def result_node(state: TravelGraphState) -> TravelGraphState:
    guardrail = state.get("guardrail")
    route_trace = list(state.get("route_trace", []))
    observations = state.get("observations", [])
    current_plan = state.get("current_plan")
    knowledge = state.get("retrieved_knowledge", [])
    selected_branch = state.get("selected_branch", "no_branch")

    if guardrail and not guardrail.allowed:
        trace_message = "result -> Guardrail 拒绝，本次请求直接结束。"
        _print_step(trace_message)
        route_trace = _append_route_trace(state, trace_message)
        return {
            "final_result": {
                "goal": state.get("user_query", ""),
                "status": "rejected",
                "error": state.get("error_message", ""),
                "route_trace": route_trace,
            },
            "route_trace": route_trace,
            "status": "rejected",
        }

    latest = observations[-1].structured_output if observations else {}
    trace_message = f"result -> 汇总完成，最终分支：{selected_branch}"
    _print_step(trace_message)
    route_trace = _append_route_trace(state, trace_message)

    return {
        "final_result": {
            "goal": current_plan.goal if current_plan else state.get("user_query", ""),
            "selected_city": state.get("selected_city", ""),
            "selected_branch": selected_branch,
            "branch_message": state.get("branch_message", ""),
            "route_trace": route_trace,
            "steps": [step.model_dump() for step in current_plan.steps] if current_plan else [],
            "observations": [item.model_dump() for item in observations],
            "knowledge": [item.model_dump() for item in knowledge],
            "answer": latest,
        },
        "route_trace": route_trace,
        "status": "finished",
    }
