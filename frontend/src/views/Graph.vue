<template>
    <div class="graph-page">
        <!-- 顶部工具栏 -->
        <GraphToolbar
            :keyword="searchKeyword"
            :entity-type="selectedEntityType"
            :stats="graphStore.stats"
            :is-loading="graphStore.isLoading"
            :entity-type-options="graphStore.entityTypeOptions"
            @update:keyword="searchKeyword = $event"
            @update:entity-type="selectedEntityType = $event"
            @search="handleSearch"
            @load-all="handleLoadAll"
            @zoom="handleZoom"
        />

        <!-- 主内容区 -->
        <div class="graph-content">
            <!-- 图谱区域 -->
            <div class="graph-main">
                <GraphViewer
                    ref="graphViewerRef"
                    :nodes="graphStore.nodes"
                    :edges="graphStore.edges"
                    :selected-node-id="graphStore.selectedNodeId"
                    :is-loading="graphStore.isLoading"
                    @node-click="handleNodeClick"
                />

                <!-- 图例 -->
                <GraphLegend class="graph-legend" />
            </div>

            <!-- 右侧详情面板 -->
            <transition name="slide-right">
                <div
                    v-if="graphStore.selectedNodeId"
                    class="detail-panel"
                >
                    <NodeDetail
                        :detail="graphStore.selectedNodeDetail"
                        :is-loading="graphStore.isLoadingDetail"
                        @navigate="handleNavigateToNode"
                        @close="handleCloseDetail"
                    />
                </div>
            </transition>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import GraphViewer from '@/components/GraphViewer.vue';
import GraphToolbar from '@/components/GraphToolbar.vue';
import GraphLegend from '@/components/GraphLegend.vue';
import NodeDetail from '@/components/NodeDetail.vue';
import { useGraphStore } from '@/stores/graph';
import type { GraphNode } from '@/types/api';

const graphStore = useGraphStore();

const graphViewerRef = ref<InstanceType<typeof GraphViewer> | null>(null);
const searchKeyword = ref('');
const selectedEntityType = ref<string | undefined>(undefined);

// 搜索处理
function handleSearch(): void {
    graphStore.loadGraph(searchKeyword.value, selectedEntityType.value);
}

// 加载全部
function handleLoadAll(): void {
    searchKeyword.value = '';
    selectedEntityType.value = undefined;
    graphStore.loadGraph('');
}

// 缩放控制
function handleZoom(action: 'in' | 'out' | 'reset'): void {
    if (!graphViewerRef.value) return;

    switch (action) {
        case 'in':
            graphViewerRef.value.zoomIn();
            break;
        case 'out':
            graphViewerRef.value.zoomOut();
            break;
        case 'reset':
            graphViewerRef.value.resetZoom();
            break;
    }
}

// 节点点击处理
function handleNodeClick(node: GraphNode): void {
    graphStore.loadNodeDetail(node.id);
}

// 导航到节点
function handleNavigateToNode(nodeId: string): void {
    graphStore.loadNodeDetail(nodeId);
}

// 关闭详情面板
function handleCloseDetail(): void {
    graphStore.clearSelection();
}

// 页面加载时初始化
onMounted(async () => {
    // 加载统计信息
    await graphStore.loadStats();
    // 加载全部图谱
    await graphStore.loadGraph('');
});
</script>

<style scoped>
.graph-page {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 100px);
    gap: 16px;
}

.graph-content {
    flex: 1;
    display: flex;
    gap: 16px;
    min-height: 0;
}

.graph-main {
    flex: 1;
    position: relative;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    overflow: hidden;
}

.graph-legend {
    position: absolute;
    left: 16px;
    bottom: 16px;
}

.detail-panel {
    width: 380px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    overflow: hidden;
    flex-shrink: 0;
}

/* 过渡动画 */
.slide-right-enter-active,
.slide-right-leave-active {
    transition: all 0.3s ease;
}

.slide-right-enter-from,
.slide-right-leave-to {
    opacity: 0;
    transform: translateX(20px);
}

@media (max-width: 1024px) {
    .graph-content {
        flex-direction: column;
    }

    .detail-panel {
        width: 100%;
        max-height: 40vh;
    }
}
</style>
