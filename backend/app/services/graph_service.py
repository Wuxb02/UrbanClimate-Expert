"""
图谱服务层

功能:
- GraphML 文件加载与缓存(基于 mtime)
- 节点查询(支持关键词、类型过滤、分页)
- 节点详情获取(含度数计算)
- 邻居子图提取
- 统计信息计算
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import networkx as nx

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


class GraphService:
    """图谱服务类"""

    def __init__(self) -> None:
        self._graph: nx.Graph | None = None
        self._last_mtime: float = 0.0
        self._entity_type_cache: dict[str, int] = {}
        self._chunk_cache: dict[str, dict[str, Any]] = {}

    @property
    def graph_file_path(self) -> Path:
        """获取 GraphML 文件路径"""
        return settings.lightrag_workspace_path / "graph_chunk_entity_relation.graphml"

    @property
    def chunks_file_path(self) -> Path:
        """获取文本分块文件路径"""
        return settings.lightrag_workspace_path / "kv_store_text_chunks.json"

    def _load_graph_if_needed(self) -> nx.Graph:
        """
        按需加载图谱(基于文件 mtime 缓存)

        Returns:
            加载的 NetworkX 图对象
        """
        if not self.graph_file_path.exists():
            logger.warning(f"图谱文件不存在 | 路径: {self.graph_file_path}")
            return nx.Graph()

        current_mtime = self.graph_file_path.stat().st_mtime

        if self._graph is None or current_mtime > self._last_mtime:
            logger.info(
                f"加载图谱文件 | 路径: {self.graph_file_path} | "
                f"mtime 变化: {self._last_mtime} -> {current_mtime}"
            )
            try:
                self._graph = nx.read_graphml(self.graph_file_path)
                self._last_mtime = current_mtime
                self._update_entity_type_cache()
                logger.info(
                    f"图谱加载成功 | "
                    f"节点数: {self._graph.number_of_nodes()} | "
                    f"边数: {self._graph.number_of_edges()}"
                )
            except Exception as e:
                logger.error(f"图谱文件加载失败 | 错误: {e}")
                self._graph = nx.Graph()

        return self._graph

    def _update_entity_type_cache(self) -> None:
        """更新实体类型缓存"""
        if self._graph is None:
            return

        self._entity_type_cache.clear()
        for _, data in self._graph.nodes(data=True):
            entity_type = data.get("entity_type", "unknown")
            self._entity_type_cache[entity_type] = (
                self._entity_type_cache.get(entity_type, 0) + 1
            )

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

    def _extract_snippets(self, source_ids: str) -> list[DocumentSnippet]:
        """
        从 source_id 提取文档片段

        Args:
            source_ids: 以 <SEP> 分隔的 chunk ID 字符串

        Returns:
            文档片段列表
        """
        if not source_ids:
            return []

        chunks = self._load_chunks_if_needed()
        snippets: list[DocumentSnippet] = []

        chunk_ids = [cid.strip() for cid in source_ids.split("<SEP>")]

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

    def _node_to_graph_node(
        self, node_id: str, data: dict[str, Any]
    ) -> GraphNode:
        """将 NetworkX 节点数据转换为 GraphNode"""
        # 合并多个描述(用 <SEP> 分隔)
        description = data.get("description", "")
        if "<SEP>" in description:
            # 只取第一个描述，避免过长
            description = description.split("<SEP>")[0].strip()

        return GraphNode(
            id=node_id,
            title=data.get("entity_id", node_id),
            description=description,
            entity_type=data.get("entity_type", "unknown"),
        )

    def _edge_to_graph_edge(
        self, source: str, target: str, data: dict[str, Any]
    ) -> GraphEdge:
        """将 NetworkX 边数据转换为 GraphEdge"""
        return GraphEdge(
            source=source,
            target=target,
            relation=data.get("description", "related_to"),
            weight=float(data.get("weight", 1.0)),
        )

    def query_nodes(
        self,
        keyword: str = "",
        entity_type: str | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> GraphQueryResponse:
        """
        查询节点和边，支持分页

        Args:
            keyword: 搜索关键词(匹配 node_id, entity_id, description)
            entity_type: 过滤实体类型
            limit: 返回节点数量限制
            offset: 偏移量

        Returns:
            GraphQueryResponse 包含节点、边、总数和是否有更多数据
        """
        graph = self._load_graph_if_needed()

        logger.info(
            f"图谱查询 | 关键词: '{keyword or '(全部)'}' | "
            f"类型: {entity_type or '(全部)'} | limit: {limit} | offset: {offset}"
        )

        matched_nodes: list[GraphNode] = []

        for node_id, data in graph.nodes(data=True):
            # 类型过滤
            if entity_type and data.get("entity_type", "unknown") != entity_type:
                continue

            # 关键词匹配
            if keyword.strip():
                keyword_lower = keyword.lower()
                entity_id = data.get("entity_id", node_id).lower()
                description = data.get("description", "").lower()

                if not (
                    keyword_lower in node_id.lower()
                    or keyword_lower in entity_id
                    or keyword_lower in description
                ):
                    continue

            matched_nodes.append(self._node_to_graph_node(node_id, data))

        # 计算总数
        total_nodes = len(matched_nodes)

        # 应用分页
        paginated_nodes = matched_nodes[offset : offset + limit]

        # 获取分页后节点的 ID 集合
        node_ids = {n.id for n in paginated_nodes}

        # 获取相关的边(至少一端在节点集合中)
        edges: list[GraphEdge] = []
        for source, target, data in graph.edges(data=True):
            if source in node_ids or target in node_ids:
                edges.append(self._edge_to_graph_edge(source, target, data))

        has_more = offset + limit < total_nodes

        logger.info(
            f"图谱查询完成 | 匹配节点: {total_nodes} | "
            f"返回节点: {len(paginated_nodes)} | 相关边: {len(edges)} | "
            f"has_more: {has_more}"
        )

        return GraphQueryResponse(
            nodes=paginated_nodes,
            edges=edges,
            total_nodes=total_nodes,
            has_more=has_more,
        )

    def get_node_detail(self, node_id: str) -> GraphNodeDetail | None:
        """
        获取节点详情

        Args:
            node_id: 节点 ID

        Returns:
            节点详情，如果节点不存在返回 None
        """
        graph = self._load_graph_if_needed()

        if node_id not in graph.nodes:
            logger.warning(f"节点不存在 | node_id: {node_id}")
            return None

        data = graph.nodes[node_id]

        # 计算度数
        degree = graph.degree(node_id)
        # 对于无向图，in_degree 和 out_degree 相同
        # 如果是有向图，可以分别计算
        if isinstance(graph, nx.DiGraph):
            in_degree = graph.in_degree(node_id)
            out_degree = graph.out_degree(node_id)
        else:
            in_degree = degree
            out_degree = degree

        # 获取邻居节点 ID
        neighbors = list(graph.neighbors(node_id))

        # 提取关联文档片段
        source_ids = data.get("source_id", "")
        snippets = self._extract_snippets(source_ids)

        # 合并描述
        description = data.get("description", "")
        if "<SEP>" in description:
            # 合并所有描述
            descriptions = [d.strip() for d in description.split("<SEP>")]
            description = "\n\n".join(descriptions)

        logger.debug(
            f"获取节点详情 | node_id: {node_id} | "
            f"degree: {degree} | snippets: {len(snippets)}"
        )

        return GraphNodeDetail(
            id=node_id,
            title=data.get("entity_id", node_id),
            description=description,
            entity_type=data.get("entity_type", "unknown"),
            degree=degree,
            in_degree=in_degree,
            out_degree=out_degree,
            snippets=snippets,
            neighbors=neighbors[:50],  # 限制邻居数量
        )

    def get_neighbors(
        self, node_id: str, limit: int = 50
    ) -> NeighborsResponse | None:
        """
        获取节点的邻居子图

        Args:
            node_id: 中心节点 ID
            limit: 返回邻居数量限制

        Returns:
            邻居子图响应，如果节点不存在返回 None
        """
        graph = self._load_graph_if_needed()

        if node_id not in graph.nodes:
            logger.warning(f"节点不存在 | node_id: {node_id}")
            return None

        # 获取中心节点
        center_data = graph.nodes[node_id]
        center_node = self._node_to_graph_node(node_id, center_data)

        # 获取邻居节点
        neighbor_ids = list(graph.neighbors(node_id))[:limit]
        neighbors: list[GraphNode] = []
        for nid in neighbor_ids:
            ndata = graph.nodes[nid]
            neighbors.append(self._node_to_graph_node(nid, ndata))

        # 获取相关的边(中心节点与邻居之间)
        node_set = {node_id} | set(neighbor_ids)
        edges: list[GraphEdge] = []
        for source, target, data in graph.edges(data=True):
            if source in node_set and target in node_set:
                edges.append(self._edge_to_graph_edge(source, target, data))

        logger.debug(
            f"获取邻居子图 | center: {node_id} | "
            f"neighbors: {len(neighbors)} | edges: {len(edges)}"
        )

        return NeighborsResponse(
            center_node=center_node,
            neighbors=neighbors,
            edges=edges,
        )

    def get_stats(self) -> GraphStats:
        """
        获取图谱统计信息

        Returns:
            图谱统计信息
        """
        graph = self._load_graph_if_needed()

        # 获取文件最后修改时间
        last_updated = None
        if self.graph_file_path.exists():
            mtime = self.graph_file_path.stat().st_mtime
            last_updated = datetime.fromtimestamp(mtime)

        stats = GraphStats(
            total_nodes=graph.number_of_nodes(),
            total_edges=graph.number_of_edges(),
            entity_types=dict(self._entity_type_cache),
            last_updated=last_updated,
        )

        logger.debug(
            f"获取图谱统计 | 节点: {stats.total_nodes} | "
            f"边: {stats.total_edges} | 类型: {len(stats.entity_types)}"
        )

        return stats


# 全局单例
_graph_service: GraphService | None = None


def get_graph_service() -> GraphService:
    """获取图谱服务单例"""
    global _graph_service
    if _graph_service is None:
        logger.info("首次创建图谱服务实例...")
        _graph_service = GraphService()
    return _graph_service
