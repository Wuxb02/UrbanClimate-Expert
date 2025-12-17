"""
Pytest 配置文件

提供全局的测试 fixtures 和配置
"""
import asyncio
import sys
from pathlib import Path

import pytest

# 添加项目根目录到 Python 路径
backend_dir = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(backend_dir))


@pytest.fixture(scope="session")
def event_loop():
    """
    创建事件循环供整个测试会话使用

    解决 pytest-asyncio 的事件循环问题
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def tmp_upload_dir(tmp_path):
    """创建临时上传目录"""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir(exist_ok=True)
    return upload_dir


@pytest.fixture
def sample_text_content():
    """样本文本内容"""
    return """Urban Heat Island Effect

The urban heat island effect refers to the phenomenon where urban areas
experience higher temperatures than surrounding rural areas.

Key Factors:
1. Building materials with high thermal mass
2. Reduced vegetation and evapotranspiration
3. Anthropogenic heat emissions
4. Altered surface albedo

Research shows temperature differences can exceed 5°C during peak hours.

Mitigation strategies include:
- Green roofs and walls
- Urban tree planting
- Cool pavement materials
- Strategic urban planning"""


@pytest.fixture
def sample_text_with_references():
    """带参考文献的样本文本"""
    return """Urban Climate Research

Main content discussing urban climate phenomena.

Temperature variations across different urban zones.

References

[1] Johnson, A. (2020). Urban Heat Islands. Climate Journal.
[2] Smith, B. (2019). Mitigation Strategies. Urban Studies."""


# Pytest 标记配置
def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line(
        "markers", "unit: 单元测试"
    )
    config.addinivalue_line(
        "markers", "integration: 集成测试"
    )
    config.addinivalue_line(
        "markers", "slow: 慢速测试(需要更长时间)"
    )
    config.addinivalue_line(
        "markers", "requires_db: 需要数据库的测试"
    )
    config.addinivalue_line(
        "markers", "requires_pdf: 需要 PDF 文件的测试"
    )


# 测试收集钩子
def pytest_collection_modifyitems(config, items):
    """自动为测试添加标记"""
    for item in items:
        # 为集成测试添加标记
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)

        # 为需要数据库的测试添加标记
        if "db" in item.nodeid.lower():
            item.add_marker(pytest.mark.requires_db)

        # 为慢速测试添加标记
        if "test_upload_to_completion" in item.nodeid:
            item.add_marker(pytest.mark.slow)
