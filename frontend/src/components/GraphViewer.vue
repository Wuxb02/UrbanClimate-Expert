<template>
    <div class="graph-viewer">
        <!-- 加载状态 -->
        <div v-if="isLoading" class="loading-overlay">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
            <p>加载图谱数据...</p>
        </div>

        <!-- 空状态 -->
        <div v-else-if="isEmpty" class="empty-state">
            <el-icon :size="48" color="#c0c4cc"><Share /></el-icon>
            <p>未找到相关实体,请尝试其他关键词</p>
        </div>

        <!-- 图谱 -->
        <v-network-graph
            v-else
            ref="graphRef"
            :nodes="graphNodes"
            :edges="graphEdges"
            :layouts="layouts"
            :configs="configs"
            @node:click="handleNodeClick"
        />
    </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { VNetworkGraph } from 'v-network-graph';
import 'v-network-graph/lib/style.css';
import { Loading, Share } from '@element-plus/icons-vue';
import type { GraphNode, GraphEdge } from '@/types/api';

// 实体类型颜色映射
const ENTITY_COLORS: Record<string, string> = {
    location: '#67c23a',
    method: '#409eff',
    concept: '#e6a23c',
    artifact: '#909399',
    person: '#f56c6c',
    organization: '#9b59b6',
    unknown: '#c0c4cc',
};

interface Props {
    nodes: GraphNode[];
    edges: GraphEdge[];
    selectedNodeId?: string | null;
    isLoading?: boolean;
}

interface Emits {
    (e: 'node-click', node: GraphNode): void;
}

const props = withDefaults(defineProps<Props>(), {
    nodes: () => [],
    edges: () => [],
    selectedNodeId: null,
    isLoading: false,
});

const emit = defineEmits<Emits>();

const graphRef = ref<InstanceType<typeof VNetworkGraph> | null>(null);

const isEmpty = computed(
    () => props.nodes.length === 0 && !props.isLoading
);

// 计算节点度数(用于调整节点大小)
const nodeDegrees = computed(() => {
    const degrees: Record<string, number> = {};
    for (const node of props.nodes) {
        degrees[node.id] = 0;
    }
    for (const edge of props.edges) {
        if (degrees[edge.source] !== undefined) degrees[edge.source]++;
        if (degrees[edge.target] !== undefined) degrees[edge.target]++;
    }
    return degrees;
});

// 转换为 v-network-graph 格式
const graphNodes = computed(() => {
    const result: Record<string, { name: string; color: string; size: number }> = {};
    for (const node of props.nodes) {
        const degree = nodeDegrees.value[node.id] || 0;
        const entityType = node.entity_type || 'unknown';
        result[node.id] = {
            name: node.title,
            color: ENTITY_COLORS[entityType] || ENTITY_COLORS.unknown,
            size: Math.min(30, Math.max(15, 12 + degree * 2)),
        };
    }
    return result;
});

const graphEdges = computed(() => {
    const result: Record<
        string,
        { source: string; target: string; label: string }
    > = {};
    props.edges.forEach((edge, idx) => {
        const id = `${edge.source}-${edge.target}-${idx}`;
        result[id] = {
            source: edge.source,
            target: edge.target,
            label: edge.relation,
        };
    });
    return result;
});

// 布局配置
const layouts = ref({
    nodes: {} as Record<string, { x: number; y: number }>,
});

// 图谱配置
const configs = computed(() => ({
    view: {
        scalingObjects: true,
        minZoomLevel: 0.1,
        maxZoomLevel: 4,
    },
    node: {
        normal: {
            radius: (node: { size?: number }) => node.size || 20,
            color: (node: { color?: string }) => node.color || '#409eff',
        },
        hover: {
            color: '#67c23a',
        },
        selected: {
            radius: (node: { size?: number }) => (node.size || 20) + 4,
            color: '#f56c6c',
        },
        label: {
            visible: true,
            fontSize: 12,
            color: '#303133',
            direction: 'south',
            margin: 4,
        },
    },
    edge: {
        normal: {
            color: '#dcdfe6',
            width: 2,
        },
        hover: {
            color: '#409eff',
            width: 3,
        },
        label: {
            visible: false,
            fontSize: 10,
            color: '#909399',
        },
        marker: {
            target: {
                type: 'arrow' as const,
                width: 4,
                height: 4,
            },
        },
    },
}));

// 生成布局
function generateLayout(): void {
    const nodeLayouts: Record<string, { x: number; y: number }> = {};
    const nodeCount = props.nodes.length;

    if (nodeCount === 0) {
        layouts.value.nodes = nodeLayouts;
        return;
    }

    const centerX = 400;
    const centerY = 300;
    const baseRadius = Math.max(150, nodeCount * 12);

    // 按实体类型分组
    const typeGroups: Record<string, GraphNode[]> = {};
    for (const node of props.nodes) {
        const type = node.entity_type || 'unknown';
        if (!typeGroups[type]) typeGroups[type] = [];
        typeGroups[type].push(node);
    }

    // 计算每个类型的角度范围
    const types = Object.keys(typeGroups);
    const anglePerType = (2 * Math.PI) / types.length;

    let typeIndex = 0;
    for (const type of types) {
        const nodesInType = typeGroups[type];
        const typeAngleStart = typeIndex * anglePerType - Math.PI / 2;
        const angleStep = anglePerType / (nodesInType.length + 1);

        nodesInType.forEach((node, idx) => {
            const angle = typeAngleStart + (idx + 1) * angleStep;
            // 根据度数调整半径
            const degree = nodeDegrees.value[node.id] || 0;
            const radiusOffset = degree > 5 ? -30 : degree > 2 ? 0 : 30;
            const radius = baseRadius + radiusOffset;

            nodeLayouts[node.id] = {
                x: centerX + Math.cos(angle) * radius,
                y: centerY + Math.sin(angle) * radius,
            };
        });

        typeIndex++;
    }

    layouts.value.nodes = nodeLayouts;
}

// 节点点击处理
function handleNodeClick(nodeId: string): void {
    const node = props.nodes.find((n) => n.id === nodeId);
    if (node) {
        emit('node-click', node);
    }
}

// 缩放控制
function zoomIn(): void {
    graphRef.value?.zoomIn();
}

function zoomOut(): void {
    graphRef.value?.zoomOut();
}

function resetZoom(): void {
    graphRef.value?.fitToContents();
}

// 暴露方法给父组件
defineExpose({
    zoomIn,
    zoomOut,
    resetZoom,
});

// 监听节点变化重新生成布局
watch(
    () => props.nodes,
    () => {
        generateLayout();
    },
    { immediate: true }
);

onMounted(() => {
    generateLayout();
});
</script>

<style scoped>
.graph-viewer {
    width: 100%;
    height: 100%;
    min-height: 400px;
    position: relative;
}

.loading-overlay,
.empty-state {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 12px;
    color: #909399;
    background: rgba(255, 255, 255, 0.9);
}
</style>
