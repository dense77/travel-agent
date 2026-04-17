"""作用：
- 定义技能抽象基类，以及把技能适配成 LangChain Tool 的桥接层。

约定：
- 项目内部技能统一实现 `BaseSkill.invoke`。
- 执行器实际取到的是 `StructuredTool`，因此这里负责两套接口之间的转换。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.tools import StructuredTool
from pydantic import BaseModel

from travel_agent.app.agents.contracts import SkillRequest, SkillResult


class SkillToolInput(BaseModel):
    # 这是 LangChain Tool 层看到的入参结构，字段名需要和执行器调用一致。
    session_id: str
    parameters: dict
    idempotency_key: str


class BaseSkill(ABC):
    name: str
    description: str

    @abstractmethod
    def invoke(self, request: SkillRequest) -> SkillResult:
        # 所有具体技能都必须返回统一的 `SkillResult`，避免执行层分支处理。
        raise NotImplementedError


class LangChainToolAdapter:
    def __init__(self, skill: BaseSkill) -> None:
        self._skill = skill

    def as_tool(self) -> StructuredTool:
        # 每次按技能实例生成一个 Tool，方便直接挂到 LangChain/LangGraph 生态。
        return StructuredTool.from_function(
            func=self._invoke_tool,
            name=self._skill.name,
            description=self._skill.description,
            args_schema=SkillToolInput,
        )

    def _invoke_tool(self, session_id: str, parameters: dict, idempotency_key: str) -> dict:
        # Tool 层最终返回原生字典，执行器再把它校验回 `SkillResult`。
        result = self._skill.invoke(
            SkillRequest(
                session_id=session_id,
                parameters=parameters,
                idempotency_key=idempotency_key,
            )
        )
        return result.model_dump()
