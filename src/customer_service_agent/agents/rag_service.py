# src/customer_service_agent/agents/rag_service.py
from sqlalchemy import select
from customer_service_agent.db import session
from customer_service_agent.db.models import KnowledgeDoc
from langchain_openai import OpenAIEmbeddings
from customer_service_agent.config import settings
import asyncio

class RAGService:
    def __init__(self):
        # 使用 OpenAI 兼容的 Embedding 模型（DeepSeek 官方暂未提供 Embedding，可以使用阿里云百炼的 text-embedding-v3，或者本地的 BGE）
        # 为了演示，这里假设你 config 里配了支持 embedding 的 base_url 和 key
        self.embeddings = OpenAIEmbeddings(
            api_key=settings.EMBEDDING_API_KEY,
            base_url=settings.EMBEDDING_BASE_URL,
            model=settings.EMBEDDING_MODEL
        )

    async def query_similar_docs(self, query: str, limit: int = 3, threshold: float = 0.5) -> list[str]:
        """真实的向量检索"""
        # 实时读取，拿到最新的factory，规避快照None
        factory = session.async_session_factory
        if factory is None:
            raise RuntimeError("数据库未初始化，请先调用 init_db_engine")
        # 1. 把用户的问题向量化
        try:
            query_vector = await self.embeddings.aembed_query(query)
        except Exception as e:
            print(f"⚠️ Embedding 失败，请检查模型配置: {e}")
            return []

        # 2. 去 pgvector 里做余弦相似度查询
        async with factory() as db:
            stmt = (
            select(
                KnowledgeDoc.content,
                KnowledgeDoc.embedding.cosine_distance(query_vector).label("distance"),
            )
            .order_by("distance")
            .limit(limit)
           )
            
            result = await db.execute(stmt)
            rows = result.all() 
        filtered = [row.content for row in rows if row.distance < threshold]
        if not filtered:
            print(f"   ⚠️ 检索到 {len(rows)} 条，但全部超过阈值 {threshold}，判定为不相关")
        else:
            print(f"   ✅ 命中 {len(filtered)} 条，最低距离 {rows[0].distance:.4f}")

        return filtered

rag_service = RAGService()