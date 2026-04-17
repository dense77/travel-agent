"""作用：
- 提供技能注册和按名称查找的能力。

约定：
- 技能名称必须唯一；后注册同名技能会覆盖旧技能。
- 执行器通过 `get_tool` 获取可调用对象，而不是直接持有技能实例。
"""

from __future__ import annotations

from langchain_core.tools import StructuredTool

from travel_agent.app.skills.base import BaseSkill, LangChainToolAdapter


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        # 当前实现允许覆盖注册，便于开发阶段替换 mock 技能。
        self._skills[skill.name] = skill

    def get(self, name: str) -> BaseSkill:
        skill = self._skills.get(name)
        if skill is None:
            raise KeyError(name)
        return skill

    def get_tool(self, name: str) -> StructuredTool:
        # 对外统一暴露 Tool 形态，隐藏适配细节。
        return LangChainToolAdapter(self.get(name)).as_tool()
