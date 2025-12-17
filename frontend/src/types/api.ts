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

/** 图谱节点 */
export interface GraphNode {
    id: string;
    title: string;
    description?: string;
}

/** 图谱边 */
export interface GraphEdge {
    source: string;
    target: string;
    relation: string;
}

/** 图谱查询响应 */
export interface GraphQueryResponse {
    nodes: GraphNode[];
    edges: GraphEdge[];
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
