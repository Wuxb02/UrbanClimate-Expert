from __future__ import annotations

import inspect
import json
import re
import time
import unicodedata
from collections.abc import AsyncGenerator
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np

from lightrag import LightRAG, QueryParam
from lightrag.kg.shared_storage import initialize_pipeline_status
from lightrag.llm.ollama import ollama_embed, ollama_model_complete
from lightrag.llm.openai import openai_complete_if_cache
from lightrag.rerank import ali_rerank
from lightrag.utils import EmbeddingFunc

from app.core.config import settings
from app.core.logger import logger
from app.core.prompts import RAG_QUERY_PROMPT, RAG_STREAM_QUERY_PROMPT


def _remove_references_section(text: str) -> str:
    """
    移除学术论文的参考文献部分，保留附录

    策略：找到 References 标题，然后找到下一个章节标题，只删除中间部分
    """
    # 参考文献标题模式
    ref_patterns = [
        r'\n\s*#{0,3}\s*References?\s*\n',
        r'\n\s*#{0,3}\s*REFERENCES?\s*\n',
        r'\n\s*#{0,3}\s*Bibliography\s*\n',
        r'\n\s*#{0,3}\s*参考文献\s*\n',
        r'\n\s*#{0,3}\s*Works\s+Cited\s*\n',
        r'\n\s*\d+\.?\s*References?\s*\n',
        r'\n\s*\d+\.?\s*REFERENCES?\s*\n',
    ]

    # 参考文献之后可能出现的章节标题（附录、致谢等）
    next_section_patterns = [
        r'\n\s*#{0,3}\s*Appendix',
        r'\n\s*#{0,3}\s*APPENDIX',
        r'\n\s*#{0,3}\s*Supplementary',
        r'\n\s*#{0,3}\s*SUPPLEMENTARY',
        r'\n\s*#{0,3}\s*Acknowledgment',
        r'\n\s*#{0,3}\s*ACKNOWLEDGMENT',
        r'\n\s*#{0,3}\s*附录',
        r'\n\s*#{0,3}\s*致谢',
        r'\n\s*#{0,3}\s*Supporting\s+Information',
        r'\n\s*[A-Z]\.\s+',  # 附录编号如 "A. xxx"
        r'\n\s*Appendix\s+[A-Z]',
    ]

    # 1. 找到 References 的位置
    ref_start = None
    for pattern in ref_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if ref_start is None or match.start() < ref_start:
                ref_start = match.start()

    if ref_start is None:
        # 没找到参考文献部分
        return text

    # 2. 在 References 之后找下一个章节
    text_after_ref = text[ref_start + 1:]  # +1 跳过换行符
    ref_end = len(text)  # 默认到文档末尾

    for pattern in next_section_patterns:
        match = re.search(pattern, text_after_ref, re.IGNORECASE)
        if match:
            candidate_end = ref_start + 1 + match.start()
            if candidate_end < ref_end:
                ref_end = candidate_end

    # 3. 删除 References 部分，拼接前后内容
    before_ref = text[:ref_start].rstrip()
    after_ref = text[ref_end:].lstrip() if ref_end < len(text) else ""

    # 记录日志
    removed_chars = ref_end - ref_start
    logger.debug(f"移除参考文献部分 | 删除字符数: {removed_chars}")

    if after_ref:
        return before_ref + "\n\n" + after_ref
    else:
        return before_ref + "\n"


def _sanitize_text_for_embedding(text: str) -> str:
    """
    清理可能导致嵌入模型返回 NaN 的文本

    bge-m3 模型在处理某些 Unicode 字符时会返回 NaN，需要彻底清理
    """
    # 0. 首先移除参考文献部分（学术论文），保留附录
    text = _remove_references_section(text)

    # 1. Unicode 规范化 (NFKC: 兼容分解后再规范组合)
    # 这会将特殊字符转换为兼容形式，如 ² → 2, ∗ → *
    text = unicodedata.normalize('NFKC', text)

    # 2. 移除控制字符 (保留换行 \n=0x0a 和制表符 \t=0x09)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)

    # 3. 替换特殊 Unicode 空格为普通空格
    text = re.sub(r'[\u00a0\u2000-\u200b\u202f\u205f\u3000]', ' ', text)

    # 4. 移除零宽字符 (零宽非连接符、零宽连接符、BOM)
    text = re.sub(r'[\u200c\u200d\ufeff]', '', text)

    # 5. 移除其他可能导致问题的 Unicode 字符
    # 包括：组合字符、私用区字符、代理对等
    text = re.sub(r'[\u0300-\u036f]', '', text)  # 组合附加符号
    text = re.sub(r'[\ue000-\uf8ff]', '', text)  # 私用区
    text = re.sub(r'[\ud800-\udfff]', '', text)  # 代理对

    # 6. 替换常见的数学/技术符号为 ASCII 等价物
    replacements = {
        '∗': '*',
        '×': 'x',
        '÷': '/',
        '±': '+/-',
        '≤': '<=',
        '≥': '>=',
        '≠': '!=',
        '≈': '~=',
        '∞': 'inf',
        '∑': 'sum',
        '∏': 'prod',
        '√': 'sqrt',
        '∂': 'd',
        '∇': 'nabla',
        '∈': 'in',
        '∉': 'not in',
        '⊂': 'subset',
        '⊃': 'superset',
        '∪': 'union',
        '∩': 'intersection',
        '→': '->',
        '←': '<-',
        '↔': '<->',
        '⇒': '=>',
        '⇐': '<=',
        '⇔': '<=>',
        '′': "'",
        '″': '"',
        '‴': "'''",
        '°': ' degrees',
        '·': '.',
        '…': '...',
        '—': '-',
        '–': '-',
        '"': '"',
        '"': '"',
        ''': "'",
        ''': "'",
        '„': '"',
        '‟': '"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # 7. 只保留基本的可打印 ASCII 字符和常见 Unicode 字符
    # 移除所有非常见字符（保留中文、日文、韩文等常用字符）
    def is_safe_char(c: str) -> bool:
        code = ord(c)
        # ASCII 可打印字符
        if 0x20 <= code <= 0x7e:
            return True
        # 换行和制表符
        if c in '\n\t\r':
            return True
        # 中日韩统一表意文字
        if 0x4e00 <= code <= 0x9fff:
            return True
        # 中日韩扩展 A
        if 0x3400 <= code <= 0x4dbf:
            return True
        # 常用标点和符号
        if 0x3000 <= code <= 0x303f:
            return True
        # 全角 ASCII
        if 0xff00 <= code <= 0xffef:
            return True
        # 日文平假名和片假名
        if 0x3040 <= code <= 0x30ff:
            return True
        # 韩文
        if 0xac00 <= code <= 0xd7af:
            return True
        # 拉丁扩展（带重音的字母等）
        if 0x00c0 <= code <= 0x024f:
            return True
        return False

    text = ''.join(c if is_safe_char(c) else ' ' for c in text)

    # 8. 压缩多余空格
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n+', '\n', text)

    return text.strip()


# 用于跟踪已记录 NaN 警告的 doc_id，避免重复日志
_nan_warning_logged_docs: set[str] = set()


def _extract_doc_id_from_text(text: str) -> str | None:
    """从文本中提取 [DOC_ID:xxx] 标记"""
    match = re.search(r'\[DOC_ID:([^\]]+)\]', text)
    return match.group(1) if match else None


def reset_nan_warning_tracker() -> None:
    """重置 NaN 警告跟踪器（在新文档处理开始时调用）"""
    global _nan_warning_logged_docs
    _nan_warning_logged_docs.clear()


async def _safe_ollama_embed(texts: list[str], **kwargs) -> list[list[float]]:
    """
    安全的 Ollama 嵌入函数包装器 (熔断防御版)

    1. 清理文本
    2. 捕获 Ollama 服务端因 NaN 导致的 500 崩溃
    3. 返回零向量兜底，防止整个 Pipeline 失败
    """
    global _nan_warning_logged_docs

    # 1. 清理所有文本
    cleaned_texts = [_sanitize_text_for_embedding(t) for t in texts]

    try:
        # 2. 尝试调用 API
        # 注意: 如果模型算出 NaN, 这里会直接抛出 ResponseError (Status 500)
        return await ollama_embed(
            cleaned_texts,
            embed_model="bge-m3:567m",
            host=settings.ollama_base_url.replace("/v1", ""),
        )
    except Exception as e:
        # 3. 捕获严重的崩溃异常
        error_str = str(e)
        # 检查是否是 NaN 导致的 JSON 编码错误
        if "NaN" in error_str or "500" in error_str or "json" in error_str.lower():
            # 尝试从文本中提取 doc_id，每个 doc_id 只记录一次警告
            doc_id = None
            for text in texts:
                doc_id = _extract_doc_id_from_text(text)
                if doc_id:
                    break

            # 如果找不到 doc_id，使用文本前缀作为标识
            log_key = doc_id if doc_id else cleaned_texts[0][:50]

            if log_key not in _nan_warning_logged_docs:
                _nan_warning_logged_docs.add(log_key)
                logger.warning(
                    f"Embedding NaN 错误 | doc_id: {doc_id or 'unknown'} | "
                    f"返回零向量兜底"
                )

            # 返回 1024 维度的零向量 (对应 bge-m3)
            return [[0.0] * 1024 for _ in range(len(texts))]

        # 如果是其他错误（如网络断连），继续抛出
        raise e


async def _openai_llm_func(
    prompt: str,
    system_prompt: str | None = None,
    history_messages: list | None = None,
    **kwargs
) -> str:
    """OpenAI LLM 函数包装器,用于 LightRAG"""
    return await openai_complete_if_cache(
        model=settings.openai_model,
        prompt=prompt,
        system_prompt=system_prompt,
        history_messages=history_messages or [],
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        **kwargs,
    )


def _build_rerank_func():
    """构建 rerank 函数 (如果启用)"""
    if not settings.enable_rerank:
        return None

    return partial(
        ali_rerank,
        model=settings.rerank_model,
        api_key=settings.rerank_api_key,
        base_url=settings.rerank_base_url,
    )


class LightRAGService:
    """
    Thin wrapper around LightRAG to centralize initialization and streaming helpers.
    """

    def __init__(self) -> None:
        workspace = settings.lightrag_workspace_path
        workspace.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"初始化 LightRAG | "
            f"工作区: {workspace} | "
            f"LLM 类型: {settings.llm_type} | "
            f"LLM 超时: {settings.llm_timeout}s | "
            f"Embedding 超时: {settings.embedding_timeout}s"
        )

        # 统一的 Embedding 配置 (使用安全包装器防止 NaN 错误)
        embedding_config = EmbeddingFunc(
            embedding_dim=1024,
            max_token_size=8192,
            func=_safe_ollama_embed,
        )

        # 构建 Rerank 函数 (可选)
        rerank_func = _build_rerank_func()

        # 根据配置选择 LLM
        if settings.llm_type == "ollama":
            logger.debug(f"使用 Ollama LLM | 模型: {settings.ollama_model}")
            # 使用 Ollama LLM + Ollama Embedding + Neo4j 图存储
            self.rag = LightRAG(
                working_dir=str(workspace),
                llm_model_func=ollama_model_complete,
                llm_model_name=settings.ollama_model,
                llm_model_kwargs={
                    "host": settings.ollama_base_url.replace("/v1", ""),
                    "options": {"num_ctx": 8192},
                },
                embedding_func=embedding_config,
                rerank_model_func=rerank_func,
                graph_storage="Neo4JStorage",  # 使用 Neo4j 作为图存储
                default_llm_timeout=settings.llm_timeout,
                default_embedding_timeout=settings.embedding_timeout,
            )
        elif settings.llm_type == "openai":
            logger.debug(f"使用 OpenAI LLM | 模型: {settings.openai_model}")
            # 使用 OpenAI LLM + Ollama Embedding + Neo4j 图存储
            self.rag = LightRAG(
                working_dir=str(workspace),
                llm_model_func=_openai_llm_func,
                embedding_func=embedding_config,
                rerank_model_func=rerank_func,
                graph_storage="Neo4JStorage",  # 使用 Neo4j 作为图存储
                default_llm_timeout=settings.llm_timeout,
                default_embedding_timeout=settings.embedding_timeout,
            )
        else:
            logger.error(f"不支持的 LLM 类型: {settings.llm_type}")
            raise ValueError(f"不支持的 LLM 类型: {settings.llm_type}，请使用 'ollama' 或 'openai'")

        logger.info(
            f"LightRAG 配置完成 | "
            f"图存储: Neo4j | "
            f"Rerank 启用: {settings.enable_rerank}"
        )

    async def initialize(self) -> None:
        """初始化存储"""
        logger.debug("开始初始化 LightRAG 存储...")
        await self.rag.initialize_storages()
        await initialize_pipeline_status()
        logger.info("LightRAG 存储初始化完成")

    def _check_lightrag_doc_status(
        self, doc_id: int | str, filename: str
    ) -> dict | None:
        """
        检查 LightRAG 内部特定文档的处理状态

        通过匹配 content_summary 中的 [DOC_ID:x][FILENAME:xxx] 标记
        来确定是当前插入的文档

        Args:
            doc_id: 文档 ID
            filename: 文件名

        Returns:
            如果该文档处理失败，返回状态信息；否则返回 None
        """
        status_file = Path(self.rag.working_dir) / "kv_store_doc_status.json"
        if not status_file.exists():
            return None

        try:
            with open(status_file, 'r', encoding='utf-8') as f:
                doc_statuses = json.load(f)

            # 查找匹配当前文档的记录
            target_marker = f"[DOC_ID:{doc_id}][FILENAME:{filename}]"

            for lightrag_doc_id, status_info in doc_statuses.items():
                content_summary = status_info.get("content_summary", "")
                if target_marker in content_summary:
                    if status_info.get("status") == "failed":
                        return status_info
                    # 找到了文档但状态不是 failed，说明成功
                    return None

            # 没找到匹配的文档记录（可能是首次插入时文件还未创建）
            return None

        except Exception as e:
            logger.warning(f"读取 LightRAG 状态文件失败: {e}")
            return None

    async def insert_document(self, text: str, metadata: dict[str, Any] | None = None) -> None:
        """
        异步插入文档到 LightRAG

        Args:
            text: 文档文本内容
            metadata: 文档元数据 (doc_id, filename, filepath)
        """
        doc_id = metadata.get("doc_id", "unknown") if metadata else "unknown"
        filename = metadata.get("filename", "unknown") if metadata else "unknown"

        logger.info(
            f"开始插入文档 | doc_id: {doc_id} | "
            f"文件名: {filename} | 原始文本长度: {len(text)}"
        )

        # 重置 NaN 警告跟踪器，确保每个文档的警告只记录一次
        reset_nan_warning_tracker()

        start_time = time.perf_counter()

        try:
            # 清理文本，防止嵌入模型返回 NaN
            text = _sanitize_text_for_embedding(text)
            logger.debug(f"文本清洗完成 | doc_id: {doc_id} | 清洗后长度: {len(text)}")

            # 将 metadata 存储在文本开头作为特殊标记
            # 这样可以在后续查询时追溯来源
            if metadata:
                # 在文本开头添加元数据标记 (不影响语义理解)
                text_with_meta = f"[DOC_ID:{doc_id}][FILENAME:{filename}]\n\n{text}"
                await self.rag.ainsert(text_with_meta)
            else:
                await self.rag.ainsert(text)

            # 验证插入是否成功：检查 LightRAG 内部状态
            # LightRAG 的 ainsert() 可能静默失败（只打印日志不抛出异常）
            failed_doc = self._check_lightrag_doc_status(doc_id, filename)
            if failed_doc:
                error_msg = failed_doc.get("error_msg", "未知错误")
                raise RuntimeError(f"LightRAG 文档处理失败: {error_msg}")

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"文档插入成功 | doc_id: {doc_id} | 耗时: {elapsed_ms:.2f}ms")

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"文档插入失败 | doc_id: {doc_id} | "
                f"耗时: {elapsed_ms:.2f}ms | 错误: {e}"
            )
            raise

    async def query(self, question: str, mode: str = "hybrid") -> str:
        """
        异步查询,返回字符串结果
        """
        logger.info(f"RAG 查询开始 | 模式: {mode} | 问题: {question[:100]}...")
        start_time = time.perf_counter()

        # 使用统一管理的提示词
        prompt = RAG_QUERY_PROMPT.format(question=question)

        try:
            result = await self.rag.aquery(
                prompt,
                param=QueryParam(mode=mode, stream=False)
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(
                f"RAG 查询成功 | 模式: {mode} | "
                f"结果长度: {len(result)} | 耗时: {elapsed_ms:.2f}ms"
            )
            return result
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"RAG 查询失败 | 模式: {mode} | "
                f"耗时: {elapsed_ms:.2f}ms | 错误: {e}"
            )
            raise

    async def stream_query(self, question: str, mode: str = "hybrid") -> AsyncGenerator[str, None]:
        """
        异步流式查询,返回异步生成器
        """
        logger.info(f"RAG 流式查询开始 | 模式: {mode} | 问题: {question[:100]}...")

        # 使用统一管理的提示词
        prompt = RAG_STREAM_QUERY_PROMPT.format(question=question)

        result = await self.rag.aquery(
            prompt,
            param=QueryParam(mode=mode, stream=True)
        )

        chunk_count = 0
        # 检查是否是异步生成器
        if inspect.isasyncgen(result):
            async for chunk in result:
                chunk_count += 1
                yield chunk
            logger.info(f"RAG 流式查询完成 | 模式: {mode} | Chunk 数量: {chunk_count}")
        else:
            # 如果不是流式响应,直接返回
            logger.debug("RAG 返回非流式响应，直接输出")
            yield str(result)

    async def stream_query_with_citations(
        self, question: str, mode: str = "hybrid"
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        异步流式查询,返回带 Citation 的结果块

        每个块的格式:
        {
            "text": "回答文本",
            "citations": [
                {
                    "doc_id": 1,
                    "filename": "xxx.pdf",
                    "chunk_id": "chunk_xxx",
                    "score": 0.85,
                    "content_preview": "..."
                }
            ],
            "is_final": False
        }
        """
        logger.info(
            f"RAG 流式查询(带引用)开始 | 模式: {mode} | "
            f"问题: {question[:100]}..."
        )

        # 先进行流式查询
        result = await self.rag.aquery(
            question,
            param=QueryParam(mode=mode, stream=True)
        )

        chunk_count = 0
        if inspect.isasyncgen(result):
            # 流式响应
            async for chunk in result:
                chunk_count += 1
                # 提取文本中的引用标记
                citations = self._extract_citations_from_text(chunk)
                yield {
                    "text": chunk,
                    "citations": citations,
                    "is_final": False
                }

            # 最后一个块,标记结束
            yield {
                "text": "",
                "citations": [],
                "is_final": True
            }
            logger.info(
                f"RAG 流式查询(带引用)完成 | 模式: {mode} | "
                f"Chunk 数量: {chunk_count}"
            )
        else:
            # 非流式响应
            logger.debug("RAG 返回非流式响应，直接输出")
            text = str(result)
            citations = self._extract_citations_from_text(text)
            yield {
                "text": text,
                "citations": citations,
                "is_final": False
            }
            yield {
                "text": "",
                "citations": [],
                "is_final": True
            }

    def _extract_citations_from_text(self, text: str) -> list[dict[str, Any]]:
        """
        从文本中提取引用信息

        查找文本中的 [DOC_ID:xxx][FILENAME:xxx] 标记
        """
        import re

        citations = []
        # 匹配模式: [DOC_ID:1][FILENAME:test.pdf]
        pattern = r'\[DOC_ID:(\d+)\]\[FILENAME:([^\]]+)\]'
        matches = re.finditer(pattern, text)

        for match in matches:
            doc_id = int(match.group(1))
            filename = match.group(2)
            citations.append({
                "doc_id": doc_id,
                "filename": filename,
                "chunk_id": f"chunk_{doc_id}",  # 简化的 chunk_id
                "score": 0.0,  # LightRAG 不直接提供 score,这里设为 0
                "content_preview": text[:200]  # 前 200 字符作为预览
            })

        # 去重
        seen = set()
        unique_citations = []
        for citation in citations:
            key = (citation["doc_id"], citation["filename"])
            if key not in seen:
                seen.add(key)
                unique_citations.append(citation)

        return unique_citations


_rag_service: LightRAGService | None = None


async def get_rag_service() -> LightRAGService:
    """获取 RAG 服务单例"""
    global _rag_service
    if _rag_service is None:
        logger.info("首次创建 RAG 服务实例...")
        _rag_service = LightRAGService()
        await _rag_service.initialize()
        logger.info("RAG 服务实例创建完成")
    return _rag_service
