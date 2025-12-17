"""
PDF 解析服务 - 使用 MinerU

功能:
- 使用 MinerU 从 PDF 提取结构化文本 (Markdown 格式)
- 支持公式、表格、多栏布局的精确提取
- 保留 LaTeX 格式
"""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Protocol

# 在导入 MinerU 之前设置模型源环境变量
# 使用 modelscope 作为模型源（中国大陆网络友好）
# 这样可以避免每次都从 HuggingFace 下载模型
if "MINERU_MODEL_SOURCE" not in os.environ:
    os.environ["MINERU_MODEL_SOURCE"] = "modelscope"

from mineru.cli.common import (
    convert_pdf_bytes_to_bytes_by_pypdfium2,
    prepare_env,
    read_fn,
)
from mineru.data.data_reader_writer import FileBasedDataWriter
from mineru.backend.pipeline.pipeline_analyze import (
    doc_analyze as pipeline_doc_analyze,
)
from mineru.backend.pipeline.model_json_to_middle_json import (
    result_to_middle_json as pipeline_result_to_middle_json,
)
from mineru.backend.pipeline.pipeline_middle_json_mkcontent import (
    union_make as pipeline_union_make,
)
from mineru.utils.enum_class import MakeMode
from loguru import logger


class PDFParser(Protocol):
    """PDF 解析器接口"""

    def extract_text(self, pdf_path: Path) -> str: ...


def _normalize_whitespace(text: str) -> str:
    """
    规范化空白字符

    - 将多个空格压缩为一个
    - 将多个换行压缩为最多两个(保留段落分隔)
    - 去除行首行尾空白
    """
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(lines)


def parse_pdf_text(pdf_path: Path, lang: str = "ch") -> str:
    """
    使用 MinerU 提取 PDF 文本

    MinerU 会输出 Markdown 格式的结构化文本，
    包含公式、表格等信息。

    Args:
        pdf_path: PDF 文件路径
        lang: OCR 语言选项，默认 'ch'（中文，同时支持英文识别）
              可选值:
              - 'ch': 中文（支持中英文混合，推荐用于中英文文档）
              - 'en': 英文
              - 'ch_server': 中文服务器版
              - 'ch_lite': 中文轻量版
              - 'korean': 韩文
              - 'japan': 日文
              - 'chinese_cht': 繁体中文

    Returns:
        提取的 Markdown 格式文本

    Raises:
        ValueError: PDF 文件无法打开或解析失败

    Note:
        'ch' 模式使用的 OCR 模型可以同时识别中文和英文，
        适用于大多数中英文混合的学术文档。
    """

    if not pdf_path.exists():
        raise ValueError(f"PDF 文件不存在: {pdf_path}")

    # 创建临时输出目录
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir)

        try:
            # 1. 读取 PDF 文件
            pdf_bytes = read_fn(str(pdf_path))
            pdf_file_name = pdf_path.stem

            # 2. 转换 PDF 字节（处理页面范围）
            pdf_bytes = convert_pdf_bytes_to_bytes_by_pypdfium2(
                pdf_bytes, start_page_id=0, end_page_id=None
            )

            # 3. 使用 pipeline 后端解析 PDF
            infer_results, all_image_lists, all_pdf_docs, lang_list, ocr_enabled_list = (
                pipeline_doc_analyze(
                    [pdf_bytes],
                    [lang],
                    parse_method="auto",
                    formula_enable=True,
                    table_enable=True,
                )
            )

            # 4. 处理解析结果
            model_list = infer_results[0]
            images_list = all_image_lists[0]
            pdf_doc = all_pdf_docs[0]
            _lang = lang_list[0]
            _ocr_enable = ocr_enabled_list[0]

            # 准备输出目录
            local_image_dir, local_md_dir = prepare_env(
                str(output_dir), pdf_file_name, "auto"
            )
            image_writer = FileBasedDataWriter(local_image_dir)

            # 5. 转换为中间 JSON 格式
            middle_json = pipeline_result_to_middle_json(
                model_list,
                images_list,
                pdf_doc,
                image_writer,
                _lang,
                _ocr_enable,
                formula_enabled=True,
            )

            pdf_info = middle_json["pdf_info"]
            image_dir = str(os.path.basename(local_image_dir))

            # 6. 生成 Markdown 内容
            md_content = pipeline_union_make(pdf_info, MakeMode.MM_MD, image_dir)

            # 7. 规范化空白字符
            md_content = _normalize_whitespace(md_content)

            logger.info(
                f"MinerU 解析完成: {pdf_path.name}, 输出长度: {len(md_content)}"
            )
            return md_content.strip()

        except Exception as e:
            logger.exception(f"MinerU PDF 解析失败: {pdf_path}")
            raise ValueError(f"MinerU PDF 解析失败: {str(e)}")


def validate_pdf(pdf_path: Path) -> tuple[bool, str | None]:
    """
    验证 PDF 文件是否有效

    Args:
        pdf_path: PDF 文件路径

    Returns:
        (是否有效, 错误信息)
    """
    if not pdf_path.exists():
        return False, "文件不存在"

    if not pdf_path.is_file():
        return False, "不是有效的文件"

    if pdf_path.suffix.lower() != ".pdf":
        return False, "不是 PDF 文件"

    # 简单检查 PDF 头部
    try:
        with open(pdf_path, "rb") as f:
            header = f.read(8)
            if not header.startswith(b"%PDF"):
                return False, "不是有效的 PDF 文件格式"
        return True, None
    except Exception as e:
        return False, f"PDF 验证失败: {str(e)}"
