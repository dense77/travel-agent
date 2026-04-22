"""会话存储抽象与内存实现。"""

# 启用延迟类型注解。
from __future__ import annotations

# ABC 和 abstractmethod 用来定义抽象存储接口。
from abc import ABC, abstractmethod
# datetime 和 timezone 用来生成统一 UTC 时间。
from datetime import datetime, timezone
# RLock 用来保证内存态多线程读写安全。
from threading import RLock
# Any 和 Optional 用来描述灵活字段与可空字段。
from typing import Any, Optional
# uuid4 用来生成 session_id 和 task_id。
from uuid import uuid4

# BaseModel 和 Field 用来定义存储模型。
from pydantic import BaseModel, Field

# 导入共享上下文和工作流结果模型。
from travel_agent.app.agents.contracts import ExecutionObservation, ExecutionPlan, SharedContext, TaskResult


def _utc_now() -> str:
    """返回当前 UTC 时间字符串。"""
    return datetime.now(timezone.utc).isoformat()


class SessionEvent(BaseModel):
    """会话事件模型。"""

    # stage 表示事件阶段。
    stage: str
    # message 是事件描述。
    message: str
    # status 是事件发生时的状态。
    status: str
    # created_at 是事件时间戳。
    created_at: str = Field(default_factory=_utc_now)


class SessionRecord(BaseModel):
    """会话快照模型。"""

    # session_id 是会话主键。
    session_id: str
    # user_id 预留给未来用户体系。
    user_id: Optional[str] = None
    # query 是原始问题。
    query: str
    # constraints 是结构化约束。
    constraints: dict[str, Any] = Field(default_factory=dict)
    # status 是当前状态。
    status: str = "created"
    # task_id 是当前或最近一次后台任务 ID。
    task_id: Optional[str] = None
    # run_attempt 表示运行尝试次数。
    run_attempt: int = 0
    # current_plan 是当前计划快照。
    current_plan: Optional[ExecutionPlan] = None
    # observations 是最近执行结果。
    observations: list[ExecutionObservation] = Field(default_factory=list)
    # final_result 是对外展示的最终结果。
    final_result: dict[str, Any] = Field(default_factory=dict)
    # error_message 在失败时记录错误描述。
    error_message: Optional[str] = None
    # events 记录事件流水。
    events: list[SessionEvent] = Field(default_factory=list)
    # created_at 记录创建时间。
    created_at: str = Field(default_factory=_utc_now)
    # updated_at 记录最后更新时间。
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
        """读取会话。"""

    @abstractmethod
    def load_context(self, session_id: str) -> SharedContext:
        """把会话快照转换成工作流上下文。"""

    @abstractmethod
    def dispatch_run(self, session_id: str) -> tuple[SessionRecord, bool]:
        """为会话发起一次新的运行。"""

    @abstractmethod
    def mark_running(self, session_id: str, task_id: str) -> SessionRecord:
        """把任务标记成运行中。"""

    @abstractmethod
    def append_event(self, session_id: str, stage: str, message: str, status: str) -> SessionRecord:
        """追加一条事件。"""

    @abstractmethod
    def save_run_result(self, session_id: str, task_id: str, result: TaskResult) -> SessionRecord:
        """保存执行结果。"""

    @abstractmethod
    def mark_failed(self, session_id: str, task_id: str, error_message: str) -> SessionRecord:
        """保存失败结果。"""


class InMemoryMemoryStore(SessionStore):
    """进程内存储实现。"""

    def __init__(self) -> None:
        """初始化空会话表和锁。"""
        # 用字典保存全部 session。
        self._sessions: dict[str, SessionRecord] = {}
        # 用可重入锁保证并发读写安全。
        self._lock = RLock()

    def create_session(
        self,
        query: str,
        constraints: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,
    ) -> SessionRecord:
        """创建一个新的会话记录。"""
        # 对共享状态的写操作需要加锁。
        with self._lock:
            # 生成带前缀的 session_id。
            session_id = f"sess_{uuid4().hex[:8]}"
            # 组装一条初始会话记录。
            record = SessionRecord(
                session_id=session_id,
                user_id=user_id,
                query=query,
                constraints=constraints or {},
                events=[SessionEvent(stage="session", message="Session created.", status="created")],
            )
            # 写入内存字典。
            self._sessions[session_id] = record
            # 返回记录副本。
            return record

    def get_session(self, session_id: str) -> SessionRecord:
        """按 ID 读取会话快照。"""
        with self._lock:
            # 先尝试读取原始记录。
            record = self._sessions.get(session_id)
            # 如果不存在，抛出 KeyError。
            if record is None:
                raise KeyError(session_id)
            # 返回深拷贝，避免外部误改内部状态。
            return record.model_copy(deep=True)

    def load_context(self, session_id: str) -> SharedContext:
        """把会话快照转换成工作流上下文。"""
        # 先读取会话记录。
        record = self.get_session(session_id)
        # 再构造 SharedContext。
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
        """标记一次新的运行请求。"""
        with self._lock:
            # 取可变记录对象。
            record = self._get_mutable(session_id)
            # 如果已经在排队或运行中，
            # 就不再重复创建任务。
            if record.status in {"queued", "running"} and record.task_id:
                return record.model_copy(deep=True), False

            # 生成新的 task_id。
            record.task_id = f"task_{uuid4().hex[:10]}"
            # 运行次数加一。
            record.run_attempt += 1
            # 状态变成 queued。
            record.status = "queued"
            # 清空历史错误。
            record.error_message = None
            # 更新时间。
            record.updated_at = _utc_now()
            # 记录一条排队事件。
            record.events.append(
                SessionEvent(stage="dispatch", message="Workflow task dispatched.", status="queued")
            )
            # 返回当前快照并标记 created=True。
            return record.model_copy(deep=True), True

    def mark_running(self, session_id: str, task_id: str) -> SessionRecord:
        """把任务标记为运行中。"""
        with self._lock:
            # 取可变记录。
            record = self._get_mutable(session_id)
            # 更新 task_id。
            record.task_id = task_id
            # 状态切成 running。
            record.status = "running"
            # 更新时间。
            record.updated_at = _utc_now()
            # 记录一条运行事件。
            record.events.append(SessionEvent(stage="run", message="Workflow is running.", status="running"))
            # 返回副本。
            return record.model_copy(deep=True)

    def append_event(self, session_id: str, stage: str, message: str, status: str) -> SessionRecord:
        """追加一条事件记录。"""
        with self._lock:
            # 取可变记录。
            record = self._get_mutable(session_id)
            # 更新时间。
            record.updated_at = _utc_now()
            # 追加事件。
            record.events.append(SessionEvent(stage=stage, message=message, status=status))
            # 返回副本。
            return record.model_copy(deep=True)

    def save_run_result(self, session_id: str, task_id: str, result: TaskResult) -> SessionRecord:
        """保存工作流执行成功后的结果。"""
        with self._lock:
            # 取可变记录。
            record = self._get_mutable(session_id)
            # 刷新 task_id。
            record.task_id = task_id
            # 刷新状态。
            record.status = result.status
            # 保存最终计划。
            record.current_plan = result.current_plan
            # 保存 observation。
            record.observations = list(result.observations)
            # 保存最终结果。
            record.final_result = dict(result.final_result)
            # 保存错误信息。
            record.error_message = result.error_message
            # 更新时间。
            record.updated_at = _utc_now()
            # 追加结果事件。
            record.events.append(SessionEvent(stage="result", message="Workflow finished.", status=result.status))

            # 如果 final_result 里有轨迹，就把每一步都追加到事件里，
            # 便于查询接口回放过程。
            for trace in result.final_result.get("route_trace", []):
                record.events.append(SessionEvent(stage="trace", message=trace, status=result.status))

            # 返回副本。
            return record.model_copy(deep=True)

    def mark_failed(self, session_id: str, task_id: str, error_message: str) -> SessionRecord:
        """保存失败结果。"""
        with self._lock:
            # 取可变记录。
            record = self._get_mutable(session_id)
            # 刷新 task_id。
            record.task_id = task_id
            # 设置状态为 failed。
            record.status = "failed"
            # 保存错误信息。
            record.error_message = error_message
            # 更新时间。
            record.updated_at = _utc_now()
            # 写入失败事件。
            record.events.append(SessionEvent(stage="error", message=error_message, status="failed"))
            # 返回副本。
            return record.model_copy(deep=True)

    def _get_mutable(self, session_id: str) -> SessionRecord:
        """读取内部可变记录对象。"""
        # 直接从内部字典里取对象引用。
        record = self._sessions.get(session_id)
        # 如果不存在就抛出 KeyError。
        if record is None:
            raise KeyError(session_id)
        # 返回原对象引用，供内部更新。
        return record
