<template>
    <div class="documents-page">
        <!-- 工具栏 -->
        <div class="toolbar">
            <el-input
                v-model="searchKeyword"
                placeholder="搜索文件名..."
                clearable
                class="search-input"
                @keydown.enter="handleSearch"
                @clear="handleSearch"
            >
                <template #prefix>
                    <el-icon><Search /></el-icon>
                </template>
            </el-input>

            <el-button :icon="Refresh" @click="handleRefresh" :loading="documentsStore.isLoading">
                刷新
            </el-button>

            <el-button type="primary" :icon="Upload" @click="showUploadDialog = true">
                上传文档
            </el-button>
        </div>

        <!-- 统计信息 -->
        <div class="stats-bar">
            <el-tag type="info" effect="plain">
                共 {{ documentsStore.stats.total }} 个文档
            </el-tag>
            <el-tag type="success" effect="plain">
                已完成 {{ documentsStore.stats.completed }}
            </el-tag>
            <el-tag type="primary" effect="plain" v-if="documentsStore.stats.processing > 0">
                处理中 {{ documentsStore.stats.processing }}
            </el-tag>
            <el-tag type="danger" effect="plain" v-if="documentsStore.stats.failed > 0">
                失败 {{ documentsStore.stats.failed }}
            </el-tag>
        </div>

        <!-- 文档表格 -->
        <div class="table-container">
            <el-table
                :data="documentsStore.documents"
                v-loading="documentsStore.isLoading"
                stripe
                style="width: 100%"
            >
                <el-table-column prop="id" label="ID" width="80" />

                <el-table-column prop="filename" label="文件名" min-width="180">
                    <template #default="{ row }">
                        <div class="filename-cell">
                            <el-icon><Document /></el-icon>
                            <span class="filename-text" :title="row.filename">
                                {{ row.filename }}
                            </span>
                        </div>
                    </template>
                </el-table-column>

                <el-table-column prop="summary" label="摘要" min-width="250">
                    <template #default="{ row }">
                        <el-tooltip
                            v-if="row.summary"
                            :content="row.summary"
                            placement="top"
                            :show-after="300"
                        >
                            <span class="summary-text">{{ row.summary }}</span>
                        </el-tooltip>
                        <span v-else class="summary-empty">
                            {{ row.status === 'COMPLETED' ? '暂无摘要' : '-' }}
                        </span>
                    </template>
                </el-table-column>

                <el-table-column prop="filesize" label="文件大小" width="100">
                    <template #default="{ row }">
                        {{ formatFileSize(row.filesize) }}
                    </template>
                </el-table-column>

                <el-table-column prop="status" label="状态" width="120">
                    <template #default="{ row }">
                        <StatusTag :status="row.status" />
                    </template>
                </el-table-column>

                <el-table-column prop="created_at" label="上传时间" width="180">
                    <template #default="{ row }">
                        {{ formatDateTime(row.created_at) }}
                    </template>
                </el-table-column>

                <el-table-column label="操作" width="200" fixed="right">
                    <template #default="{ row }">
                        <div class="action-buttons">
                            <el-button
                                type="primary"
                                link
                                :icon="Download"
                                :disabled="row.status !== 'COMPLETED'"
                                @click="handleDownload(row.id, row.filename)"
                            >
                                下载
                            </el-button>
                            <el-button
                                type="warning"
                                link
                                :icon="EditPen"
                                @click="openRenameDialog(row)"
                            >
                                重命名
                            </el-button>
                            <el-popconfirm
                                title="确定要删除这个文档吗？"
                                confirm-button-text="删除"
                                cancel-button-text="取消"
                                @confirm="handleDelete(row.id)"
                            >
                                <template #reference>
                                    <el-button
                                        type="danger"
                                        link
                                        :icon="Delete"
                                        :loading="deletingIds.has(row.id)"
                                    >
                                        删除
                                    </el-button>
                                </template>
                            </el-popconfirm>
                        </div>
                    </template>
                </el-table-column>
            </el-table>

            <!-- 空状态 -->
            <el-empty
                v-if="documentsStore.isEmpty"
                description="暂无文档，点击上方按钮上传"
            />
        </div>

        <!-- 分页 -->
        <div class="pagination-container" v-if="documentsStore.total > 0">
            <el-pagination
                v-model:current-page="currentPage"
                v-model:page-size="currentPageSize"
                :page-sizes="[10, 20, 50, 100]"
                :total="documentsStore.total"
                layout="total, sizes, prev, pager, next, jumper"
                @size-change="handlePageSizeChange"
                @current-change="handlePageChange"
            />
        </div>

        <!-- 上传对话框 -->
        <UploadDialog
            v-model="showUploadDialog"
            @success="handleUploadSuccess"
        />

        <!-- 重命名对话框 -->
        <el-dialog
            v-model="showRenameDialog"
            title="重命名文档"
            width="400px"
            :close-on-click-modal="!isRenaming"
        >
            <el-form @submit.prevent="handleRename">
                <el-form-item label="新文件名">
                    <el-input
                        v-model="newFilename"
                        placeholder="请输入新文件名"
                        :disabled="isRenaming"
                    />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="showRenameDialog = false" :disabled="isRenaming">
                    取消
                </el-button>
                <el-button
                    type="primary"
                    @click="handleRename"
                    :loading="isRenaming"
                    :disabled="!newFilename.trim()"
                >
                    确定
                </el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import { ElMessage } from 'element-plus';
import {
    Search,
    Refresh,
    Upload,
    Delete,
    Document,
    Download,
    EditPen,
} from '@element-plus/icons-vue';
import StatusTag from '@/components/StatusTag.vue';
import UploadDialog from '@/components/UploadDialog.vue';
import { useDocumentsStore } from '@/stores/documents';
import { getDocumentDownloadUrl, renameDocument } from '@/api/documents';
import type { DocumentListItem } from '@/types/api';

const documentsStore = useDocumentsStore();

const searchKeyword = ref('');
const showUploadDialog = ref(false);
const deletingIds = ref<Set<number>>(new Set());
const currentPage = ref(1);
const currentPageSize = ref(20);

// 重命名相关状态
const showRenameDialog = ref(false);
const isRenaming = ref(false);
const renameDocId = ref<number | null>(null);
const newFilename = ref('');

// 格式化文件大小
function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 格式化日期时间
function formatDateTime(dateStr: string): string {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
}

// 搜索处理
function handleSearch(): void {
    documentsStore.searchDocuments(searchKeyword.value);
}

// 刷新处理
function handleRefresh(): void {
    documentsStore.loadDocuments();
}

// 删除处理
async function handleDelete(docId: number): Promise<void> {
    deletingIds.value.add(docId);
    try {
        await documentsStore.deleteDocument(docId);
        ElMessage.success('文档删除成功');
    } catch (error) {
        ElMessage.error('删除失败，请重试');
    } finally {
        deletingIds.value.delete(docId);
    }
}

// 上传成功处理
function handleUploadSuccess(): void {
    documentsStore.loadDocuments();
}

// 下载处理
function handleDownload(docId: number, filename: string): void {
    const url = getDocumentDownloadUrl(docId);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// 打开重命名对话框
function openRenameDialog(doc: DocumentListItem): void {
    renameDocId.value = doc.id;
    // 去掉 .pdf 后缀方便编辑
    newFilename.value = doc.filename.replace(/\.pdf$/i, '');
    showRenameDialog.value = true;
}

// 重命名处理
async function handleRename(): Promise<void> {
    if (!renameDocId.value || !newFilename.value.trim()) return;

    isRenaming.value = true;
    try {
        await renameDocument(renameDocId.value, newFilename.value.trim());
        ElMessage.success('重命名成功');
        showRenameDialog.value = false;
        documentsStore.loadDocuments();
    } catch (error) {
        ElMessage.error('重命名失败，请重试');
    } finally {
        isRenaming.value = false;
    }
}

// 分页处理
function handlePageChange(page: number): void {
    currentPage.value = page;
    documentsStore.changePage(page);
}

function handlePageSizeChange(size: number): void {
    currentPageSize.value = size;
    documentsStore.changePageSize(size);
}

// 生命周期
onMounted(() => {
    documentsStore.loadDocuments();
});

onUnmounted(() => {
    documentsStore.stopPolling();
});
</script>

<style scoped>
.documents-page {
    display: flex;
    flex-direction: column;
    gap: 16px;
    height: calc(100vh - 100px);
}

.toolbar {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 16px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.search-input {
    width: 300px;
}

.stats-bar {
    display: flex;
    gap: 12px;
    padding: 12px 16px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.table-container {
    flex: 1;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
    padding: 16px;
    overflow: auto;
}

.filename-cell {
    display: flex;
    align-items: center;
    gap: 8px;
}

.filename-text {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.summary-text {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    text-overflow: ellipsis;
    font-size: 13px;
    color: #606266;
    line-height: 1.4;
    cursor: pointer;
}

.summary-empty {
    color: #909399;
    font-size: 13px;
}

.action-buttons {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
}

.pagination-container {
    display: flex;
    justify-content: flex-end;
    padding: 16px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

@media (max-width: 768px) {
    .toolbar {
        flex-wrap: wrap;
    }

    .search-input {
        width: 100%;
        order: 1;
    }

    .stats-bar {
        flex-wrap: wrap;
    }
}
</style>
