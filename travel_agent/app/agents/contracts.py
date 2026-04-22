"""系统内部共享契约。

这个文件非常重要，
因为 API、Workflow、Agent、Skill、Memory、RAG 都要靠它来“说同一种话”。
"""

# 启用延迟类型注解。
from __future__ import annotations

# Any 和 Optional 用来声明灵活字段及可空字段。
from typing import Any, Optional

# BaseModel 是 Pydantic 模型基类，
# Field 用于提供默认工厂和字段元信息。
from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    """执行计划中的单个步骤。"""

    # step_id 是这一步的唯一标识。
    step_id: str
    # action_type 表示动作类型，例如 skill_invoke。
    action_type: str
    # tool_name 表示这一步要调用哪个技能。
    tool_name: Optional[str] = None
    # input_payload 是传给工具的结构化输入。
    input_payload: dict[str, Any] = Field(default_factory=dict)
    # expected_output 用来描述这一步希望得到什么结果。
    expected_output: str
    # status 表示当前步骤状态，默认是 planned。
    status: str = "planned"
    # allow_cache 用于预留缓存策略。
    allow_cache: bool = True


class ExecutionPlan(BaseModel):
    """Planner 输出的完整执行计划。"""

    # goal 是用户任务目标的结构化表达。
    goal: str
    # steps 是按顺序执行的步骤列表。
    steps: list[PlanStep] = Field(default_factory=list)
    # missing_info 记录当前仍缺少哪些关键约束。
    missing_info: list[str] = Field(default_factory=list)
    # need_rag 表示当前计划是否需要知识检索增强。
    need_rag: bool = False
    # need_replan 表示当前计划是否预期需要再次规划。
    need_replan: bool = False
    # strategy 用来描述当前计划策略。
    strategy: str = "single_skill"
    # iteration_index 表示这是第几次规划。
    iteration_index: int = 0


class ExecutionObservation(BaseModel):
    """Executor 对每一步执行结果的记录。"""

    # step_id 对应的是哪一步计划。
    step_id: str
    # source 表示这个 observation 来自哪个执行源。
    source: str
    # success 标记这一步是否成功。
    success: bool
    # structured_output 是结构化结果正文。
    structured_output: dict[str, Any] = Field(default_factory=dict)
    # error_message 在失败时记录错误原因。
    error_message: Optional[str] = None
    # evidence_refs 用来记录证据引用。
    evidence_refs: list[str] = Field(default_factory=list)


class SkillRequest(BaseModel):
    """统一技能调用请求。"""

    # session_id 方便技能侧知道自己属于哪个会话。
    session_id: str
    # parameters 是技能真正的入参。
    parameters: dict[str, Any] = Field(default_factory=dict)
    # idempotency_key 用于防重复执行。
    idempotency_key: str


class SkillResult(BaseModel):
    """统一技能调用结果。"""

    # skill_name 表示是哪个技能返回的结果。
    skill_name: str
    # success 表示调用是否成功。
    success: bool
    # data 是结构化业务数据。
    data: dict[str, Any] = Field(default_factory=dict)
    # error_code 用来承接统一错误码或错误信息。
    error_code: Optional[str] = None
    # raw_ref 可以存原始证据引用。
    raw_ref: Optional[str] = None


class ContextFact(BaseModel):
    """上下文事实片段。"""

    # key 是事实名称。
    key: str
    # value 是事实值。
    value: Any


class KnowledgeChunk(BaseModel):
    """RAG 返回的知识片段。"""

    # chunk_id 是知识片段编号。
    chunk_id: str
    # title 是知识片段标题。
    title: str
    # content 是知识正文。
    content: str
    # source 记录来源。
    source: str
    # score 记录召回或排序分数。
    score: float = 0.0


class SharedContext(BaseModel):
    """Planner 和 Executor 共享的上下文快照。"""

    # session_id 表示这个上下文属于哪个会话。
    session_id: str
    # user_query 是原始用户问题。
    user_query: str
    # hard_constraints 存结构化硬约束。
    hard_constraints: dict[str, Any] = Field(default_factory=dict)
    # current_plan 存当前计划。
    current_plan: Optional[ExecutionPlan] = None
    # completed_actions 预留记录已完成动作。
    completed_actions: list[str] = Field(default_factory=list)
    # facts 存关键事实。
    facts: list[ContextFact] = Field(default_factory=list)
    # memory_summary 存压缩后的摘要记忆。
    memory_summary: str = ""
    # latest_observations 存最近一轮执行观察。
    latest_observations: list[ExecutionObservation] = Field(default_factory=list)
    # retrieved_knowledge 存当前检索到的知识片段。
    retrieved_knowledge: list[KnowledgeChunk] = Field(default_factory=list)
    # metadata 预留额外扩展信息。
    metadata: dict[str, Any] = Field(default_factory=dict)


class GuardrailDecision(BaseModel):
    """Guardrail 节点输出。"""

    # allowed 表示请求是否通过校验。
    allowed: bool
    # reasons 存储未通过的原因列表。
    reasons: list[str] = Field(default_factory=list)


class TaskResult(BaseModel):
    """一次完整工作流执行后的最终结果。"""

    # session_id 表示属于哪个会话。
    session_id: str
    # status 表示最终状态，例如 finished/failed/rejected。
    status: str
    # current_plan 记录最终停留时的计划。
    current_plan: Optional[ExecutionPlan] = None
    # observations 记录整个执行得到的观测结果。
    observations: list[ExecutionObservation] = Field(default_factory=list)
    # final_result 是面向外部接口返回的最终收敛数据。
    final_result: dict[str, Any] = Field(default_factory=dict)
    # iteration_count 记录总迭代次数。
    iteration_count: int = 0
    # error_message 在失败场景下记录错误描述。
    error_message: Optional[str] = None
