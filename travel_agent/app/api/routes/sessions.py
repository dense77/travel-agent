"""作用：
- 提供最小闭环需要的 3 个 session 接口：创建、运行、查询结果。

约定：
- `POST /sessions` 只创建会话，不执行规划。
- `POST /sessions/{session_id}/run` 才会真正触发工作流。
- `GET /sessions/{session_id}` 返回当前会话快照，便于调试和验证。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from travel_agent.app.api.schemas.session import (
    CreateSessionRequest,
    CreateSessionResponse,
    RunSessionResponse,
    SessionResponse,
)
from travel_agent.app.graph.state import TravelGraphState

router = APIRouter()


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(payload: CreateSessionRequest, request: Request) -> CreateSessionResponse:
    # 创建阶段只落库存储，保持接口职责单一，方便最短路径验证。
    record = request.app.state.memory_store.create_session(
        query=payload.query,
        constraints=payload.constraints,
    )
    return CreateSessionResponse(session_id=record.session_id, status=record.status)


@router.post("/sessions/{session_id}/run", response_model=RunSessionResponse)
def run_session(session_id: str, request: Request) -> RunSessionResponse:
    try:
        context = request.app.state.memory_store.load_context(session_id)
    except KeyError as exc:
        # 存储层统一抛 `KeyError`，路由层负责转换成 HTTP 语义。
        raise HTTPException(status_code=404, detail="session not found") from exc

    # 先把会话置为 running，再进入工作流，便于外部观察状态变化。
    request.app.state.memory_store.update_status(session_id, "running")

    task_result = request.app.state.workflow.invoke(
        TravelGraphState(
            session_id=session_id,
            user_query=context.user_query,
            shared_context=context,
            status="running",
        )
    )
    record = request.app.state.memory_store.save_run_result(session_id, task_result)

    return RunSessionResponse(
        session_id=record.session_id,
        status=record.status,
        final_result=record.final_result,
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, request: Request) -> SessionResponse:
    try:
        record = request.app.state.memory_store.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc

    # 查询接口直接返回存储快照，不在这里做二次推导，避免调试时信息失真。
    return SessionResponse(
        session_id=record.session_id,
        query=record.query,
        constraints=record.constraints,
        status=record.status,
        current_plan=record.current_plan,
        observations=record.observations,
        final_result=record.final_result,
    )
