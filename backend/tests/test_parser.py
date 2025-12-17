"""
PDF 解析服务单元测试

测试 parser_service.py 中的各个清洗函数
"""
import pytest
from pathlib import Path

from app.services.parser_service import (
    _merge_hyphenated_lines,
    _normalize_whitespace,
    _remove_references_section,
    _strip_headers_footers,
    parse_pdf_text,
    validate_pdf,
)


class TestTextCleaning:
    """文本清洗函数测试"""

    def test_merge_hyphenated_lines(self):
        """测试合并连字符断行"""
        # 基本测试
        text = "environ-\nment analysis"
        result = _merge_hyphenated_lines(text)
        assert result == "environment analysis"

        # 多个连字符
        text = "environ-\nment manage-\nment"
        result = _merge_hyphenated_lines(text)
        assert result == "environment management"

        # 无连字符
        text = "environment analysis"
        result = _merge_hyphenated_lines(text)
        assert result == "environment analysis"

    def test_normalize_whitespace(self):
        """测试规范化空白字符"""
        # 多个空格
        text = "line1  line2   line3"
        result = _normalize_whitespace(text)
        assert result == "line1 line2 line3"

        # 多个换行
        text = "line1\n\n\n\nline2"
        result = _normalize_whitespace(text)
        assert result == "line1\n\nline2"

        # 行首行尾空白
        text = "  line1  \n  line2  "
        result = _normalize_whitespace(text)
        assert result == "line1\nline2"

    def test_remove_references_section(self):
        """测试去除参考文献部分"""
        # 英文 References
        text = "Main content\n\nReferences\n\n[1] Paper 1\n[2] Paper 2"
        result = _remove_references_section(text)
        assert "References" not in result
        assert "Main content" in result
        assert "[1] Paper 1" not in result

        # 中文参考文献
        text = "主要内容\n\n参考文献\n\n[1] 论文1"
        result = _remove_references_section(text)
        assert "参考文献" not in result
        assert "主要内容" in result

        # REFERENCES 大写
        text = "Content\n\nREFERENCES\n\n[1] Ref"
        result = _remove_references_section(text)
        assert "REFERENCES" not in result

        # 无参考文献
        text = "Only main content"
        result = _remove_references_section(text)
        assert result == "Only main content"

    def test_strip_headers_footers(self):
        """测试去除页眉页脚"""
        # 纯数字页码
        text = "1\nMain content\n50"
        result = _strip_headers_footers(text)
        assert result == "Main content"

        # Page 格式
        text = "Page 1\nContent here\nPage 2"
        result = _strip_headers_footers(text)
        assert result == "Content here"

        # 中文页码
        text = "第 1 页\n内容\n第 2 页"
        result = _strip_headers_footers(text)
        assert result == "内容"

        # 短文本不处理
        text = "Short"
        result = _strip_headers_footers(text, max_lines=2)
        assert result == "Short"


class TestPDFValidation:
    """PDF 文件验证测试"""

    def test_validate_pdf_not_exists(self, tmp_path):
        """测试文件不存在"""
        pdf_path = tmp_path / "nonexistent.pdf"
        is_valid, error_msg = validate_pdf(pdf_path)
        assert not is_valid
        assert "不存在" in error_msg

    def test_validate_pdf_not_file(self, tmp_path):
        """测试不是文件(是目录)"""
        dir_path = tmp_path / "test_dir"
        dir_path.mkdir()
        is_valid, error_msg = validate_pdf(dir_path)
        assert not is_valid
        assert "不是有效的文件" in error_msg

    def test_validate_pdf_wrong_extension(self, tmp_path):
        """测试错误的文件扩展名"""
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("Not a PDF")
        is_valid, error_msg = validate_pdf(txt_path)
        assert not is_valid
        assert "不是 PDF 文件" in error_msg

    @pytest.mark.skipif(
        not Path("backend/data/test.pdf").exists(),
        reason="需要测试 PDF 文件"
    )
    def test_validate_pdf_valid(self):
        """测试有效的 PDF 文件"""
        # 使用项目中的测试文件
        pdf_path = Path("backend/data/test.pdf")
        if pdf_path.exists():
            is_valid, error_msg = validate_pdf(pdf_path)
            assert is_valid
            assert error_msg is None


class TestPDFParsing:
    """PDF 解析测试"""

    @pytest.mark.skipif(
        not Path("backend/data/test.pdf").exists(),
        reason="需要测试 PDF 文件"
    )
    def test_parse_pdf_text_success(self):
        """测试成功解析 PDF"""
        pdf_path = Path("backend/data/test.pdf")
        if pdf_path.exists():
            text = parse_pdf_text(pdf_path)
            assert len(text) > 100
            assert isinstance(text, str)

    def test_parse_pdf_text_not_exists(self, tmp_path):
        """测试解析不存在的文件"""
        pdf_path = tmp_path / "nonexistent.pdf"
        with pytest.raises(ValueError, match="PDF 文件不存在"):
            parse_pdf_text(pdf_path)

    def test_parse_pdf_text_invalid(self, tmp_path):
        """测试解析损坏的 PDF"""
        # 创建一个假的 PDF 文件
        fake_pdf = tmp_path / "fake.pdf"
        fake_pdf.write_bytes(b"Not a real PDF content")

        with pytest.raises(ValueError, match="PDF"):
            parse_pdf_text(fake_pdf)


class TestIntegrationCleaning:
    """集成测试:完整清洗流程"""

    def test_full_cleaning_pipeline(self):
        """测试完整的清洗流程"""
        # 模拟 PDF 提取的原始文本
        raw_text = """Page 1
Urban heat island effect research

The urban heat-
island effect is a phenomenon where urban areas experi-
ence higher temperatures.

Main   content    here.


Multiple    spaces.


References

[1] Smith et al., 2020
[2] Jones, 2019
Page 2"""

        # 逐步应用清洗函数
        cleaned = _strip_headers_footers(raw_text)
        cleaned = _remove_references_section(cleaned)
        cleaned = _merge_hyphenated_lines(cleaned)
        cleaned = _normalize_whitespace(cleaned)

        # 验证结果
        assert "Page 1" not in cleaned
        assert "Page 2" not in cleaned
        assert "References" not in cleaned
        assert "[1] Smith" not in cleaned
        assert "heatisland" in cleaned  # 连字符已合并
        assert "Multiple spaces" in cleaned  # 空格已规范化
        assert cleaned.count("  ") == 0  # 无多余空格


# 测试配置
@pytest.fixture
def sample_pdf_content():
    """样本 PDF 文本内容"""
    return """Urban Climate Research

The study of urban climate involves understanding the complex
interactions between urban structures and atmospheric processes.

Key findings include temperature variations and air quality impacts.

References

[1] Johnson, A. (2020). Urban Climate Modeling.
[2] Smith, B. (2019). Heat Island Effects."""
