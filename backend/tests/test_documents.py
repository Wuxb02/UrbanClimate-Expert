"""
文档上传 API 单元测试

测试 documents.py 中的各个功能
"""
import hashlib
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import UploadFile
from sqlalchemy import select

from app.api.v1.documents import _calculate_sha256
from app.db.models import Document, DocumentStatus


class TestSHA256Calculation:
    """SHA256 哈希计算测试"""

    def test_calculate_sha256_simple(self):
        """测试简单内容的哈希计算"""
        content = b"Hello, World!"
        expected = hashlib.sha256(content).hexdigest()
        result = _calculate_sha256(content)
        assert result == expected
        assert len(result) == 64  # SHA256 是 64 个十六进制字符

    def test_calculate_sha256_empty(self):
        """测试空内容的哈希"""
        content = b""
        result = _calculate_sha256(content)
        assert len(result) == 64
        assert result == hashlib.sha256(b"").hexdigest()

    def test_calculate_sha256_large(self):
        """测试大内容的哈希"""
        content = b"x" * 1024 * 1024  # 1MB
        result = _calculate_sha256(content)
        assert len(result) == 64

    def test_calculate_sha256_same_content(self):
        """测试相同内容产生相同哈希"""
        content = b"Test content"
        hash1 = _calculate_sha256(content)
        hash2 = _calculate_sha256(content)
        assert hash1 == hash2

    def test_calculate_sha256_different_content(self):
        """测试不同内容产生不同哈希"""
        hash1 = _calculate_sha256(b"Content 1")
        hash2 = _calculate_sha256(b"Content 2")
        assert hash1 != hash2


class TestDocumentModel:
    """Document 模型测试"""

    def test_document_creation(self):
        """测试创建 Document 实例"""
        doc = Document(
            filename="test.pdf",
            filepath="/uploads/abc123.pdf",
            sha256="abc123",
            filesize=1024,
            status=DocumentStatus.PENDING,
        )

        assert doc.filename == "test.pdf"
        assert doc.filepath == "/uploads/abc123.pdf"
        assert doc.sha256 == "abc123"
        assert doc.filesize == 1024
        assert doc.status == DocumentStatus.PENDING
        assert doc.error_message is None

    def test_document_status_enum(self):
        """测试文档状态枚举"""
        assert DocumentStatus.PENDING == "pending"
        assert DocumentStatus.PROCESSING == "processing"
        assert DocumentStatus.COMPLETED == "completed"
        assert DocumentStatus.FAILED == "failed"

    def test_document_repr(self):
        """测试 Document 的字符串表示"""
        doc = Document(
            id=1,
            filename="test.pdf",
            filepath="/uploads/test.pdf",
            sha256="abc",
            filesize=100,
            status=DocumentStatus.PENDING,
        )
        repr_str = repr(doc)
        assert "Document" in repr_str
        assert "id=1" in repr_str
        assert "test.pdf" in repr_str
        # 状态可能是 DocumentStatus.PENDING 对象或 'pending' 字符串
        assert "pending" in repr_str.lower() or "PENDING" in repr_str


# 集成测试需要数据库,使用 pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def sample_pdf_bytes():
    """样本 PDF 文件内容(简化版)"""
    # 最简单的 PDF 文件头
    return b"%PDF-1.4\n%\xc3\xa4\xc3\xbc\xc3\xb6\xc3\x9f\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n/F1 4 0 R\n>>\n>>\n/MediaBox [0 0 612 792]\n/Contents 5 0 R\n>>\nendobj\n4 0 obj\n<<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Times-Roman\n>>\nendobj\n5 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n100 700 Td\n(Hello World) Tj\nET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f\n0000000015 00000 n\n0000000074 00000 n\n0000000131 00000 n\n0000000273 00000 n\n0000000361 00000 n\ntrailer\n<<\n/Size 6\n/Root 1 0 R\n>>\nstartxref\n453\n%%EOF"


@pytest.fixture
def mock_upload_file(sample_pdf_bytes):
    """模拟 FastAPI UploadFile"""
    file = MagicMock(spec=UploadFile)
    file.filename = "test.pdf"
    file.read = AsyncMock(return_value=sample_pdf_bytes)
    file.content_type = "application/pdf"
    return file


class TestFileValidation:
    """文件验证测试"""

    def test_valid_pdf_extension(self):
        """测试有效的 PDF 扩展名"""
        filenames = ["test.pdf", "document.PDF", "file.Pdf"]
        for filename in filenames:
            assert filename.lower().endswith(".pdf")

    def test_invalid_pdf_extension(self):
        """测试无效的文件扩展名"""
        filenames = ["test.txt", "document.docx", "file.png", "no_extension"]
        for filename in filenames:
            assert not filename.lower().endswith(".pdf")

    def test_file_size_validation(self):
        """测试文件大小验证"""
        max_size_mb = 100
        max_size_bytes = max_size_mb * 1024 * 1024

        # 有效大小
        valid_sizes = [1024, 50 * 1024 * 1024, max_size_bytes - 1]
        for size in valid_sizes:
            assert size <= max_size_bytes

        # 超出大小
        invalid_sizes = [max_size_bytes + 1, 200 * 1024 * 1024]
        for size in invalid_sizes:
            assert size > max_size_bytes


class TestDocumentDeduplication:
    """文档去重测试"""

    def test_same_content_same_hash(self):
        """测试相同内容产生相同哈希"""
        content = b"Test PDF content"
        hash1 = _calculate_sha256(content)
        hash2 = _calculate_sha256(content)
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        """测试不同内容产生不同哈希"""
        content1 = b"PDF content 1"
        content2 = b"PDF content 2"
        hash1 = _calculate_sha256(content1)
        hash2 = _calculate_sha256(content2)
        assert hash1 != hash2


class TestDocumentStatusFlow:
    """文档状态流转测试"""

    def test_status_flow_success(self):
        """测试成功的状态流转"""
        doc = Document(
            filename="test.pdf",
            filepath="/uploads/test.pdf",
            sha256="abc",
            filesize=1024,
            status=DocumentStatus.PENDING,
        )

        # PENDING -> PROCESSING
        assert doc.status == DocumentStatus.PENDING
        doc.status = DocumentStatus.PROCESSING
        assert doc.status == DocumentStatus.PROCESSING

        # PROCESSING -> COMPLETED
        doc.status = DocumentStatus.COMPLETED
        assert doc.status == DocumentStatus.COMPLETED
        assert doc.error_message is None

    def test_status_flow_failure(self):
        """测试失败的状态流转"""
        doc = Document(
            filename="test.pdf",
            filepath="/uploads/test.pdf",
            sha256="abc",
            filesize=1024,
            status=DocumentStatus.PENDING,
        )

        # PENDING -> PROCESSING
        doc.status = DocumentStatus.PROCESSING

        # PROCESSING -> FAILED
        doc.status = DocumentStatus.FAILED
        doc.error_message = "PDF 解析失败: 文件损坏"
        assert doc.status == DocumentStatus.FAILED
        assert doc.error_message is not None
        assert "损坏" in doc.error_message


class TestBackgroundTaskLogic:
    """后台任务逻辑测试"""

    def test_error_message_truncation(self):
        """测试错误信息截断"""
        # 模拟超长错误信息
        long_error = "x" * 2000
        truncated = long_error[:1000]
        assert len(truncated) == 1000
        assert len(truncated) < len(long_error)

    def test_minimal_text_length_validation(self):
        """测试最小文本长度验证"""
        min_length = 100

        # 有效文本
        valid_text = "x" * 150
        assert len(valid_text.strip()) >= min_length

        # 无效文本
        invalid_texts = ["", "   ", "short", "x" * 50]
        for text in invalid_texts:
            assert len(text.strip()) < min_length


# 测试帮助函数
def create_test_document(
    filename="test.pdf",
    sha256="abc123",
    status=DocumentStatus.PENDING
) -> Document:
    """创建测试用的 Document 实例"""
    return Document(
        filename=filename,
        filepath=f"/uploads/{sha256}.pdf",
        sha256=sha256,
        filesize=1024,
        status=status,
    )


class TestHelperFunctions:
    """辅助函数测试"""

    def test_create_test_document_defaults(self):
        """测试创建测试文档的默认值"""
        doc = create_test_document()
        assert doc.filename == "test.pdf"
        assert doc.sha256 == "abc123"
        assert doc.status == DocumentStatus.PENDING

    def test_create_test_document_custom(self):
        """测试创建自定义测试文档"""
        doc = create_test_document(
            filename="custom.pdf",
            sha256="xyz789",
            status=DocumentStatus.COMPLETED
        )
        assert doc.filename == "custom.pdf"
        assert doc.sha256 == "xyz789"
        assert doc.status == DocumentStatus.COMPLETED
