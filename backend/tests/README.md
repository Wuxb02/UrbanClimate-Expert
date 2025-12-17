# 测试文档

## 测试结构

```
tests/
├── conftest.py                     # Pytest 全局配置
├── requirements-test.txt           # 测试依赖
├── test_parser.py                  # PDF 解析单元测试
├── test_documents.py               # 文档 API 单元测试
└── test_documents_integration.py   # 文档 API 集成测试
```

## 安装测试依赖

```bash
cd backend
"D:\anaconda\python.exe" -m pip install -r tests/requirements-test.txt
```

## 运行测试

### 运行所有测试
```bash
cd backend
"D:\anaconda\python.exe" -m pytest
```

### 运行特定测试文件
```bash
"D:\anaconda\python.exe" -m pytest tests/test_parser.py
"D:\anaconda\python.exe" -m pytest tests/test_documents.py
"D:\anaconda\python.exe" -m pytest tests/test_documents_integration.py
```

### 运行特定测试类
```bash
"D:\anaconda\python.exe" -m pytest tests/test_parser.py::TestTextCleaning
```

### 运行特定测试函数
```bash
"D:\anaconda\python.exe" -m pytest tests/test_parser.py::TestTextCleaning::test_merge_hyphenated_lines
```

### 根据标记运行测试
```bash
# 仅运行单元测试
"D:\anaconda\python.exe" -m pytest -m unit

# 仅运行集成测试
"D:\anaconda\python.exe" -m pytest -m integration

# 排除慢速测试
"D:\anaconda\python.exe" -m pytest -m "not slow"
```

### 带详细输出
```bash
"D:\anaconda\python.exe" -m pytest -v -s
```

### 查看测试覆盖率
```bash
"D:\anaconda\python.exe" -m pytest --cov=app --cov-report=html
# 打开 htmlcov/index.html 查看详细报告
```

### 仅运行失败的测试
```bash
"D:\anaconda\python.exe" -m pytest --lf
```

### 并行运行测试(需要 pytest-xdist)
```bash
"D:\anaconda\python.exe" -m pip install pytest-xdist
"D:\anaconda\python.exe" -m pytest -n auto
```

## 测试说明

### 1. test_parser.py - PDF 解析单元测试

**测试内容**:
- 文本清洗函数(去除页眉页脚、参考文献、合并断行、规范化空白)
- PDF 文件验证
- PDF 解析功能

**测试类**:
- `TestTextCleaning` - 各个清洗函数的单元测试
- `TestPDFValidation` - PDF 文件验证测试
- `TestPDFParsing` - PDF 解析测试
- `TestIntegrationCleaning` - 完整清洗流程集成测试

**运行示例**:
```bash
"D:\anaconda\python.exe" -m pytest tests/test_parser.py -v
```

### 2. test_documents.py - 文档 API 单元测试

**测试内容**:
- SHA256 哈希计算
- Document 模型基本功能
- 文件验证逻辑
- 文档去重逻辑
- 状态流转逻辑
- 后台任务辅助功能

**测试类**:
- `TestSHA256Calculation` - 哈希计算测试
- `TestDocumentModel` - 模型功能测试
- `TestFileValidation` - 文件验证测试
- `TestDocumentDeduplication` - 去重测试
- `TestDocumentStatusFlow` - 状态流转测试
- `TestBackgroundTaskLogic` - 后台任务逻辑测试

**运行示例**:
```bash
"D:\anaconda\python.exe" -m pytest tests/test_documents.py -v
```

### 3. test_documents_integration.py - 文档 API 集成测试

**测试内容**:
- 完整的文档上传流程
- 文档状态查询
- 文档列表查询
- 端到端测试

**测试类**:
- `TestDocumentUploadAPI` - 上传 API 测试
- `TestDocumentStatusAPI` - 状态查询 API 测试
- `TestDocumentListAPI` - 列表查询 API 测试
- `TestEndToEndFlow` - 端到端流程测试

**运行示例**:
```bash
"D:\anaconda\python.exe" -m pytest tests/test_documents_integration.py -v
```

**注意**: 集成测试会创建临时数据库和文件,测试完成后自动清理。

## 测试标记

项目使用以下测试标记:

- `@pytest.mark.unit` - 单元测试
- `@pytest.mark.integration` - 集成测试
- `@pytest.mark.slow` - 慢速测试(运行时间 > 5秒)
- `@pytest.mark.requires_db` - 需要数据库的测试
- `@pytest.mark.requires_pdf` - 需要实际 PDF 文件的测试

## 测试 Fixtures

在 `conftest.py` 中定义的全局 fixtures:

- `event_loop` - 异步事件循环
- `tmp_upload_dir` - 临时上传目录
- `sample_text_content` - 样本文本内容
- `sample_text_with_references` - 带参考文献的样本文本

在各测试文件中定义的 fixtures:

- `sample_pdf_bytes` - 样本 PDF 二进制内容
- `test_db_engine` - 测试数据库引擎
- `test_db_session` - 测试数据库会话
- `cleanup_uploads` - 清理上传文件

## 常见问题

### 1. 导入错误

**问题**: `ModuleNotFoundError: No module named 'app'`

**解决**: 确保从 `backend/` 目录运行测试:
```bash
cd backend
"D:\anaconda\python.exe" -m pytest
```

### 2. 异步测试失败

**问题**: `RuntimeError: Event loop is closed`

**解决**: 确保安装了 `pytest-asyncio`:
```bash
"D:\anaconda\python.exe" -m pip install pytest-asyncio
```

### 3. 数据库连接错误

**问题**: 集成测试中的数据库连接失败

**解决**: 集成测试使用 SQLite 内存数据库,不需要外部数据库。确保安装 `aiosqlite`:
```bash
"D:\anaconda\python.exe" -m pip install aiosqlite
```

### 4. PDF 文件缺失

**问题**: 某些测试需要实际的 PDF 文件

**解决**: 这些测试会自动跳过(使用 `@pytest.mark.skipif`)。如果想运行,需要在 `backend/data/` 目录下放置 `test.pdf` 文件。

## 持续集成 (CI)

可以在 CI/CD 管道中使用以下命令:

```bash
# 安装依赖
"D:\anaconda\python.exe" -m pip install -r requirements.txt
"D:\anaconda\python.exe" -m pip install -r tests/requirements-test.txt

# 代码格式检查
"D:\anaconda\python.exe" -m black --check app/
"D:\anaconda\python.exe" -m isort --check-only app/
"D:\anaconda\python.exe" -m flake8 app/

# 运行测试
"D:\anaconda\python.exe" -m pytest --cov=app --cov-report=xml

# 类型检查
"D:\anaconda\python.exe" -m mypy app/
```

## 编写新测试

### 单元测试模板

```python
import pytest

class TestYourFeature:
    """功能描述"""

    def test_basic_functionality(self):
        """测试基本功能"""
        # Arrange
        input_data = "test"

        # Act
        result = your_function(input_data)

        # Assert
        assert result == expected_output

    @pytest.mark.parametrize("input,expected", [
        ("input1", "output1"),
        ("input2", "output2"),
    ])
    def test_with_parameters(self, input, expected):
        """参数化测试"""
        assert your_function(input) == expected
```

### 异步测试模板

```python
import pytest

class TestAsyncFeature:
    """异步功能测试"""

    @pytest.mark.asyncio
    async def test_async_function(self):
        """测试异步函数"""
        result = await your_async_function()
        assert result is not None
```

### 集成测试模板

```python
import pytest
from httpx import AsyncClient
from app.main import app

class TestAPIIntegration:
    """API 集成测试"""

    @pytest.mark.asyncio
    async def test_api_endpoint(self):
        """测试 API 端点"""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/api/v1/endpoint")
            assert response.status_code == 200
```

## 测试最佳实践

1. **测试命名**: 使用描述性的测试名称,清楚说明测试内容
2. **AAA 模式**: Arrange(准备), Act(执行), Assert(断言)
3. **单一职责**: 每个测试只测试一个功能点
4. **独立性**: 测试之间不应相互依赖
5. **可重复性**: 测试结果应该稳定可重复
6. **速度**: 单元测试应该快速(<1秒),慢速测试使用 `@pytest.mark.slow`
7. **清理**: 使用 fixtures 自动清理测试数据

## 测试覆盖率目标

- **整体覆盖率**: > 80%
- **核心模块**: > 90%
  - `app/db/models.py`
  - `app/services/parser_service.py`
  - `app/api/v1/documents.py`
- **工具函数**: > 95%

当前覆盖率可通过以下命令查看:
```bash
"D:\anaconda\python.exe" -m pytest --cov=app --cov-report=term-missing
```
