<template>
    <div class="graph-legend" :class="{ collapsed: isCollapsed }">
        <div class="legend-header" @click="toggleCollapse">
            <span class="legend-title">图例</span>
            <el-icon :class="{ 'rotate-180': !isCollapsed }">
                <ArrowDown />
            </el-icon>
        </div>

        <div v-show="!isCollapsed" class="legend-content">
            <!-- 实体类型图例 -->
            <div class="legend-section">
                <div class="section-title">实体类型</div>
                <div class="legend-items">
                    <div
                        v-for="(color, type) in entityColors"
                        :key="type"
                        class="legend-item"
                    >
                        <span
                            class="color-dot"
                            :style="{ backgroundColor: color }"
                        ></span>
                        <span class="type-label">{{ typeLabels[type] || type }}</span>
                    </div>
                </div>
            </div>

            <!-- 节点大小说明 -->
            <div class="legend-section">
                <div class="section-title">节点大小</div>
                <div class="size-hint">
                    <span class="size-dot small"></span>
                    <span class="size-arrow">→</span>
                    <span class="size-dot large"></span>
                    <span class="size-label">度数 (连接数)</span>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ArrowDown } from '@element-plus/icons-vue';

// 实体类型颜色映射
const entityColors: Record<string, string> = {
    location: '#67c23a',
    method: '#409eff',
    concept: '#e6a23c',
    artifact: '#909399',
    person: '#f56c6c',
    organization: '#9b59b6',
    unknown: '#c0c4cc',
};

// 实体类型中文标签
const typeLabels: Record<string, string> = {
    location: '地点',
    method: '方法',
    concept: '概念',
    artifact: '产物',
    person: '人物',
    organization: '组织',
    unknown: '未知',
};

const isCollapsed = ref(false);

function toggleCollapse(): void {
    isCollapsed.value = !isCollapsed.value;
}
</script>

<style scoped>
.graph-legend {
    position: absolute;
    left: 16px;
    bottom: 16px;
    background: rgba(255, 255, 255, 0.95);
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    padding: 12px;
    min-width: 160px;
    z-index: 10;
    transition: all 0.3s ease;
}

.graph-legend.collapsed {
    min-width: auto;
}

.legend-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    cursor: pointer;
    user-select: none;
    gap: 8px;
}

.legend-title {
    font-weight: 600;
    font-size: 14px;
    color: #303133;
}

.legend-header .el-icon {
    transition: transform 0.3s ease;
    color: #909399;
}

.legend-header .rotate-180 {
    transform: rotate(180deg);
}

.legend-content {
    margin-top: 12px;
}

.legend-section {
    margin-bottom: 12px;
}

.legend-section:last-child {
    margin-bottom: 0;
}

.section-title {
    font-size: 12px;
    color: #909399;
    margin-bottom: 8px;
}

.legend-items {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
}

.color-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    flex-shrink: 0;
}

.type-label {
    font-size: 12px;
    color: #606266;
}

.size-hint {
    display: flex;
    align-items: center;
    gap: 6px;
}

.size-dot {
    border-radius: 50%;
    background: #409eff;
}

.size-dot.small {
    width: 10px;
    height: 10px;
}

.size-dot.large {
    width: 20px;
    height: 20px;
}

.size-arrow {
    color: #909399;
    font-size: 12px;
}

.size-label {
    font-size: 12px;
    color: #606266;
    margin-left: 4px;
}
</style>
