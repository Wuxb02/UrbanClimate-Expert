"""
图谱相关 Schema 定义

包含:
- DocumentSnippet: 文档片段
- GraphNode: 图谱节点基础信息
- GraphNodeDetail: 节点详情(含度数和关联片段)
- GraphEdge: 图谱边
- GraphStats: 图谱统计信息
- GraphQueryResponse: 图谱查询响应
- NeighborsResponse: 邻居子图响应
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DocumentSnippet(BaseModel):
    """文档片段"""

    doc_id: int = Field(..., description="文档ID")
    filename: str = Field(..., description="文件名")
    chunk_id: str = Field(..., description="分块ID")
    text: str = Field(..., description="片段文本")


class GraphNode(BaseModel):
    """图谱节点基础信息"""

    id: str = Field(..., description="节点ID")
    title: str = Field(..., description="节点标题")
    description: str = Field(default="", description="节点描述")
    entity_type: str = Field(default="unknown", description="实体类型")


class GraphNodeDetail(GraphNode):
    """节点详情(含度数和关联片段)"""

    degree: int = Field(default=0, description="总度数")
    in_degree: int = Field(default=0, description="入度")
    out_degree: int = Field(default=0, description="出度")
    snippets: list[DocumentSnippet] = Field(
        default_factory=list, description="关联文档片段"
    )
    neighbors: list[str] = Field(
        default_factory=list, description="邻居节点ID列表"
    )


class GraphEdge(BaseModel):
    """图谱边"""

    source: str = Field(..., description="源节点ID")
    target: str = Field(..., description="目标节点ID")
    relation: str = Field(..., description="关系描述")
    weight: float = Field(default=1.0, description="权重")


class GraphStats(BaseModel):
    """图谱统计信息"""

    total_nodes: int = Field(..., description="总节点数")
    total_edges: int = Field(..., description="总边数")
    entity_types: dict[str, int] = Field(
        default_factory=dict, description="实体类型分布"
    )
    last_updated: Optional[datetime] = Field(
        default=None, description="最后更新时间"
    )


class GraphQueryResponse(BaseModel):
    """图谱查询响应"""

    nodes: list[GraphNode] = Field(..., description="节点列表")
    edges: list[GraphEdge] = Field(..., description="边列表")
    total_nodes: int = Field(..., description="总匹配节点数")
    has_more: bool = Field(default=False, description="是否还有更多数据")


class NeighborsResponse(BaseModel):
    """邻居子图响应"""

    center_node: GraphNode = Field(..., description="中心节点")
    neighbors: list[GraphNode] = Field(..., description="邻居节点")
    edges: list[GraphEdge] = Field(..., description="相关边")
