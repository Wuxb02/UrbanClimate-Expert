<template>
    <div class="graph-toolbar">
        <!-- 搜索框 -->
        <el-input
            v-model="searchInput"
            placeholder="输入关键词搜索实体..."
            clearable
            class="search-input"
            @keydown.enter="handleSearch"
            @clear="handleClear"
        >
            <template #prefix>
                <el-icon><Search /></el-icon>
            </template>
        </el-input>

        <!-- 实体类型过滤 -->
        <el-select
            v-model="selectedEntityType"
            placeholder="实体类型"
            clearable
            class="type-filter"
            @change="handleTypeChange"
        >
            <el-option
                v-for="option in entityTypeOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
            />
        </el-select>

        <!-- 搜索按钮 -->
        <el-button
            type="primary"
            :loading="isLoading"
            @click="handleSearch"
        >
            搜索
        </el-button>

        <!-- 加载全部按钮 -->
        <el-button @click="handleLoadAll">
            加载全部
        </el-button>

        <!-- 分隔线 -->
        <el-divider direction="vertical" />

        <!-- 缩放控制 -->
        <el-button-group class="zoom-controls">
            <el-tooltip content="放大" placement="top">
                <el-button :icon="ZoomIn" @click="$emit('zoom', 'in')" />
            </el-tooltip>
            <el-tooltip content="缩小" placement="top">
                <el-button :icon="ZoomOut" @click="$emit('zoom', 'out')" />
            </el-tooltip>
            <el-tooltip content="重置缩放" placement="top">
                <el-button :icon="RefreshRight" @click="$emit('zoom', 'reset')" />
            </el-tooltip>
        </el-button-group>

        <!-- 统计信息 -->
        <div class="stats-info" v-if="stats">
            <el-tag type="info" effect="plain" size="small">
                节点: {{ stats.total_nodes }}
            </el-tag>
            <el-tag type="info" effect="plain" size="small">
                边: {{ stats.total_edges }}
            </el-tag>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue';
import {
    Search,
    ZoomIn,
    ZoomOut,
    RefreshRight,
} from '@element-plus/icons-vue';
import type { GraphStats } from '@/types/api';

interface Props {
    keyword?: string;
    entityType?: string;
    stats?: GraphStats | null;
    isLoading?: boolean;
    entityTypeOptions?: { label: string; value: string }[];
}

interface Emits {
    (e: 'update:keyword', value: string): void;
    (e: 'update:entityType', value: string | undefined): void;
    (e: 'search'): void;
    (e: 'loadAll'): void;
    (e: 'zoom', action: 'in' | 'out' | 'reset'): void;
}

const props = withDefaults(defineProps<Props>(), {
    keyword: '',
    entityType: undefined,
    stats: null,
    isLoading: false,
    entityTypeOptions: () => [],
});

const emit = defineEmits<Emits>();

const searchInput = ref(props.keyword);
const selectedEntityType = ref<string | undefined>(props.entityType);

// 监听 props 变化
watch(
    () => props.keyword,
    (newVal) => {
        searchInput.value = newVal;
    }
);

watch(
    () => props.entityType,
    (newVal) => {
        selectedEntityType.value = newVal;
    }
);

function handleSearch(): void {
    emit('update:keyword', searchInput.value);
    emit('search');
}

function handleClear(): void {
    searchInput.value = '';
    emit('update:keyword', '');
    emit('search');
}

function handleTypeChange(value: string | undefined): void {
    emit('update:entityType', value || undefined);
    emit('search');
}

function handleLoadAll(): void {
    searchInput.value = '';
    selectedEntityType.value = undefined;
    emit('update:keyword', '');
    emit('update:entityType', undefined);
    emit('loadAll');
}
</script>

<style scoped>
.graph-toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    flex-wrap: wrap;
}

.search-input {
    width: 280px;
}

.type-filter {
    width: 160px;
}

.zoom-controls {
    display: flex;
}

.stats-info {
    display: flex;
    gap: 8px;
    margin-left: auto;
}

@media (max-width: 1024px) {
    .graph-toolbar {
        flex-wrap: wrap;
    }

    .search-input {
        width: 100%;
        order: 1;
    }

    .type-filter {
        flex: 1;
        order: 2;
    }

    .stats-info {
        width: 100%;
        justify-content: flex-end;
        order: 10;
        margin-top: 8px;
    }
}
</style>
