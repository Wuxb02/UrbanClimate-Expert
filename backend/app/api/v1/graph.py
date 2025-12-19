"""
知识图谱查询 API

功能:
- 图谱查询(支持关键词、类型过滤、分页)
- 节点详情获取
- 邻居子图获取
- 图谱统计信息
"""
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.logger import logger
from app.schemas.graph import (
    GraphNodeDetail,
    GraphQueryResponse,
    GraphStats,
    NeighborsResponse,
)
from app.services.graph_service import get_graph_service

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/query", response_model=GraphQueryResponse)
async def query_graph(
    q: str = Query(default="", description="搜索关键词"),
    limit: int = Query(default=200, ge=1, le=1000, description="返回节点数量限制"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
    entity_type: Optional[str] = Query(default=None, description="过滤实体类型"),
) -> GraphQueryResponse:
    """
    查询图谱，返回按关键词过滤的节点/边列表

    - **q**: 搜索关键词，为空时返回全部图谱
    - **limit**: 返回节点数量限制，默认 200，最大 1000
    - **offset**: 分页偏移量，默认 0
    - **entity_type**: 过滤实体类型，如 location, method, concept, artifact
    """
    logger.info(
        f"接收图谱查询请求 | 关键词: '{q or '(全部)'}' | "
        f"类型: {entity_type or '(全部)'} | limit: {limit} | offset: {offset}"
    )

    service = get_graph_service()
    return service.query_nodes(
        keyword=q,
        entity_type=entity_type,
        limit=limit,
        offset=offset,
    )


@router.get("/nodes/{node_id}", response_model=GraphNodeDetail)
async def get_node_detail(node_id: str) -> GraphNodeDetail:
    """
    获取节点详情

    返回节点的完整信息，包括:
    - 基础信息: id, title, description, entity_type
    - 度数统计: degree, in_degree, out_degree
    - 关联文档片段: snippets
    - 邻居节点列表: neighbors
    """
    logger.info(f"接收节点详情请求 | node_id: {node_id}")

    service = get_graph_service()
    detail = service.get_node_detail(node_id)

    if detail is None:
        raise HTTPException(status_code=404, detail=f"节点不存在: {node_id}")

    return detail


@router.get("/neighbors/{node_id}", response_model=NeighborsResponse)
async def get_neighbors(
    node_id: str,
    limit: int = Query(default=50, ge=1, le=200, description="返回邻居数量限制"),
) -> NeighborsResponse:
    """
    获取节点的邻居子图

    返回指定节点的 1-hop 邻居节点和相关边

    - **node_id**: 中心节点 ID
    - **limit**: 返回邻居数量限制，默认 50，最大 200
    """
    logger.info(f"接收邻居子图请求 | node_id: {node_id} | limit: {limit}")

    service = get_graph_service()
    neighbors = service.get_neighbors(node_id, limit=limit)

    if neighbors is None:
        raise HTTPException(status_code=404, detail=f"节点不存在: {node_id}")

    return neighbors


@router.get("/stats", response_model=GraphStats)
async def get_graph_stats() -> GraphStats:
    """
    获取图谱统计信息

    返回:
    - 总节点数
    - 总边数
    - 实体类型分布
    - 最后更新时间
    """
    logger.info("接收图谱统计请求")

    service = get_graph_service()
    return service.get_stats()
