"""测试流式聊天 API"""
import asyncio
import sys

from app.services.rag_service import get_rag_service


async def test_stream():
    """测试流式查询"""
    print("初始化 RAG 服务...")
    rag = await get_rag_service()

    print("开始流式查询...")
    query = "什么是城市热岛效应?"

    try:
        async for chunk in rag.stream_query_with_citations(query, mode="naive"):
            print(f"收到块: {chunk}")

        print("\n✅ 流式查询成功!")

    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_stream())
