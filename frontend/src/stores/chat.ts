/**
 * 聊天状态管理 (Pinia Store)
 *
 * 状态:
 * - messages: 消息列表
 * - isLoading: 是否正在加载
 * - currentBuffer: 当前流式回答的累积内容
 * - error: 错误信息
 *
 * 操作:
 * - sendMessage: 发送消息并获取流式回答
 * - clearMessages: 清空消息
 * - abortStream: 中断当前流式请求
 */
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';
import type { ChatMessage, ChatChunk, Citation } from '@/types/api';
import { fetchStream, SSEError } from '@/api/chat';

/** 生成唯一 ID */
function generateId(): string {
    return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

export const useChatStore = defineStore('chat', () => {
    // ========== State ==========
    const messages = ref<ChatMessage[]>([]);
    const isLoading = ref(false);
    const currentBuffer = ref('');
    const currentCitations = ref<Citation[]>([]);
    const error = ref<string | null>(null);
    const abortController = ref<AbortController | null>(null);

    // ========== Getters ==========
    const hasMessages = computed(() => messages.value.length > 0);
    const lastAssistantMessage = computed(() => {
        for (let i = messages.value.length - 1; i >= 0; i--) {
            if (messages.value[i].role === 'assistant') {
                return messages.value[i];
            }
        }
        return null;
    });

    // ========== Actions ==========

    /**
     * 发送消息并获取流式回答
     */
    async function sendMessage(
        query: string,
        mode: 'naive' | 'local' | 'global' | 'hybrid' = 'hybrid'
    ): Promise<void> {
        if (!query.trim()) return;
        if (isLoading.value) return;

        // 重置状态
        error.value = null;
        isLoading.value = true;
        currentBuffer.value = '';
        currentCitations.value = [];

        // 创建 AbortController
        abortController.value = new AbortController();

        // 添加用户消息
        const userMessage: ChatMessage = {
            id: generateId(),
            role: 'user',
            content: query,
            timestamp: Date.now(),
        };
        messages.value.push(userMessage);

        // 添加占位的 assistant 消息
        const assistantMessage: ChatMessage = {
            id: generateId(),
            role: 'assistant',
            content: '',
            citations: [],
            timestamp: Date.now(),
        };
        messages.value.push(assistantMessage);

        try {
            await fetchStream(
                '/api/v1/chat/stream',
                { query, mode },
                (chunk: ChatChunk) => {
                    // 累积文本
                    currentBuffer.value += chunk.text;
                    assistantMessage.content = currentBuffer.value;

                    // 累积引用 (去重)
                    if (chunk.citations && chunk.citations.length > 0) {
                        for (const citation of chunk.citations) {
                            const exists = currentCitations.value.some(
                                (c) => c.chunk_id === citation.chunk_id
                            );
                            if (!exists) {
                                currentCitations.value.push(citation);
                            }
                        }
                        assistantMessage.citations = [...currentCitations.value];
                    }
                },
                abortController.value.signal
            );
        } catch (err) {
            if (err instanceof Error && err.name === 'AbortError') {
                // 用户主动中断,不视为错误
                assistantMessage.content += '\n\n[已中断]';
            } else if (err instanceof SSEError) {
                error.value = `请求失败: ${err.message}`;
                assistantMessage.content = `[错误] ${err.message}`;
            } else {
                error.value = '未知错误';
                assistantMessage.content = '[错误] 请求失败,请稍后重试';
            }
        } finally {
            isLoading.value = false;
            abortController.value = null;
        }
    }

    /**
     * 中断当前流式请求
     */
    function abortStream(): void {
        if (abortController.value) {
            abortController.value.abort();
        }
    }

    /**
     * 清空消息
     */
    function clearMessages(): void {
        messages.value = [];
        currentBuffer.value = '';
        currentCitations.value = [];
        error.value = null;
    }

    return {
        // State
        messages,
        isLoading,
        currentBuffer,
        error,

        // Getters
        hasMessages,
        lastAssistantMessage,

        // Actions
        sendMessage,
        abortStream,
        clearMessages,
    };
});
