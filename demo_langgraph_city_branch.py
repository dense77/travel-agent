"""演示 LangGraph 条件分支：
- 根据不同城市，把流程路由到不同分支。
- 每经过一个节点，都会在控制台打印当前走到哪一步。
"""

from __future__ import annotations

import json

from travel_agent.app.agents.executor.agent import ExecutorAgent
from travel_agent.app.agents.planner.agent import PlannerAgent
from travel_agent.app.graph.state import TravelGraphState
from travel_agent.app.graph.workflow import TravelGraphWorkflow
from travel_agent.app.skills.mock_travel import MockTravelSkill
from travel_agent.app.skills.registry import SkillRegistry
from travel_agent.app.agents.contracts import SharedContext


def build_demo_workflow() -> TravelGraphWorkflow:
    skill_registry = SkillRegistry()
    skill_registry.register(MockTravelSkill())
    planner = PlannerAgent()
    executor = ExecutorAgent(skill_registry=skill_registry)
    return TravelGraphWorkflow(planner=planner, executor=executor)


def build_initial_state(session_id: str, query: str, constraints: dict) -> TravelGraphState:
    context = SharedContext(
        session_id=session_id,
        user_query=query,
        hard_constraints=constraints,
    )
    return TravelGraphState(
        session_id=session_id,
        user_query=query,
        shared_context=context,
        route_trace=[],
        status="running",
    )


def run_case(workflow: TravelGraphWorkflow, session_id: str, query: str, constraints: dict) -> None:
    print("=" * 88)
    print(f"输入问题: {query}")
    print(f"约束条件: {json.dumps(constraints, ensure_ascii=False)}")
    print("执行过程:")

    result = workflow.invoke(build_initial_state(session_id, query, constraints))

    print("最终结果:")
    print(json.dumps(result.final_result, ensure_ascii=False, indent=2))
    print(f"最终命中的分支: {result.final_result.get('selected_branch', '')}")
    print(f"路线轨迹: {result.final_result.get('route_trace', [])}")
    print()


def main() -> None:
    workflow = build_demo_workflow()
    cases = [
        (
            "sess_demo_shanghai",
            "周末想在上海玩两天，看看外滩和豫园。",
            {"city": "上海", "travel_days": 2, "budget": 1500},
        ),
        (
            "sess_demo_beijing",
            "下周去北京玩三天，想看故宫和天坛。",
            {"city": "北京", "travel_days": 3, "budget": 2800},
        ),
        (
            "sess_demo_hangzhou",
            "我想去杭州玩三天，重点看看西湖和灵隐寺。",
            {"city": "杭州", "travel_days": 3, "budget": 2200},
        ),
        (
            "sess_demo_suzhou",
            "计划去苏州度假两天，想逛园林、吃本帮菜。",
            {"city": "苏州", "travel_days": 2, "budget": 1800},
        ),
    ]

    for session_id, query, constraints in cases:
        run_case(workflow, session_id, query, constraints)


if __name__ == "__main__":
    main()
