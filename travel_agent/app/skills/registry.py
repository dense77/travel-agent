"""技能注册表。"""

# 启用延迟类型注解。
from __future__ import annotations

# StructuredTool 是 LangChain 工具类型。
from langchain_core.tools import StructuredTool

# 导入技能请求和结果模型。
from travel_agent.app.agents.contracts import SkillRequest, SkillResult
# 导入技能基类和 Tool 适配器。
from travel_agent.app.skills.base import BaseSkill, LangChainToolAdapter


class SkillRegistry:
    """按名称管理技能实例。"""

    def __init__(self) -> None:
        """初始化一个空技能表。"""
        # 这里用字典按技能名索引技能实例。
        self._skills: dict[str, BaseSkill] = {}

    def register(self, skill: BaseSkill) -> None:
        """注册一个技能实例。"""
        # 后注册的同名技能会覆盖旧技能，
        # 这对开发阶段替换 mock 技能很方便。
        self._skills[skill.name] = skill

    def get(self, name: str) -> BaseSkill:
        """按名称获取技能。"""
        # 先尝试从字典里读出技能。
        skill = self._skills.get(name)
        # 如果找不到，就明确抛出 KeyError。
        if skill is None:
            raise KeyError(name)
        # 找到则返回技能实例。
        return skill

    def invoke(self, name: str, request: SkillRequest) -> SkillResult:
        """按名称直接调用技能。"""
        # 先取到技能，再把 request 交给它执行。
        return self.get(name).invoke(request)

    def get_tool(self, name: str) -> StructuredTool:
        """按名称获取 Tool 形态的技能。"""
        # 先拿到内部技能，再包装成 Tool。
        return LangChainToolAdapter(self.get(name)).as_tool()
