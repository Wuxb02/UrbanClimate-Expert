/**
 * 文档 API 客户端
 */
import axios from 'axios';
import type {
    DocumentListResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
    DocumentDeleteResponse,
    DocumentRenameRequest,
    DocumentRenameResponse,
} from '@/types/api';

const API_BASE = '/api/v1/documents';

/**
 * 获取文档列表
 * @param page 页码 (从1开始)
 * @param pageSize 每页数量
 * @param keyword 搜索关键词 (可选)
 */
export async function fetchDocuments(
    page: number = 1,
    pageSize: number = 20,
    keyword?: string
): Promise<DocumentListResponse> {
    const params: Record<string, string | number> = {
        page,
        page_size: pageSize,
    };
    if (keyword && keyword.trim()) {
        params.keyword = keyword.trim();
    }
    const response = await axios.get<DocumentListResponse>(API_BASE, { params });
    return response.data;
}

/**
 * 获取文档状态
 * @param docId 文档 ID
 */
export async function fetchDocumentStatus(
    docId: number
): Promise<DocumentStatusResponse> {
    const response = await axios.get<DocumentStatusResponse>(
        `${API_BASE}/${docId}`
    );
    return response.data;
}

/**
 * 上传单个文件
 * @param file 要上传的文件
 * @param onProgress 上传进度回调
 */
export async function uploadFile(
    file: File,
    onProgress?: (percent: number) => void
): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await axios.post<DocumentUploadResponse>(
        `${API_BASE}/upload`,
        formData,
        {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
            onUploadProgress: (progressEvent) => {
                if (onProgress && progressEvent.total) {
                    const percent = Math.round(
                        (progressEvent.loaded * 100) / progressEvent.total
                    );
                    onProgress(percent);
                }
            },
        }
    );
    return response.data;
}

/**
 * 批量上传文件
 * @param files 要上传的文件列表
 * @param onFileProgress 单个文件上传进度回调 (fileIndex, percent)
 * @param onFileComplete 单个文件上传完成回调 (fileIndex, response)
 */
export async function uploadFiles(
    files: File[],
    onFileProgress?: (fileIndex: number, percent: number) => void,
    onFileComplete?: (fileIndex: number, response: DocumentUploadResponse) => void
): Promise<DocumentUploadResponse[]> {
    const results: DocumentUploadResponse[] = [];

    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const response = await uploadFile(file, (percent) => {
            onFileProgress?.(i, percent);
        });
        results.push(response);
        onFileComplete?.(i, response);
    }

    return results;
}

/**
 * 删除文档
 * @param docId 文档 ID
 */
export async function deleteDocument(
    docId: number
): Promise<DocumentDeleteResponse> {
    const response = await axios.delete<DocumentDeleteResponse>(
        `${API_BASE}/${docId}`
    );
    return response.data;
}

/**
 * 获取文档下载链接
 * @param docId 文档 ID
 */
export function getDocumentDownloadUrl(docId: number): string {
    return `${API_BASE}/${docId}/download`;
}

/**
 * 重命名文档
 * @param docId 文档 ID
 * @param filename 新文件名
 */
export async function renameDocument(
    docId: number,
    filename: string
): Promise<DocumentRenameResponse> {
    const response = await axios.patch<DocumentRenameResponse>(
        `${API_BASE}/${docId}/rename`,
        { filename } as DocumentRenameRequest
    );
    return response.data;
}
