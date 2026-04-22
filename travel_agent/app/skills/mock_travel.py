"""本地 mock 旅行技能。"""

# 启用延迟类型注解。
from __future__ import annotations

# Any 用来描述宽松约束值类型。
from typing import Any

# 导入统一的技能请求与响应模型。
from travel_agent.app.agents.contracts import SkillRequest, SkillResult
# 导入技能基类。
from travel_agent.app.skills.base import BaseSkill


class MockTravelSkill(BaseSkill):
    """一个确定性返回结果的本地演示技能。"""

    # 技能名称。
    name = "mock_travel"
    # 技能描述。
    description = "Return a deterministic mock travel suggestion for the current query."

    def invoke(self, request: SkillRequest) -> SkillResult:
        """根据请求参数生成稳定可复现的 mock 结果。"""
        # 从参数里读 query。
        query = str(request.parameters.get("query", "")).strip()
        # 从参数里读结构化约束。
        constraints: dict[str, Any] = request.parameters.get("constraints", {})
        # 从参数里读城市分支信息。
        selected_city = str(request.parameters.get("selected_city", "")).strip()
        selected_branch = str(request.parameters.get("selected_branch", "")).strip()
        branch_message = str(request.parameters.get("branch_message", "")).strip()
        # 读取是否处于回退模式。
        fallback_mode = bool(request.parameters.get("fallback_mode", False))
        # 读取可能的知识片段。
        knowledge_chunks = request.parameters.get("knowledge_chunks", [])

        # 根据 query 猜测目的地。
        destination = self._guess_destination(query)
        # 尝试从约束中读取出行天数。
        days = constraints.get("travel_days", 3)
        # 尝试从约束中读取预算。
        budget = constraints.get("budget", "unknown")
        # 根据目的地生成亮点列表。
        highlights = self._build_highlights(destination)
        # 从知识片段里抽出 title，方便展示“用了哪些知识”。
        knowledge_titles = [item.get("title", "") for item in knowledge_chunks if isinstance(item, dict)]

        # 返回统一结构的 SkillResult。
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
        """用最简单的关键词匹配推断城市。"""
        if "杭州" in query:
            return "Hangzhou"
        if "上海" in query:
            return "Shanghai"
        if "北京" in query:
            return "Beijing"
        return "target city not detected"

    def _build_highlights(self, destination: str) -> list[str]:
        """根据目的地返回固定亮点。"""
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
        """拼接一段可读性较强的总结文本。"""
        # 先根据 fallback_mode 决定模式文本。
        mode = "fallback" if fallback_mode else "normal"
        # 如果用到了知识片段，就把知识标题也拼进总结里。
        if knowledge_titles:
            return (
                f"Mock {mode} travel suggestion for {destination}: {days} day(s), budget {budget}, "
                f"knowledge used: {', '.join(knowledge_titles)}."
            )
        # 否则返回不带知识信息的总结。
        return f"Mock {mode} travel suggestion for {destination}: {days} day(s), budget {budget}."
