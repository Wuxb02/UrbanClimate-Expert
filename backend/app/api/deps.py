from collections.abc import AsyncGenerator

from app.services.rag_service import LightRAGService, get_rag_service


async def get_rag() -> AsyncGenerator[LightRAGService, None]:
    """依赖注入:获取 RAG 服务实例"""
    rag = await get_rag_service()
    yield rag
