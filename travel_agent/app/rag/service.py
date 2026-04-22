"""RAG 服务抽象和本地 mock 实现。"""

# 启用延迟类型注解。
from __future__ import annotations

# ABC 和 abstractmethod 用来声明抽象接口。
from abc import ABC, abstractmethod

# 引入知识片段和共享上下文模型。
from travel_agent.app.agents.contracts import KnowledgeChunk, SharedContext


class BaseRAGService(ABC):
    """统一的 RAG 服务接口。"""

    @abstractmethod
    def retrieve(self, query: str, context: SharedContext) -> list[KnowledgeChunk]:
        """根据查询和上下文召回知识片段。"""


class MockRAGService(BaseRAGService):
    """本地可运行的 mock 检索服务。"""

    def retrieve(self, query: str, context: SharedContext) -> list[KnowledgeChunk]:
        """根据输入粗略模拟返回一些知识片段。"""
        # 先猜测当前问题主要针对哪个城市。
        city = self._guess_city(query, context)
        # 初始化空结果列表。
        chunks: list[KnowledgeChunk] = []

        # 如果识别到杭州，就返回两条杭州知识。
        if city == "杭州":
            chunks.extend(
                [
                    KnowledgeChunk(
                        chunk_id="hz_1",
                        title="杭州经典景点",
                        content="西湖适合白天慢游，灵隐寺更适合安排半日深度参观。",
                        source="mock://rag/hangzhou/highlights",
                        score=0.92,
                    ),
                    KnowledgeChunk(
                        chunk_id="hz_2",
                        title="杭州出行建议",
                        content="高峰期建议避开景区周边自驾，优先地铁加步行。",
                        source="mock://rag/hangzhou/mobility",
                        score=0.83,
                    ),
                ]
            )
        # 如果识别到上海，就返回一条上海知识。
        elif city == "上海":
            chunks.append(
                KnowledgeChunk(
                    chunk_id="sh_1",
                    title="上海经典线路",
                    content="外滩、豫园、南京路适合安排在同一天形成经典城市步行线。",
                    source="mock://rag/shanghai/citywalk",
                    score=0.88,
                )
            )
        # 如果识别到北京，就返回一条北京知识。
        elif city == "北京":
            chunks.append(
                KnowledgeChunk(
                    chunk_id="bj_1",
                    title="北京文化景点",
                    content="故宫和天坛可与前门片区串联，建议提前预约热门场馆。",
                    source="mock://rag/beijing/culture",
                    score=0.87,
                )
            )

        # 如果 query 里明显提到了预算，
        # 就额外补一条预算知识。
        if "预算" in query or "budget" in query.lower():
            chunks.append(
                KnowledgeChunk(
                    chunk_id="common_budget",
                    title="预算拆分建议",
                    content="旅行预算通常建议拆分为交通、住宿、餐饮、门票、应急费用五类。",
                    source="mock://rag/common/budget",
                    score=0.79,
                )
            )

        # 返回召回到的知识列表。
        return chunks

    def _guess_city(self, query: str, context: SharedContext) -> str:
        """优先从约束中猜测城市，否则再从 query 中猜。"""
        # 优先扫描结构化约束字段。
        for field in ("destination_city", "target_city", "city", "start_city"):
            value = str(context.hard_constraints.get(field, "")).strip()
            if value:
                return value

        # 如果约束里没有，再从 query 文本里做简单匹配。
        for city in ("杭州", "上海", "北京", "深圳", "广州"):
            if city in query:
                return city
        # 如果都没匹配到，就返回“其他城市”。
        return "其他城市"
