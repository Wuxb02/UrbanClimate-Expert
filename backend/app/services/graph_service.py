"""
图谱服务层（基于 Neo4j）

功能:
- 节点查询(支持关键词、类型过滤、分页) - 使用 Cypher
- 节点详情获取(含度数计算) - 使用 Cypher
- 邻居子图提取 - 使用 Cypher
- 统计信息计算 - 使用 Cypher
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logger import logger
from app.schemas.graph import (
    DocumentSnippet,
    GraphEdge,
    GraphNode,
    GraphNodeDetail,
    GraphQueryResponse,
    GraphStats,
    NeighborsResponse,
)
from app.services.neo4j_service import get_neo4j_service


class GraphService:
    """图谱服务类（基于 Neo4j）"""

    def __init__(self) -> None:
        self._chunk_cache: dict[str, dict[str, Any]] = {}

    @property
    def chunks_file_path(self) -> Path:
        """获取文本分块文件路径"""
        return settings.lightrag_workspace_path / "kv_store_text_chunks.json"

    def _load_chunks_if_needed(self) -> dict[str, dict[str, Any]]:
        """加载文本分块数据"""
        if self._chunk_cache:
            return self._chunk_cache

        if not self.chunks_file_path.exists():
            logger.warning(f"分块文件不存在 | 路径: {self.chunks_file_path}")
            return {}

        try:
            with open(self.chunks_file_path, "r", encoding="utf-8") as f:
                self._chunk_cache = json.load(f)
            logger.debug(f"分块数据加载成功 | 数量: {len(self._chunk_cache)}")
        except Exception as e:
            logger.error(f"分块文件加载失败 | 错误: {e}")
            self._chunk_cache = {}

        return self._chunk_cache

    def _extract_snippets(self, source_ids: list[str] | str) -> list[DocumentSnippet]:
        """
        从 source_id 提取文档片段

        Args:
            source_ids: chunk ID 列表或以 <SEP> 分隔的字符串

        Returns:
            文档片段列表
        """
        # 处理 source_ids 参数
        if isinstance(source_ids, str):
            if not source_ids:
                return []
            chunk_ids = [cid.strip() for cid in source_ids.split("<SEP>")]
        else:
            chunk_ids = source_ids

        if not chunk_ids:
            return []

        chunks = self._load_chunks_if_needed()
        snippets: list[DocumentSnippet] = []

        for chunk_id in chunk_ids[:5]:  # 限制最多 5 个片段
            if chunk_id not in chunks:
                continue

            chunk_data = chunks[chunk_id]
            content = chunk_data.get("content", "")

            # 从内容中提取 DOC_ID 和 FILENAME
            doc_id_match = re.search(r"\[DOC_ID:(\d+)\]", content)
            filename_match = re.search(r"\[FILENAME:([^\]]+)\]", content)

            doc_id = int(doc_id_match.group(1)) if doc_id_match else 0
            filename = filename_match.group(1) if filename_match else "unknown"

            # 清理内容中的标记
            clean_content = re.sub(r"\[DOC_ID:\d+\]\[FILENAME:[^\]]+\]\n*", "", content)
            # 截取前 500 字符作为预览
            preview = clean_content[:500].strip()

            snippets.append(
                DocumentSnippet(
                    doc_id=doc_id,
                    filename=filename,
                    chunk_id=chunk_id,
                    text=preview,
                )
            )

        return snippets

    def _neo4j_node_to_graph_node(self, node_record: dict[str, Any]) -> GraphNode:
        """将 Neo4j 节点记录转换为 GraphNode"""
        # 取描述的第一段（如果有多段的话）
        description = node_record.get("description", "")
        if "\n\n" in description:
            description = description.split("\n\n")[0].strip()

        return GraphNode(
            id=node_record.get("name", ""),
            title=node_record.get("entity_id", node_record.get("name", "")),
            description=description,
            entity_type=node_record.get("entity_type", "unknown"),
        )

    def _neo4j_edge_to_graph_edge(
        self, source: str, target: str, rel_data: dict[str, Any]
    ) -> GraphEdge:
        """将 Neo4j 关系转换为 GraphEdge"""
        return GraphEdge(
            source=source,
            target=target,
            relation=rel_data.get("description", "related_to"),
            weight=float(rel_data.get("weight", 1.0)),
        )

    async def query_nodes(
        self,
        keyword: str = "",
        entity_type: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> GraphQueryResponse:
        """
        查询节点和边，支持分页（使用 Neo4j Cypher）

        Args:
            keyword: 搜索关键词(匹配 name, description)
            entity_type: 过滤实体类型
            limit: 返回节点数量限制
            offset: 偏移量

        Returns:
            GraphQueryResponse 包含节点、边、总数和是否有更多数据
        """
        logger.info(
            f"图谱查询(Neo4j) | 关键词: '{keyword or '(全部)'}' | "
            f"类型: {entity_type or '(全部)'} | limit: {limit} | offset: {offset}"
        )

        neo4j_service = get_neo4j_service()

        # 构建 Cypher 查询
        # 1. 查询匹配的节点
        node_query = """
        MATCH (n:Entity)
        WHERE ($keyword = '' OR n.name CONTAINS $keyword OR n.description CONTAINS $keyword)
          AND ($entity_type IS NULL OR n.entity_type = $entity_type)
        RETURN n.name AS name, n.entity_id AS entity_id, n.entity_type AS entity_type,
               n.description AS description
        ORDER BY n.name
        SKIP $offset
        LIMIT $limit
        """

        # 2. 查询总数
        count_query = """
        MATCH (n:Entity)
        WHERE ($keyword = '' OR n.name CONTAINS $keyword OR n.description CONTAINS $keyword)
          AND ($entity_type IS NULL OR n.entity_type = $entity_type)
        RETURN count(n) AS total
        """

        params = {
            "keyword": keyword,
            "entity_type": entity_type,
            "offset": offset,
            "limit": limit,
        }

        nodes: list[GraphNode] = []
        total_count = 0

        def _query_neo4j():
            nonlocal nodes, total_count

            with neo4j_service.driver.session(database=settings.neo4j_database) as session:
                # 查询节点
                result = session.run(node_query, params)
                node_records = list(result)

                for record in node_records:
                    node_data = {
                        "name": record["name"],
                        "entity_id": record["entity_id"],
                        "entity_type": record["entity_type"],
                        "description": record["description"],
                    }
                    nodes.append(self._neo4j_node_to_graph_node(node_data))

                # 查询总数
                result = session.run(count_query, params)
                total_count = result.single()["total"]

        # 使用 asyncio.to_thread 避免阻塞
        await asyncio.to_thread(_query_neo4j)

        # 获取匹配节点的 ID 列表
        node_ids = [n.id for n in nodes]

        # 3. 查询这些节点之间的边
        edges: list[GraphEdge] = []
        if node_ids:
            edge_query = """
            MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity)
            WHERE a.name IN $node_ids AND b.name IN $node_ids
            RETURN a.name AS source, b.name AS target,
                   r.description AS description, r.weight AS weight
            """

            def _query_edges():
                nonlocal edges
                with neo4j_service.driver.session(database=settings.neo4j_database) as session:
                    result = session.run(edge_query, {"node_ids": node_ids})
                    for record in result:
                        rel_data = {
                            "description": record["description"],
                            "weight": record["weight"],
                        }
                        edges.append(
                            self._neo4j_edge_to_graph_edge(
                                record["source"], record["target"], rel_data
                            )
                        )

            await asyncio.to_thread(_query_edges)

        has_more = (offset + len(nodes)) < total_count

        logger.info(
            f"查询完成 | 返回节点: {len(nodes)} | 边: {len(edges)} | "
            f"总数: {total_count} | 有更多: {has_more}"
        )

        return GraphQueryResponse(
            nodes=nodes,
            edges=edges,
            total=total_count,
            has_more=has_more,
        )

    async def get_node_detail(self, node_id: str) -> GraphNodeDetail | None:
        """
        获取节点详情（使用 Neo4j Cypher）

        Args:
            node_id: 节点 ID

        Returns:
            节点详情，如果节点不存在返回 None
        """
        logger.info(f"获取节点详情(Neo4j) | node_id: {node_id}")

        neo4j_service = get_neo4j_service()

        # Cypher 查询：获取节点详情和度数
        query = """
        MATCH (n:Entity {name: $node_id})
        OPTIONAL MATCH (n)-[r:RELATED_TO]-()
        RETURN n.name AS name, n.entity_id AS entity_id, n.entity_type AS entity_type,
               n.description AS description, n.source_ids AS source_ids,
               count(r) AS degree
        """

        node_detail = None

        def _query_neo4j():
            nonlocal node_detail

            with neo4j_service.driver.session(database=settings.neo4j_database) as session:
                result = session.run(query, {"node_id": node_id})
                record = result.single()

                if not record:
                    logger.warning(f"节点不存在 | node_id: {node_id}")
                    return

                # 构建 GraphNode
                node_data = {
                    "name": record["name"],
                    "entity_id": record["entity_id"],
                    "entity_type": record["entity_type"],
                    "description": record["description"],
                }
                graph_node = self._neo4j_node_to_graph_node(node_data)

                degree = record["degree"]
                source_ids = record["source_ids"] or []

                # 提取文档片段
                snippets = self._extract_snippets(source_ids)

                node_detail = GraphNodeDetail(
                    node=graph_node,
                    degree=degree,
                    in_degree=degree,  # 对于无向图，in/out 相同
                    out_degree=degree,
                    snippets=snippets,
                )

        await asyncio.to_thread(_query_neo4j)

        if node_detail:
            logger.info(f"节点详情获取成功 | node_id: {node_id} | 度数: {node_detail.degree}")

        return node_detail

    async def get_neighbors(
        self, node_id: str, limit: int = 50
    ) -> NeighborsResponse | None:
        """
        获取节点的邻居子图（使用 Neo4j Cypher）

        Args:
            node_id: 中心节点 ID
            limit: 返回邻居数量限制

        Returns:
            邻居子图响应，如果节点不存在返回 None
        """
        logger.info(f"获取邻居子图(Neo4j) | node_id: {node_id} | limit: {limit}")

        neo4j_service = get_neo4j_service()

        # Cypher 查询：获取中心节点和邻居
        query = """
        MATCH (center:Entity {name: $node_id})
        OPTIONAL MATCH (center)-[r:RELATED_TO]-(neighbor:Entity)
        RETURN center, collect(DISTINCT neighbor) AS neighbors,
               collect(DISTINCT r) AS relationships
        LIMIT $limit
        """

        neighbors_response = None

        def _query_neo4j():
            nonlocal neighbors_response

            with neo4j_service.driver.session(database=settings.neo4j_database) as session:
                result = session.run(query, {"node_id": node_id, "limit": limit})
                record = result.single()

                if not record or not record["center"]:
                    logger.warning(f"节点不存在 | node_id: {node_id}")
                    return

                # 中心节点
                center_props = dict(record["center"])
                center_node = self._neo4j_node_to_graph_node(center_props)

                # 邻居节点
                neighbors: list[GraphNode] = []
                for neighbor in record["neighbors"]:
                    if neighbor:  # 排除 None
                        neighbor_props = dict(neighbor)
                        neighbors.append(self._neo4j_node_to_graph_node(neighbor_props))

                # 边（中心节点与邻居之间）
                edges: list[GraphEdge] = []
                # 重新查询边（因为上面的查询没有返回边的源和目标信息）
                edge_query = """
                MATCH (center:Entity {name: $node_id})-[r:RELATED_TO]-(neighbor:Entity)
                RETURN center.name AS center_name, neighbor.name AS neighbor_name,
                       r.description AS description, r.weight AS weight
                LIMIT $limit
                """
                edge_result = session.run(
                    edge_query, {"node_id": node_id, "limit": limit}
                )
                for edge_record in edge_result:
                    rel_data = {
                        "description": edge_record["description"],
                        "weight": edge_record["weight"],
                    }
                    edges.append(
                        self._neo4j_edge_to_graph_edge(
                            edge_record["center_name"],
                            edge_record["neighbor_name"],
                            rel_data,
                        )
                    )

                neighbors_response = NeighborsResponse(
                    center=center_node,
                    neighbors=neighbors[:limit],
                    edges=edges,
                )

        await asyncio.to_thread(_query_neo4j)

        if neighbors_response:
            logger.info(
                f"邻居查询成功 | node_id: {node_id} | "
                f"邻居数: {len(neighbors_response.neighbors)} | "
                f"边数: {len(neighbors_response.edges)}"
            )

        return neighbors_response

    async def get_stats(self) -> GraphStats:
        """
        获取图谱统计信息（使用 Neo4j Cypher）

        Returns:
            图谱统计信息
        """
        logger.info("获取图谱统计(Neo4j)")

        neo4j_service = get_neo4j_service()

        # Cypher 查询：统计节点、边、实体类型分布
        query = """
        MATCH (n:Entity)
        OPTIONAL MATCH ()-[r:RELATED_TO]->()
        RETURN
            count(DISTINCT n) AS total_nodes,
            count(DISTINCT r) AS total_edges,
            n.entity_type AS entity_type
        """

        stats = None

        def _query_neo4j():
            nonlocal stats

            with neo4j_service.driver.session(database=settings.neo4j_database) as session:
                # 统计总数
                result = session.run(
                    "MATCH (n:Entity) "
                    "OPTIONAL MATCH ()-[r:RELATED_TO]->() "
                    "RETURN count(DISTINCT n) AS total_nodes, "
                    "count(DISTINCT r) AS total_edges"
                )
                record = result.single()
                total_nodes = record["total_nodes"]
                total_edges = record["total_edges"]

                # 统计实体类型分布
                type_result = session.run(
                    "MATCH (n:Entity) "
                    "RETURN n.entity_type AS type, count(n) AS count "
                    "ORDER BY count DESC"
                )
                entity_types = {r["type"]: r["count"] for r in type_result}

                stats = GraphStats(
                    total_nodes=total_nodes,
                    total_edges=total_edges,
                    entity_types=entity_types,
                    last_updated=datetime.now(),  # Neo4j 不存储文件 mtime，使用当前时间
                )

        await asyncio.to_thread(_query_neo4j)

        logger.info(
            f"统计完成 | 节点: {stats.total_nodes} | "
            f"边: {stats.total_edges} | 类型: {len(stats.entity_types)}"
        )

        return stats


# 全局单例
_graph_service: GraphService | None = None


def get_graph_service() -> GraphService:
    """获取图谱服务单例"""
    global _graph_service
    if _graph_service is None:
        _graph_service = GraphService()
    return _graph_service
