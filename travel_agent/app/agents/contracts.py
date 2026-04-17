"""作用：
- 定义 Planner、Executor、Skill、Memory 之间共享的数据契约。

约定：
- 这里的模型是系统内部“说同一种话”的基础，改字段要同步多层逻辑。
- 当前模型围绕最小闭环设计，只保留规划、执行观察和最终结果所需字段。
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    # `tool_name` 为空时表示计划不完整；最小闭环里执行器会直接报错观察。
    step_id: str
    action_type: str
    tool_name: Optional[str] = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    expected_output: str
    status: str


class ExecutionPlan(BaseModel):
    # 当前只支持线性步骤列表，还不支持分支、循环和动态回退。
    goal: str
    steps: list[PlanStep] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    need_rag: bool = False
    need_replan: bool = False


class ExecutionObservation(BaseModel):
    # 每个 observation 对应一次步骤执行结果，是最终结果组装的原材料。
    step_id: str
    source: str
    success: bool
    structured_output: dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list)


class SkillRequest(BaseModel):
    # `idempotency_key` 当前直接复用 step_id，约定同一步骤可被幂等识别。
    session_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str


class SkillResult(BaseModel):
    # `raw_ref` 用来记录原始证据引用；当前 mock 技能会返回一个伪 URI。
    skill_name: str
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error_code: Optional[str] = None
    raw_ref: Optional[str] = None


class ContextFact(BaseModel):
    key: str
    value: Any


class SharedContext(BaseModel):
    # 这是 Planner 和 Executor 共享的上下文快照，不直接暴露给 HTTP 层。
    session_id: str
    user_query: str
    hard_constraints: dict[str, Any] = Field(default_factory=dict)
    current_plan: Optional[ExecutionPlan] = None
    completed_actions: list[str] = Field(default_factory=list)
    facts: list[ContextFact] = Field(default_factory=list)
    memory_summary: str = ""
    latest_observations: list[ExecutionObservation] = Field(default_factory=list)


class TaskResult(BaseModel):
    # 工作流输出统一收敛到这个模型，方便存储层直接落会话结果。
    session_id: str
    status: str
    current_plan: ExecutionPlan
    observations: list[ExecutionObservation] = Field(default_factory=list)
    final_result: dict[str, Any] = Field(default_factory=dict)
