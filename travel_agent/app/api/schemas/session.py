"""Session 相关 API schema。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from travel_agent.app.agents.contracts import ExecutionObservation, ExecutionPlan


class CreateSessionRequest(BaseModel):
    user_id: Optional[str] = None
    query: str
    constraints: dict[str, Any] = Field(default_factory=dict)


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str


class RunSessionResponse(BaseModel):
    session_id: str
    task_id: Optional[str] = None
    status: str
    accepted: bool
    message: str


class SessionEventResponse(BaseModel):
    stage: str
    message: str
    status: str
    created_at: str


class SessionResponse(BaseModel):
    session_id: str
    query: str
    constraints: dict[str, Any] = Field(default_factory=dict)
    status: str
    task_id: Optional[str] = None
    error_message: Optional[str] = None
    current_plan: Optional[ExecutionPlan] = None
    observations: list[ExecutionObservation] = Field(default_factory=list)
    final_result: dict[str, Any] = Field(default_factory=dict)
    events: list[SessionEventResponse] = Field(default_factory=list)
