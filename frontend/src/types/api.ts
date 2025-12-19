/**
 * API 类型定义
 * 与后端 app/schemas/ 保持一致
 */

// ========== 聊天相关 ==========

/** 引用信息 */
export interface Citation {
    doc_id: number;
    filename: string;
    chunk_id: string;
    score: number;
    content_preview: string;
}

/** 流式聊天响应块 */
export interface ChatChunk {
    text: string;
    citations: Citation[];
    is_final: boolean;
}

/** 聊天请求 */
export interface ChatRequest {
    query: string;
    mode?: 'naive' | 'local' | 'global' | 'hybrid';
    top_k?: number;
}

/** 聊天消息 */
export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    citations?: Citation[];
    timestamp: number;
}

// ========== 图谱相关 ==========

/** 文档片段 */
export interface DocumentSnippet {
    doc_id: number;
    filename: string;
    chunk_id: string;
    text: string;
}

/** 图谱节点基础信息 */
export interface GraphNode {
    id: string;
    title: string;
    description?: string;
    entity_type?: string;
}

/** 图谱节点详情(含度数和关联片段) */
export interface GraphNodeDetail extends GraphNode {
    entity_type: string;
    degree: number;
    in_degree: number;
    out_degree: number;
    snippets: DocumentSnippet[];
    neighbors: string[];
}

/** 图谱边 */
export interface GraphEdge {
    source: string;
    target: string;
    relation: string;
    weight?: number;
}

/** 图谱统计信息 */
export interface GraphStats {
    total_nodes: number;
    total_edges: number;
    entity_types: Record<string, number>;
    last_updated: string | null;
}

/** 图谱查询参数 */
export interface GraphQueryParams {
    q?: string;
    limit?: number;
    offset?: number;
    entity_type?: string;
}

/** 图谱查询响应 */
export interface GraphQueryResponse {
    nodes: GraphNode[];
    edges: GraphEdge[];
    total_nodes: number;
    has_more: boolean;
}

/** 邻居子图响应 */
export interface NeighborsResponse {
    center_node: GraphNode;
    neighbors: GraphNode[];
    edges: GraphEdge[];
}

/** 图谱过滤器 */
export interface GraphFilters {
    entityTypes: string[];
    searchKeyword: string;
}

// ========== 文档相关 ==========

/** 文档状态枚举 */
export type DocumentStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

/** 文档上传响应 */
export interface DocumentUploadResponse {
    id: number;
    filename: string;
    sha256: string;
    status: DocumentStatus;
    created_at: string;
}

/** 文档状态响应 */
export interface DocumentStatusResponse {
    id: number;
    filename: string;
    status: DocumentStatus;
    error_message?: string;
    total_chunks?: number;
    total_entities?: number;
    total_relationships?: number;
    created_at: string;
    updated_at: string;
}

/** 文档列表项 */
export interface DocumentListItem {
    id: number;
    filename: string;
    filesize: number;
    status: DocumentStatus;
    error_message?: string;
    summary?: string;
    created_at: string;
    updated_at?: string;
}

/** 文档列表响应 */
export interface DocumentListResponse {
    total: number;
    items: DocumentListItem[];
}

/** 文档删除响应 */
export interface DocumentDeleteResponse {
    id: number;
    message: string;
}

/** 文档重命名请求 */
export interface DocumentRenameRequest {
    filename: string;
}

/** 文档重命名响应 */
export interface DocumentRenameResponse {
    id: number;
    filename: string;
    message: string;
}
