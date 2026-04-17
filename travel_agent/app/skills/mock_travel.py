"""作用：
- 提供一个确定性的 mock 旅游技能，用来打通最小可运行闭环。

约定：
- 这个技能不访问外部 API，也不做真实路线计算。
- 返回值必须稳定可复现，方便验证接口、工作流和存储是否连通。
"""

from __future__ import annotations

from typing import Any

from travel_agent.app.agents.contracts import SkillRequest, SkillResult
from travel_agent.app.skills.base import BaseSkill


class MockTravelSkill(BaseSkill):
    name = "mock_travel"
    description = "Return a deterministic mock travel suggestion for the current query."

    def invoke(self, request: SkillRequest) -> SkillResult:
        # 最小闭环里约定：query 和 constraints 都从 `parameters` 中读取。
        query = str(request.parameters.get("query", "")).strip()
        constraints: dict[str, Any] = request.parameters.get("constraints", {})
        selected_city = str(request.parameters.get("selected_city", "")).strip()
        selected_branch = str(request.parameters.get("selected_branch", "")).strip()
        branch_message = str(request.parameters.get("branch_message", "")).strip()

        destination = self._guess_destination(query)
        days = constraints.get("travel_days", 3)
        budget = constraints.get("budget", "unknown")

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
                "highlights": self._build_highlights(destination),
                "summary": f"Mock travel suggestion for {destination}: {days} day(s), budget {budget}.",
            },
            raw_ref=f"mock://travel/{request.idempotency_key}",
        )

    def _guess_destination(self, query: str) -> str:
        # 当前只是最简单的关键词匹配，目的是给前后链路提供稳定输出。
        if "杭州" in query:
            return "Hangzhou"
        if "上海" in query:
            return "Shanghai"
        if "北京" in query:
            return "Beijing"
        return "target city not detected"

    def _build_highlights(self, destination: str) -> list[str]:
        # 亮点列表是固定映射，不依赖实时数据。
        if destination == "Hangzhou":
            return ["West Lake", "Lingyin Temple"]
        if destination == "Shanghai":
            return ["The Bund", "Yu Garden"]
        if destination == "Beijing":
            return ["Forbidden City", "Temple of Heaven"]
        return ["city walk", "local food"]
