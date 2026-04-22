"""为规划层提供预算和节奏基线的技能。"""

from __future__ import annotations

from typing import Any

from travel_agent.app.agents.contracts import KnowledgeChunk, SkillRequest, SkillResult
from travel_agent.app.infra.city_resolver import guess_trip_city
from travel_agent.app.skills.base import BaseSkill


class PlanningSupportSkill(BaseSkill):
    """输出预算基线和规划提示，供候选方案生成阶段使用。"""

    name = "planning_support"
    description = "Estimate travel budget baseline and planning notes for candidate generation."

    def invoke(self, request: SkillRequest) -> SkillResult:
        """根据约束和知识片段生成规划辅助信息。"""
        query = str(request.parameters.get("query", "")).strip()
        constraints: dict[str, Any] = request.parameters.get("constraints", {})
        travel_days = self._safe_positive_int(constraints.get("travel_days"), default=3)
        destination_city = guess_trip_city(query, constraints)
        preference_tags = list(request.parameters.get("preference_tags", []))
        knowledge_chunks = self._parse_knowledge(request.parameters.get("knowledge_chunks", []))

        city_multiplier = {
            "上海": 1.18,
            "北京": 1.12,
            "杭州": 1.0,
            "深圳": 1.15,
            "广州": 1.02,
        }.get(destination_city, 1.0)

        base_breakdown = {
            "transport": round(160.0 * travel_days * city_multiplier, 2),
            "hotel": round(240.0 * travel_days * city_multiplier, 2),
            "food": round(110.0 * travel_days * city_multiplier, 2),
            "tickets": round(90.0 * travel_days, 2),
            "buffer": round(80.0 * city_multiplier, 2),
        }

        if "亲子" in preference_tags:
            base_breakdown["tickets"] = round(base_breakdown["tickets"] * 1.15, 2)
        if "特种兵" in preference_tags or "高效率" in preference_tags:
            base_breakdown["hotel"] = round(base_breakdown["hotel"] * 0.9, 2)

        planning_notes = self._build_planning_notes(destination_city, knowledge_chunks, travel_days, preference_tags)
        total_estimate = round(sum(base_breakdown.values()), 2)

        return SkillResult(
            skill_name=self.name,
            success=True,
            data={
                "destination_city": destination_city,
                "travel_days": travel_days,
                "budget_breakdown": base_breakdown,
                "total_estimate": total_estimate,
                "planning_notes": planning_notes,
            },
            raw_ref=f"skill://planning_support/{request.idempotency_key}",
        )

    def _parse_knowledge(self, raw_chunks: Any) -> list[KnowledgeChunk]:
        """把松散知识对象转成统一模型。"""
        chunks: list[KnowledgeChunk] = []
        for item in raw_chunks:
            if isinstance(item, KnowledgeChunk):
                chunks.append(item)
                continue
            if isinstance(item, dict):
                chunks.append(KnowledgeChunk.model_validate(item))
        return chunks

    def _build_planning_notes(
        self,
        destination_city: str,
        knowledge_chunks: list[KnowledgeChunk],
        travel_days: int,
        preference_tags: list[str],
    ) -> list[str]:
        """生成规划提示。"""
        notes: list[str] = []
        if destination_city and destination_city != "其他城市":
            notes.append(f"{destination_city} 建议至少预留 {max(travel_days, 2)} 天，避免过度赶路。")
        if preference_tags:
            notes.append(f"当前会优先考虑这些偏好：{', '.join(preference_tags[:3])}。")
        for chunk in knowledge_chunks[:2]:
            sentence = chunk.content.split("。", 1)[0].strip()
            if sentence:
                notes.append(sentence)
        if not notes:
            notes.append("当前本地知识较少，建议把交通、住宿和核心景点拆开做预算。")
        return notes[:4]

    def _safe_positive_int(self, value: Any, default: int) -> int:
        """把输入转成正整数。"""
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default
