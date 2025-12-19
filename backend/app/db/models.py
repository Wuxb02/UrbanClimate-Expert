"""
数据库模型定义

包含:
- Document: 文档表,记录上传的 PDF 文档及其处理状态
"""
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    """异步 SQLAlchemy Base 类"""

    pass


class DocumentStatus(str, PyEnum):
    """
    文档处理状态枚举

    状态流转:
    PENDING -> PROCESSING -> COMPLETED (成功)
                          -> FAILED (失败)
    """

    PENDING = "pending"  # 已上传,等待处理
    PROCESSING = "processing"  # 正在解析和插入
    COMPLETED = "completed"  # 处理完成
    FAILED = "failed"  # 处理失败


class Document(Base):
    """
    文档表

    用于记录上传的 PDF 文档及其处理状态
    """

    __tablename__ = "documents"

    # 主键
    id = Column(
        Integer, primary_key=True, autoincrement=True, comment="文档ID"
    )

    # 文件信息
    filename = Column(
        String(255), nullable=False, index=True, comment="原始文件名"
    )
    filepath = Column(
        String(512), nullable=False, unique=True, comment="服务器存储路径"
    )
    sha256 = Column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
        comment="文件SHA256哈希(用于去重)",
    )
    filesize = Column(Integer, nullable=False, comment="文件大小(字节)")

    # 处理状态
    status = Column(
        Enum(DocumentStatus),
        nullable=False,
        default=DocumentStatus.PENDING,
        index=True,
        comment="处理状态",
    )
    error_message = Column(
        Text, nullable=True, comment="错误信息(仅在 FAILED 状态时填充)"
    )

    # LightRAG 关联信息
    total_chunks = Column(Integer, nullable=True, comment="分块数量")
    total_entities = Column(Integer, nullable=True, comment="提取的实体数量")
    total_relationships = Column(
        Integer, nullable=True, comment="提取的关系数量"
    )

    # 文档摘要
    summary = Column(
        Text, nullable=True, comment="LLM生成的文档摘要"
    )

    # 时间戳
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="上传时间",
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="最后更新时间",
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, filename={self.filename}, status={self.status})>"
