"""
知识图谱查询 API

功能:
- 图谱查询(支持关键词、类型过滤、分页)
- 节点详情获取
- 邻居子图获取
- 图谱统计信息
- Neo4j 管理端点(同步、清空)
"""
import asyncio
import time
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
from app.services.neo4j_service import get_neo4j_service

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
    return await service.query_nodes(
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
    detail = await service.get_node_detail(node_id)

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
    neighbors = await service.get_neighbors(node_id, limit=limit)

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
    return await service.get_stats()


@router.post("/admin/neo4j/sync", tags=["admin"])
async def trigger_neo4j_sync(
    mode: str = Query(default="json", pattern="^(json|graphml)$")
):
    """
    手动触发 Neo4j 全量同步

    **模式**:
    - json: 从 JSON 文件同步（推荐，更快，支持增量）
    - graphml: 从 GraphML 文件同步（备用）

    **功能**:
    - 读取 LightRAG 工作区中的数据文件
    - 将所有节点和关系 UPSERT 到 Neo4j 数据库
    - 返回同步统计信息

    **使用场景**:
    - Neo4j 数据丢失或损坏后恢复
    - 修改 Neo4j 配置后重新同步
    - 定期数据校验和同步

    **注意**: 这是一个幂等操作，重复执行不会导致数据重复
    """
    logger.info(f"接收 Neo4j 全量同步请求 | 模式: {mode}")

    try:
        neo4j_service = get_neo4j_service()

        if mode == "json":
            # JSON 模式：全量同步（不使用增量过滤）
            stats = await asyncio.to_thread(
                neo4j_service.sync_from_json,
                None,  # doc_id=None 表示全量同步
                incremental=False,  # 全量模式
            )

            # 更新同步时间戳
            current_ts = int(time.time())
            await asyncio.to_thread(
                neo4j_service.update_sync_timestamp,
                current_ts,
            )
        else:
            # GraphML 模式（备用）
            stats = await asyncio.to_thread(
                neo4j_service.sync_from_graphml,
                None,
            )

        logger.info(
            f"Neo4j 全量同步完成 ({mode}) | "
            f"节点: {stats['nodes_synced']} | 边: {stats['edges_synced']}"
        )

        return {
            "message": f"Neo4j 同步完成 (模式: {mode})",
            "mode": mode,
            "nodes_synced": stats["nodes_synced"],
            "edges_synced": stats["edges_synced"],
        }

    except Exception as e:
        logger.error(f"Neo4j 同步失败 | 错误: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Neo4j 同步失败: {str(e)}"
        )


@router.delete("/admin/neo4j/clear", tags=["admin"])
async def clear_neo4j():
    """
    清空 Neo4j 数据库（危险操作！）

    **功能**:
    - 删除 Neo4j 中所有节点和关系
    - 返回删除的节点数量

    **使用场景**:
    - 完全重建图谱前清理旧数据
    - 测试环境数据重置

    **警告**:
    - 这是一个不可逆操作！
    - 生产环境慎用！
    - 建议在操作前备份 Neo4j 数据库

    **恢复方法**:
    - 清空后可通过 `/admin/neo4j/sync` 端点从 GraphML 重新同步
    """
    logger.warning("接收 Neo4j 清空请求 | 这是危险操作！")

    try:
        neo4j_service = get_neo4j_service()
        count = await asyncio.to_thread(neo4j_service.clear_all)

        logger.warning(f"Neo4j 数据库已清空 | 删除节点数: {count}")

        return {
            "message": "Neo4j 数据库已清空",
            "deleted_nodes": count,
        }

    except Exception as e:
        logger.error(f"Neo4j 清空失败 | 错误: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Neo4j 清空失败: {str(e)}"
        )
