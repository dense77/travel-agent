"""LangGraph 节点定义。

这个文件是整个工作流里最核心的业务编排位置，
因为 Planner、RAG、Executor、Judge 等能力最终都是在这里串起来的。
"""

# 启用延迟类型注解。
from __future__ import annotations

# Any 用来描述动态 payload 结构。
from typing import Any

# 导入 GuardrailDecision 和 SharedContext 这两个状态里会反复用到的模型。
from travel_agent.app.agents.contracts import GuardrailDecision, SharedContext
# 导入执行器和规划器类型，用于构造节点函数。
from travel_agent.app.agents.executor.agent import ExecutorAgent
from travel_agent.app.agents.planner.agent import PlannerAgent
# 导入工作流状态类型。
from travel_agent.app.graph.state import TravelGraphState
# 导入城市识别工具。
from travel_agent.app.infra.city_resolver import guess_trip_city
# 导入 RAG 服务接口。
from travel_agent.app.rag.service import BaseRAGService


def _append_route_trace(state: TravelGraphState, message: str) -> list[str]:
    """在 route_trace 后面追加一条新消息。"""
    # 先从状态里取出已有轨迹，如果没有就给一个空列表。
    route_trace = list(state.get("route_trace", []))
    # 把本次节点消息追加进去。
    route_trace.append(message)
    # 返回新的轨迹列表。
    return route_trace


def _print_step(message: str) -> None:
    """把节点过程打印到控制台。"""
    # 统一给调试输出加一个前缀，便于在控制台里识别。
    print(f"[LangGraph Demo] {message}")


def _guess_city(user_query: str, constraints: dict[str, Any]) -> str:
    """优先从约束中猜城市，再从 query 文本中猜。"""
    return guess_trip_city(user_query, constraints)


def _resolve_branch_name(selected_city: str) -> str:
    """把城市名映射成工作流里的分支节点名。"""
    if selected_city == "上海":
        return "shanghai_branch"
    if selected_city == "北京":
        return "beijing_branch"
    if selected_city == "杭州":
        return "hangzhou_branch"
    return "other_city_branch"


def _update_plan_payload(state: TravelGraphState, extra_payload: dict[str, Any]) -> tuple[Any, SharedContext]:
    """把额外参数写回当前计划的每一个步骤。"""
    # 取出当前计划。
    current_plan = state["current_plan"]
    # 准备一个新的 step 列表。
    updated_steps = []

    # 逐步遍历当前计划中的每一个 step。
    for step in current_plan.steps:
        # 先复制原本的输入 payload。
        updated_payload = dict(step.input_payload)
        # 再把额外字段合并进去。
        updated_payload.update(extra_payload)
        # 生成一个带新 payload 的 step 副本并加入新列表。
        updated_steps.append(step.model_copy(update={"input_payload": updated_payload}))

    # 用新步骤列表生成一个新的计划对象。
    updated_plan = current_plan.model_copy(update={"steps": updated_steps})
    # 同时把共享上下文里的 current_plan 也更新掉。
    updated_context = state["shared_context"].model_copy(update={"current_plan": updated_plan})
    # 返回更新后的计划和上下文。
    return updated_plan, updated_context


def guardrail_node(state: TravelGraphState) -> TravelGraphState:
    """对请求做基础合法性校验。"""
    # 先取出 query。
    query = state["user_query"].strip()
    # 再取出硬约束。
    constraints = state["shared_context"].hard_constraints
    # 初始化一个理由列表，后面记录所有拒绝原因。
    reasons: list[str] = []

    # 如果 query 是空字符串，就记录错误。
    if not query:
        reasons.append("user_query is empty")

    # 检查 travel_days 是否存在非法值。
    travel_days = constraints.get("travel_days")
    if travel_days is not None and int(travel_days) <= 0:
        reasons.append("travel_days must be positive")

    # 检查 budget 是否存在非法值。
    budget = constraints.get("budget")
    if budget is not None and float(budget) < 0:
        reasons.append("budget must not be negative")

    # 没有拒绝理由就说明允许通过。
    allowed = not reasons
    # 组装一条更易读的 trace。
    trace_message = "guardrail -> 请求通过校验" if allowed else f"guardrail -> 拒绝请求: {', '.join(reasons)}"
    # 打印调试信息。
    _print_step(trace_message)
    # 返回状态更新。
    return {
        "guardrail": GuardrailDecision(allowed=allowed, reasons=reasons),
        "route_trace": _append_route_trace(state, trace_message),
        "status": "guardrail_passed" if allowed else "rejected",
        "error_message": "; ".join(reasons) if reasons else "",
    }


def route_after_guardrail(state: TravelGraphState) -> str:
    """根据 guardrail 结果决定下一跳。"""
    # 先取出 guardrail 决策。
    guardrail = state["guardrail"]
    # 通过则去 planner，否则直接去 result。
    return "planner" if guardrail.allowed else "result"


def city_selector_node(state: TravelGraphState) -> TravelGraphState:
    """识别当前请求对应的城市。"""
    # 先取出共享上下文。
    context = state["shared_context"]
    # 根据 query 和 constraints 猜城市。
    selected_city = _guess_city(state["user_query"], context.hard_constraints)
    # 再把城市映射到分支节点名。
    selected_branch = _resolve_branch_name(selected_city)
    # 生成 trace 信息。
    trace_message = f"city_selector -> 识别到城市：{selected_city}，准备路由到：{selected_branch}"
    # 打印日志。
    _print_step(trace_message)
    # 返回状态更新。
    return {
        "selected_city": selected_city,
        "selected_branch": selected_branch,
        "route_trace": _append_route_trace(state, trace_message),
        "status": "city_selected",
    }


def route_by_city(state: TravelGraphState) -> str:
    """根据 selected_city 返回分支名。"""
    # 尝试从状态里读取 selected_city。
    selected_city = state.get("selected_city", "其他城市")
    # 映射成分支名称。
    branch = _resolve_branch_name(selected_city)
    # 打印调试信息。
    _print_step(f"route_by_city -> selected_city={selected_city}，命中分支：{branch}")
    # 返回给 LangGraph 用于条件跳转。
    return branch


def _build_branch_update(state: TravelGraphState, branch_name: str, branch_message: str) -> TravelGraphState:
    """构造城市分支节点的统一更新逻辑。"""
    # 把分支相关信息批量写回计划步骤。
    updated_plan, updated_context = _update_plan_payload(
        state=state,
        extra_payload={
            "selected_city": state.get("selected_city", "其他城市"),
            "selected_branch": branch_name,
            "branch_message": branch_message,
        },
    )
    # 生成 trace 文本。
    trace_message = f"{branch_name} -> {branch_message}"
    # 打印调试信息。
    _print_step(trace_message)

    # 返回新的状态片段。
    return {
        "current_plan": updated_plan,
        "shared_context": updated_context,
        "selected_branch": branch_name,
        "branch_message": branch_message,
        "route_trace": _append_route_trace(state, trace_message),
        "status": "branch_selected",
    }


def shanghai_branch_node(state: TravelGraphState) -> TravelGraphState:
    """处理上海分支。"""
    return _build_branch_update(state, "shanghai_branch", "进入上海分支，准备生成上海城市玩法建议。")


def beijing_branch_node(state: TravelGraphState) -> TravelGraphState:
    """处理北京分支。"""
    return _build_branch_update(state, "beijing_branch", "进入北京分支，准备生成北京城市玩法建议。")


def hangzhou_branch_node(state: TravelGraphState) -> TravelGraphState:
    """处理杭州分支。"""
    return _build_branch_update(state, "hangzhou_branch", "进入杭州分支，准备生成杭州城市玩法建议。")


def other_city_branch_node(state: TravelGraphState) -> TravelGraphState:
    """处理非专属城市分支。"""
    # 先取出识别到的城市。
    selected_city = state.get("selected_city", "其他城市")
    # 调用统一分支更新函数。
    return _build_branch_update(
        state,
        "other_city_branch",
        f"进入通用分支，当前城市是 {selected_city}。",
    )


def build_planner_node(planner: PlannerAgent):
    """根据规划器实例返回一个 planner 节点函数。"""

    def planner_node(state: TravelGraphState) -> TravelGraphState:
        """执行规划或重规划。"""
        # 取出共享上下文。
        context = state["shared_context"]
        # 如果已经有 observation 且 iteration_count > 0，
        # 就说明现在走的是重规划。
        is_replan = state.get("iteration_count", 0) > 0 and context.latest_observations
        # 按条件决定调用 plan 还是 replan。
        plan = planner.replan(context) if is_replan else planner.plan(context)
        # 把新计划写回上下文。
        updated_context = context.model_copy(update={"current_plan": plan})
        # 生成 trace 文本。
        trace_message = "planner -> 已生成重规划计划" if is_replan else "planner -> 已生成基础旅行计划"
        # 打印调试信息。
        _print_step(trace_message)
        # 返回状态更新。
        return {
            "current_plan": plan,
            "shared_context": updated_context,
            "route_trace": _append_route_trace(state, trace_message),
            "status": "planned",
        }

    # 返回节点函数本身。
    return planner_node


def build_rag_node(rag_service: BaseRAGService):
    """根据 RAG 服务实例返回一个 rag 节点函数。"""

    def rag_node(state: TravelGraphState) -> TravelGraphState:
        """执行检索，或在不需要时跳过。"""
        # 先拿到当前计划。
        current_plan = state["current_plan"]
        # 如果当前计划不需要 RAG，就直接跳过。
        if not current_plan.need_rag:
            trace_message = "rag -> 当前计划不需要检索，跳过。"
            _print_step(trace_message)
            return {
                "retrieved_knowledge": [],
                "route_trace": _append_route_trace(state, trace_message),
                "status": "rag_skipped",
            }

        # 需要检索时，先拿上下文。
        context = state["shared_context"]
        # 调用 RAG 服务执行召回。
        knowledge_chunks = rag_service.retrieve(state["user_query"], context)
        # 把检索结果写回计划步骤的 payload 中。
        updated_plan, updated_context = _update_plan_payload(
            state=state,
            extra_payload={"knowledge_chunks": [item.model_dump() for item in knowledge_chunks]},
        )
        # 同时把知识片段写回共享上下文。
        updated_context = updated_context.model_copy(update={"retrieved_knowledge": knowledge_chunks})
        # 生成 trace 文本。
        trace_message = f"rag -> 已检索到 {len(knowledge_chunks)} 条知识片段"
        # 打印调试信息。
        _print_step(trace_message)
        # 返回状态更新。
        return {
            "current_plan": updated_plan,
            "shared_context": updated_context,
            "retrieved_knowledge": knowledge_chunks,
            "route_trace": _append_route_trace(state, trace_message),
            "status": "rag_retrieved",
        }

    # 返回节点函数本身。
    return rag_node


def build_executor_node(executor: ExecutorAgent):
    """根据执行器实例返回一个 executor 节点函数。"""

    def executor_node(state: TravelGraphState) -> TravelGraphState:
        """执行当前计划。"""
        # 取出当前计划。
        plan = state["current_plan"]
        # 取出共享上下文。
        context = state["shared_context"]
        # 取出当前分支名，便于日志展示。
        selected_branch = state.get("selected_branch", "no_branch")
        # 生成 trace 文本。
        trace_message = f"executor -> 开始执行计划，当前分支：{selected_branch}"
        # 打印调试信息。
        _print_step(trace_message)
        # 调用执行器执行计划。
        observations = executor.execute(plan, context)
        # 把 observation 写回共享上下文。
        updated_context = context.model_copy(update={"latest_observations": observations})
        # 返回状态更新。
        return {
            "observations": observations,
            "shared_context": updated_context,
            "route_trace": _append_route_trace(state, trace_message),
            "status": "executed",
        }

    # 返回节点函数本身。
    return executor_node


def judge_node(state: TravelGraphState) -> TravelGraphState:
    """根据 observation 判断是否需要重规划。"""
    # 读取 observation 列表。
    observations = state.get("observations", [])
    # 迭代次数在原值基础上加一。
    iteration_count = state.get("iteration_count", 0) + 1
    # 读取最大迭代次数。
    max_iterations = state.get("max_iterations", 1)
    # 只要有任意一步失败，就认为存在失败 observation。
    any_failed = any(not item.success for item in observations)
    # 只有存在失败且还没超过最大迭代次数时才允许重规划。
    should_replan = any_failed and iteration_count < max_iterations

    # 根据是否需要重规划生成不同 trace 文本。
    trace_message = (
        f"judge -> 存在失败 observation，准备进入第 {iteration_count} 次重规划。"
        if should_replan
        else f"judge -> 当前结果可收敛，iteration_count={iteration_count}。"
    )
    # 打印调试信息。
    _print_step(trace_message)
    # 返回状态更新。
    return {
        "iteration_count": iteration_count,
        "should_replan": should_replan,
        "route_trace": _append_route_trace(state, trace_message),
        "status": "replanning" if should_replan else "judged",
    }


def route_after_judge(state: TravelGraphState) -> str:
    """根据 Judge 结果决定去 planner 还是 result。"""
    # 如果需要重规划就返回 planner，否则返回 result。
    return "planner" if state.get("should_replan", False) else "result"


def result_node(state: TravelGraphState) -> TravelGraphState:
    """汇总整个工作流结果。"""
    # 先取出 guardrail 结果。
    guardrail = state.get("guardrail")
    # 复制当前 route_trace。
    route_trace = list(state.get("route_trace", []))
    # 读取 observation。
    observations = state.get("observations", [])
    # 读取当前计划。
    current_plan = state.get("current_plan")
    # 读取知识片段。
    knowledge = state.get("retrieved_knowledge", [])
    # 读取最终分支名。
    selected_branch = state.get("selected_branch", "no_branch")

    # 如果 guardrail 明确拒绝了请求，
    # 这里直接生成一个 rejected 结果。
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

    # 如果 observation 非空，就把最后一个 observation 的结构化结果当答案主体。
    latest = observations[-1].structured_output if observations else {}
    # 生成结果节点 trace。
    trace_message = f"result -> 汇总完成，最终分支：{selected_branch}"
    # 打印调试信息。
    _print_step(trace_message)
    # 把本次结果节点也记入轨迹。
    route_trace = _append_route_trace(state, trace_message)

    # 返回完整收敛结果。
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
