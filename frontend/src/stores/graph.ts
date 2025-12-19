/**
 * 图谱状态管理 (Pinia Store)
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type {
    GraphNode,
    GraphEdge,
    GraphNodeDetail,
    GraphStats,
    GraphFilters,
} from '@/types/api';
import {
    fetchGraph,
    fetchNodeDetail,
    fetchGraphStats,
} from '@/api/graph';

export const useGraphStore = defineStore('graph', () => {
    // ========== State ==========
    const nodes = ref<GraphNode[]>([]);
    const edges = ref<GraphEdge[]>([]);
    const selectedNodeId = ref<string | null>(null);
    const selectedNodeDetail = ref<GraphNodeDetail | null>(null);
    const stats = ref<GraphStats | null>(null);
    const isLoading = ref(false);
    const isLoadingDetail = ref(false);
    const error = ref<string | null>(null);
    const totalNodes = ref(0);
    const hasMore = ref(false);

    const filters = ref<GraphFilters>({
        entityTypes: [],
        searchKeyword: '',
    });

    // ========== Getters ==========
    const selectedNode = computed(() => {
        if (!selectedNodeId.value) return null;
        return nodes.value.find(n => n.id === selectedNodeId.value) || null;
    });

    const entityTypeOptions = computed(() => {
        if (!stats.value) return [];
        return Object.entries(stats.value.entity_types)
            .map(([type, count]) => ({
                label: `${type} (${count})`,
                value: type,
            }))
            .sort((a, b) => {
                // 按数量降序排列
                const countA = stats.value?.entity_types[a.value] || 0;
                const countB = stats.value?.entity_types[b.value] || 0;
                return countB - countA;
            });
    });

    const isEmpty = computed(() => {
        return nodes.value.length === 0 && !isLoading.value;
    });

    // ========== Actions ==========

    /**
     * 加载图谱数据
     */
    async function loadGraph(
        keyword: string = '',
        entityType?: string
    ): Promise<void> {
        isLoading.value = true;
        error.value = null;

        try {
            const response = await fetchGraph({
                q: keyword,
                entity_type: entityType,
                limit: 200,
            });
            nodes.value = response.nodes;
            edges.value = response.edges;
            totalNodes.value = response.total_nodes;
            hasMore.value = response.has_more;

            // 更新过滤器状态
            filters.value.searchKeyword = keyword;
        } catch (e) {
            error.value = e instanceof Error ? e.message : '加载图谱失败';
            nodes.value = [];
            edges.value = [];
            console.error('加载图谱失败:', e);
        } finally {
            isLoading.value = false;
        }
    }

    /**
     * 加载节点详情
     */
    async function loadNodeDetail(nodeId: string): Promise<void> {
        isLoadingDetail.value = true;
        selectedNodeId.value = nodeId;

        try {
            selectedNodeDetail.value = await fetchNodeDetail(nodeId);
        } catch (e) {
            console.error('加载节点详情失败:', e);
            selectedNodeDetail.value = null;
        } finally {
            isLoadingDetail.value = false;
        }
    }

    /**
     * 加载统计信息
     */
    async function loadStats(): Promise<void> {
        try {
            stats.value = await fetchGraphStats();
        } catch (e) {
            console.error('加载统计信息失败:', e);
        }
    }

    /**
     * 清除选中状态
     */
    function clearSelection(): void {
        selectedNodeId.value = null;
        selectedNodeDetail.value = null;
    }

    /**
     * 重置状态
     */
    function reset(): void {
        nodes.value = [];
        edges.value = [];
        selectedNodeId.value = null;
        selectedNodeDetail.value = null;
        error.value = null;
        totalNodes.value = 0;
        hasMore.value = false;
        filters.value = {
            entityTypes: [],
            searchKeyword: '',
        };
    }

    return {
        // State
        nodes,
        edges,
        selectedNodeId,
        selectedNodeDetail,
        stats,
        isLoading,
        isLoadingDetail,
        error,
        filters,
        totalNodes,
        hasMore,

        // Getters
        selectedNode,
        entityTypeOptions,
        isEmpty,

        // Actions
        loadGraph,
        loadNodeDetail,
        loadStats,
        clearSelection,
        reset,
    };
});
