"""作用：
- 提供当前项目的会话存储实现，负责创建、读取和保存运行结果。

约定：
- 当前是纯内存实现，进程重启后所有 session 都会丢失。
- 存储层只保存“当前快照”，不做版本历史和并发控制。
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from travel_agent.app.agents.contracts import ExecutionObservation, ExecutionPlan, SharedContext, TaskResult


class SessionRecord(BaseModel):
    # 这是对外查询接口最终返回的底层数据来源。
    session_id: str
    query: str
    constraints: dict[str, Any] = Field(default_factory=dict)
    status: str = "created"
    current_plan: Optional[ExecutionPlan] = None
    observations: list[ExecutionObservation] = Field(default_factory=list)
    final_result: dict[str, Any] = Field(default_factory=dict)


class InMemoryMemoryStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}

    def create_session(self, query: str, constraints: Optional[dict[str, Any]] = None) -> SessionRecord:
        # session_id 约定为 `sess_` 前缀，方便和普通字符串区分。
        session_id = f"sess_{uuid4().hex[:8]}"
        record = SessionRecord(
            session_id=session_id,
            query=query,
            constraints=constraints or {},
        )
        self._sessions[session_id] = record
        return record

    def get_session(self, session_id: str) -> SessionRecord:
        record = self._sessions.get(session_id)
        if record is None:
            raise KeyError(session_id)
        return record

    def load_context(self, session_id: str) -> SharedContext:
        # 路由层需要的是工作流上下文，而不是裸存储记录，所以这里做一次转换。
        record = self.get_session(session_id)
        return SharedContext(
            session_id=record.session_id,
            user_query=record.query,
            hard_constraints=record.constraints,
            current_plan=record.current_plan,
            latest_observations=record.observations,
        )

    def update_status(self, session_id: str, status: str) -> SessionRecord:
        record = self.get_session(session_id)
        record.status = status
        return record

    def save_run_result(self, session_id: str, result: TaskResult) -> SessionRecord:
        # 最小闭环直接覆盖当前快照，不保留中间版本。
        record = self.get_session(session_id)
        record.status = result.status
        record.current_plan = result.current_plan
        record.observations = result.observations
        record.final_result = result.final_result
        return record
