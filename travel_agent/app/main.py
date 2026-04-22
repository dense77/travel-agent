"""应用启动入口。"""

from __future__ import annotations

from fastapi import FastAPI

from travel_agent.app.agents.executor.agent import ExecutorAgent
from travel_agent.app.agents.planner.agent import PlannerAgent
from travel_agent.app.api.routes.sessions import router as session_router
from travel_agent.app.graph.workflow import TravelGraphWorkflow
from travel_agent.app.infra.config.settings import AppSettings
from travel_agent.app.memory.memory_store import InMemoryMemoryStore
from travel_agent.app.rag.service import MockRAGService
from travel_agent.app.runtime.task_dispatcher import InlineTaskDispatcher, ThreadPoolTaskDispatcher
from travel_agent.app.services.session_service import SessionService
from travel_agent.app.skills.mock_travel import MockTravelSkill
from travel_agent.app.skills.registry import SkillRegistry


def _build_dispatcher(settings: AppSettings):
    if settings.execution_mode == "inline":
        return InlineTaskDispatcher()
    return ThreadPoolTaskDispatcher(max_workers=settings.task_worker_size)


def create_app() -> FastAPI:
    settings = AppSettings.from_env()
    app = FastAPI(title=settings.app_name)

    memory_store = InMemoryMemoryStore()
    skill_registry = SkillRegistry()
    skill_registry.register(MockTravelSkill())

    planner = PlannerAgent(default_tool_name=settings.default_tool_name)
    executor = ExecutorAgent(skill_registry=skill_registry)
    rag_service = MockRAGService()
    workflow = TravelGraphWorkflow(planner=planner, executor=executor, rag_service=rag_service)
    dispatcher = _build_dispatcher(settings)
    session_service = SessionService(
        store=memory_store,
        workflow=workflow,
        dispatcher=dispatcher,
        settings=settings,
    )

    app.state.settings = settings
    app.state.memory_store = memory_store
    app.state.skill_registry = skill_registry
    app.state.workflow = workflow
    app.state.session_service = session_service

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": settings.health_message, "queue": settings.task_queue_name}

    app.include_router(session_router, prefix=settings.api_prefix)
    return app


app = create_app()
