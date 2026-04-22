"""应用运行时配置。

这个文件的目标是集中管理“应用启动时会读取的参数”。
当前版本故意不依赖额外的配置库，
这样项目在本地可以更轻松地直接跑起来。
"""

# 启用延迟类型注解。
from __future__ import annotations

# os 用来从环境变量中读取配置。
import os

# BaseModel 用来定义强约束配置模型，
# Field 用来给字段设置默认工厂等元信息。
from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    """应用级配置模型。

    这里把和运行模式相关的重要参数都集中定义在一起，
    这样后续替换成 MySQL、Redis、Celery 时，
    可以继续沿用这套配置入口。
    """

    # app_name 是 FastAPI 展示的应用名。
    app_name: str = "Travel Agent Service"
    # execution_mode 决定任务是同步执行还是线程池执行。
    execution_mode: str = "threadpool"
    # task_worker_size 用来控制本地线程池的 worker 数量。
    task_worker_size: int = 4
    # agent_max_iterations 控制工作流最多允许重规划几次。
    agent_max_iterations: int = 2
    # default_tool_name 是 Planner 默认写入计划的技能名。
    default_tool_name: str = "rag_travel"
    # enable_mock_rag 用来标记当前是否启用 mock RAG。
    enable_mock_rag: bool = True
    # api_prefix 用来给所有 API 路由统一加前缀。
    api_prefix: str = ""
    # event_log_limit 控制查询接口最多返回多少条事件。
    event_log_limit: int = 50
    # health_message 是健康检查接口返回的状态文本。
    health_message: str = "ok"
    # planner_timeout_seconds 预留给未来的 Planner 超时控制。
    planner_timeout_seconds: int = 15
    # executor_timeout_seconds 预留给未来的 Executor 超时控制。
    executor_timeout_seconds: int = 30
    # task_queue_name 预留给未来消息队列场景。
    task_queue_name: str = "travel-agent-local"
    # metadata 预留给后续自定义扩展配置。
    metadata: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "AppSettings":
        """从环境变量中构造配置对象。"""
        # 这里直接返回一个 AppSettings 实例。
        # 每个字段都尽量给出环境变量覆盖入口和默认值，
        # 这样本地直接运行时不会缺配置。
        return cls(
            app_name=os.getenv("TRAVEL_AGENT_APP_NAME", "Travel Agent Service"),
            execution_mode=os.getenv("TRAVEL_AGENT_EXECUTION_MODE", "threadpool"),
            task_worker_size=int(os.getenv("TRAVEL_AGENT_TASK_WORKERS", "4")),
            agent_max_iterations=int(os.getenv("TRAVEL_AGENT_MAX_ITERATIONS", "2")),
            default_tool_name=os.getenv("TRAVEL_AGENT_DEFAULT_TOOL", "rag_travel"),
            enable_mock_rag=os.getenv("TRAVEL_AGENT_ENABLE_MOCK_RAG", "true").lower() == "true",
            api_prefix=os.getenv("TRAVEL_AGENT_API_PREFIX", ""),
            event_log_limit=int(os.getenv("TRAVEL_AGENT_EVENT_LOG_LIMIT", "50")),
            health_message=os.getenv("TRAVEL_AGENT_HEALTH_MESSAGE", "ok"),
        )
