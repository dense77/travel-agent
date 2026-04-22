"""LangGraph 节点定义。"""

from __future__ import annotations

import re
from typing import Any, Optional

from travel_agent.app.agents.contracts import (
    ExecutionObservation,
    ExecutionPlan,
    GuardrailDecision,
    IntentDecision,
    PlanStep,
    RiskCheckResult,
    RouteDecision,
    SharedContext,
)
from travel_agent.app.agents.executor.agent import ExecutorAgent
from travel_agent.app.agents.planner.agent import PlannerAgent
from travel_agent.app.graph.state import TravelGraphState
from travel_agent.app.infra.city_resolver import guess_trip_city
from travel_agent.app.rag.service import BaseRAGService


INTENT_KEYWORDS = {
    "modify_trip": ("修改", "调整", "改一下", "优化现有", "改行程", "换酒店", "删掉", "增加"),
    "budget_optimization": ("预算优化", "省钱", "压缩预算", "便宜点", "控制预算", "预算不够", "超预算"),
    "content_recommendation": ("推荐", "有什么好玩", "玩什么", "吃什么", "去哪", "景点", "内容推荐"),
}

PREFERENCE_KEYWORDS = (
    "美食",
    "拍照",
    "亲子",
    "情侣",
    "博物馆",
    "徒步",
    "夜景",
    "购物",
    "特种兵",
    "高效率",
    "慢节奏",
)


def _append_route_trace(state: TravelGraphState, message: str) -> list[str]:
    """在 route_trace 后面追加一条新消息。"""
    route_trace = list(state.get("route_trace", []))
    route_trace.append(message)
    return route_trace


def _print_step(message: str) -> None:
    """把节点过程打印到控制台。"""
    print(f"[LangGraph Demo] {message}")


def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """把输入转成浮点数。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_positive_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    """把输入转成正整数。"""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


def _extract_budget(query: str) -> Optional[float]:
    """从 query 中提取预算。"""
    match = re.search(r"预算\s*([0-9]+(?:\.[0-9]+)?)", query)
    if match:
        return float(match.group(1))
    match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*元", query)
    if match:
        return float(match.group(1))
    return None


def _extract_travel_days(query: str) -> Optional[int]:
    """从 query 中提取天数。"""
    for pattern in (r"([0-9]+)\s*天", r"([一二三四五六七八九十两]+)天"):
        match = re.search(pattern, query)
        if not match:
            continue
        raw_value = match.group(1)
        if raw_value.isdigit():
            return int(raw_value)
        cn_mapping = {
            "一": 1,
            "二": 2,
            "两": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
        }
        total = 0
        if raw_value == "十":
            return 10
        for char in raw_value:
            total += cn_mapping.get(char, 0)
        if total > 0:
            return total
    return None


def _extract_preference_tags(query: str, constraints: dict[str, Any]) -> list[str]:
    """从 query 和约束中提取偏好标签。"""
    tags = set()
    combined_text = f"{query} {' '.join(str(value) for value in constraints.values())}"
    for tag in PREFERENCE_KEYWORDS:
        if tag in combined_text:
            tags.add(tag)

    raw_preferences = constraints.get("preferences")
    if isinstance(raw_preferences, list):
        for item in raw_preferences:
            if item:
                tags.add(str(item))
    elif isinstance(raw_preferences, str) and raw_preferences.strip():
        for part in re.split(r"[，,、/\s]+", raw_preferences):
            if part:
                tags.add(part)

    return list(tags)


def _select_intent(query: str, context: SharedContext) -> tuple[str, str, float]:
    """用规则识别当前请求主意图。"""
    stripped_query = query.strip()
    for intent, keywords in INTENT_KEYWORDS.items():
        if any(keyword in stripped_query for keyword in keywords):
            return intent, f"命中关键词：{next(keyword for keyword in keywords if keyword in stripped_query)}", 0.85

    if context.current_plan:
        return "modify_trip", "当前上下文里已存在计划，优先判定为修改已有行程。", 0.68

    return "new_trip", "未命中修改/推荐/预算优化关键词，默认按新建行程处理。", 0.6


def _base_plan_available(constraints: dict[str, Any], context: SharedContext) -> bool:
    """判断是否已经有可供修改的基础方案。"""
    return bool(
        constraints.get("current_plan_summary")
        or constraints.get("base_plan")
        or constraints.get("existing_itinerary")
        or context.current_plan
    )


def _find_selected_candidate(state: TravelGraphState) -> Optional[dict[str, Any]]:
    """根据 selected_candidate_id 找到推荐方案。"""
    selected_candidate_id = state.get("selected_candidate_id", "")
    for candidate in state.get("candidate_plans", []):
        if candidate.candidate_id == selected_candidate_id:
            return candidate.model_dump()
    return None


def guardrail_node(state: TravelGraphState) -> TravelGraphState:
    """对请求做基础合法性校验。"""
    query = state["user_query"].strip()
    constraints = state["shared_context"].hard_constraints
    reasons: list[str] = []

    if not query:
        reasons.append("user_query is empty")

    travel_days = constraints.get("travel_days")
    if travel_days is not None and _safe_positive_int(travel_days) is None:
        reasons.append("travel_days must be positive")

    budget = constraints.get("budget")
    if budget is not None:
        parsed_budget = _safe_float(budget)
        if parsed_budget is None or parsed_budget < 0:
            reasons.append("budget must be a non-negative number")

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
    """根据 guardrail 结果决定下一跳。"""
    return "intent_recognition" if state["guardrail"].allowed else "result"


def intent_recognition_node(state: TravelGraphState) -> TravelGraphState:
    """识别本次请求的主意图。"""
    intent, reason, confidence = _select_intent(state["user_query"], state["shared_context"])
    trace_message = f"intent_recognition -> 识别意图为 {intent}"
    _print_step(trace_message)

    return {
        "intent_decision": IntentDecision(intent=intent, reason=reason, confidence=confidence),
        "route_trace": _append_route_trace(state, trace_message),
        "status": "intent_identified",
    }


def constraint_extraction_node(state: TravelGraphState) -> TravelGraphState:
    """提取并归一化约束信息。"""
    context = state["shared_context"]
    extracted_constraints = dict(context.hard_constraints)
    query = state["user_query"]

    if "budget" not in extracted_constraints:
        extracted_budget = _extract_budget(query)
        if extracted_budget is not None:
            extracted_constraints["budget"] = extracted_budget

    if "travel_days" not in extracted_constraints:
        extracted_days = _extract_travel_days(query)
        if extracted_days is not None:
            extracted_constraints["travel_days"] = extracted_days

    selected_city = guess_trip_city(query, extracted_constraints)
    if selected_city != "其他城市":
        extracted_constraints["destination_city"] = selected_city

    preference_tags = _extract_preference_tags(query, extracted_constraints)
    if preference_tags:
        extracted_constraints["preference_tags"] = preference_tags

    if state["intent_decision"].intent == "modify_trip" and "modification_request" not in extracted_constraints:
        extracted_constraints["modification_request"] = query

    updated_context = context.model_copy(update={"hard_constraints": extracted_constraints})
    trace_message = f"constraint_extraction -> 已提取 {len(extracted_constraints)} 项约束"
    _print_step(trace_message)
    return {
        "shared_context": updated_context,
        "extracted_constraints": extracted_constraints,
        "route_trace": _append_route_trace(state, trace_message),
        "status": "constraints_extracted",
    }


def build_missing_info_node(planner: PlannerAgent):
    """构造缺失信息判断节点。"""

    def missing_info_node(state: TravelGraphState) -> TravelGraphState:
        """判断是否需要追问。"""
        missing_info = planner.identify_missing_info(
            intent=state["intent_decision"].intent,
            constraints=state["extracted_constraints"],
            context=state["shared_context"],
        )
        interaction_action = "ask_user" if missing_info else "continue_planning"
        trace_message = (
            f"missing_info_check -> 缺失信息: {', '.join(missing_info)}"
            if missing_info
            else "missing_info_check -> 关键信息齐全，进入规划层。"
        )
        _print_step(trace_message)
        return {
            "missing_info": missing_info,
            "interaction_action": interaction_action,
            "route_trace": _append_route_trace(state, trace_message),
            "status": "needs_follow_up" if missing_info else "ready_for_planning",
        }

    return missing_info_node


def route_after_missing_info(state: TravelGraphState) -> str:
    """根据是否缺失信息决定下一跳。"""
    return "follow_up" if state.get("interaction_action") == "ask_user" else "planning_router"


def build_follow_up_node(planner: PlannerAgent):
    """构造追问补全节点。"""

    def follow_up_node(state: TravelGraphState) -> TravelGraphState:
        """生成追问问题。"""
        questions = planner.build_follow_up_questions(
            missing_fields=state.get("missing_info", []),
            intent=state["intent_decision"].intent,
        )
        trace_message = f"follow_up -> 已生成 {len(questions)} 个追问问题"
        _print_step(trace_message)
        return {
            "follow_up_questions": questions,
            "route_trace": _append_route_trace(state, trace_message),
            "status": "needs_user_input",
        }

    return follow_up_node


def planning_router_node(state: TravelGraphState) -> TravelGraphState:
    """根据用户意图选择规划路线。"""
    intent = state["intent_decision"].intent
    route_mapping = {
        "new_trip": ("plan_new_trip", "新建行程，需要从零生成候选方案。"),
        "modify_trip": ("adjust_existing_trip", "基于已有行程做修改和重排。"),
        "content_recommendation": ("recommend_trip_content", "重点输出景点/玩法内容推荐。"),
        "budget_optimization": ("optimize_budget", "优先围绕预算约束做压缩和优化。"),
    }
    route_name, reason = route_mapping[intent]
    trace_message = f"planning_router -> 路由到 {route_name}"
    _print_step(trace_message)
    return {
        "route_decision": RouteDecision(route_name=route_name, reason=reason),
        "route_trace": _append_route_trace(state, trace_message),
        "status": "route_selected",
    }


def constraint_analysis_node(state: TravelGraphState) -> TravelGraphState:
    """分析约束并生成规划层条件。"""
    extracted_constraints = dict(state["extracted_constraints"])
    planning_constraints = {
        "intent": state["intent_decision"].intent,
        "route_name": state["route_decision"].route_name,
        "destination_city": extracted_constraints.get("destination_city", ""),
        "travel_days": extracted_constraints.get("travel_days"),
        "budget": extracted_constraints.get("budget"),
        "preference_tags": list(extracted_constraints.get("preference_tags", [])),
        "modification_request": extracted_constraints.get("modification_request", ""),
        "base_plan_available": _base_plan_available(extracted_constraints, state["shared_context"]),
        "selected_city": extracted_constraints.get("destination_city", ""),
    }
    trace_message = "constraint_analysis -> 已生成规划层约束条件"
    _print_step(trace_message)
    return {
        "planning_constraints": planning_constraints,
        "route_trace": _append_route_trace(state, trace_message),
        "status": "planning_constraints_ready",
    }


def build_tool_collection_node(rag_service: BaseRAGService, executor: ExecutorAgent):
    """构造工具收集节点。"""

    def tool_collection_node(state: TravelGraphState) -> TravelGraphState:
        """调用 RAG 和 Skill 收集规划信息。"""
        context = state["shared_context"].model_copy(update={"hard_constraints": state["planning_constraints"]})
        knowledge_chunks = rag_service.retrieve(state["user_query"], context)
        rag_observation = ExecutionObservation(
            step_id="rag_retrieve",
            source="rag",
            success=True,
            structured_output={
                "count": len(knowledge_chunks),
                "chunks": [item.model_dump() for item in knowledge_chunks],
            },
            evidence_refs=[item.source for item in knowledge_chunks[:3]],
        )
        tool_plan = ExecutionPlan(
            goal="collect planning signals",
            steps=[
                PlanStep(
                    step_id="planning_support",
                    action_type="skill_invoke",
                    tool_name="planning_support",
                    input_payload={
                        "query": state["user_query"],
                        "constraints": state["planning_constraints"],
                        "preference_tags": state["planning_constraints"].get("preference_tags", []),
                        "knowledge_chunks": [item.model_dump() for item in knowledge_chunks],
                        "intent": state["intent_decision"].intent,
                    },
                    expected_output="Budget baseline and planning notes for planning layer.",
                )
            ],
            missing_info=[],
            need_rag=False,
            need_replan=False,
            strategy="planning-tool-collection",
            iteration_index=0,
        )
        tool_observations = [rag_observation] + executor.execute(tool_plan, context)
        updated_context = context.model_copy(
            update={
                "retrieved_knowledge": knowledge_chunks,
                "latest_observations": tool_observations,
            }
        )
        trace_message = (
            f"tool_collection -> 已完成 RAG 检索并调用 Skill，获得 {len(tool_observations)} 条工具结果"
        )
        _print_step(trace_message)
        return {
            "shared_context": updated_context,
            "retrieved_knowledge": knowledge_chunks,
            "tool_observations": tool_observations,
            "route_trace": _append_route_trace(state, trace_message),
            "status": "tool_info_collected",
        }

    return tool_collection_node


def build_candidate_generation_node(planner: PlannerAgent):
    """构造候选方案生成节点。"""

    def candidate_generation_node(state: TravelGraphState) -> TravelGraphState:
        """生成 2-3 个候选方案。"""
        fallback_mode = state.get("candidate_retry_count", 0) > 0
        candidates = planner.generate_candidates(
            context=state["shared_context"],
            intent=state["intent_decision"].intent,
            route_name=state["route_decision"].route_name,
            planning_constraints=state["planning_constraints"],
            retrieved_knowledge=[item.model_dump() for item in state.get("retrieved_knowledge", [])],
            tool_observations=state.get("tool_observations", []),
            fallback_mode=fallback_mode,
        )
        selected_candidate = candidates[0] if candidates else None
        current_plan = planner.build_execution_plan(
            context=state["shared_context"],
            selected_candidate=selected_candidate,
            missing_info=state.get("missing_info", []),
        )
        updated_context = state["shared_context"].model_copy(update={"current_plan": current_plan})
        trace_message = (
            f"candidate_generation -> 已生成 {len(candidates)} 个候选方案"
            if candidates
            else "candidate_generation -> 未生成有效候选方案"
        )
        _print_step(trace_message)
        return {
            "shared_context": updated_context,
            "current_plan": current_plan,
            "candidate_plans": candidates,
            "selected_candidate_id": selected_candidate.candidate_id if selected_candidate else "",
            "route_trace": _append_route_trace(state, trace_message),
            "status": "candidates_generated",
        }

    return candidate_generation_node


def build_risk_check_node(planner: PlannerAgent):
    """构造风险检查节点。"""

    def risk_check_node(state: TravelGraphState) -> TravelGraphState:
        """检查候选方案是否满足约束和预算。"""
        planning_constraints = state["planning_constraints"]
        budget_limit = _safe_float(planning_constraints.get("budget"))
        travel_days = _safe_positive_int(planning_constraints.get("travel_days"))
        retry_count = state.get("candidate_retry_count", 0)

        risk_checks: list[RiskCheckResult] = []
        passing_candidates = []
        budget_gap_index: dict[str, float] = {}
        for candidate in state.get("candidate_plans", []):
            issues: list[str] = []
            estimated_budget = candidate.estimated_budget

            if budget_limit is not None and estimated_budget > budget_limit:
                issues.append(f"估算预算 {estimated_budget} 超过上限 {budget_limit}")
            if travel_days is not None and len(candidate.daily_outline) != travel_days:
                issues.append("日程天数与用户要求不一致")

            passed = not issues
            budget_gap = 0.0
            if budget_limit is not None:
                budget_gap = round(estimated_budget - budget_limit, 2)
            risk_checks.append(
                RiskCheckResult(
                    candidate_id=candidate.candidate_id,
                    passed=passed,
                    issues=issues,
                    estimated_budget=estimated_budget,
                    budget_limit=budget_limit,
                    budget_gap=budget_gap,
                )
            )
            budget_gap_index[candidate.candidate_id] = abs(budget_gap)
            if passed:
                passing_candidates.append(candidate)

        candidate_retry_needed = not passing_candidates and retry_count < 1 and bool(state.get("candidate_plans"))
        if passing_candidates:
            selected_candidate = sorted(passing_candidates, key=lambda item: item.fit_score, reverse=True)[0]
        else:
            selected_candidate = min(
                state.get("candidate_plans", []),
                key=lambda item: (budget_gap_index.get(item.candidate_id, 0.0), -item.fit_score),
                default=None,
            )

        current_plan = planner.build_execution_plan(
            context=state["shared_context"],
            selected_candidate=selected_candidate,
            missing_info=state.get("missing_info", []),
        )
        updated_context = state["shared_context"].model_copy(update={"current_plan": current_plan})
        trace_message = (
            "risk_check -> 所有候选方案均未通过预算检查，进入一次回退生成。"
            if candidate_retry_needed
            else "risk_check -> 已完成约束与预算检查。"
        )
        _print_step(trace_message)
        return {
            "shared_context": updated_context,
            "current_plan": current_plan,
            "risk_checks": risk_checks,
            "selected_candidate_id": selected_candidate.candidate_id if selected_candidate else "",
            "candidate_retry_count": retry_count + 1 if candidate_retry_needed else retry_count,
            "candidate_retry_needed": candidate_retry_needed,
            "route_trace": _append_route_trace(state, trace_message),
            "status": "retry_candidate_generation" if candidate_retry_needed else "risk_checked",
        }

    return risk_check_node


def route_after_risk_check(state: TravelGraphState) -> str:
    """根据风险检查结果决定是否回退。"""
    return "candidate_generation" if state.get("candidate_retry_needed", False) else "result"


def result_node(state: TravelGraphState) -> TravelGraphState:
    """汇总整个工作流结果。"""
    guardrail = state.get("guardrail")
    route_trace = list(state.get("route_trace", []))
    selected_candidate = _find_selected_candidate(state)

    if guardrail and not guardrail.allowed:
        trace_message = "result -> Guardrail 拒绝，本次请求直接结束。"
        _print_step(trace_message)
        route_trace = _append_route_trace(state, trace_message)
        return {
            "final_result": {
                "status": "rejected",
                "error": state.get("error_message", ""),
                "route_trace": route_trace,
            },
            "route_trace": route_trace,
            "status": "rejected",
        }

    if state.get("interaction_action") == "ask_user":
        trace_message = "result -> 信息不足，返回追问问题等待用户补全。"
        _print_step(trace_message)
        route_trace = _append_route_trace(state, trace_message)
        return {
            "final_result": {
                "status": "needs_user_input",
                "intent": state["intent_decision"].model_dump() if state.get("intent_decision") else {},
                "constraints": state.get("extracted_constraints", {}),
                "missing_info": state.get("missing_info", []),
                "follow_up_questions": [item.model_dump() for item in state.get("follow_up_questions", [])],
                "route_trace": route_trace,
                "next_action": "等待用户补充信息后重新进入规划。",
            },
            "route_trace": route_trace,
            "status": "needs_user_input",
        }

    risk_checks = state.get("risk_checks", [])
    any_passed = any(item.passed for item in risk_checks)
    final_status = "finished" if any_passed else "finished_with_risk"
    trace_message = f"result -> 已输出最终方案，状态为 {final_status}"
    _print_step(trace_message)
    route_trace = _append_route_trace(state, trace_message)

    return {
        "final_result": {
            "status": final_status,
            "intent": state["intent_decision"].model_dump() if state.get("intent_decision") else {},
            "route": state["route_decision"].model_dump() if state.get("route_decision") else {},
            "constraints": state.get("planning_constraints", {}),
            "candidate_plans": [item.model_dump() for item in state.get("candidate_plans", [])],
            "recommended_plan": selected_candidate or {},
            "risk_checks": [item.model_dump() for item in risk_checks],
            "knowledge": [item.model_dump() for item in state.get("retrieved_knowledge", [])],
            "tool_observations": [item.model_dump() for item in state.get("tool_observations", [])],
            "route_trace": route_trace,
            "next_action": "可以直接展示推荐方案，并继续接受用户的修改意见。",
        },
        "observations": state.get("tool_observations", []),
        "route_trace": route_trace,
        "status": final_status,
    }
