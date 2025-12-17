"""
文档管理 API

包含:
- POST /upload: 上传 PDF 文档
- GET /{doc_id}: 查询文档处理状态
- GET /: 获取文档列表(分页)
"""
import hashlib
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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import Document, DocumentStatus, get_async_session, get_session_context
from app.schemas import (
    DocumentListItem,
    DocumentListResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from app.services.parser_service import parse_pdf_text, validate_pdf
from app.services.rag_service import get_rag_service

router = APIRouter(prefix="/documents", tags=["documents"])


def _calculate_sha256(content: bytes) -> str:
    """计算文件 SHA256 哈希"""
    return hashlib.sha256(content).hexdigest()


async def _process_document_background(doc_id: int, filepath: Path) -> None:
    """
    后台任务:处理文档

    处理流程:
    1. 标记状态为 PROCESSING
    2. 验证并解析 PDF
    3. 插入 LightRAG
    4. 更新状态为 COMPLETED
    5. 异常时标记 FAILED
    """
    async with get_session_context() as db:
        try:
            # 1. 更新状态为 PROCESSING
            result = await db.execute(
                select(Document).where(Document.id == doc_id)
            )
            doc = result.scalar_one_or_none()
            if not doc:
                return

            doc.status = DocumentStatus.PROCESSING
            await db.commit()

            # 2. 验证并解析 PDF
            is_valid, error_msg = validate_pdf(filepath)
            if not is_valid:
                raise ValueError(error_msg)

            text = parse_pdf_text(filepath)

            if not text or len(text.strip()) < 100:
                raise ValueError("提取的文本过短,可能是无效的 PDF")

            # 3. 插入 LightRAG
            rag = await get_rag_service()
            await rag.insert_document(
                text=text,
                metadata={
                    "doc_id": doc_id,
                    "filename": doc.filename,
                    "filepath": str(filepath),
                },
            )

            # 4. 更新状态为 COMPLETED
            doc.status = DocumentStatus.COMPLETED
            await db.commit()

        except Exception as e:
            # 5. 异常处理:标记 FAILED
            result = await db.execute(
                select(Document).where(Document.id == doc_id)
            )
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = DocumentStatus.FAILED
                doc.error_message = str(e)[:1000]  # 限制错误信息长度
                await db.commit()


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
    # 1. 验证文件类型
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 PDF 文件"
        )

    # 2. 读取文件内容
    content = await file.read()
    filesize = len(content)

    # 验证文件大小
    max_size = settings.max_file_size_mb * 1024 * 1024
    if filesize > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小超过限制({settings.max_file_size_mb}MB)",
        )

    if filesize == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="文件为空"
        )

    # 3. 计算 SHA256 哈希
    sha256 = _calculate_sha256(content)

    # 4. 检查是否已存在
    result = await db.execute(select(Document).where(Document.sha256 == sha256))
    existing_doc = result.scalar_one_or_none()
    if existing_doc:
        # 如果文档处理失败,允许重新处理
        if existing_doc.status == DocumentStatus.FAILED:
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

    # 8. 触发后台处理任务
    background_tasks.add_task(_process_document_background, doc.id, filepath)

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
    db: AsyncSession = Depends(get_async_session),
) -> DocumentListResponse:
    """
    获取文档列表(分页)
    """
    # 查询总数
    count_result = await db.execute(select(Document))
    total = len(count_result.scalars().all())

    # 查询分页数据
    offset = (page - 1) * page_size
    result = await db.execute(
        select(Document)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = result.scalars().all()

    return DocumentListResponse(
        total=total,
        items=[DocumentListItem.model_validate(doc) for doc in items],
    )
