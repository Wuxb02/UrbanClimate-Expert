"""
文档上传 API 集成测试

测试完整的上传流程:上传 -> 后台处理 -> 状态查询

注意: 这些测试需要实际的数据库连接和完整的应用环境
建议在配置好 MySQL 后运行这些测试
"""
import asyncio
from io import BytesIO
from pathlib import Path

import pytest

# 标记所有集成测试为需要数据库
pytestmark = pytest.mark.requires_db

# 注意: 集成测试暂时跳过,因为需要完整的数据库环境
# 这些测试应该在配置好 MySQL 后运行
pytest.skip("集成测试需要完整的数据库环境,请在配置 MySQL 后运行", allow_module_level=True)


@pytest.fixture
async def test_db_engine():
    """创建测试数据库引擎"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False}
    )

    # 创建所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # 清理:删除所有表
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def test_db_session(test_db_engine):
    """创建测试数据库会话"""
    async_session = sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest.fixture
def sample_pdf_bytes():
    """样本 PDF 文件内容"""
    # 最简单的有效 PDF
    return b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\nxref\n0 2\ntrailer\n<<\n/Size 2\n/Root 1 0 R\n>>\nstartxref\n0\n%%EOF"


@pytest.fixture
def cleanup_uploads():
    """清理测试上传的文件"""
    yield
    # 测试后清理
    upload_dir = settings.upload_dir_path
    if upload_dir.exists():
        for file in upload_dir.glob("*.pdf"):
            try:
                file.unlink()
            except Exception:
                pass


class TestDocumentUploadAPI:
    """文档上传 API 集成测试"""

    @pytest.mark.asyncio
    async def test_upload_valid_pdf(
        self,
        test_db_session,
        sample_pdf_bytes,
        cleanup_uploads
    ):
        """测试上传有效的 PDF 文件"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 准备上传文件
            files = {
                "file": ("test.pdf", BytesIO(sample_pdf_bytes), "application/pdf")
            }

            # 发送上传请求
            response = await client.post("/api/v1/documents/upload", files=files)

            # 验证响应
            assert response.status_code == 202  # Accepted
            data = response.json()
            assert "id" in data
            assert data["filename"] == "test.pdf"
            assert "sha256" in data
            assert data["status"] in ["pending", "processing"]

    @pytest.mark.asyncio
    async def test_upload_duplicate_file(
        self,
        test_db_session,
        sample_pdf_bytes,
        cleanup_uploads
    ):
        """测试上传重复文件(去重)"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            files = {
                "file": ("test.pdf", BytesIO(sample_pdf_bytes), "application/pdf")
            }

            # 第一次上传
            response1 = await client.post("/api/v1/documents/upload", files=files)
            assert response1.status_code == 202
            doc_id1 = response1.json()["id"]

            # 第二次上传相同文件
            files = {
                "file": ("test.pdf", BytesIO(sample_pdf_bytes), "application/pdf")
            }
            response2 = await client.post("/api/v1/documents/upload", files=files)
            assert response2.status_code == 202
            doc_id2 = response2.json()["id"]

            # 应返回同一个文档
            assert doc_id1 == doc_id2

    @pytest.mark.asyncio
    async def test_upload_invalid_file_type(self):
        """测试上传非 PDF 文件"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 上传 TXT 文件
            files = {
                "file": ("test.txt", BytesIO(b"Not a PDF"), "text/plain")
            }

            response = await client.post("/api/v1/documents/upload", files=files)
            assert response.status_code == 400
            assert "仅支持 PDF 文件" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_empty_file(self):
        """测试上传空文件"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            files = {
                "file": ("empty.pdf", BytesIO(b""), "application/pdf")
            }

            response = await client.post("/api/v1/documents/upload", files=files)
            assert response.status_code == 400
            assert "文件为空" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_oversized_file(self):
        """测试上传超大文件"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 创建超过限制的文件内容
            max_size = settings.max_file_size_mb * 1024 * 1024
            oversized_content = b"x" * (max_size + 1000)

            files = {
                "file": ("huge.pdf", BytesIO(oversized_content), "application/pdf")
            }

            response = await client.post("/api/v1/documents/upload", files=files)
            assert response.status_code == 413
            assert "文件大小超过限制" in response.json()["detail"]


class TestDocumentStatusAPI:
    """文档状态查询 API 测试"""

    @pytest.mark.asyncio
    async def test_get_document_status_exists(
        self,
        test_db_session,
        sample_pdf_bytes,
        cleanup_uploads
    ):
        """测试查询已存在文档的状态"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 先上传文件
            files = {
                "file": ("test.pdf", BytesIO(sample_pdf_bytes), "application/pdf")
            }
            upload_response = await client.post(
                "/api/v1/documents/upload",
                files=files
            )
            doc_id = upload_response.json()["id"]

            # 查询状态
            status_response = await client.get(f"/api/v1/documents/{doc_id}")
            assert status_response.status_code == 200

            data = status_response.json()
            assert data["id"] == doc_id
            assert data["filename"] == "test.pdf"
            assert data["status"] in [
                "pending",
                "processing",
                "completed",
                "failed"
            ]

    @pytest.mark.asyncio
    async def test_get_document_status_not_found(self):
        """测试查询不存在的文档"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/documents/99999")
            assert response.status_code == 404
            assert "文档不存在" in response.json()["detail"]


class TestDocumentListAPI:
    """文档列表 API 测试"""

    @pytest.mark.asyncio
    async def test_list_documents_empty(self):
        """测试查询空列表"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/documents")
            assert response.status_code == 200

            data = response.json()
            assert "total" in data
            assert "items" in data
            assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_list_documents_pagination(
        self,
        test_db_session,
        sample_pdf_bytes,
        cleanup_uploads
    ):
        """测试分页功能"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 上传多个文件
            for i in range(5):
                content = sample_pdf_bytes + str(i).encode()
                files = {
                    "file": (f"test{i}.pdf", BytesIO(content), "application/pdf")
                }
                await client.post("/api/v1/documents/upload", files=files)

            # 查询第一页
            response = await client.get("/api/v1/documents?page=1&page_size=3")
            assert response.status_code == 200

            data = response.json()
            assert data["total"] >= 5
            assert len(data["items"]) <= 3

    @pytest.mark.asyncio
    async def test_list_documents_ordering(
        self,
        test_db_session,
        sample_pdf_bytes,
        cleanup_uploads
    ):
        """测试按时间倒序排列"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 上传文件
            files = {
                "file": ("test.pdf", BytesIO(sample_pdf_bytes), "application/pdf")
            }
            await client.post("/api/v1/documents/upload", files=files)

            # 稍作延迟
            await asyncio.sleep(0.1)

            # 上传第二个文件
            content2 = sample_pdf_bytes + b"2"
            files2 = {
                "file": ("test2.pdf", BytesIO(content2), "application/pdf")
            }
            await client.post("/api/v1/documents/upload", files=files2)

            # 查询列表
            response = await client.get("/api/v1/documents")
            data = response.json()

            # 验证最新的文档在前面
            if len(data["items"]) >= 2:
                assert data["items"][0]["filename"] == "test2.pdf"


class TestEndToEndFlow:
    """端到端流程测试"""

    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_upload_to_completion(
        self,
        test_db_session,
        sample_pdf_bytes,
        cleanup_uploads
    ):
        """测试从上传到完成的完整流程"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            # 1. 上传文件
            files = {
                "file": ("test.pdf", BytesIO(sample_pdf_bytes), "application/pdf")
            }
            upload_response = await client.post(
                "/api/v1/documents/upload",
                files=files
            )
            assert upload_response.status_code == 202
            doc_id = upload_response.json()["id"]

            # 2. 轮询状态直到完成或失败
            max_attempts = 30
            for _ in range(max_attempts):
                status_response = await client.get(f"/api/v1/documents/{doc_id}")
                data = status_response.json()

                if data["status"] in ["completed", "failed"]:
                    break

                await asyncio.sleep(1)

            # 3. 验证最终状态
            final_response = await client.get(f"/api/v1/documents/{doc_id}")
            final_data = final_response.json()

            # 状态应该是 completed 或 failed (不应该仍在 processing)
            assert final_data["status"] in ["completed", "failed"]

            if final_data["status"] == "failed":
                # 如果失败,应该有错误信息
                assert final_data["error_message"] is not None
            else:
                # 如果成功,错误信息应该为空
                assert final_data["error_message"] is None


# Pytest 配置
def pytest_configure(config):
    """配置 pytest"""
    config.addinivalue_line("markers", "slow: 标记慢速测试")
