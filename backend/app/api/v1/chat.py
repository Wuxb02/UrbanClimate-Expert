import json
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.api.deps import get_rag
from app.core.logger import logger
from app.schemas.chat import ChatRequest
from app.services.rag_service import LightRAGService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    rag: LightRAGService = Depends(get_rag),
) -> StreamingResponse:
    """
    流式聊天 API (带 Citation 支持)

    请求体:
    {
        "query": "什么是城市热岛效应?",
        "mode": "hybrid",
        "top_k": 5
    }

    响应格式 (SSE):
    data: {"text":"城市热岛效应是指...","citations":[...],"is_final":false}
    data: {"text":"补充说明...","citations":[],"is_final":false}
    data: {"text":"","citations":[],"is_final":true}
    data: [DONE]
    """
    # 生成唯一请求 ID
    request_id = str(uuid.uuid4())[:8]

    logger.info(
        f"接收流式聊天请求 | 请求ID: {request_id} | "
        f"模式: {request.mode} | 问题: {request.query[:100]}..."
    )

    async def event_stream() -> AsyncGenerator[bytes, None]:
        chunk_count = 0
        try:
            # 使用带 Citation 的流式查询
            async for chunk in rag.stream_query_with_citations(
                question=request.query,
                mode=request.mode
            ):
                chunk_count += 1
                # 将字典序列化为 JSON
                json_data = json.dumps(chunk, ensure_ascii=False)
                yield f"data: {json_data}\n\n".encode("utf-8")

            # 发送结束标记
            yield b"data: [DONE]\n\n"

            logger.info(
                f"流式响应完成 | 请求ID: {request_id} | "
                f"Chunks: {chunk_count}"
            )

        except Exception as e:
            logger.error(
                f"流式响应异常 | 请求ID: {request_id} | "
                f"已发送: {chunk_count} chunks | 错误: {e}"
            )
            # 错误处理:发送错误事件
            error_data = json.dumps({
                "error": str(e),
                "type": "error"
            }, ensure_ascii=False)
            yield f"event: error\ndata: {error_data}\n\n".encode("utf-8")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
        }
    )


@router.post("/query")
async def chat_query(
    request: ChatRequest,
    rag: LightRAGService = Depends(get_rag),
) -> dict:
    """
    非流式聊天 API (同步查询)

    请求体:
    {
        "query": "什么是城市热岛效应?",
        "mode": "hybrid"
    }

    响应:
    {
        "answer": "...",
        "mode": "hybrid"
    }
    """
    request_id = str(uuid.uuid4())[:8]

    logger.info(
        f"接收同步查询请求 | 请求ID: {request_id} | "
        f"模式: {request.mode} | 问题: {request.query[:100]}..."
    )

    try:
        result = await rag.query(
            question=request.query,
            mode=request.mode
        )

        logger.info(
            f"同步查询完成 | 请求ID: {request_id} | "
            f"结果长度: {len(result)}"
        )

        return {
            "answer": result,
            "mode": request.mode
        }
    except Exception as e:
        logger.error(f"同步查询失败 | 请求ID: {request_id} | 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
