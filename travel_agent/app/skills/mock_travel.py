"""本地 mock 旅行技能。"""

from __future__ import annotations

from typing import Any

from travel_agent.app.agents.contracts import SkillRequest, SkillResult
from travel_agent.app.skills.base import BaseSkill


class MockTravelSkill(BaseSkill):
    name = "mock_travel"
    description = "Return a deterministic mock travel suggestion for the current query."

    def invoke(self, request: SkillRequest) -> SkillResult:
        query = str(request.parameters.get("query", "")).strip()
        constraints: dict[str, Any] = request.parameters.get("constraints", {})
        selected_city = str(request.parameters.get("selected_city", "")).strip()
        selected_branch = str(request.parameters.get("selected_branch", "")).strip()
        branch_message = str(request.parameters.get("branch_message", "")).strip()
        fallback_mode = bool(request.parameters.get("fallback_mode", False))
        knowledge_chunks = request.parameters.get("knowledge_chunks", [])

        destination = self._guess_destination(query)
        days = constraints.get("travel_days", 3)
        budget = constraints.get("budget", "unknown")
        highlights = self._build_highlights(destination)
        knowledge_titles = [item.get("title", "") for item in knowledge_chunks if isinstance(item, dict)]

        return SkillResult(
            skill_name=self.name,
            success=True,
            data={
                "destination": destination,
                "days": days,
                "budget": budget,
                "selected_city": selected_city,
                "selected_branch": selected_branch,
                "branch_message": branch_message,
                "fallback_mode": fallback_mode,
                "highlights": highlights,
                "knowledge_used": knowledge_titles,
                "summary": self._build_summary(
                    destination=destination,
                    days=days,
                    budget=budget,
                    fallback_mode=fallback_mode,
                    knowledge_titles=knowledge_titles,
                ),
            },
            raw_ref=f"mock://travel/{request.idempotency_key}",
        )

    def _guess_destination(self, query: str) -> str:
        if "杭州" in query:
            return "Hangzhou"
        if "上海" in query:
            return "Shanghai"
        if "北京" in query:
            return "Beijing"
        return "target city not detected"

    def _build_highlights(self, destination: str) -> list[str]:
        if destination == "Hangzhou":
            return ["West Lake", "Lingyin Temple"]
        if destination == "Shanghai":
            return ["The Bund", "Yu Garden"]
        if destination == "Beijing":
            return ["Forbidden City", "Temple of Heaven"]
        return ["city walk", "local food"]

    def _build_summary(
        self,
        destination: str,
        days: Any,
        budget: Any,
        fallback_mode: bool,
        knowledge_titles: list[str],
    ) -> str:
        mode = "fallback" if fallback_mode else "normal"
        if knowledge_titles:
            return (
                f"Mock {mode} travel suggestion for {destination}: {days} day(s), budget {budget}, "
                f"knowledge used: {', '.join(knowledge_titles)}."
            )
        return f"Mock {mode} travel suggestion for {destination}: {days} day(s), budget {budget}."
