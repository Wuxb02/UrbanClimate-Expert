/**
 * 图谱 API 客户端
 */
import axios from 'axios';
import type {
    GraphQueryParams,
    GraphQueryResponse,
    GraphNodeDetail,
    GraphStats,
    NeighborsResponse,
} from '@/types/api';

const BASE_URL = '/api/v1/graph';

/**
 * 查询图谱
 * @param params 查询参数
 */
export async function fetchGraph(
    params: GraphQueryParams = {}
): Promise<GraphQueryResponse> {
    const { data } = await axios.get<GraphQueryResponse>(
        `${BASE_URL}/query`,
        { params }
    );
    return data;
}

/**
 * 获取节点详情
 * @param nodeId 节点 ID
 */
export async function fetchNodeDetail(
    nodeId: string
): Promise<GraphNodeDetail> {
    const { data } = await axios.get<GraphNodeDetail>(
        `${BASE_URL}/nodes/${encodeURIComponent(nodeId)}`
    );
    return data;
}

/**
 * 获取邻居子图
 * @param nodeId 中心节点 ID
 * @param limit 返回邻居数量限制
 */
export async function fetchNeighbors(
    nodeId: string,
    limit: number = 50
): Promise<NeighborsResponse> {
    const { data } = await axios.get<NeighborsResponse>(
        `${BASE_URL}/neighbors/${encodeURIComponent(nodeId)}`,
        { params: { limit } }
    );
    return data;
}

/**
 * 获取图谱统计信息
 */
export async function fetchGraphStats(): Promise<GraphStats> {
    const { data } = await axios.get<GraphStats>(`${BASE_URL}/stats`);
    return data;
}
