"""运行时配置。"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field


class AppSettings(BaseModel):
    """应用级配置。

    当前不依赖额外配置库，直接从环境变量读取，保持仓库可直接运行。
    """

    app_name: str = "Travel Agent Service"
    execution_mode: str = "threadpool"
    task_worker_size: int = 4
    agent_max_iterations: int = 2
    default_tool_name: str = "mock_travel"
    enable_mock_rag: bool = True
    api_prefix: str = ""
    event_log_limit: int = 50
    health_message: str = "ok"
    planner_timeout_seconds: int = 15
    executor_timeout_seconds: int = 30
    task_queue_name: str = "travel-agent-local"
    metadata: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "AppSettings":
        """从环境变量构建配置。"""
        return cls(
            app_name=os.getenv("TRAVEL_AGENT_APP_NAME", "Travel Agent Service"),
            execution_mode=os.getenv("TRAVEL_AGENT_EXECUTION_MODE", "threadpool"),
            task_worker_size=int(os.getenv("TRAVEL_AGENT_TASK_WORKERS", "4")),
            agent_max_iterations=int(os.getenv("TRAVEL_AGENT_MAX_ITERATIONS", "2")),
            default_tool_name=os.getenv("TRAVEL_AGENT_DEFAULT_TOOL", "mock_travel"),
            enable_mock_rag=os.getenv("TRAVEL_AGENT_ENABLE_MOCK_RAG", "true").lower() == "true",
            api_prefix=os.getenv("TRAVEL_AGENT_API_PREFIX", ""),
            event_log_limit=int(os.getenv("TRAVEL_AGENT_EVENT_LOG_LIMIT", "50")),
            health_message=os.getenv("TRAVEL_AGENT_HEALTH_MESSAGE", "ok"),
        )
