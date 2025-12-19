<template>
    <el-dialog
        v-model="visible"
        title="上传文档"
        width="600px"
        :close-on-click-modal="!isUploading"
        :close-on-press-escape="!isUploading"
        @close="handleClose"
    >
        <!-- 拖拽上传区域 -->
        <el-upload
            ref="uploadRef"
            drag
            multiple
            :auto-upload="false"
            :file-list="fileList"
            :limit="10"
            accept=".pdf"
            :disabled="isUploading"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            :on-exceed="handleExceed"
        >
            <el-icon class="upload-icon" :size="48"><UploadFilled /></el-icon>
            <div class="upload-text">
                拖拽文件到此处，或 <em>点击上传</em>
            </div>
            <template #tip>
                <div class="upload-tip">仅支持 PDF 文件，单次最多上传 10 个</div>
            </template>
        </el-upload>

        <!-- 上传进度 -->
        <div v-if="isUploading" class="upload-progress">
            <div class="progress-header">
                <span>上传进度</span>
                <span>{{ completedCount }} / {{ totalCount }}</span>
            </div>
            <el-progress
                :percentage="overallProgress"
                :status="progressStatus"
            />
            <div class="current-file" v-if="currentFileName">
                正在上传: {{ currentFileName }}
            </div>
        </div>

        <!-- 上传结果 -->
        <div v-if="uploadResults.length > 0" class="upload-results">
            <div class="results-header">上传结果</div>
            <div
                v-for="result in uploadResults"
                :key="result.filename"
                class="result-item"
                :class="{ 'result-error': result.error }"
            >
                <el-icon v-if="result.error" color="#f56c6c"><CircleClose /></el-icon>
                <el-icon v-else color="#67c23a"><CircleCheck /></el-icon>
                <span class="result-filename">{{ result.filename }}</span>
                <span v-if="result.error" class="result-error-msg">{{ result.error }}</span>
            </div>
        </div>

        <template #footer>
            <el-button @click="handleClose" :disabled="isUploading">
                {{ isUploading ? '上传中...' : '关闭' }}
            </el-button>
            <el-button
                type="primary"
                :loading="isUploading"
                :disabled="fileList.length === 0 || isUploading"
                @click="handleUpload"
            >
                {{ isUploading ? '上传中...' : '开始上传' }}
            </el-button>
        </template>
    </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { ElMessage } from 'element-plus';
import {
    UploadFilled,
    CircleCheck,
    CircleClose,
} from '@element-plus/icons-vue';
import type { UploadFile, UploadInstance, UploadRawFile } from 'element-plus';
import { uploadFile } from '@/api/documents';

interface Props {
    modelValue: boolean;
}

interface Emits {
    (e: 'update:modelValue', value: boolean): void;
    (e: 'success'): void;
}

interface UploadResult {
    filename: string;
    error?: string;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const uploadRef = ref<UploadInstance | null>(null);
const fileList = ref<UploadFile[]>([]);
const isUploading = ref(false);
const currentFileIndex = ref(0);
const currentFileProgress = ref(0);
const currentFileName = ref('');
const uploadResults = ref<UploadResult[]>([]);

const visible = computed({
    get: () => props.modelValue,
    set: (value) => emit('update:modelValue', value),
});

const totalCount = computed(() => fileList.value.length);
const completedCount = computed(() => uploadResults.value.length);

const overallProgress = computed(() => {
    if (totalCount.value === 0) return 0;
    const completedProgress = completedCount.value * 100;
    const currentProgress = currentFileProgress.value;
    return Math.round((completedProgress + currentProgress) / totalCount.value);
});

const progressStatus = computed(() => {
    if (uploadResults.value.some((r) => r.error)) {
        return 'exception';
    }
    if (overallProgress.value >= 100) {
        return 'success';
    }
    return undefined;
});

// 监听对话框关闭时重置状态
watch(visible, (newValue) => {
    if (!newValue) {
        resetState();
    }
});

function handleFileChange(file: UploadFile, files: UploadFile[]): void {
    // 验证文件类型
    if (file.raw && !file.raw.name.toLowerCase().endsWith('.pdf')) {
        ElMessage.warning('仅支持 PDF 文件');
        fileList.value = files.filter((f) => f.uid !== file.uid);
        return;
    }
    fileList.value = files;
}

function handleFileRemove(file: UploadFile, files: UploadFile[]): void {
    fileList.value = files;
}

function handleExceed(): void {
    ElMessage.warning('单次最多上传 10 个文件');
}

async function handleUpload(): Promise<void> {
    if (fileList.value.length === 0) return;

    isUploading.value = true;
    uploadResults.value = [];
    currentFileIndex.value = 0;
    currentFileProgress.value = 0;

    let successCount = 0;
    let failCount = 0;

    for (let i = 0; i < fileList.value.length; i++) {
        const file = fileList.value[i];
        if (!file.raw) continue;

        currentFileIndex.value = i;
        currentFileName.value = file.name;
        currentFileProgress.value = 0;

        try {
            await uploadFile(file.raw as File, (percent) => {
                currentFileProgress.value = percent;
            });
            uploadResults.value.push({ filename: file.name });
            successCount++;
        } catch (error) {
            const errorMsg = error instanceof Error ? error.message : '上传失败';
            uploadResults.value.push({ filename: file.name, error: errorMsg });
            failCount++;
        }
    }

    currentFileName.value = '';
    currentFileProgress.value = 100;
    isUploading.value = false;

    // 显示结果消息
    if (failCount === 0) {
        ElMessage.success(`成功上传 ${successCount} 个文件`);
        emit('success');
    } else if (successCount === 0) {
        ElMessage.error(`上传失败: ${failCount} 个文件`);
    } else {
        ElMessage.warning(`上传完成: ${successCount} 成功, ${failCount} 失败`);
        emit('success');
    }
}

function handleClose(): void {
    if (isUploading.value) {
        ElMessage.warning('上传进行中，请等待完成');
        return;
    }
    visible.value = false;
}

function resetState(): void {
    fileList.value = [];
    isUploading.value = false;
    currentFileIndex.value = 0;
    currentFileProgress.value = 0;
    currentFileName.value = '';
    uploadResults.value = [];
    uploadRef.value?.clearFiles();
}
</script>

<style scoped>
.upload-icon {
    color: #c0c4cc;
    margin-bottom: 8px;
}

.upload-text {
    color: #606266;
    font-size: 14px;
}

.upload-text em {
    color: #409eff;
    font-style: normal;
}

.upload-tip {
    font-size: 12px;
    color: #909399;
    margin-top: 8px;
}

.upload-progress {
    margin-top: 20px;
    padding: 16px;
    background: #f5f7fa;
    border-radius: 8px;
}

.progress-header {
    display: flex;
    justify-content: space-between;
    margin-bottom: 12px;
    font-size: 14px;
    color: #606266;
}

.current-file {
    margin-top: 8px;
    font-size: 12px;
    color: #909399;
}

.upload-results {
    margin-top: 16px;
    max-height: 200px;
    overflow-y: auto;
}

.results-header {
    font-size: 14px;
    font-weight: 500;
    color: #303133;
    margin-bottom: 12px;
}

.result-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: #f0f9eb;
    border-radius: 4px;
    margin-bottom: 8px;
    font-size: 13px;
}

.result-item.result-error {
    background: #fef0f0;
}

.result-filename {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.result-error-msg {
    color: #f56c6c;
    font-size: 12px;
}
</style>
