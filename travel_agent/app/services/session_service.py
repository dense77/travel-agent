"""会话服务。

这一层位于 API 和底层 Workflow/Store 之间，
它的职责是把“HTTP 请求意图”翻译成“明确的业务动作”。
"""

# 启用延迟类型注解。
from __future__ import annotations

# TravelGraphState 是工作流启动时需要的状态类型。
from travel_agent.app.graph.state import TravelGraphState
# TravelGraphWorkflow 是工作流总入口。
from travel_agent.app.graph.workflow import TravelGraphWorkflow
# AppSettings 提供运行时配置。
from travel_agent.app.infra.config.settings import AppSettings
# SessionRecord 和 SessionStore 分别表示会话快照和存储接口。
from travel_agent.app.memory.memory_store import SessionRecord, SessionStore
# TaskDispatcher 负责把任务交给具体执行器。
from travel_agent.app.runtime.task_dispatcher import TaskDispatcher


class SessionService:
    """承接会话相关业务动作。"""

    def __init__(
        self,
        store: SessionStore,
        workflow: TravelGraphWorkflow,
        dispatcher: TaskDispatcher,
        settings: AppSettings,
    ) -> None:
        """把依赖统一注入到服务对象里。"""
        # store 负责存取会话和状态。
        self._store = store
        # workflow 负责真正执行 Agent 工作流。
        self._workflow = workflow
        # dispatcher 负责把工作流提交出去执行。
        self._dispatcher = dispatcher
        # settings 提供运行时参数。
        self._settings = settings

    def create_session(self, query: str, constraints: dict[str, object], user_id: str | None = None) -> SessionRecord:
        """创建一个新会话。"""
        # 直接委托给存储层创建会话。
        return self._store.create_session(query=query, constraints=constraints, user_id=user_id)

    def get_session(self, session_id: str) -> SessionRecord:
        """读取会话快照。"""
        # 直接委托给存储层读取。
        return self._store.get_session(session_id)

    def start_run(self, session_id: str) -> tuple[SessionRecord, bool]:
        """为指定会话启动一次运行。"""
        # 先让存储层判断是否真的能创建新任务。
        record, created = self._store.dispatch_run(session_id)
        # 如果没有创建成功，
        # 说明这个会话已经在排队或运行中，
        # 直接返回当前状态即可。
        if not created:
            return record, False

        # 这里拿到的是存储层生成好的任务 ID。
        task_id = record.task_id
        # task_id 理论上在 created=True 时一定存在，
        # 这里用 assert 明确表达这个约束。
        assert task_id is not None

        def _target() -> None:
            """真正在线程池或未来队列里执行的任务函数。"""
            self._execute_run(session_id=session_id, task_id=task_id)

        # 把任务提交给调度器。
        self._dispatcher.submit(task_id, _target)
        # 返回当前记录和 accepted=True。
        return record, True

    def _execute_run(self, session_id: str, task_id: str) -> None:
        """在后台执行完整工作流。"""
        # 先把会话状态标记成 running。
        self._store.mark_running(session_id=session_id, task_id=task_id)
        # 追加一条事件，便于外部观察执行过程。
        self._store.append_event(session_id, stage="workflow", message="Workflow execution started.", status="running")

        try:
            # 从存储层加载工作流需要的共享上下文。
            context = self._store.load_context(session_id)
            # 构造工作流初始状态并启动执行。
            task_result = self._workflow.invoke(
                TravelGraphState(
                    session_id=session_id,
                    user_query=context.user_query,
                    shared_context=context,
                    route_trace=[],
                    status="running",
                    candidate_retry_count=0,
                    candidate_retry_needed=False,
                )
            )
            # 把最终结果写回存储层。
            self._store.save_run_result(session_id=session_id, task_id=task_id, result=task_result)
        except Exception as exc:  # pragma: no cover - 兜底保护
            # 任意异常都收敛成 failed 状态，
            # 避免后台任务直接丢失。
            self._store.mark_failed(session_id=session_id, task_id=task_id, error_message=str(exc))
