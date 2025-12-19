"""
文档相关 Schema 定义

包含:
- DocumentUploadResponse: 文档上传响应
- DocumentStatusResponse: 文档状态查询响应
- DocumentListItem: 文档列表项
- DocumentListResponse: 文档列表响应
- DocumentDeleteResponse: 文档删除响应
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import DocumentStatus


class DocumentUploadResponse(BaseModel):
    """文档上传响应"""

    id: int = Field(..., description="文档ID")
    filename: str = Field(..., description="文件名")
    sha256: str = Field(..., description="文件哈希")
    status: DocumentStatus = Field(..., description="处理状态")
    created_at: datetime = Field(..., description="上传时间")

    model_config = ConfigDict(from_attributes=True)


class DocumentStatusResponse(BaseModel):
    """文档状态查询响应"""

    id: int
    filename: str
    status: DocumentStatus
    error_message: str | None = None
    total_chunks: int | None = None
    total_entities: int | None = None
    total_relationships: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListItem(BaseModel):
    """文档列表项"""

    id: int
    filename: str
    filesize: int
    status: DocumentStatus
    error_message: str | None = None
    summary: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    """文档列表响应"""

    total: int = Field(..., description="总数")
    items: list[DocumentListItem] = Field(..., description="文档列表")


class DocumentDeleteResponse(BaseModel):
    """文档删除响应"""

    id: int = Field(..., description="已删除的文档ID")
    message: str = Field(default="文档删除成功", description="操作结果信息")
