"""
聊天相关 Schema 定义

包含:
- Citation: 引用信息
- ChatRequest: 聊天请求
- ChatChunk: 流式聊天响应块
- ChatResponse: 非流式聊天响应
"""
from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    """引用信息"""

    doc_id: int = Field(..., description="文档ID")
    filename: str = Field(..., description="文档文件名")
    chunk_id: str = Field(..., description="分块ID")
    score: float = Field(..., ge=0.0, le=1.0, description="相关性分数")
    content_preview: str = Field(
        ..., max_length=200, description="内容预览(前200字符)"
    )


class ChatRequest(BaseModel):
    """聊天请求"""

    query: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    mode: Literal["naive", "local", "global", "hybrid"] = Field(
        default="hybrid",
        description="检索模式: naive(仅向量), local(局部图), global(全局图), hybrid(混合)",
    )
    top_k: int = Field(default=5, ge=1, le=20, description="返回的 Top-K 结果数")
    stream: bool = Field(default=True, description="是否流式返回")


class ChatChunk(BaseModel):
    """流式聊天响应块"""

    text: str = Field(..., description="生成的文本片段")
    citations: list[Citation] = Field(
        default_factory=list, description="引用来源"
    )
    is_final: bool = Field(default=False, description="是否是最后一个块")


class ChatResponse(BaseModel):
    """非流式聊天响应"""

    answer: str = Field(..., description="完整回答")
    citations: list[Citation] = Field(..., description="引用来源")
    mode: str = Field(..., description="使用的检索模式")
