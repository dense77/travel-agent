"""作用：
- 应用启动入口，负责组装 FastAPI、内存存储、技能注册和 LangGraph 工作流。

约定：
- 路由层通过 `app.state.memory_store` 访问会话存储。
- 路由层通过 `app.state.workflow` 调用最小闭环工作流。
- 当前只注册一个 `mock_travel` 技能，这是最小可运行闭环的边界。
"""

from __future__ import annotations

from fastapi import FastAPI

from travel_agent.app.agents.executor.agent import ExecutorAgent
from travel_agent.app.agents.planner.agent import PlannerAgent
from travel_agent.app.api.routes.sessions import router as session_router
from travel_agent.app.graph.workflow import TravelGraphWorkflow
from travel_agent.app.memory.memory_store import InMemoryMemoryStore
from travel_agent.app.skills.mock_travel import MockTravelSkill
from travel_agent.app.skills.registry import SkillRegistry


def create_app() -> FastAPI:
    app = FastAPI(title="Travel Agent Minimal Loop")

    # 这里集中创建共享依赖，避免在路由函数里重复初始化对象。
    memory_store = InMemoryMemoryStore()
    skill_registry = SkillRegistry()
    skill_registry.register(MockTravelSkill())

    # 规划器负责出计划，执行器负责按计划调技能。
    planner = PlannerAgent()
    executor = ExecutorAgent(skill_registry=skill_registry)
    workflow = TravelGraphWorkflow(planner=planner, executor=executor)

    # `app.state` 是 FastAPI 提供的共享挂载点，当前项目用它传递运行期对象。
    app.state.memory_store = memory_store
    app.state.workflow = workflow

    app.include_router(session_router)
    return app


# `uvicorn travel_agent.app.main:app --reload` 会读取这个全局应用对象。
app = create_app()
