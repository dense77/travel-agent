"""规划器实现。"""

from __future__ import annotations

from typing import Any, Optional

from travel_agent.app.agents.contracts import (
    CandidatePlan,
    ExecutionObservation,
    ExecutionPlan,
    FollowUpQuestion,
    PlanStep,
    SharedContext,
)


class PlannerAgent:
    """面向旅行场景的轻量规划器。"""

    def __init__(self, default_tool_name: str = "rag_travel") -> None:
        """初始化规划器。"""
        self._default_tool_name = default_tool_name

    def identify_missing_info(
        self,
        intent: str,
        constraints: dict[str, Any],
        context: SharedContext,
    ) -> list[str]:
        """根据意图判断缺失信息。"""
        missing: list[str] = []
        destination_city = str(constraints.get("destination_city", "")).strip()
        budget = self._safe_float(constraints.get("budget"))
        travel_days = self._safe_positive_int(constraints.get("travel_days"))
        has_base_plan = bool(
            constraints.get("current_plan_summary")
            or constraints.get("base_plan")
            or constraints.get("existing_itinerary")
            or context.current_plan
        )

        if intent == "new_trip":
            if not destination_city:
                missing.append("destination_city")
            if travel_days is None:
                missing.append("travel_days")
            if budget is None:
                missing.append("budget")
        elif intent == "modify_trip":
            if not has_base_plan:
                missing.append("current_plan_summary")
            if not destination_city and not context.current_plan:
                missing.append("destination_city")
        elif intent == "content_recommendation":
            if not destination_city:
                missing.append("destination_city")
        elif intent == "budget_optimization":
            if budget is None:
                missing.append("budget")
            if not has_base_plan and travel_days is None:
                missing.append("travel_days")

        return missing

    def build_follow_up_questions(self, missing_fields: list[str], intent: str) -> list[FollowUpQuestion]:
        """把缺失字段转成可直接展示给用户的追问。"""
        question_bank = {
            "destination_city": FollowUpQuestion(
                field_name="destination_city",
                question="你这次主要想去哪个城市或目的地？",
                reason="没有目的地就无法生成具体景点、交通和预算建议。",
            ),
            "travel_days": FollowUpQuestion(
                field_name="travel_days",
                question="这次计划玩几天？",
                reason="天数会直接影响节奏安排、住宿晚数和预算估算。",
            ),
            "budget": FollowUpQuestion(
                field_name="budget",
                question="这次总预算大概控制在多少？",
                reason="预算是判断方案是否可执行以及是否需要回退优化的关键约束。",
            ),
            "current_plan_summary": FollowUpQuestion(
                field_name="current_plan_summary",
                question="把你现有行程的核心安排和你想改的地方告诉我，我再帮你调整。",
                reason="修改已有行程时，需要先知道原方案和修改目标。",
            ),
        }
        questions = [question_bank[field_name] for field_name in missing_fields if field_name in question_bank]
        if intent == "budget_optimization" and not questions:
            questions.append(
                FollowUpQuestion(
                    field_name="budget_goal",
                    question="你更想压缩住宿、交通，还是整体总价？",
                    reason="预算优化需要知道你优先想优化哪一类成本。",
                )
            )
        return questions

    def generate_candidates(
        self,
        context: SharedContext,
        intent: str,
        route_name: str,
        planning_constraints: dict[str, Any],
        retrieved_knowledge: list[dict[str, Any]],
        tool_observations: list[ExecutionObservation],
        fallback_mode: bool = False,
    ) -> list[CandidatePlan]:
        """根据规划约束和工具结果生成 2-3 个候选方案。"""
        destination_city = str(planning_constraints.get("destination_city", "")).strip() or "待确认城市"
        travel_days = self._safe_positive_int(planning_constraints.get("travel_days"), default=3)
        budget_limit = self._safe_float(planning_constraints.get("budget"), default=0.0)
        preference_tags = list(planning_constraints.get("preference_tags", []))
        planning_notes, baseline_breakdown = self._collect_tool_signals(tool_observations, travel_days)
        highlights = self._build_highlights(retrieved_knowledge, planning_notes, destination_city)
        templates = self._candidate_templates(intent=intent, fallback_mode=fallback_mode)

        candidates: list[CandidatePlan] = []
        for index, template in enumerate(templates, start=1):
            budget_breakdown = self._build_budget_breakdown(
                baseline_breakdown=baseline_breakdown,
                profile=template["profile"],
                fallback_mode=fallback_mode,
            )
            estimated_budget = round(sum(budget_breakdown.values()), 2)
            fit_score = self._fit_score(
                estimated_budget=estimated_budget,
                budget_limit=budget_limit,
                preference_tags=preference_tags,
                profile_tags=template["tags"],
                fallback_mode=fallback_mode,
            )
            candidates.append(
                CandidatePlan(
                    candidate_id=f"candidate_{index}",
                    title=template["title"],
                    summary=self._build_summary(
                        title=template["title"],
                        destination_city=destination_city,
                        travel_days=travel_days,
                        highlights=highlights,
                        fallback_mode=fallback_mode,
                    ),
                    route_name=route_name,
                    daily_outline=self._build_daily_outline(
                        destination_city=destination_city,
                        travel_days=travel_days,
                        highlights=highlights,
                        theme=template["theme"],
                    ),
                    highlights=self._select_highlights(highlights, template["theme"]),
                    budget_breakdown=budget_breakdown,
                    estimated_budget=estimated_budget,
                    assumptions=self._build_assumptions(
                        destination_city=destination_city,
                        budget_limit=budget_limit,
                        preference_tags=preference_tags,
                        notes=planning_notes,
                        fallback_mode=fallback_mode,
                    ),
                    fit_score=fit_score,
                )
            )

        return sorted(candidates, key=lambda item: item.fit_score, reverse=True)

    def build_execution_plan(
        self,
        context: SharedContext,
        selected_candidate: Optional[CandidatePlan],
        missing_info: list[str],
    ) -> ExecutionPlan:
        """把选中的候选方案收敛成当前执行计划快照。"""
        candidate_payload = selected_candidate.model_dump() if selected_candidate else {}
        return ExecutionPlan(
            goal=context.user_query,
            steps=[
                PlanStep(
                    step_id="review_candidate",
                    action_type="present_plan",
                    tool_name=self._default_tool_name,
                    input_payload=candidate_payload,
                    expected_output="Present the recommended travel option to the user.",
                )
            ],
            missing_info=missing_info,
            need_rag=False,
            need_replan=False,
            strategy="interactive-planning",
            iteration_index=context.current_plan.iteration_index + 1 if context.current_plan else 0,
        )

    def _candidate_templates(self, intent: str, fallback_mode: bool) -> list[dict[str, Any]]:
        """根据意图选出候选模板。"""
        if intent == "modify_trip":
            templates = [
                {"title": "保留主线微调版", "theme": "balance", "profile": "balanced", "tags": {"稳定", "微调"}},
                {"title": "压缩重排版", "theme": "compact", "profile": "budget", "tags": {"压缩", "效率"}},
            ]
        elif intent == "content_recommendation":
            templates = [
                {"title": "经典内容推荐版", "theme": "classic", "profile": "balanced", "tags": {"经典", "打卡"}},
                {"title": "兴趣偏好延展版", "theme": "interest", "profile": "quality", "tags": {"兴趣", "体验"}},
            ]
        elif intent == "budget_optimization":
            templates = [
                {"title": "预算优先版", "theme": "budget", "profile": "budget", "tags": {"省钱", "效率"}},
                {"title": "平衡优化版", "theme": "balance", "profile": "balanced", "tags": {"平衡", "实用"}},
                {"title": "体验保留版", "theme": "quality", "profile": "quality", "tags": {"体验", "重点保留"}},
            ]
        else:
            templates = [
                {"title": "经典平衡版", "theme": "classic", "profile": "balanced", "tags": {"经典", "平衡"}},
                {"title": "深度体验版", "theme": "depth", "profile": "quality", "tags": {"深度", "体验"}},
                {"title": "预算友好版", "theme": "budget", "profile": "budget", "tags": {"预算", "轻量"}},
            ]

        if fallback_mode:
            return templates[:2]
        return templates

    def _collect_tool_signals(
        self,
        tool_observations: list[ExecutionObservation],
        travel_days: int,
    ) -> tuple[list[str], dict[str, float]]:
        """从工具 observation 中提取预算基线和说明。"""
        planning_notes: list[str] = []
        baseline_breakdown = {
            "transport": 180.0 * travel_days,
            "hotel": 260.0 * travel_days,
            "food": 120.0 * travel_days,
            "tickets": 100.0 * travel_days,
            "buffer": 80.0,
        }

        for observation in tool_observations:
            if not observation.success:
                continue
            structured_output = observation.structured_output
            for note in structured_output.get("planning_notes", []):
                if isinstance(note, str) and note:
                    planning_notes.append(note)
            breakdown = structured_output.get("budget_breakdown", {})
            if isinstance(breakdown, dict):
                for field_name, field_value in breakdown.items():
                    value = self._safe_float(field_value)
                    if value is not None:
                        baseline_breakdown[field_name] = value

        return planning_notes, baseline_breakdown

    def _build_highlights(
        self,
        retrieved_knowledge: list[dict[str, Any]],
        planning_notes: list[str],
        destination_city: str,
    ) -> list[str]:
        """把知识和工具说明整理成亮点。"""
        highlights: list[str] = []
        for chunk in retrieved_knowledge:
            content = str(chunk.get("content", "")).strip()
            if content:
                highlights.append(content.split("。", 1)[0].strip())
        for note in planning_notes:
            if note not in highlights:
                highlights.append(note)
        if not highlights:
            highlights.append(f"{destination_city} 的具体玩法信息还不够，建议补充景点偏好后再细化。")
        return highlights[:4]

    def _build_budget_breakdown(
        self,
        baseline_breakdown: dict[str, float],
        profile: str,
        fallback_mode: bool,
    ) -> dict[str, float]:
        """按方案画像调整预算拆分。"""
        multiplier_by_profile = {
            "budget": 0.82,
            "balanced": 1.0,
            "quality": 1.22,
        }
        multiplier = multiplier_by_profile.get(profile, 1.0)
        if fallback_mode:
            multiplier *= 0.88
        return {
            field_name: round(value * multiplier, 2)
            for field_name, value in baseline_breakdown.items()
        }

    def _fit_score(
        self,
        estimated_budget: float,
        budget_limit: float,
        preference_tags: list[str],
        profile_tags: set[str],
        fallback_mode: bool,
    ) -> float:
        """给候选方案打一个轻量适配度分数。"""
        score = 0.6
        if budget_limit > 0:
            gap_ratio = abs(estimated_budget - budget_limit) / max(budget_limit, 1.0)
            score += max(0.0, 0.25 - gap_ratio * 0.2)
        if preference_tags and any(tag in "".join(profile_tags) for tag in preference_tags):
            score += 0.08
        if fallback_mode:
            score += 0.03
        return round(min(score, 0.99), 3)

    def _build_summary(
        self,
        title: str,
        destination_city: str,
        travel_days: int,
        highlights: list[str],
        fallback_mode: bool,
    ) -> str:
        """生成候选方案摘要。"""
        mode = "回退优化" if fallback_mode else "标准规划"
        lead = highlights[0] if highlights else f"围绕 {destination_city} 做基础行程安排"
        return f"{title}：面向 {destination_city} 的 {travel_days} 天方案，当前为{mode}模式，重点围绕“{lead}”展开。"

    def _build_daily_outline(
        self,
        destination_city: str,
        travel_days: int,
        highlights: list[str],
        theme: str,
    ) -> list[str]:
        """生成按天的行程骨架。"""
        theme_suffix = {
            "classic": "优先串联经典地标和高确定性路线。",
            "depth": "适当拉长停留时间，留出深度体验窗口。",
            "budget": "尽量压缩通勤和门票成本。",
            "balance": "在效率和体验之间取中位。",
            "compact": "减少跨区折返，提高单位时间收益。",
            "interest": "围绕用户兴趣做主题化安排。",
            "quality": "保留体验上限更高的关键节点。",
        }.get(theme, "保持整体节奏稳定。")
        outline: list[str] = []
        for index in range(travel_days):
            highlight = highlights[index % len(highlights)] if highlights else f"{destination_city} 城市漫游"
            outline.append(f"Day {index + 1}: {highlight} {theme_suffix}")
        return outline

    def _select_highlights(self, highlights: list[str], theme: str) -> list[str]:
        """按主题挑选亮点。"""
        if theme in {"budget", "compact"}:
            return highlights[:2]
        return highlights[:3]

    def _build_assumptions(
        self,
        destination_city: str,
        budget_limit: float,
        preference_tags: list[str],
        notes: list[str],
        fallback_mode: bool,
    ) -> list[str]:
        """生成候选方案使用的前提假设。"""
        assumptions = [f"默认目的地为 {destination_city}。"]
        if budget_limit > 0:
            assumptions.append(f"以总预算 {round(budget_limit, 2)} 为主要约束。")
        if preference_tags:
            assumptions.append(f"优先考虑这些偏好：{', '.join(preference_tags[:3])}。")
        if notes:
            assumptions.append(f"参考了 {min(len(notes), 3)} 条工具侧规划提示。")
        if fallback_mode:
            assumptions.append("已启用更保守的预算回退策略。")
        return assumptions

    def _safe_positive_int(self, value: Any, default: Optional[int] = None) -> Optional[int]:
        """把输入转成正整数。"""
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        if parsed <= 0:
            return default
        return parsed

    def _safe_float(self, value: Any, default: Optional[float] = None) -> Optional[float]:
        """把输入转成浮点数。"""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
