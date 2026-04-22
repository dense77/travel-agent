"""演示 LangGraph 工作流是如何分支执行的。

这个脚本适合用来观察：
- Guardrail 是怎么先校验请求的
- Planner 是怎么生成计划的
- 城市分支是怎么命中的
- RAG 是怎么参与链路的
- Executor 和 Judge 是怎么收口结果的
"""

# 启用延迟类型注解。
from __future__ import annotations

# json 用于把最终结果格式化打印出来。
import json

# SharedContext 是工作流共享上下文模型。
from travel_agent.app.agents.contracts import SharedContext
# ExecutorAgent 负责执行规划结果。
from travel_agent.app.agents.executor.agent import ExecutorAgent
# PlannerAgent 负责先出计划。
from travel_agent.app.agents.planner.agent import PlannerAgent
# TravelGraphState 是工作流初始状态类型。
from travel_agent.app.graph.state import TravelGraphState
# TravelGraphWorkflow 是整张 LangGraph 工作流的封装入口。
from travel_agent.app.graph.workflow import TravelGraphWorkflow
# MockRAGService 用来提供本地可运行的检索结果。
from travel_agent.app.rag.service import MockRAGService
# MockTravelSkill 是示例技能。
from travel_agent.app.skills.mock_travel import MockTravelSkill
# SkillRegistry 用来注册和查找技能。
from travel_agent.app.skills.registry import SkillRegistry


def build_demo_workflow() -> TravelGraphWorkflow:
    """构造一套演示专用工作流。"""
    # 先创建技能注册表。
    skill_registry = SkillRegistry()
    # 把 mock 技能注册进去。
    skill_registry.register(MockTravelSkill())
    # 初始化规划器。
    planner = PlannerAgent()
    # 初始化执行器，并把技能注册表注入进去。
    executor = ExecutorAgent(skill_registry=skill_registry)
    # 返回带 mock RAG 的完整工作流。
    return TravelGraphWorkflow(planner=planner, executor=executor, rag_service=MockRAGService())


def build_initial_state(session_id: str, query: str, constraints: dict) -> TravelGraphState:
    """把一组输入参数组装成可送入工作流的初始状态。"""
    # 先把请求包装成共享上下文。
    context = SharedContext(
        session_id=session_id,
        user_query=query,
        hard_constraints=constraints,
    )
    # 再构造 LangGraph 需要的初始状态字典。
    return TravelGraphState(
        session_id=session_id,
        user_query=query,
        shared_context=context,
        route_trace=[],
        status="running",
        iteration_count=0,
        max_iterations=2,
    )


def run_case(workflow: TravelGraphWorkflow, session_id: str, query: str, constraints: dict) -> None:
    """运行一组案例并把过程结果打印出来。"""
    # 打印分隔线，让多组案例更容易区分。
    print("=" * 88)
    # 打印输入问题。
    print(f"输入问题: {query}")
    # 打印约束条件，并保留中文。
    print(f"约束条件: {json.dumps(constraints, ensure_ascii=False)}")
    # 提示下面会开始输出工作流执行过程。
    print("执行过程:")

    # 调用工作流执行这组案例。
    result = workflow.invoke(build_initial_state(session_id, query, constraints))

    # 提示下面开始输出最终汇总结果。
    print("最终结果:")
    # 把最终结果格式化为更易读的 JSON。
    print(json.dumps(result.final_result, ensure_ascii=False, indent=2))
    # 打印最终状态。
    print(f"最终状态: {result.status}")
    # 打印命中的城市分支。
    print(f"最终分支: {result.final_result.get('selected_branch', '')}")
    # 打印整条路径轨迹。
    print(f"路线轨迹: {result.final_result.get('route_trace', [])}")
    # 多打一行空行，隔开下一个案例。
    print()


def main() -> None:
    """依次跑多组案例。"""
    # 先创建演示工作流。
    workflow = build_demo_workflow()
    # 准备四组不同城市的测试数据。
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

    # 逐组执行案例。
    for session_id, query, constraints in cases:
        run_case(workflow, session_id, query, constraints)


# 只有直接执行脚本时才进入 main。
if __name__ == "__main__":
    main()
