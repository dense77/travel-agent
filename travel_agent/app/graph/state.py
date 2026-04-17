"""作用：
- 定义 LangGraph 在节点间流转的状态结构。

约定：
- 这里只声明状态键，不写业务逻辑。
- `total=False` 表示节点可以只返回自己更新过的字段，由 LangGraph 合并。
"""

from __future__ import annotations

from typing import Any, TypedDict

from travel_agent.app.agents.contracts import ExecutionObservation, ExecutionPlan, SharedContext


class TravelGraphState(TypedDict, total=False):
    # `session_id` 和 `user_query` 是贯穿全流程的最小身份信息。
    session_id: str
    user_query: str
    shared_context: SharedContext
    current_plan: ExecutionPlan
    observations: list[ExecutionObservation]
    final_result: dict[str, Any]
    selected_city: str
    selected_branch: str
    branch_message: str
    route_trace: list[str]
    status: str
