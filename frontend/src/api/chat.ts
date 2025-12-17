/**
 * SSE 流式聊天客户端
 *
 * 功能:
 * - HTTP 状态码检查
 * - JSON 解析与错误处理
 * - [DONE] 结束标记处理
 * - AbortController 中断支持
 * - 粘包处理 (使用 buffer)
 */
import type { ChatChunk, ChatRequest } from '@/types/api';

/** SSE 错误类 */
export class SSEError extends Error {
    constructor(
        message: string,
        public readonly statusCode?: number,
        public readonly responseBody?: string
    ) {
        super(message);
        this.name = 'SSEError';
    }
}

/**
 * 流式聊天请求
 *
 * @param endpoint - API 端点
 * @param payload - 请求体
 * @param onChunk - 数据块回调
 * @param signal - 中断信号
 */
export async function fetchStream(
    endpoint: string,
    payload: ChatRequest,
    onChunk: (chunk: ChatChunk) => void,
    signal?: AbortSignal
): Promise<void> {
    // 1. 发起请求
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal,
    });

    // 2. 检查 HTTP 状态码
    if (!response.ok) {
        const errorBody = await response.text();
        throw new SSEError(
            `HTTP Error: ${response.status} ${response.statusText}`,
            response.status,
            errorBody
        );
    }

    // 3. 检查流式支持
    if (!response.body) {
        throw new SSEError('浏览器不支持流式响应');
    }

    // 4. 读取流
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';

    try {
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            // 解码并追加到 buffer (处理粘包)
            buffer += decoder.decode(value, { stream: true });

            // 按 SSE 格式分割 (双换行符)
            const parts = buffer.split('\n\n');
            // 最后一部分可能不完整,保留在 buffer 中
            buffer = parts.pop() || '';

            for (const part of parts) {
                const trimmed = part.trim();
                if (!trimmed) continue;

                // 处理多行数据,提取 data: 后的内容
                const lines = trimmed.split('\n');
                for (const line of lines) {
                    if (!line.startsWith('data:')) continue;

                    const data = line.slice(5).trim();

                    // 检查结束标记
                    if (data === '[DONE]') {
                        return;
                    }

                    // 解析 JSON
                    try {
                        const chunk = JSON.parse(data) as ChatChunk;
                        onChunk(chunk);
                    } catch (parseError) {
                        console.warn('JSON 解析失败:', data, parseError);
                        // 非 JSON 数据,跳过
                    }
                }
            }
        }
    } finally {
        reader.releaseLock();
    }
}

/**
 * 非流式聊天请求
 */
export async function queryChat(
    payload: ChatRequest
): Promise<{ answer: string; mode: string }> {
    const response = await fetch('/api/v1/chat/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });

    if (!response.ok) {
        const errorBody = await response.text();
        throw new SSEError(
            `HTTP Error: ${response.status}`,
            response.status,
            errorBody
        );
    }

    return response.json();
}
