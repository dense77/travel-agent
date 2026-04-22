"""Session API。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from travel_agent.app.api.schemas.session import (
    CreateSessionRequest,
    CreateSessionResponse,
    RunSessionResponse,
    SessionEventResponse,
    SessionResponse,
)

router = APIRouter()


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(payload: CreateSessionRequest, request: Request) -> CreateSessionResponse:
    service = request.app.state.session_service
    record = service.create_session(
        query=payload.query,
        constraints=payload.constraints,
        user_id=payload.user_id,
    )
    return CreateSessionResponse(session_id=record.session_id, status=record.status)


@router.post("/sessions/{session_id}/run", response_model=RunSessionResponse)
def run_session(session_id: str, request: Request) -> RunSessionResponse:
    service = request.app.state.session_service
    try:
        record, accepted = service.start_run(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc

    return RunSessionResponse(
        session_id=record.session_id,
        task_id=record.task_id,
        status=record.status,
        accepted=accepted,
        message="workflow dispatched" if accepted else "workflow already queued or running",
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, request: Request) -> SessionResponse:
    service = request.app.state.session_service
    try:
        record = service.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc

    event_limit = request.app.state.settings.event_log_limit
    visible_events = record.events[-event_limit:]

    return SessionResponse(
        session_id=record.session_id,
        query=record.query,
        constraints=record.constraints,
        status=record.status,
        task_id=record.task_id,
        error_message=record.error_message,
        current_plan=record.current_plan,
        observations=record.observations,
        final_result=record.final_result,
        events=[
            SessionEventResponse(
                stage=item.stage,
                message=item.message,
                status=item.status,
                created_at=item.created_at,
            )
            for item in visible_events
        ],
    )
