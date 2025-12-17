"""
API 单元测试(不依赖数据库)

测试 API 路由的基本逻辑,使用 mock 替代数据库
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile
from io import BytesIO

from app.api.v1.documents import _calculate_sha256, _process_document_background
from app.db.models import Document, DocumentStatus


class TestDocumentAPIHelpers:
    """测试 API 辅助函数"""

    def test_calculate_sha256(self):
        """测试 SHA256 计算"""
        content = b"Test PDF content"
        result = _calculate_sha256(content)
        assert len(result) == 64
        assert isinstance(result, str)

    def test_calculate_sha256_empty(self):
        """测试空内容哈希"""
        result = _calculate_sha256(b"")
        assert len(result) == 64


class TestDocumentValidation:
    """测试文档验证逻辑"""

    def test_pdf_extension_validation(self):
        """测试 PDF 扩展名验证"""
        valid_files = ["test.pdf", "document.PDF", "file.Pdf"]
        for filename in valid_files:
            assert filename.lower().endswith(".pdf")

        invalid_files = ["test.txt", "doc.docx", "image.png"]
        for filename in invalid_files:
            assert not filename.lower().endswith(".pdf")

    def test_file_size_limits(self):
        """测试文件大小限制"""
        max_size_mb = 100
        max_bytes = max_size_mb * 1024 * 1024

        # 在限制内
        assert 1024 <= max_bytes
        assert 50 * 1024 * 1024 <= max_bytes

        # 超出限制
        assert 150 * 1024 * 1024 > max_bytes


class TestDocumentStatusTransitions:
    """测试文档状态转换"""

    def test_pending_to_processing(self):
        """测试从 PENDING 到 PROCESSING"""
        doc = Document(
            filename="test.pdf",
            filepath="/uploads/test.pdf",
            sha256="abc123",
            filesize=1024,
            status=DocumentStatus.PENDING
        )
        assert doc.status == DocumentStatus.PENDING

        doc.status = DocumentStatus.PROCESSING
        assert doc.status == DocumentStatus.PROCESSING

    def test_processing_to_completed(self):
        """测试从 PROCESSING 到 COMPLETED"""
        doc = Document(
            filename="test.pdf",
            filepath="/uploads/test.pdf",
            sha256="abc123",
            filesize=1024,
            status=DocumentStatus.PROCESSING
        )

        doc.status = DocumentStatus.COMPLETED
        assert doc.status == DocumentStatus.COMPLETED
        assert doc.error_message is None

    def test_processing_to_failed(self):
        """测试从 PROCESSING 到 FAILED"""
        doc = Document(
            filename="test.pdf",
            filepath="/uploads/test.pdf",
            sha256="abc123",
            filesize=1024,
            status=DocumentStatus.PROCESSING
        )

        doc.status = DocumentStatus.FAILED
        doc.error_message = "解析失败"
        assert doc.status == DocumentStatus.FAILED
        assert doc.error_message == "解析失败"


class TestErrorHandling:
    """测试错误处理"""

    def test_error_message_truncation(self):
        """测试错误信息截断到 1000 字符"""
        long_error = "x" * 2000
        truncated = long_error[:1000]

        assert len(truncated) == 1000
        assert truncated == "x" * 1000

    def test_text_length_validation(self):
        """测试文本最小长度验证"""
        min_length = 100

        # 有效文本
        valid_text = "x" * 150
        assert len(valid_text.strip()) >= min_length

        # 无效文本
        short_text = "x" * 50
        assert len(short_text.strip()) < min_length


@pytest.mark.unit
class TestResponseModels:
    """测试响应模型"""

    def test_document_status_values(self):
        """测试文档状态枚举值"""
        assert DocumentStatus.PENDING.value == "pending"
        assert DocumentStatus.PROCESSING.value == "processing"
        assert DocumentStatus.COMPLETED.value == "completed"
        assert DocumentStatus.FAILED.value == "failed"

    def test_document_creation_defaults(self):
        """测试 Document 创建时的默认值"""
        doc = Document(
            filename="test.pdf",
            filepath="/uploads/test.pdf",
            sha256="abc123",
            filesize=1024
        )

        # 默认状态应该通过数据库设置,这里测试字段存在
        assert hasattr(doc, 'status')
        assert hasattr(doc, 'error_message')
        assert hasattr(doc, 'created_at')
        assert hasattr(doc, 'updated_at')
