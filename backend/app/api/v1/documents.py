"""
文档管理 API

包含:
- POST /upload: 上传 PDF 文档
- GET /{doc_id}: 查询文档处理状态
- GET /: 获取文档列表(分页)
"""
import hashlib
import time
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logger import logger
from app.db import Document, DocumentStatus, get_async_session, get_session_context
from app.schemas import (
    DocumentDeleteResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.core.llm_factory import LLMFactory
from app.core.prompts import (
    DOCUMENT_SUMMARY_PROMPT,
    SUMMARY_MAX_INPUT_LENGTH,
    SUMMARY_MAX_OUTPUT_LENGTH,
)
from app.services.parser_service import get_parser_service, validate_pdf
from app.services.rag_service import get_rag_service

router = APIRouter(prefix="/documents", tags=["documents"])


def _calculate_sha256(content: bytes) -> str:
    """计算文件 SHA256 哈希"""
    return hashlib.sha256(content).hexdigest()


async def _generate_summary(text: str) -> str:
    """
    使用 LLM 生成文档摘要

    Args:
        text: 文档全文

    Returns:
        生成的摘要文本
    """
    try:
        # 限制输入长度，避免超出 LLM 上下文限制
        content = text[:SUMMARY_MAX_INPUT_LENGTH] if len(text) > SUMMARY_MAX_INPUT_LENGTH else text

        llm = LLMFactory.build_chat_model()
        prompt = DOCUMENT_SUMMARY_PROMPT.format(content=content)
        summary = await llm(prompt, None)

        # 清理摘要文本
        summary = summary.strip()
        # 限制摘要长度
        if len(summary) > SUMMARY_MAX_OUTPUT_LENGTH:
            summary = summary[:SUMMARY_MAX_OUTPUT_LENGTH] + "..."

        return summary
    except Exception as e:
        logger.warning(f"生成摘要失败: {e}")
        return ""


async def _update_document_summary(doc_id: int, summary: str) -> bool:
    """
    更新文档摘要

    Args:
        doc_id: 文档 ID
        summary: 摘要文本

    Returns:
        True 表示更新成功，False 表示更新失败
    """
    try:
        async with get_session_context() as db:
            result = await db.execute(
                select(Document).where(Document.id == doc_id)
            )
            doc = result.scalar_one_or_none()
            if doc:
                doc.summary = summary
                await db.commit()
                return True
            return False
    except Exception as e:
        logger.warning(f"更新摘要失败 | doc_id: {doc_id} | 错误: {e}")
        return False


async def _save_parsed_text(doc_id: int, filename_stem: str, text: str) -> None:
    """
    保存 PDF 解析结果（Markdown 格式）

    保存文件：{doc_id}_{filename}.md - 清洗后的 Markdown 文本

    保存位置: backend/parsed_texts/
    """
    try:
        # 创建保存目录
        parsed_dir = settings.upload_dir_path.parent / "parsed_texts"
        parsed_dir.mkdir(parents=True, exist_ok=True)

        # 文件名前缀
        prefix = f"{doc_id}_{filename_stem[:50]}"  # 限制文件名长度

        # 保存 Markdown 文件
        md_file = parsed_dir / f"{prefix}.md"
        md_file.write_text(text, encoding="utf-8")

        logger.info(
            f"解析结果已保存 | doc_id: {doc_id} | "
            f"长度: {len(text)} 字符 | 文件: {md_file.name}"
        )

    except Exception as e:
        # 保存失败不影响主流程
        logger.warning(f"保存解析结果失败 | doc_id: {doc_id} | 错误: {e}")


async def _update_document_status(
    doc_id: int,
    status: DocumentStatus,
    error_message: str | None = None,
) -> bool:
    """
    使用独立会话更新文档状态

    Args:
        doc_id: 文档 ID
        status: 目标状态
        error_message: 错误信息（仅在 FAILED 状态时使用）

    Returns:
        True 表示更新成功，False 表示更新失败
    """
    try:
        async with get_session_context() as db:
            result = await db.execute(
                select(Document).where(Document.id == doc_id)
            )
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = status
                if error_message is not None:
                    doc.error_message = error_message[:1000]
                await db.commit()
                return True
            return False
    except Exception:
        return False


async def _process_document_background(doc_id: int, filepath: Path) -> None:
    """
    后台任务:处理文档

    处理流程:
    1. 标记状态为 PROCESSING（使用独立会话）
    2. 验证并解析 PDF
    3. 插入 LightRAG
    4. 更新状态为 COMPLETED（使用独立会话）
    5. 异常时标记 FAILED（使用独立会话）

    注意: 状态更新使用独立的数据库会话，确保即使主处理流程
    发生异常（如超时），状态也能正确更新。
    """
    logger.info(f"后台任务启动 | doc_id: {doc_id} | 文件: {filepath.name}")
    task_start_time = time.perf_counter()

    # 1. 标记为 PROCESSING（使用独立会话）
    if not await _update_document_status(doc_id, DocumentStatus.PROCESSING):
        logger.error(f"状态更新失败，任务终止 | doc_id: {doc_id}")
        return

    logger.info(f"状态更新: PENDING → PROCESSING | doc_id: {doc_id}")

    try:
        # 2. 验证并解析 PDF
        logger.debug(f"开始 PDF 验证 | doc_id: {doc_id}")
        is_valid, error_msg = validate_pdf(filepath)
        if not is_valid:
            raise ValueError(error_msg)
        logger.info(f"PDF 验证通过 | doc_id: {doc_id}")

        logger.info(f"开始 PDF 解析 | doc_id: {doc_id}")
        parse_start = time.perf_counter()
        parser = get_parser_service()
        text = await parser.parse_pdf(filepath)
        parse_elapsed = (time.perf_counter() - parse_start) * 1000
        logger.info(
            f"PDF 解析完成 | doc_id: {doc_id} | "
            f"文本长度: {len(text)} | 耗时: {parse_elapsed:.2f}ms"
        )

        if not text or len(text.strip()) < 100:
            raise ValueError("提取的文本过短,可能是无效的 PDF")

        # 保存解析结果用于检查
        await _save_parsed_text(doc_id, filepath.stem, text)

        # 3. 获取文档信息用于 metadata
        async with get_session_context() as db:
            result = await db.execute(
                select(Document).where(Document.id == doc_id)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                logger.error(f"文档记录不存在 | doc_id: {doc_id}")
                return
            filename = doc.filename

        # 4. 生成文档摘要
        logger.info(f"开始生成文档摘要 | doc_id: {doc_id}")
        summary_start = time.perf_counter()
        summary = await _generate_summary(text)
        summary_elapsed = (time.perf_counter() - summary_start) * 1000

        if summary:
            await _update_document_summary(doc_id, summary)
            logger.info(
                f"文档摘要生成成功 | doc_id: {doc_id} | "
                f"摘要长度: {len(summary)} | 耗时: {summary_elapsed:.2f}ms"
            )
        else:
            logger.warning(f"文档摘要生成失败 | doc_id: {doc_id}")


        # 5. 插入 LightRAG
        logger.info(f"开始插入 LightRAG | doc_id: {doc_id}")
        rag = await get_rag_service()
        await rag.insert_document(
            text=text,
            metadata={
                "doc_id": doc_id,
                "filename": filename,
                "filepath": str(filepath),
            },
        )

        # 6. 标记为 COMPLETED（使用独立会话）
        await _update_document_status(doc_id, DocumentStatus.COMPLETED)

        total_elapsed = (time.perf_counter() - task_start_time) * 1000
        logger.info(
            f"文档处理成功 | doc_id: {doc_id} | "
            f"状态: COMPLETED | 总耗时: {total_elapsed:.2f}ms"
        )

    except Exception as e:
        # 7. 标记为 FAILED（使用独立会话）
        await _update_document_status(doc_id, DocumentStatus.FAILED, str(e))

        total_elapsed = (time.perf_counter() - task_start_time) * 1000
        logger.error(
            f"文档处理失败 | doc_id: {doc_id} | "
            f"状态: FAILED | 总耗时: {total_elapsed:.2f}ms | 错误: {e}"
        )


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="上传的 PDF 文件"),
    db: AsyncSession = Depends(get_async_session),
) -> DocumentUploadResponse:
    """
    上传 PDF 文档

    - 文件会保存到服务器
    - 自动去重(基于 SHA256)
    - 返回 202 Accepted,后台异步处理
    """
    logger.info(f"接收文档上传请求 | 文件名: {file.filename}")

    # 1. 验证文件类型
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        logger.warning(f"文件类型验证失败 | 文件名: {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 PDF 文件"
        )

    # 2. 读取文件内容
    content = await file.read()
    filesize = len(content)
    logger.debug(f"文件读取完成 | 大小: {filesize / 1024:.2f} KB")

    # 验证文件大小
    max_size = settings.max_file_size_mb * 1024 * 1024
    if filesize > max_size:
        logger.warning(
            f"文件大小超限 | 文件名: {file.filename} | "
            f"大小: {filesize / 1024 / 1024:.2f} MB | 限制: {settings.max_file_size_mb} MB"
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小超过限制({settings.max_file_size_mb}MB)",
        )

    if filesize == 0:
        logger.warning(f"文件为空 | 文件名: {file.filename}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="文件为空"
        )

    # 3. 计算 SHA256 哈希
    sha256 = _calculate_sha256(content)
    logger.debug(f"文件哈希计算完成 | SHA256: {sha256[:16]}...")

    # 4. 检查是否已存在
    result = await db.execute(select(Document).where(Document.sha256 == sha256))
    existing_doc = result.scalar_one_or_none()
    if existing_doc:
        logger.warning(
            f"检测到重复文档 | SHA256: {sha256[:16]}... | "
            f"现有 doc_id: {existing_doc.id} | 状态: {existing_doc.status}"
        )
        # 如果文档处理失败,允许重新处理
        if existing_doc.status == DocumentStatus.FAILED:
            logger.info(f"重新触发失败文档处理 | doc_id: {existing_doc.id}")
            existing_doc.status = DocumentStatus.PENDING
            existing_doc.error_message = None  # 清除之前的错误信息
            await db.commit()
            await db.refresh(existing_doc)
            # 重新触发后台处理任务
            background_tasks.add_task(
                _process_document_background,
                existing_doc.id,
                Path(existing_doc.filepath)
            )
        # 返回已存在的文档记录
        return DocumentUploadResponse.model_validate(existing_doc)

    # 5. 创建存储目录
    upload_dir = settings.upload_dir_path
    upload_dir.mkdir(parents=True, exist_ok=True)

    # 6. 保存文件(使用 SHA256 作为文件名,避免冲突)
    filepath = upload_dir / f"{sha256}.pdf"
    filepath.write_bytes(content)
    logger.info(f"文件保存成功 | 路径: {filepath}")

    # 7. 创建数据库记录
    doc = Document(
        filename=file.filename,
        filepath=str(filepath),
        sha256=sha256,
        filesize=filesize,
        status=DocumentStatus.PENDING,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    logger.info(
        f"文档记录创建成功 | doc_id: {doc.id} | "
        f"文件名: {file.filename} | 大小: {filesize / 1024:.2f} KB"
    )

    # 8. 触发后台处理任务
    background_tasks.add_task(_process_document_background, doc.id, filepath)
    logger.info(f"后台处理任务已触发 | doc_id: {doc.id}")

    return DocumentUploadResponse.model_validate(doc)


@router.get("/{doc_id}", response_model=DocumentStatusResponse)
async def get_document_status(
    doc_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> DocumentStatusResponse:
    """查询文档处理状态"""
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在"
        )

    return DocumentStatusResponse.model_validate(doc)


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    keyword: str | None = None,
    db: AsyncSession = Depends(get_async_session),
) -> DocumentListResponse:
    """
    获取文档列表(分页)

    支持按文件名关键词搜索
    """
    # 构建基础查询
    base_query = select(Document)

    # 如果有关键词，添加过滤条件
    if keyword and keyword.strip():
        base_query = base_query.where(
            Document.filename.ilike(f"%{keyword.strip()}%")
        )

    # 查询总数
    count_result = await db.execute(base_query)
    total = len(count_result.scalars().all())

    # 查询分页数据
    offset = (page - 1) * page_size
    result = await db.execute(
        base_query
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = result.scalars().all()

    return DocumentListResponse(
        total=total,
        items=[DocumentListItem.model_validate(doc) for doc in items],
    )


@router.delete("/{doc_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_async_session),
) -> DocumentDeleteResponse:
    """
    删除文档

    - 从数据库中删除文档记录
    - 同时删除关联的文件
    """
    logger.info(f"接收文档删除请求 | doc_id: {doc_id}")

    # 查询文档
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()

    if not doc:
        logger.warning(f"删除失败：文档不存在 | doc_id: {doc_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    # 删除文件
    filepath = Path(doc.filepath)
    if filepath.exists():
        try:
            filepath.unlink()
            logger.info(f"文件删除成功 | 路径: {filepath}")
        except Exception as e:
            logger.warning(f"文件删除失败 | 路径: {filepath} | 错误: {e}")

    # 删除解析结果文件
    parsed_dir = settings.upload_dir_path.parent / "parsed_texts"
    if parsed_dir.exists():
        for parsed_file in parsed_dir.glob(f"{doc_id}_*"):
            try:
                parsed_file.unlink()
                logger.info(f"解析文件删除成功 | 路径: {parsed_file}")
            except Exception as e:
                logger.warning(f"解析文件删除失败 | 路径: {parsed_file} | 错误: {e}")

    # 删除数据库记录
    await db.delete(doc)
    await db.commit()

    logger.info(f"文档删除成功 | doc_id: {doc_id}")

    return DocumentDeleteResponse(id=doc_id, message="文档删除成功")


@router.get("/{doc_id}/download")
async def download_document(
    doc_id: int,
    db: AsyncSession = Depends(get_async_session),
):
    """
    下载文档

    返回原始 PDF 文件
    """
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    filepath = Path(doc.filepath)
    if not filepath.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文件不存在"
        )

    logger.info(f"文档下载请求 | doc_id: {doc_id} | 文件名: {doc.filename}")

    return FileResponse(
        path=filepath,
        filename=doc.filename,
        media_type="application/pdf"
    )


class DocumentRenameRequest(BaseModel):
    """文档重命名请求"""
    filename: str = Field(..., min_length=1, max_length=255, description="新文件名")


class DocumentRenameResponse(BaseModel):
    """文档重命名响应"""
    id: int
    filename: str
    message: str = "重命名成功"


@router.patch("/{doc_id}/rename", response_model=DocumentRenameResponse)
async def rename_document(
    doc_id: int,
    request: DocumentRenameRequest,
    db: AsyncSession = Depends(get_async_session),
) -> DocumentRenameResponse:
    """
    重命名文档

    只修改显示的文件名，不修改实际存储的文件
    """
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="文档不存在"
        )

    old_filename = doc.filename
    new_filename = request.filename.strip()

    # 确保文件名以 .pdf 结尾
    if not new_filename.lower().endswith(".pdf"):
        new_filename += ".pdf"

    doc.filename = new_filename
    await db.commit()
    await db.refresh(doc)

    logger.info(
        f"文档重命名成功 | doc_id: {doc_id} | "
        f"原文件名: {old_filename} | 新文件名: {new_filename}"
    )

    return DocumentRenameResponse(
        id=doc_id,
        filename=new_filename,
        message="重命名成功"
    )
