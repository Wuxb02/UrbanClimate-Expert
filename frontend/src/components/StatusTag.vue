<template>
    <el-tag :type="tagType" :effect="effect" class="status-tag">
        <el-icon v-if="status === 'PROCESSING' || status === 'PENDING'" class="is-loading">
            <Loading />
        </el-icon>
        <el-icon v-else-if="status === 'COMPLETED'">
            <CircleCheck />
        </el-icon>
        <el-icon v-else-if="status === 'FAILED'">
            <CircleClose />
        </el-icon>
        <span class="status-text">{{ statusText }}</span>
    </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { Loading, CircleCheck, CircleClose } from '@element-plus/icons-vue';
import type { DocumentStatus } from '@/types/api';

interface Props {
    status: DocumentStatus;
    effect?: 'dark' | 'light' | 'plain';
}

const props = withDefaults(defineProps<Props>(), {
    effect: 'light',
});

const tagType = computed(() => {
    const typeMap: Record<DocumentStatus, 'success' | 'warning' | 'info' | 'danger' | ''> = {
        COMPLETED: 'success',
        PROCESSING: '',      // primary (default)
        PENDING: 'info',
        FAILED: 'danger',
    };
    return typeMap[props.status] || 'info';
});

const statusText = computed(() => {
    const textMap: Record<DocumentStatus, string> = {
        COMPLETED: '已完成',
        PROCESSING: '处理中',
        PENDING: '等待中',
        FAILED: '失败',
    };
    return textMap[props.status] || props.status;
});
</script>

<style scoped>
.status-tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
}

.status-text {
    font-size: 12px;
}
</style>
