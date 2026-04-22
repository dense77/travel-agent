"""基于本地 RAG 结果生成旅行建议的技能。"""

from __future__ import annotations

from typing import Any

from travel_agent.app.agents.contracts import KnowledgeChunk, SkillRequest, SkillResult
from travel_agent.app.infra.city_resolver import guess_trip_city
from travel_agent.app.skills.base import BaseSkill


class RAGTravelSkill(BaseSkill):
    """把检索到的本地知识片段整理成结构化旅行建议。"""

    name = "rag_travel"
    description = "Generate a grounded travel suggestion from retrieved local knowledge."

    def invoke(self, request: SkillRequest) -> SkillResult:
        """根据 query、约束和知识片段生成最终建议。"""
        query = str(request.parameters.get("query", "")).strip()
        constraints: dict[str, Any] = request.parameters.get("constraints", {})
        selected_city = self._guess_destination(
            query=query,
            constraints=constraints,
            selected_city=str(request.parameters.get("selected_city", "")).strip(),
        )
        selected_branch = str(request.parameters.get("selected_branch", "")).strip()
        branch_message = str(request.parameters.get("branch_message", "")).strip()
        fallback_mode = bool(request.parameters.get("fallback_mode", False))
        days = constraints.get("travel_days", 3)
        budget = constraints.get("budget", "unknown")

        knowledge_chunks = self._parse_knowledge(request.parameters.get("knowledge_chunks", []))
        highlights = self._build_highlights(knowledge_chunks)
        itinerary = self._build_itinerary(days, highlights)
        citations = [
            {
                "title": chunk.title,
                "source": chunk.source,
                "score": chunk.score,
            }
            for chunk in knowledge_chunks
        ]

        return SkillResult(
            skill_name=self.name,
            success=True,
            data={
                "destination": selected_city,
                "days": days,
                "budget": budget,
                "selected_branch": selected_branch,
                "branch_message": branch_message,
                "fallback_mode": fallback_mode,
                "highlights": highlights,
                "itinerary_outline": itinerary,
                "knowledge_used": [chunk.title for chunk in knowledge_chunks],
                "citations": citations,
                "summary": self._build_summary(
                    selected_city=selected_city,
                    days=days,
                    budget=budget,
                    fallback_mode=fallback_mode,
                    highlights=highlights,
                    knowledge_chunks=knowledge_chunks,
                ),
            },
            raw_ref=citations[0]["source"] if citations else f"local://travel/{request.idempotency_key}",
        )

    def _parse_knowledge(self, raw_chunks: Any) -> list[KnowledgeChunk]:
        """把松散字典列表规范化成 KnowledgeChunk 列表。"""
        chunks: list[KnowledgeChunk] = []
        for item in raw_chunks:
            if isinstance(item, KnowledgeChunk):
                chunks.append(item)
                continue
            if isinstance(item, dict):
                chunks.append(KnowledgeChunk.model_validate(item))
        return chunks

    def _guess_destination(self, query: str, constraints: dict[str, Any], selected_city: str) -> str:
        """优先用显式选择的城市，否则从约束或 query 猜测目的地。"""
        if selected_city:
            return selected_city
        destination = guess_trip_city(query, constraints)
        return destination if destination != "其他城市" else "待确认城市"

    def _build_highlights(self, knowledge_chunks: list[KnowledgeChunk]) -> list[str]:
        """从知识标题和内容中提炼亮点。"""
        if not knowledge_chunks:
            return ["建议先补充景点偏好、预算和出行节奏后再生成详细方案。"]

        highlights: list[str] = []
        for chunk in knowledge_chunks:
            sentence = chunk.content.split("。", 1)[0].strip()
            if sentence:
                highlights.append(sentence)

        return highlights[:3]

    def _build_itinerary(self, days: Any, highlights: list[str]) -> list[str]:
        """按天数给出简洁的行程骨架。"""
        total_days = self._safe_positive_int(days, default=3)
        itinerary: list[str] = []
        for day_index in range(total_days):
            if day_index < len(highlights):
                itinerary.append(f"Day {day_index + 1}: {highlights[day_index]}")
            else:
                itinerary.append(f"Day {day_index + 1}: 预留自由活动、返程或机动时间。")
        return itinerary

    def _build_summary(
        self,
        selected_city: str,
        days: Any,
        budget: Any,
        fallback_mode: bool,
        highlights: list[str],
        knowledge_chunks: list[KnowledgeChunk],
    ) -> str:
        """拼装一段带知识依据的结果摘要。"""
        mode = "fallback" if fallback_mode else "grounded"
        summary = (
            f"{selected_city} {days} 天行程建议已生成，预算参考为 {budget}，"
            f"当前模式为 {mode}。"
        )

        if highlights:
            summary += f" 重点建议包括：{'；'.join(highlights[:2])}。"
        if knowledge_chunks:
            summary += f" 共引用 {len(knowledge_chunks)} 条本地知识。"
        else:
            summary += " 当前未命中知识库内容，建议继续补充本地旅行资料。"
        return summary

    def _safe_positive_int(self, value: Any, default: int) -> int:
        """把输入转成正整数；异常时返回默认值。"""
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default
