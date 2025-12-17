<template>
    <div class="graph-page">
        <div class="graph-header">
            <el-input
                v-model="searchKeyword"
                placeholder="输入关键词搜索实体..."
                clearable
                style="width: 300px"
                @keydown.enter="handleSearch"
            >
                <template #prefix>
                    <el-icon><Search /></el-icon>
                </template>
            </el-input>
            <el-button type="primary" :loading="isLoading" @click="handleSearch">
                搜索
            </el-button>
            <el-button @click="handleLoadAll">
                加载全部
            </el-button>
        </div>

        <div class="graph-container">
            <GraphViewer
                :search-keyword="currentKeyword"
                @node-click="handleNodeClick"
            />
        </div>

        <!-- 节点详情抽屉 -->
        <el-drawer
            v-model="drawerVisible"
            :title="selectedNode?.title || '节点详情'"
            size="400px"
        >
            <div v-if="selectedNode" class="node-detail">
                <el-descriptions :column="1" border>
                    <el-descriptions-item label="ID">
                        {{ selectedNode.id }}
                    </el-descriptions-item>
                    <el-descriptions-item label="名称">
                        {{ selectedNode.title }}
                    </el-descriptions-item>
                    <el-descriptions-item
                        v-if="selectedNode.description"
                        label="描述"
                    >
                        {{ selectedNode.description }}
                    </el-descriptions-item>
                </el-descriptions>
            </div>
        </el-drawer>
    </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { Search } from '@element-plus/icons-vue';
import GraphViewer from '@/components/GraphViewer.vue';
import type { GraphNode } from '@/types/api';

const searchKeyword = ref('');
const currentKeyword = ref('');  // 初始为空，自动加载全部图谱
const isLoading = ref(false);
const drawerVisible = ref(false);
const selectedNode = ref<GraphNode | null>(null);

function handleSearch(): void {
    currentKeyword.value = searchKeyword.value.trim();
}

function handleLoadAll(): void {
    searchKeyword.value = '';
    currentKeyword.value = '';  // 空关键词触发加载全部
}

function handleNodeClick(node: GraphNode): void {
    selectedNode.value = node;
    drawerVisible.value = true;
}
</script>

<style scoped>
.graph-page {
    display: flex;
    flex-direction: column;
    height: calc(100vh - 100px);
}

.graph-header {
    display: flex;
    gap: 12px;
    margin-bottom: 16px;
}

.graph-container {
    flex: 1;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    overflow: hidden;
}

.node-detail {
    padding: 16px;
}
</style>
