<template>
    <div class="node-detail">
        <!-- 加载状态 -->
        <div v-if="isLoading" class="loading-state">
            <el-skeleton :rows="5" animated />
        </div>

        <!-- 详情内容 -->
        <template v-else-if="detail">
            <!-- 关闭按钮 -->
            <div class="detail-header">
                <h3 class="detail-title">{{ detail.title }}</h3>
                <el-button
                    type="default"
                    :icon="Close"
                    circle
                    size="small"
                    @click="$emit('close')"
                />
            </div>

            <!-- 基础信息 -->
            <el-descriptions :column="1" border size="small" class="info-section">
                <el-descriptions-item label="ID">
                    <el-text truncated>{{ detail.id }}</el-text>
                </el-descriptions-item>
                <el-descriptions-item label="类型">
                    <el-tag :type="getTagType(detail.entity_type)" size="small">
                        {{ getTypeLabel(detail.entity_type) }}
                    </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="度数">
                    <span class="degree-info">
                        总: {{ detail.degree }}
                        <el-divider direction="vertical" />
                        入: {{ detail.in_degree }}
                        <el-divider direction="vertical" />
                        出: {{ detail.out_degree }}
                    </span>
                </el-descriptions-item>
            </el-descriptions>

            <!-- 描述 -->
            <div class="section" v-if="detail.description">
                <h4 class="section-title">描述</h4>
                <p class="description-text">{{ detail.description }}</p>
            </div>

            <!-- 关联文档 -->
            <div class="section" v-if="detail.snippets && detail.snippets.length > 0">
                <h4 class="section-title">
                    关联文档
                    <el-tag size="small" type="info">
                        {{ detail.snippets.length }}
                    </el-tag>
                </h4>
                <el-collapse accordion class="snippets-collapse">
                    <el-collapse-item
                        v-for="snippet in detail.snippets"
                        :key="snippet.chunk_id"
                        :name="snippet.chunk_id"
                    >
                        <template #title>
                            <div class="snippet-title">
                                <el-icon><Document /></el-icon>
                                <span>{{ snippet.filename }}</span>
                            </div>
                        </template>
                        <p class="snippet-text">{{ snippet.text }}</p>
                    </el-collapse-item>
                </el-collapse>
            </div>

            <!-- 邻居节点 -->
            <div class="section" v-if="detail.neighbors && detail.neighbors.length > 0">
                <h4 class="section-title">
                    邻居节点
                    <el-tag size="small" type="info">
                        {{ detail.neighbors.length }}
                    </el-tag>
                </h4>
                <div class="neighbors-list">
                    <el-tag
                        v-for="neighborId in displayedNeighbors"
                        :key="neighborId"
                        class="neighbor-tag"
                        effect="plain"
                        @click="handleNavigate(neighborId)"
                    >
                        {{ neighborId }}
                    </el-tag>
                    <el-button
                        v-if="detail.neighbors.length > maxDisplayNeighbors"
                        type="primary"
                        link
                        size="small"
                        @click="showAllNeighbors = !showAllNeighbors"
                    >
                        {{ showAllNeighbors
                            ? '收起'
                            : `显示全部 (${detail.neighbors.length})` }}
                    </el-button>
                </div>
            </div>
        </template>

        <!-- 空状态 -->
        <el-empty v-else description="请选择一个节点" :image-size="80" />
    </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { Close, Document } from '@element-plus/icons-vue';
import type { GraphNodeDetail } from '@/types/api';

interface Props {
    detail: GraphNodeDetail | null;
    isLoading?: boolean;
}

interface Emits {
    (e: 'navigate', nodeId: string): void;
    (e: 'close'): void;
}

const props = withDefaults(defineProps<Props>(), {
    isLoading: false,
});

const emit = defineEmits<Emits>();

const maxDisplayNeighbors = 20;
const showAllNeighbors = ref(false);

const displayedNeighbors = computed(() => {
    if (!props.detail?.neighbors) return [];
    if (showAllNeighbors.value) return props.detail.neighbors;
    return props.detail.neighbors.slice(0, maxDisplayNeighbors);
});

// 实体类型标签映射
const typeLabels: Record<string, string> = {
    location: '地点',
    method: '方法',
    concept: '概念',
    artifact: '产物',
    person: '人物',
    organization: '组织',
    unknown: '未知',
};

function getTypeLabel(type: string): string {
    return typeLabels[type] || type;
}

function getTagType(entityType: string): 'success' | 'warning' | 'info' | 'danger' | '' {
    const typeMap: Record<string, 'success' | 'warning' | 'info' | 'danger' | ''> = {
        location: 'success',
        method: '',
        concept: 'warning',
        artifact: 'info',
        person: 'danger',
        organization: '',
    };
    return typeMap[entityType] || 'info';
}

function handleNavigate(nodeId: string): void {
    emit('navigate', nodeId);
}
</script>

<style scoped>
.node-detail {
    height: 100%;
    overflow-y: auto;
    padding: 16px;
}

.loading-state {
    padding: 20px 0;
}

.detail-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 16px;
}

.detail-title {
    margin: 0;
    font-size: 18px;
    font-weight: 600;
    color: #303133;
    word-break: break-all;
}

.info-section {
    margin-bottom: 16px;
}

.degree-info {
    font-size: 13px;
    color: #606266;
}

.section {
    margin-bottom: 16px;
}

.section-title {
    display: flex;
    align-items: center;
    gap: 8px;
    margin: 0 0 12px 0;
    font-size: 14px;
    font-weight: 600;
    color: #303133;
}

.description-text {
    margin: 0;
    font-size: 13px;
    line-height: 1.6;
    color: #606266;
    white-space: pre-wrap;
    word-break: break-word;
}

.snippets-collapse {
    border: none;
}

.snippets-collapse :deep(.el-collapse-item__header) {
    height: auto;
    min-height: 40px;
    padding: 8px 0;
    line-height: 1.4;
}

.snippet-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #409eff;
}

.snippet-text {
    margin: 0;
    font-size: 12px;
    line-height: 1.6;
    color: #606266;
    max-height: 200px;
    overflow-y: auto;
}

.neighbors-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.neighbor-tag {
    cursor: pointer;
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
}

.neighbor-tag:hover {
    background-color: #ecf5ff;
    border-color: #409eff;
    color: #409eff;
}
</style>
