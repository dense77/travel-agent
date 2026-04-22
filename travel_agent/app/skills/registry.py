"""技能注册表。"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from travel_agent.app.agents.contracts import SkillRequest, SkillResult
from travel_agent.app.skills.base import BaseSkill, LangChainToolAdapter


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> BaseSkill:
        skill = self._skills.get(name)
        if skill is None:
            raise KeyError(name)
        return skill

    def invoke(self, name: str, request: SkillRequest) -> SkillResult:
        return self.get(name).invoke(request)

    def get_tool(self, name: str) -> StructuredTool:
        return LangChainToolAdapter(self.get(name)).as_tool()
