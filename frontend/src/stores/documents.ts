/**
 * 文档状态管理 (Pinia Store)
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { DocumentListItem, DocumentStatusResponse } from '@/types/api';
import {
    fetchDocuments,
    fetchDocumentStatus,
    deleteDocument as apiDeleteDocument,
} from '@/api/documents';

export const useDocumentsStore = defineStore('documents', () => {
    // ========== State ==========
    const documents = ref<DocumentListItem[]>([]);
    const total = ref(0);
    const currentPage = ref(1);
    const pageSize = ref(20);
    const keyword = ref('');
    const isLoading = ref(false);
    const error = ref<string | null>(null);

    // 轮询相关
    let pollingTimer: ReturnType<typeof setInterval> | null = null;
    const pollingInterval = 3000; // 3秒

    // ========== Getters ==========
    const hasPendingDocuments = computed(() => {
        return documents.value.some(
            (doc) => doc.status === 'PENDING' || doc.status === 'PROCESSING'
        );
    });

    const stats = computed(() => {
        const completed = documents.value.filter(
            (d) => d.status === 'COMPLETED'
        ).length;
        const processing = documents.value.filter(
            (d) => d.status === 'PROCESSING' || d.status === 'PENDING'
        ).length;
        const failed = documents.value.filter(
            (d) => d.status === 'FAILED'
        ).length;
        return { completed, processing, failed, total: total.value };
    });

    const isEmpty = computed(() => {
        return documents.value.length === 0 && !isLoading.value;
    });

    // ========== Actions ==========

    /**
     * 加载文档列表
     */
    async function loadDocuments(
        page: number = currentPage.value,
        size: number = pageSize.value,
        search: string = keyword.value
    ): Promise<void> {
        isLoading.value = true;
        error.value = null;

        try {
            const response = await fetchDocuments(page, size, search);
            documents.value = response.items;
            total.value = response.total;
            currentPage.value = page;
            pageSize.value = size;
            keyword.value = search;

            // 检查是否需要启动轮询
            if (hasPendingDocuments.value) {
                startPolling();
            } else {
                stopPolling();
            }
        } catch (e) {
            error.value = e instanceof Error ? e.message : '加载文档列表失败';
            console.error('加载文档列表失败:', e);
        } finally {
            isLoading.value = false;
        }
    }

    /**
     * 刷新单个文档状态
     */
    async function refreshDocument(docId: number): Promise<DocumentStatusResponse | null> {
        try {
            const status = await fetchDocumentStatus(docId);
            // 更新本地文档列表中的对应项
            const index = documents.value.findIndex((d) => d.id === docId);
            if (index !== -1) {
                documents.value[index] = {
                    ...documents.value[index],
                    status: status.status,
                    error_message: status.error_message,
                    updated_at: status.updated_at,
                };
            }
            return status;
        } catch (e) {
            console.error(`刷新文档状态失败 | doc_id: ${docId}`, e);
            return null;
        }
    }

    /**
     * 刷新所有处理中的文档状态
     */
    async function refreshPendingDocuments(): Promise<void> {
        const pendingDocs = documents.value.filter(
            (d) => d.status === 'PENDING' || d.status === 'PROCESSING'
        );

        if (pendingDocs.length === 0) {
            stopPolling();
            return;
        }

        // 并行刷新所有处理中的文档
        await Promise.all(pendingDocs.map((d) => refreshDocument(d.id)));

        // 检查是否还有处理中的文档
        if (!hasPendingDocuments.value) {
            stopPolling();
        }
    }

    /**
     * 删除文档
     */
    async function deleteDocument(docId: number): Promise<boolean> {
        try {
            await apiDeleteDocument(docId);
            // 从本地列表中移除
            documents.value = documents.value.filter((d) => d.id !== docId);
            total.value = Math.max(0, total.value - 1);
            return true;
        } catch (e) {
            console.error(`删除文档失败 | doc_id: ${docId}`, e);
            throw e;
        }
    }

    /**
     * 启动轮询
     */
    function startPolling(): void {
        if (pollingTimer) return; // 已经在轮询

        pollingTimer = setInterval(() => {
            refreshPendingDocuments();
        }, pollingInterval);
    }

    /**
     * 停止轮询
     */
    function stopPolling(): void {
        if (pollingTimer) {
            clearInterval(pollingTimer);
            pollingTimer = null;
        }
    }

    /**
     * 搜索文档
     */
    async function searchDocuments(searchKeyword: string): Promise<void> {
        keyword.value = searchKeyword;
        currentPage.value = 1;
        await loadDocuments(1, pageSize.value, searchKeyword);
    }

    /**
     * 切换页码
     */
    async function changePage(page: number): Promise<void> {
        await loadDocuments(page, pageSize.value, keyword.value);
    }

    /**
     * 切换每页数量
     */
    async function changePageSize(size: number): Promise<void> {
        await loadDocuments(1, size, keyword.value);
    }

    /**
     * 重置状态
     */
    function reset(): void {
        stopPolling();
        documents.value = [];
        total.value = 0;
        currentPage.value = 1;
        pageSize.value = 20;
        keyword.value = '';
        isLoading.value = false;
        error.value = null;
    }

    return {
        // State
        documents,
        total,
        currentPage,
        pageSize,
        keyword,
        isLoading,
        error,

        // Getters
        hasPendingDocuments,
        stats,
        isEmpty,

        // Actions
        loadDocuments,
        refreshDocument,
        refreshPendingDocuments,
        deleteDocument,
        searchDocuments,
        changePage,
        changePageSize,
        startPolling,
        stopPolling,
        reset,
    };
});
