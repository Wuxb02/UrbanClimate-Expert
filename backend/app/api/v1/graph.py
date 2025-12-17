"""
知识图谱查询 API

功能:
- 从 LightRAG GraphML 文件加载图谱数据
- 支持关键词过滤节点
- 返回节点和边的轻量级列表
"""
from typing import Any

import networkx as nx
from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/query")
async def query_graph(q: str = "") -> dict[str, list[dict[str, Any]]]:
    """
    加载 LightRAG graphml 数据，返回按关键词过滤的节点/边列表

    Args:
        q: 搜索关键词，为空时返回全部图谱

    Returns:
        包含 nodes 和 edges 的字典
    """
    graph_file = settings.lightrag_workspace_path / "graph_chunk_entity_relation.graphml"
    if not graph_file.exists():
        return {"nodes": [], "edges": []}

    graph = nx.read_graphml(graph_file)
    nodes = []

    for node_id, data in graph.nodes(data=True):
        entity_id = data.get("entity_id", node_id)
        description = data.get("description", "")

        # 空关键词时返回所有节点
        if not q.strip():
            match = True
        else:
            match = (
                q.lower() in node_id.lower()
                or q.lower() in entity_id.lower()
                or q.lower() in description.lower()
            )

        if match:
            nodes.append({
                "id": node_id,
                "title": entity_id,
                "description": description,
                "entity_type": data.get("entity_type", "unknown")
            })

    # 获取过滤后的节点ID集合
    filtered_node_ids = {n["id"] for n in nodes}

    edges = []
    for source, target, data in graph.edges(data=True):
        if source in filtered_node_ids or target in filtered_node_ids:
            edges.append({
                "source": source,
                "target": target,
                "relation": data.get("description", "related_to"),
            })

    return {"nodes": nodes, "edges": edges}
