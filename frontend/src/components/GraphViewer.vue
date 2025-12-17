<template>
    <div class="graph-viewer">
        <div v-if="isLoading" class="loading-overlay">
            <el-icon class="is-loading" :size="32"><Loading /></el-icon>
            <p>加载图谱数据...</p>
        </div>

        <div v-else-if="isEmpty" class="empty-state">
            <el-icon :size="48" color="#c0c4cc"><Share /></el-icon>
            <p>未找到相关实体,请尝试其他关键词</p>
        </div>

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
import axios from 'axios';
import { Loading, Share } from '@element-plus/icons-vue';
import type { GraphNode, GraphEdge } from '@/types/api';

interface Props {
    searchKeyword?: string;
}

interface Emits {
    (e: 'node-click', node: GraphNode): void;
}

const props = withDefaults(defineProps<Props>(), {
    searchKeyword: '',
});

const emit = defineEmits<Emits>();

const graphRef = ref<InstanceType<typeof VNetworkGraph> | null>(null);
const isLoading = ref(false);
const rawNodes = ref<GraphNode[]>([]);
const rawEdges = ref<GraphEdge[]>([]);

const isEmpty = computed(
    () => rawNodes.value.length === 0 && !isLoading.value
);

// 转换为 v-network-graph 格式
const graphNodes = computed(() => {
    const result: Record<string, { name: string }> = {};
    for (const node of rawNodes.value) {
        result[node.id] = { name: node.title };
    }
    return result;
});

const graphEdges = computed(() => {
    const result: Record<
        string,
        { source: string; target: string; label: string }
    > = {};
    rawEdges.value.forEach((edge, idx) => {
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
const configs = ref({
    node: {
        normal: {
            radius: 20,
            color: '#409eff',
        },
        hover: {
            color: '#67c23a',
        },
        label: {
            visible: true,
            fontSize: 12,
            color: '#303133',
        },
    },
    edge: {
        normal: {
            color: '#c0c4cc',
            width: 2,
        },
        label: {
            visible: true,
            fontSize: 10,
            color: '#909399',
        },
        marker: {
            target: {
                type: 'arrow' as const,
            },
        },
    },
});

/** 加载图谱数据 */
async function loadGraph(keyword: string): Promise<void> {
    // 允许空关键词加载全部图谱
    isLoading.value = true;
    try {
        const { data } = await axios.get('/api/v1/graph/query', {
            params: { q: keyword },
        });

        rawNodes.value = data.nodes || [];
        rawEdges.value = data.edges || [];

        // 生成圆形布局
        const nodeLayouts: Record<string, { x: number; y: number }> = {};
        const nodeCount = rawNodes.value.length;
        const centerX = 300;
        const centerY = 250;
        const radius = Math.max(100, nodeCount * 15);

        rawNodes.value.forEach((node, idx) => {
            const angle = (idx / nodeCount) * 2 * Math.PI - Math.PI / 2;
            nodeLayouts[node.id] = {
                x: centerX + Math.cos(angle) * radius,
                y: centerY + Math.sin(angle) * radius,
            };
        });
        layouts.value.nodes = nodeLayouts;
    } catch (error) {
        console.error('加载图谱失败:', error);
        rawNodes.value = [];
        rawEdges.value = [];
    } finally {
        isLoading.value = false;
    }
}

/** 节点点击处理 */
function handleNodeClick(nodeId: string): void {
    const node = rawNodes.value.find((n) => n.id === nodeId);
    if (node) {
        emit('node-click', node);
    }
}

// 监听关键词变化
watch(
    () => props.searchKeyword,
    (newKeyword) => {
        if (newKeyword) {
            loadGraph(newKeyword);
        }
    }
);

onMounted(() => {
    // 初始加载：如果没有关键词，使用空字符串获取全部图谱
    loadGraph(props.searchKeyword || '');
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
