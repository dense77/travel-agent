"""Session 相关 API 模型。

这些模型的作用是：
- 规范 HTTP 入参
- 规范 HTTP 出参
- 让 Swagger 文档更清晰
"""

# 启用延迟类型注解。
from __future__ import annotations

# Any 和 Optional 用于声明灵活字段与可空字段。
from typing import Any, Optional

# BaseModel 是 Pydantic 的基础模型，
# Field 用来给字段声明默认值工厂。
from pydantic import BaseModel, Field

# 这里复用系统内部的执行计划与观测模型，
# 让查询接口直接返回结构化内部快照。
from travel_agent.app.agents.contracts import ExecutionObservation, ExecutionPlan


class CreateSessionRequest(BaseModel):
    """创建会话请求体。"""

    # user_id 预留给未来用户体系，
    # 当前版本可以不传。
    user_id: Optional[str] = None
    # query 是用户的自然语言请求。
    query: str
    # constraints 是结构化约束，例如预算、城市、天数。
    constraints: dict[str, Any] = Field(default_factory=dict)


class CreateSessionResponse(BaseModel):
    """创建会话响应体。"""

    # session_id 是后续所有接口的核心标识。
    session_id: str
    # status 通常是 created。
    status: str


class RunSessionResponse(BaseModel):
    """触发运行响应体。"""

    # session_id 表示本次投递关联的是哪个会话。
    session_id: str
    # task_id 表示后台异步任务编号。
    task_id: Optional[str] = None
    # status 是当前会话状态，例如 queued。
    status: str
    # accepted 用来标记这次请求是否真的成功创建了新任务。
    accepted: bool
    # message 给调用方更直观的语义提示。
    message: str


class SessionEventResponse(BaseModel):
    """会话事件响应体。"""

    # stage 表示事件发生在哪个阶段。
    stage: str
    # message 表示事件的文字描述。
    message: str
    # status 表示当时的状态。
    status: str
    # created_at 表示事件时间。
    created_at: str


class SessionResponse(BaseModel):
    """查询会话时返回的完整快照。"""

    # session_id 是会话主键。
    session_id: str
    # query 是原始用户问题。
    query: str
    # constraints 是原始约束。
    constraints: dict[str, Any] = Field(default_factory=dict)
    # status 表示当前执行状态。
    status: str
    # task_id 是当前或最近一次任务 ID。
    task_id: Optional[str] = None
    # error_message 只在失败场景下可能有值。
    error_message: Optional[str] = None
    # current_plan 是当前计划快照。
    current_plan: Optional[ExecutionPlan] = None
    # observations 是执行观测结果。
    observations: list[ExecutionObservation] = Field(default_factory=list)
    # final_result 是最终面向前端的收敛结果。
    final_result: dict[str, Any] = Field(default_factory=dict)
    # events 是最近的事件流水。
    events: list[SessionEventResponse] = Field(default_factory=list)
