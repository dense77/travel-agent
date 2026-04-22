"""Session API 路由。

这个文件只处理 HTTP 语义：
- 解析请求
- 调用 service
- 转换异常
- 返回响应模型
"""

# 启用延迟类型注解。
from __future__ import annotations

# APIRouter 用来注册路由，
# HTTPException 用来抛 HTTP 错误，
# Request 用来拿到 app.state 中的共享对象。
from fastapi import APIRouter, HTTPException, Request

# 导入本路由会用到的所有 schema。
from travel_agent.app.api.schemas.session import (
    CreateSessionRequest,
    CreateSessionResponse,
    RunSessionResponse,
    SessionEventResponse,
    SessionResponse,
)


# 创建一个路由对象，后续所有 session 相关接口都挂在它上面。
router = APIRouter()


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(payload: CreateSessionRequest, request: Request) -> CreateSessionResponse:
    """创建一个新的旅行会话。"""
    # 从 app.state 中取出之前在 main.py 里挂载的 session_service。
    service = request.app.state.session_service
    # 调用 service 层创建会话。
    record = service.create_session(
        query=payload.query,
        constraints=payload.constraints,
        user_id=payload.user_id,
    )
    # 把内部记录裁剪成对外响应。
    return CreateSessionResponse(session_id=record.session_id, status=record.status)


@router.post("/sessions/{session_id}/run", response_model=RunSessionResponse)
def run_session(session_id: str, request: Request) -> RunSessionResponse:
    """为指定会话投递一次异步运行任务。"""
    # 取出 service 层对象。
    service = request.app.state.session_service
    try:
        # 调用 service 启动后台执行。
        record, accepted = service.start_run(session_id)
    except KeyError as exc:
        # 如果 session_id 不存在，
        # 则把底层 KeyError 转成 404。
        raise HTTPException(status_code=404, detail="session not found") from exc

    # 返回异步投递结果。
    return RunSessionResponse(
        session_id=record.session_id,
        task_id=record.task_id,
        status=record.status,
        accepted=accepted,
        message="workflow dispatched" if accepted else "workflow already queued or running",
    )


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, request: Request) -> SessionResponse:
    """读取会话当前完整快照。"""
    # 同样先拿到 service 层对象。
    service = request.app.state.session_service
    try:
        # 读取会话记录。
        record = service.get_session(session_id)
    except KeyError as exc:
        # 不存在则返回 404。
        raise HTTPException(status_code=404, detail="session not found") from exc

    # 从配置里读取允许返回的最大事件条数，
    # 避免事件列表过长。
    event_limit = request.app.state.settings.event_log_limit
    # 只取最后 N 条事件。
    visible_events = record.events[-event_limit:]

    # 组装并返回最终响应。
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
