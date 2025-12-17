<template>
    <div class="chat-window">
        <!-- 消息列表 -->
        <div ref="messagesContainer" class="messages-container">
            <!-- 空状态 -->
            <div v-if="!chatStore.hasMessages" class="empty-state">
                <el-icon :size="64" color="#c0c4cc"><ChatDotRound /></el-icon>
                <p>输入问题,开始探索城市气候知识</p>
                <div class="example-questions">
                    <el-tag
                        v-for="q in exampleQuestions"
                        :key="q"
                        class="example-tag"
                        @click="handleExampleClick(q)"
                    >
                        {{ q }}
                    </el-tag>
                </div>
            </div>

            <!-- 消息列表 -->
            <div
                v-for="msg in chatStore.messages"
                :key="msg.id"
                :class="['message-item', msg.role]"
            >
                <div class="message-avatar">
                    <el-icon v-if="msg.role === 'user'" :size="24">
                        <User />
                    </el-icon>
                    <el-icon v-else :size="24"><Cpu /></el-icon>
                </div>
                <div class="message-content">
                    <div
                        class="message-bubble"
                        v-html="renderContent(msg.content)"
                    />
                    <!-- 引用展示 -->
                    <div
                        v-if="msg.citations && msg.citations.length > 0"
                        class="citations"
                    >
                        <div class="citations-header">
                            <el-icon><Document /></el-icon>
                            <span>引用来源 ({{ msg.citations.length }})</span>
                        </div>
                        <div class="citations-list">
                            <el-popover
                                v-for="(citation, idx) in msg.citations"
                                :key="citation.chunk_id"
                                placement="top"
                                :width="300"
                                trigger="hover"
                            >
                                <template #reference>
                                    <el-tag size="small" class="citation-tag">
                                        [{{ idx + 1 }}] {{ citation.filename }}
                                    </el-tag>
                                </template>
                                <div class="citation-popover">
                                    <p>
                                        <strong>文档:</strong>
                                        {{ citation.filename }}
                                    </p>
                                    <p>
                                        <strong>相关性:</strong>
                                        {{ (citation.score * 100).toFixed(1) }}%
                                    </p>
                                    <p><strong>内容预览:</strong></p>
                                    <p class="preview-text">
                                        {{ citation.content_preview }}
                                    </p>
                                </div>
                            </el-popover>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 加载指示器 -->
            <div v-if="chatStore.isLoading" class="loading-indicator">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>正在思考...</span>
            </div>
        </div>

        <!-- 错误提示 -->
        <el-alert
            v-if="chatStore.error"
            :title="chatStore.error"
            type="error"
            show-icon
            closable
            class="error-alert"
        />

        <!-- 输入区域 -->
        <div class="composer">
            <el-input
                v-model="inputText"
                type="textarea"
                :rows="2"
                :disabled="chatStore.isLoading"
                placeholder="输入关于城市气候的问题..."
                resize="none"
                @keydown.enter.exact.prevent="handleSend"
            />
            <div class="composer-actions">
                <el-select v-model="queryMode" size="small" style="width: 100px">
                    <el-option label="混合" value="hybrid" />
                    <el-option label="局部" value="local" />
                    <el-option label="全局" value="global" />
                    <el-option label="向量" value="naive" />
                </el-select>
                <el-button
                    v-if="chatStore.isLoading"
                    type="danger"
                    size="small"
                    @click="chatStore.abortStream()"
                >
                    <el-icon><Close /></el-icon>
                    停止
                </el-button>
                <el-button
                    v-else
                    type="primary"
                    size="small"
                    :disabled="!inputText.trim()"
                    @click="handleSend"
                >
                    <el-icon><Promotion /></el-icon>
                    发送
                </el-button>
                <el-button size="small" @click="chatStore.clearMessages()">
                    <el-icon><Delete /></el-icon>
                    清空
                </el-button>
            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import { useChatStore } from '@/stores/chat';
import { renderMarkdown } from '@/utils/markdown';
import {
    ChatDotRound,
    User,
    Cpu,
    Document,
    Loading,
    Close,
    Promotion,
    Delete,
} from '@element-plus/icons-vue';

const chatStore = useChatStore();

const inputText = ref('');
const queryMode = ref<'naive' | 'local' | 'global' | 'hybrid'>('hybrid');
const messagesContainer = ref<HTMLElement | null>(null);

const exampleQuestions = [
    '什么是城市热岛效应?',
    '如何缓解城市高温?',
    '绿色建筑对城市气候有什么影响?',
];

/** 渲染消息内容 (Markdown + LaTeX) */
function renderContent(content: string): string {
    if (!content) return '';
    return renderMarkdown(content);
}

/** 发送消息 */
async function handleSend(): Promise<void> {
    if (!inputText.value.trim()) return;
    const query = inputText.value;
    inputText.value = '';
    await chatStore.sendMessage(query, queryMode.value);
}

/** 点击示例问题 */
function handleExampleClick(question: string): void {
    inputText.value = question;
    handleSend();
}

/** 滚动到底部 */
async function scrollToBottom(): Promise<void> {
    await nextTick();
    if (messagesContainer.value) {
        messagesContainer.value.scrollTop =
            messagesContainer.value.scrollHeight;
    }
}

/** 自动滚动到底部 */
watch(
    () => chatStore.messages.length,
    () => {
        scrollToBottom();
    }
);

/** 流式输出时持续滚动 */
watch(
    () => chatStore.currentBuffer,
    () => {
        scrollToBottom();
    }
);
</script>

<style scoped lang="scss">
.chat-window {
    display: flex;
    flex-direction: column;
    height: 100%;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.messages-container {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
}

.empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #909399;

    p {
        margin: 16px 0;
    }

    .example-questions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        justify-content: center;
        max-width: 500px;
    }

    .example-tag {
        cursor: pointer;
        &:hover {
            color: #409eff;
            border-color: #409eff;
        }
    }
}

.message-item {
    display: flex;
    gap: 12px;
    margin-bottom: 20px;

    &.user {
        flex-direction: row-reverse;

        .message-bubble {
            background: #409eff;
            color: #fff;
        }
    }

    &.assistant {
        .message-bubble {
            background: #f5f7fa;
        }
    }
}

.message-avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: #e5e7eb;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}

.message-content {
    max-width: 70%;
}

.message-bubble {
    padding: 12px 16px;
    border-radius: 8px;
    line-height: 1.6;

    :deep(pre) {
        background: #1e1e1e;
        padding: 12px;
        border-radius: 4px;
        overflow-x: auto;
        margin: 8px 0;

        code {
            color: #d4d4d4;
        }
    }

    :deep(code:not(pre code)) {
        background: #f0f0f0;
        padding: 2px 6px;
        border-radius: 4px;
        font-size: 0.9em;
    }

    :deep(.katex-display) {
        overflow-x: auto;
        padding: 8px 0;
    }

    :deep(p) {
        margin: 8px 0;
        &:first-child {
            margin-top: 0;
        }
        &:last-child {
            margin-bottom: 0;
        }
    }

    :deep(ul),
    :deep(ol) {
        margin: 8px 0;
        padding-left: 20px;
    }

    :deep(li) {
        margin: 4px 0;
    }
}

.citations {
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px dashed #e5e7eb;
}

.citations-header {
    display: flex;
    align-items: center;
    gap: 4px;
    font-size: 12px;
    color: #909399;
    margin-bottom: 6px;
}

.citations-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.citation-tag {
    cursor: pointer;
}

.citation-popover {
    p {
        margin: 4px 0;
    }

    .preview-text {
        color: #606266;
        font-size: 13px;
        line-height: 1.5;
        max-height: 100px;
        overflow-y: auto;
    }
}

.loading-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    color: #909399;
    padding: 12px;
}

.error-alert {
    margin: 0 20px 12px;
}

.composer {
    padding: 16px 20px;
    border-top: 1px solid #e5e7eb;
}

.composer-actions {
    display: flex;
    gap: 8px;
    margin-top: 12px;
    justify-content: flex-end;
}
</style>
