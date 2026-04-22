"""系统内部共享契约。

说明：
- 这些模型贯穿 API、Workflow、Agent、RAG、Skill、Memory。
- 当前实现仍以最小可运行为主，但字段已经为异步执行、RAG、重规划预留。
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """单个可执行步骤。"""

    step_id: str
    action_type: str
    tool_name: Optional[str] = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    expected_output: str
    status: str = "planned"
    allow_cache: bool = True


class ExecutionPlan(BaseModel):
    """Planner 输出的结构化执行计划。"""

    goal: str
    steps: list[PlanStep] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    need_rag: bool = False
    need_replan: bool = False
    strategy: str = "single_skill"
    iteration_index: int = 0


class ExecutionObservation(BaseModel):
    """Executor 对单步执行的观测结果。"""

    step_id: str
    source: str
    success: bool
    structured_output: dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    evidence_refs: list[str] = Field(default_factory=list)


class SkillRequest(BaseModel):
    """统一技能调用入参。"""

    session_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str


class SkillResult(BaseModel):
    """统一技能调用结果。"""

    skill_name: str
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error_code: Optional[str] = None
    raw_ref: Optional[str] = None


class ContextFact(BaseModel):
    """共享事实片段。"""

    key: str
    value: Any


class KnowledgeChunk(BaseModel):
    """RAG 检索得到的知识片段。"""

    chunk_id: str
    title: str
    content: str
    source: str
    score: float = 0.0


class SharedContext(BaseModel):
    """Planner 和 Executor 共享的上下文快照。"""

    session_id: str
    user_query: str
    hard_constraints: dict[str, Any] = Field(default_factory=dict)
    current_plan: Optional[ExecutionPlan] = None
    completed_actions: list[str] = Field(default_factory=list)
    facts: list[ContextFact] = Field(default_factory=list)
    memory_summary: str = ""
    latest_observations: list[ExecutionObservation] = Field(default_factory=list)
    retrieved_knowledge: list[KnowledgeChunk] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GuardrailDecision(BaseModel):
    """Guardrail 节点的决策结果。"""

    allowed: bool
    reasons: list[str] = Field(default_factory=list)


class TaskResult(BaseModel):
    """一次完整工作流执行后的收敛结果。"""

    session_id: str
    status: str
    current_plan: Optional[ExecutionPlan] = None
    observations: list[ExecutionObservation] = Field(default_factory=list)
    final_result: dict[str, Any] = Field(default_factory=dict)
    iteration_count: int = 0
    error_message: Optional[str] = None
