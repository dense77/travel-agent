"""会话与任务编排服务。"""

from __future__ import annotations

from travel_agent.app.graph.state import TravelGraphState
from travel_agent.app.graph.workflow import TravelGraphWorkflow
from travel_agent.app.infra.config.settings import AppSettings
from travel_agent.app.memory.memory_store import SessionRecord, SessionStore
from travel_agent.app.runtime.task_dispatcher import TaskDispatcher


class SessionService:
    """承接 API 层，对会话与工作流调度做统一编排。"""

    def __init__(
        self,
        store: SessionStore,
        workflow: TravelGraphWorkflow,
        dispatcher: TaskDispatcher,
        settings: AppSettings,
    ) -> None:
        self._store = store
        self._workflow = workflow
        self._dispatcher = dispatcher
        self._settings = settings

    def create_session(self, query: str, constraints: dict[str, object], user_id: str | None = None) -> SessionRecord:
        """创建会话。"""
        return self._store.create_session(query=query, constraints=constraints, user_id=user_id)

    def get_session(self, session_id: str) -> SessionRecord:
        """读取会话快照。"""
        return self._store.get_session(session_id)

    def start_run(self, session_id: str) -> tuple[SessionRecord, bool]:
        """为指定会话启动一次异步工作流。"""
        record, created = self._store.dispatch_run(session_id)
        if not created:
            return record, False

        task_id = record.task_id
        assert task_id is not None

        def _target() -> None:
            self._execute_run(session_id=session_id, task_id=task_id)

        self._dispatcher.submit(task_id, _target)
        return record, True

    def _execute_run(self, session_id: str, task_id: str) -> None:
        """在线程池或任务队列中执行工作流。"""
        self._store.mark_running(session_id=session_id, task_id=task_id)
        self._store.append_event(session_id, stage="workflow", message="Workflow execution started.", status="running")

        try:
            context = self._store.load_context(session_id)
            task_result = self._workflow.invoke(
                TravelGraphState(
                    session_id=session_id,
                    user_query=context.user_query,
                    shared_context=context,
                    route_trace=[],
                    status="running",
                    iteration_count=0,
                    max_iterations=self._settings.agent_max_iterations,
                )
            )
            self._store.save_run_result(session_id=session_id, task_id=task_id, result=task_result)
        except Exception as exc:  # pragma: no cover - 兜底保护
            self._store.mark_failed(session_id=session_id, task_id=task_id, error_message=str(exc))
