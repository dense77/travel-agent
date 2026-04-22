"""RAG 服务抽象、本地 Markdown 检索实现和 mock 回退实现。"""

# 启用延迟类型注解。
from __future__ import annotations

# ABC 和 abstractmethod 用来声明抽象接口。
from abc import ABC, abstractmethod
# Path 用来定位本地知识库目录。
from pathlib import Path
# re 用来做轻量关键词切分。
import re
# Any 用来描述内部中间结构。
from typing import Any

# 引入知识片段和共享上下文模型。
from travel_agent.app.agents.contracts import KnowledgeChunk, SharedContext
from travel_agent.app.infra.city_resolver import guess_trip_city


class BaseRAGService(ABC):
    """统一的 RAG 服务接口。"""

    @abstractmethod
    def retrieve(self, query: str, context: SharedContext) -> list[KnowledgeChunk]:
        """根据查询和上下文召回知识片段。"""


class LocalMarkdownRAGService(BaseRAGService):
    """基于本地 Markdown 文档的轻量检索服务。"""

    def __init__(self, knowledge_dir: str | Path | None = None, top_k: int = 4) -> None:
        """保存知识库目录和召回条数。"""
        self._knowledge_dir = Path(knowledge_dir) if knowledge_dir else Path(__file__).resolve().parent / "data"
        self._top_k = top_k

    def retrieve(self, query: str, context: SharedContext) -> list[KnowledgeChunk]:
        """从本地 Markdown 知识库中召回最相关的片段。"""
        chunk_records = self._load_chunk_records()
        if not chunk_records:
            return []

        selected_city = self._guess_city(query, context)
        query_terms = self._build_query_terms(query, context)
        query_bigrams = self._build_bigrams(query)

        scored_chunks: list[KnowledgeChunk] = []
        for record in chunk_records:
            score = self._score_record(
                record=record,
                selected_city=selected_city,
                query_terms=query_terms,
                query_bigrams=query_bigrams,
            )
            if score <= 0:
                continue

            scored_chunks.append(
                KnowledgeChunk(
                    chunk_id=record["chunk_id"],
                    title=record["title"],
                    content=record["content"],
                    source=record["source"],
                    score=round(score, 3),
                )
            )

        scored_chunks.sort(key=lambda item: item.score, reverse=True)
        return scored_chunks[: self._top_k]

    def _load_chunk_records(self) -> list[dict[str, Any]]:
        """读取知识目录并按 H2 标题切成片段。"""
        records: list[dict[str, Any]] = []
        if not self._knowledge_dir.exists():
            return records

        for path in sorted(self._knowledge_dir.glob("*.md")):
            doc_title = path.stem
            current_heading = "概览"
            content_lines: list[str] = []

            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if raw_line.startswith("# "):
                    doc_title = line[2:].strip() or path.stem
                    continue

                if raw_line.startswith("## "):
                    records.extend(self._flush_chunk(path, doc_title, current_heading, content_lines))
                    current_heading = line[3:].strip() or "未命名章节"
                    content_lines = []
                    continue

                if line:
                    content_lines.append(line)

            records.extend(self._flush_chunk(path, doc_title, current_heading, content_lines))

        return records

    def _flush_chunk(
        self,
        path: Path,
        doc_title: str,
        heading: str,
        content_lines: list[str],
    ) -> list[dict[str, Any]]:
        """把一个章节内容转成单个检索片段。"""
        content = " ".join(content_lines).strip()
        if not content:
            return []

        title = f"{doc_title} / {heading}"
        chunk_id = f"{path.stem}:{self._slugify(heading)}"
        source = f"{path.as_posix()}#{heading}"
        searchable_text = f"{title} {content}".lower()
        return [
            {
                "chunk_id": chunk_id,
                "title": title,
                "content": content,
                "source": source,
                "searchable_text": searchable_text,
                "term_set": self._build_term_set(searchable_text),
                "bigram_set": self._build_bigrams(searchable_text),
            }
        ]

    def _score_record(
        self,
        record: dict[str, Any],
        selected_city: str,
        query_terms: set[str],
        query_bigrams: set[str],
    ) -> float:
        """按关键词、短语和城市上下文给片段打分。"""
        text = str(record["searchable_text"])
        term_overlap = len(query_terms & record["term_set"])
        bigram_overlap = len(query_bigrams & record["bigram_set"])

        score = term_overlap * 0.25 + bigram_overlap * 0.65

        if selected_city and selected_city != "其他城市" and selected_city in text:
            score += 1.2

        if "预算" in query_terms and ("预算" in text or "住宿" in text or "交通" in text):
            score += 0.8

        if "三天" in query_terms and "三天" in text:
            score += 0.8

        return score

    def _build_query_terms(self, query: str, context: SharedContext) -> set[str]:
        """把 query 和约束转成轻量关键词集合。"""
        text_parts = [query]
        text_parts.extend(str(value) for value in context.hard_constraints.values() if value not in (None, ""))
        combined_text = " ".join(text_parts).lower()
        return self._build_term_set(combined_text)

    def _build_term_set(self, text: str) -> set[str]:
        """把中英文文本切成可用于匹配的词项集合。"""
        terms: set[str] = set()
        for token in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", text.lower()):
            cleaned = token.strip()
            if not cleaned:
                continue
            terms.add(cleaned)

            if self._contains_cjk(cleaned) and len(cleaned) > 2:
                for width in (2, 3):
                    for index in range(len(cleaned) - width + 1):
                        terms.add(cleaned[index : index + width])
        return terms

    def _build_bigrams(self, text: str) -> set[str]:
        """为中文短语构造字符二元组。"""
        compact = "".join(char for char in text.lower() if self._contains_cjk(char))
        if len(compact) < 2:
            return set()
        return {compact[index : index + 2] for index in range(len(compact) - 1)}

    def _guess_city(self, query: str, context: SharedContext) -> str:
        """优先从结构化约束读取城市，否则再从 query 中匹配。"""
        return guess_trip_city(query, context.hard_constraints)

    def _contains_cjk(self, text: str) -> bool:
        """判断文本中是否含有中文字符。"""
        return any("\u4e00" <= char <= "\u9fff" for char in text)

    def _slugify(self, text: str) -> str:
        """把章节标题转成稳定的 chunk_id 后缀。"""
        slug = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text.lower()).strip("-")
        return slug or "chunk"


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
        return guess_trip_city(query, context.hard_constraints)
