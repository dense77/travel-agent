"""作用：
- 定义 session 相关 HTTP 请求和响应模型。

约定：
- 这里的字段命名直接对齐接口返回。
- `constraints` 和 `final_result` 先保持开放字典，方便最小闭环快速落地。
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from travel_agent.app.agents.contracts import ExecutionObservation, ExecutionPlan


class CreateSessionRequest(BaseModel):
    # `user_id` 预留给未来扩展，当前最小闭环不会使用它。
    user_id: Optional[str] = None
    query: str
    constraints: dict[str, Any] = Field(default_factory=dict)


class CreateSessionResponse(BaseModel):
    # 这里只返回最小必要信息，调用方随后用 session_id 继续跑流程。
    session_id: str
    status: str


class RunSessionResponse(BaseModel):
    # `run` 接口重点返回最终答案，方便一跳验证闭环是否通了。
    session_id: str
    status: str
    final_result: dict[str, Any] = Field(default_factory=dict)


class SessionResponse(BaseModel):
    # 查询接口返回最全快照，便于观察计划、执行和最终结果。
    session_id: str
    query: str
    constraints: dict[str, Any] = Field(default_factory=dict)
    status: str
    current_plan: Optional[ExecutionPlan] = None
    observations: list[ExecutionObservation] = Field(default_factory=list)
    final_result: dict[str, Any] = Field(default_factory=dict)
