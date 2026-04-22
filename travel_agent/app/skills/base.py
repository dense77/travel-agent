"""技能抽象基类与 Tool 适配层。"""

# 启用延迟类型注解。
from __future__ import annotations

# ABC 和 abstractmethod 用来定义抽象技能接口。
from abc import ABC, abstractmethod

# StructuredTool 用来兼容 LangChain/LangGraph 的工具形态。
from langchain_core.tools import StructuredTool
# BaseModel 用来定义 Tool 入参模型。
from pydantic import BaseModel

# 导入项目内部统一的技能请求和响应模型。
from travel_agent.app.agents.contracts import SkillRequest, SkillResult


class SkillToolInput(BaseModel):
    """LangChain Tool 层看到的入参。"""

    # session_id 用来标识会话。
    session_id: str
    # parameters 是结构化参数字典。
    parameters: dict
    # idempotency_key 用来支持幂等控制。
    idempotency_key: str


class BaseSkill(ABC):
    """项目内部技能抽象基类。"""

    # name 是技能唯一名称。
    name: str
    # description 是技能说明。
    description: str

    @abstractmethod
    def invoke(self, request: SkillRequest) -> SkillResult:
        """执行技能，并返回统一格式结果。"""


class LangChainToolAdapter:
    """把内部技能包装成 LangChain Tool 的适配器。"""

    def __init__(self, skill: BaseSkill) -> None:
        """保存一个具体技能实例。"""
        self._skill = skill

    def as_tool(self) -> StructuredTool:
        """把内部技能转换成 LangChain 可识别的 Tool。"""
        # 这里用 from_function 生成一个结构化工具对象。
        return StructuredTool.from_function(
            func=self._invoke_tool,
            name=self._skill.name,
            description=self._skill.description,
            args_schema=SkillToolInput,
        )

    def _invoke_tool(self, session_id: str, parameters: dict, idempotency_key: str) -> dict:
        """把 Tool 层参数转换成项目内部 SkillRequest。"""
        # 调用内部技能并拿到结构化 SkillResult。
        result = self._skill.invoke(
            SkillRequest(
                session_id=session_id,
                parameters=parameters,
                idempotency_key=idempotency_key,
            )
        )
        # 再把 SkillResult 转成普通字典返回给 Tool 层。
        return result.model_dump()
