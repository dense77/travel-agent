"""会话存储抽象与内存实现。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from travel_agent.app.agents.contracts import ExecutionObservation, ExecutionPlan, SharedContext, TaskResult


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionEvent(BaseModel):
    """会话事件。"""

    stage: str
    message: str
    status: str
    created_at: str = Field(default_factory=_utc_now)


class SessionRecord(BaseModel):
    """会话当前快照。"""

    session_id: str
    user_id: Optional[str] = None
    query: str
    constraints: dict[str, Any] = Field(default_factory=dict)
    status: str = "created"
    task_id: Optional[str] = None
    run_attempt: int = 0
    current_plan: Optional[ExecutionPlan] = None
    observations: list[ExecutionObservation] = Field(default_factory=list)
    final_result: dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    events: list[SessionEvent] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utc_now)
    updated_at: str = Field(default_factory=_utc_now)


class SessionStore(ABC):
    """统一会话存储接口。"""

    @abstractmethod
    def create_session(
        self,
        query: str,
        constraints: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> SessionRecord:
        """创建会话。"""

    @abstractmethod
    def get_session(self, session_id: str) -> SessionRecord:
        """获取会话。"""

    @abstractmethod
    def load_context(self, session_id: str) -> SharedContext:
        """加载工作流上下文。"""

    @abstractmethod
    def dispatch_run(self, session_id: str) -> tuple[SessionRecord, bool]:
        """标记一次新的运行请求。"""

    @abstractmethod
    def mark_running(self, session_id: str, task_id: str) -> SessionRecord:
        """把任务标记为运行中。"""

    @abstractmethod
    def append_event(self, session_id: str, stage: str, message: str, status: str) -> SessionRecord:
        """追加事件。"""

    @abstractmethod
    def save_run_result(self, session_id: str, task_id: str, result: TaskResult) -> SessionRecord:
        """保存执行结果。"""

    @abstractmethod
    def mark_failed(self, session_id: str, task_id: str, error_message: str) -> SessionRecord:
        """保存失败结果。"""


class InMemoryMemoryStore(SessionStore):
    """进程内会话存储实现。"""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._lock = RLock()

    def create_session(
        self,
        query: str,
        constraints: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> SessionRecord:
        with self._lock:
            session_id = f"sess_{uuid4().hex[:8]}"
            record = SessionRecord(
                session_id=session_id,
                user_id=user_id,
                query=query,
                constraints=constraints or {},
                events=[SessionEvent(stage="session", message="Session created.", status="created")],
            )
            self._sessions[session_id] = record
            return record

    def get_session(self, session_id: str) -> SessionRecord:
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                raise KeyError(session_id)
            return record.model_copy(deep=True)

    def load_context(self, session_id: str) -> SharedContext:
        record = self.get_session(session_id)
        return SharedContext(
            session_id=record.session_id,
            user_query=record.query,
            hard_constraints=record.constraints,
            current_plan=record.current_plan,
            latest_observations=record.observations,
            metadata={
                "task_id": record.task_id or "",
                "run_attempt": record.run_attempt,
            },
        )

    def dispatch_run(self, session_id: str) -> tuple[SessionRecord, bool]:
        with self._lock:
            record = self._get_mutable(session_id)
            if record.status in {"queued", "running"} and record.task_id:
                return record.model_copy(deep=True), False

            record.task_id = f"task_{uuid4().hex[:10]}"
            record.run_attempt += 1
            record.status = "queued"
            record.error_message = None
            record.updated_at = _utc_now()
            record.events.append(
                SessionEvent(stage="dispatch", message="Workflow task dispatched.", status="queued")
            )
            return record.model_copy(deep=True), True

    def mark_running(self, session_id: str, task_id: str) -> SessionRecord:
        with self._lock:
            record = self._get_mutable(session_id)
            record.task_id = task_id
            record.status = "running"
            record.updated_at = _utc_now()
            record.events.append(SessionEvent(stage="run", message="Workflow is running.", status="running"))
            return record.model_copy(deep=True)

    def append_event(self, session_id: str, stage: str, message: str, status: str) -> SessionRecord:
        with self._lock:
            record = self._get_mutable(session_id)
            record.updated_at = _utc_now()
            record.events.append(SessionEvent(stage=stage, message=message, status=status))
            return record.model_copy(deep=True)

    def save_run_result(self, session_id: str, task_id: str, result: TaskResult) -> SessionRecord:
        with self._lock:
            record = self._get_mutable(session_id)
            record.task_id = task_id
            record.status = result.status
            record.current_plan = result.current_plan
            record.observations = list(result.observations)
            record.final_result = dict(result.final_result)
            record.error_message = result.error_message
            record.updated_at = _utc_now()
            record.events.append(SessionEvent(stage="result", message="Workflow finished.", status=result.status))

            for trace in result.final_result.get("route_trace", []):
                record.events.append(SessionEvent(stage="trace", message=trace, status=result.status))

            return record.model_copy(deep=True)

    def mark_failed(self, session_id: str, task_id: str, error_message: str) -> SessionRecord:
        with self._lock:
            record = self._get_mutable(session_id)
            record.task_id = task_id
            record.status = "failed"
            record.error_message = error_message
            record.updated_at = _utc_now()
            record.events.append(SessionEvent(stage="error", message=error_message, status="failed"))
            return record.model_copy(deep=True)

    def _get_mutable(self, session_id: str) -> SessionRecord:
        record = self._sessions.get(session_id)
        if record is None:
            raise KeyError(session_id)
        return record
