"""应用启动入口。

这个文件负责把所有模块装配成一个真正可运行的 FastAPI 应用。
"""

# 启用延迟类型注解。
from __future__ import annotations

# FastAPI 是整个 Web 服务框架入口。
from fastapi import FastAPI

# ExecutorAgent 负责执行计划。
from travel_agent.app.agents.executor.agent import ExecutorAgent
# PlannerAgent 负责生成计划。
from travel_agent.app.agents.planner.agent import PlannerAgent
# session_router 是对外暴露的 session API。
from travel_agent.app.api.routes.sessions import router as session_router
# TravelGraphWorkflow 是 Agent 工作流总入口。
from travel_agent.app.graph.workflow import TravelGraphWorkflow
# AppSettings 负责读取运行时配置。
from travel_agent.app.infra.config.settings import AppSettings
# InMemoryMemoryStore 是当前默认的存储实现。
from travel_agent.app.memory.memory_store import InMemoryMemoryStore
# MockRAGService 是当前默认的 RAG 实现。
from travel_agent.app.rag.service import MockRAGService
# InlineTaskDispatcher 和 ThreadPoolTaskDispatcher 分别代表同步和线程池模式。
from travel_agent.app.runtime.task_dispatcher import InlineTaskDispatcher, ThreadPoolTaskDispatcher
# SessionService 负责会话相关业务编排。
from travel_agent.app.services.session_service import SessionService
# MockTravelSkill 是当前默认技能。
from travel_agent.app.skills.mock_travel import MockTravelSkill
# SkillRegistry 负责统一管理技能。
from travel_agent.app.skills.registry import SkillRegistry


def _build_dispatcher(settings: AppSettings):
    """根据配置决定使用哪种任务分发器。"""
    # 如果配置指定 inline，
    # 就直接返回同步执行器。
    if settings.execution_mode == "inline":
        return InlineTaskDispatcher()
    # 否则默认返回线程池执行器。
    return ThreadPoolTaskDispatcher(max_workers=settings.task_worker_size)


def create_app() -> FastAPI:
    """创建并装配 FastAPI 应用。"""
    # 先从环境变量加载配置。
    settings = AppSettings.from_env()
    # 用配置中的应用名初始化 FastAPI。
    app = FastAPI(title=settings.app_name)

    # 创建会话存储。
    memory_store = InMemoryMemoryStore()
    # 创建技能注册表。
    skill_registry = SkillRegistry()
    # 注册默认的 mock 技能。
    skill_registry.register(MockTravelSkill())

    # 创建规划器，并把默认技能名配置进去。
    planner = PlannerAgent(default_tool_name=settings.default_tool_name)
    # 创建执行器。
    executor = ExecutorAgent(skill_registry=skill_registry)
    # 创建 mock RAG 服务。
    rag_service = MockRAGService()
    # 创建完整工作流。
    workflow = TravelGraphWorkflow(planner=planner, executor=executor, rag_service=rag_service)
    # 根据配置创建任务分发器。
    dispatcher = _build_dispatcher(settings)
    # 创建会话服务，把所有依赖注入进去。
    session_service = SessionService(
        store=memory_store,
        workflow=workflow,
        dispatcher=dispatcher,
        settings=settings,
    )

    # 把配置挂到 app.state，供路由层读取。
    app.state.settings = settings
    # 挂存储对象，方便调试或后续扩展。
    app.state.memory_store = memory_store
    # 挂技能注册表。
    app.state.skill_registry = skill_registry
    # 挂工作流对象。
    app.state.workflow = workflow
    # 挂会话服务对象。
    app.state.session_service = session_service

    @app.get("/health")
    def health() -> dict[str, str]:
        """提供一个最简单的健康检查接口。"""
        # 返回健康状态和当前任务队列名。
        return {"status": settings.health_message, "queue": settings.task_queue_name}

    # 注册 session 路由，并附加统一前缀。
    app.include_router(session_router, prefix=settings.api_prefix)
    # 返回组装好的应用对象。
    return app


# 提供全局 app 变量，供 `uvicorn travel_agent.app.main:app` 直接加载。
app = create_app()
