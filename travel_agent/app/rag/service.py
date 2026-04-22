"""RAG 服务抽象与本地 mock 实现。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from travel_agent.app.agents.contracts import KnowledgeChunk, SharedContext


class BaseRAGService(ABC):
    """统一 RAG 服务接口。"""

    @abstractmethod
    def retrieve(self, query: str, context: SharedContext) -> list[KnowledgeChunk]:
        """根据查询和上下文召回结构化知识片段。"""


class MockRAGService(BaseRAGService):
    """本地可运行的 mock RAG。"""

    def retrieve(self, query: str, context: SharedContext) -> list[KnowledgeChunk]:
        city = self._guess_city(query, context)
        chunks: list[KnowledgeChunk] = []

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

        return chunks

    def _guess_city(self, query: str, context: SharedContext) -> str:
        for field in ("destination_city", "target_city", "city", "start_city"):
            value = str(context.hard_constraints.get(field, "")).strip()
            if value:
                return value

        for city in ("杭州", "上海", "北京", "深圳", "广州"):
            if city in query:
                return city
        return "其他城市"
