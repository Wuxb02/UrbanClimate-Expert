"""
PDF 解析服务 - 使用 MinerU 在线 API

功能:
- 通过 MinerU 在线 API 解析 PDF
- 支持本地文件上传（通过获取上传链接）
- 轮询任务状态获取解析结果
- 下载并提取 Markdown 结果
- 支持异步请求和重试机制

API 流程:
1. POST /file-urls/batch - 申请文件上传链接
2. PUT {upload_url} - 上传文件
3. GET /extract-results/batch/{batch_id} - 轮询任务状态
4. 下载 full_zip_url 中的 ZIP 文件
5. 从 ZIP 中提取 .md 文件内容
"""
from __future__ import annotations

import asyncio
import io
import re
import zipfile
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger

from app.core.config import settings


class MinerUAPIError(Exception):
    """MinerU API 调用异常"""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class MinerUParserService:
    """
    MinerU 在线 API 解析服务

    API 流程:
    1. POST /file-urls/batch - 申请文件上传链接
    2. PUT {upload_url} - 上传 PDF 文件
    3. GET /extract-results/batch/{batch_id} - 轮询任务状态
    4. 下载 full_zip_url 获取解析结果 ZIP
    5. 从 ZIP 中提取 .md 文件内容
    """

    def __init__(self):
        self.base_url = settings.mineru_api_url.rstrip("/")
        self.api_key = settings.mineru_api_key
        self.timeout = settings.mineru_api_timeout
        self.max_retries = settings.mineru_max_retries
        self.retry_delay = settings.mineru_retry_delay
        self.poll_interval = settings.mineru_poll_interval
        self.max_poll_time = settings.mineru_max_poll_time

    def _get_headers(self) -> dict[str, str]:
        """获取 API 请求头"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def _apply_upload_url(
        self,
        client: httpx.AsyncClient,
        filename: str,
    ) -> tuple[str, str]:
        """
        申请文件上传链接

        Args:
            client: HTTP 客户端
            filename: 文件名

        Returns:
            (batch_id, upload_url) 元组
        """
        url = f"{self.base_url}/file-urls/batch"
        payload = {
            "files": [{"name": filename}],
            "enable_formula": True,
            "enable_table": True,
        }

        response = await client.post(
            url,
            json=payload,
            headers=self._get_headers(),
        )

        if response.status_code != 200:
            raise MinerUAPIError(
                f"申请上传链接失败: {response.text}",
                status_code=response.status_code,
            )

        result = response.json()
        if result.get("code") != 0:
            raise MinerUAPIError(
                f"申请上传链接失败: {result.get('msg', '未知错误')}"
            )

        data = result.get("data", {})
        batch_id = data.get("batch_id")
        file_urls = data.get("file_urls", [])

        if not batch_id or not file_urls:
            raise MinerUAPIError("API 响应缺少 batch_id 或 file_urls 字段")

        logger.debug(f"获取上传链接成功 | batch_id: {batch_id}")
        return batch_id, file_urls[0]

    async def _upload_file(
        self,
        client: httpx.AsyncClient,
        upload_url: str,
        pdf_path: Path,
    ) -> None:
        """
        上传 PDF 文件到预签名 URL

        Args:
            client: HTTP 客户端
            upload_url: 预签名上传 URL
            pdf_path: PDF 文件路径
        """
        with open(pdf_path, "rb") as f:
            file_content = f.read()

        # 上传时不需要 Content-Type 和 Authorization
        response = await client.put(
            upload_url,
            content=file_content,
        )

        if response.status_code != 200:
            raise MinerUAPIError(
                f"文件上传失败: HTTP {response.status_code}",
                status_code=response.status_code,
            )

        logger.debug(f"文件上传成功 | 大小: {len(file_content)} 字节")

    async def _poll_task_result(
        self,
        client: httpx.AsyncClient,
        batch_id: str,
    ) -> str:
        """
        轮询任务状态直到完成

        Args:
            client: HTTP 客户端
            batch_id: 批量任务 ID

        Returns:
            full_zip_url: 解析结果 ZIP 下载链接
        """
        url = f"{self.base_url}/extract-results/batch/{batch_id}"
        start_time = asyncio.get_event_loop().time()

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > self.max_poll_time:
                raise MinerUAPIError(
                    f"任务轮询超时: 已等待 {elapsed:.0f} 秒"
                )

            response = await client.get(url, headers=self._get_headers())

            if response.status_code != 200:
                raise MinerUAPIError(
                    f"查询任务状态失败: {response.text}",
                    status_code=response.status_code,
                )

            result = response.json()
            if result.get("code") != 0:
                raise MinerUAPIError(
                    f"查询任务状态失败: {result.get('msg', '未知错误')}"
                )

            extract_result = result.get("data", {}).get("extract_result", [])
            if not extract_result:
                logger.debug("任务结果为空，继续等待...")
                await asyncio.sleep(self.poll_interval)
                continue

            task_info = extract_result[0]
            state = task_info.get("state", "")

            if state == "done":
                full_zip_url = task_info.get("full_zip_url")
                if not full_zip_url:
                    raise MinerUAPIError("任务完成但缺少 full_zip_url")
                logger.info(f"任务完成 | batch_id: {batch_id}")
                return full_zip_url

            elif state == "failed":
                err_msg = task_info.get("err_msg", "未知错误")
                raise MinerUAPIError(f"解析任务失败: {err_msg}")

            elif state in ("pending", "running", "waiting-file", "converting"):
                progress = task_info.get("extract_progress", {})
                extracted = progress.get("extracted_pages", 0)
                total = progress.get("total_pages", 0)
                if total > 0:
                    logger.debug(
                        f"任务进行中 | 状态: {state} | "
                        f"进度: {extracted}/{total} 页"
                    )
                else:
                    logger.debug(f"任务进行中 | 状态: {state}")
                await asyncio.sleep(self.poll_interval)

            else:
                logger.warning(f"未知任务状态: {state}")
                await asyncio.sleep(self.poll_interval)

    async def _download_result_zip(
        self,
        client: httpx.AsyncClient,
        zip_url: str,
    ) -> bytes:
        """
        下载解析结果 ZIP 文件

        Args:
            client: HTTP 客户端
            zip_url: ZIP 文件下载 URL

        Returns:
            ZIP 文件的字节内容
        """
        response = await client.get(zip_url)

        if response.status_code != 200:
            raise MinerUAPIError(
                f"下载结果失败: HTTP {response.status_code}",
                status_code=response.status_code,
            )

        if len(response.content) == 0:
            raise MinerUAPIError("下载的 ZIP 文件为空")

        logger.debug(f"ZIP 下载完成 | 大小: {len(response.content)} 字节")
        return response.content

    def _extract_markdown_from_zip(self, zip_content: bytes) -> str:
        """
        从 ZIP 文件中提取 Markdown 内容

        ZIP 结构:
        - {filename}/
          - {filename}.md           <- 目标文件
          - {filename}_content_list.json
          - images/

        Returns:
            Markdown 文本内容
        """
        with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zf:
            all_files = zf.namelist()
            logger.debug(f"ZIP 文件内容: {all_files}")

            # 查找 .md 文件（排除隐藏文件）
            md_files = [
                name
                for name in all_files
                if name.endswith(".md")
                and not name.startswith("__")
                and not name.startswith(".")
            ]

            if not md_files:
                raise MinerUAPIError(
                    f"ZIP 中未找到 Markdown 文件，包含的文件: {all_files}"
                )

            # 选择第一个 .md 文件
            md_filename = md_files[0]
            md_content = zf.read(md_filename).decode("utf-8")

            logger.debug(
                f"从 ZIP 提取 Markdown | 文件: {md_filename} | "
                f"内容长度: {len(md_content)}"
            )

            return md_content

    async def parse_pdf(self, pdf_path: Path) -> str:
        """
        使用 MinerU 在线 API 解析 PDF

        Args:
            pdf_path: PDF 文件路径

        Returns:
            Markdown 格式的文本内容

        Raises:
            MinerUAPIError: API 调用失败
            ValueError: PDF 文件问题
        """
        if not pdf_path.exists():
            raise ValueError(f"PDF 文件不存在: {pdf_path}")

        logger.info(f"开始 MinerU API 解析 | 文件: {pdf_path.name}")

        last_error: Optional[Exception] = None

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    # 1. 申请上传链接
                    batch_id, upload_url = await self._apply_upload_url(
                        client, pdf_path.name
                    )

                    # 2. 上传文件
                    await self._upload_file(client, upload_url, pdf_path)

                    # 3. 轮询任务状态
                    zip_url = await self._poll_task_result(client, batch_id)

                    # 4. 下载结果 ZIP
                    zip_content = await self._download_result_zip(client, zip_url)

                    # 5. 提取 Markdown
                    md_content = self._extract_markdown_from_zip(zip_content)

                    # 6. 清洗 Markdown（移除参考文献、规范化空白）
                    md_content = clean_markdown_text(md_content)

                    logger.info(
                        f"MinerU API 解析成功 | 文件: {pdf_path.name} | "
                        f"输出长度: {len(md_content)}"
                    )

                    return md_content

                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    last_error = e
                    logger.warning(
                        f"MinerU API 连接失败 (尝试 {attempt}/{self.max_retries}) | "
                        f"错误: {e}"
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(self.retry_delay * attempt)

                except MinerUAPIError as e:
                    last_error = e
                    # 4xx 错误不重试
                    if e.status_code and 400 <= e.status_code < 500:
                        raise
                    logger.warning(
                        f"MinerU API 调用失败 (尝试 {attempt}/{self.max_retries}) | "
                        f"错误: {e.message}"
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(self.retry_delay * attempt)

        # 所有重试都失败
        raise MinerUAPIError(
            f"MinerU API 调用失败，已重试 {self.max_retries} 次 | 最后错误: {last_error}"
        )


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


def _remove_references_section(text: str) -> str:
    """
    移除学术论文的参考文献部分，保留附录

    策略：找到 References 标题，然后找到下一个章节标题，只删除中间部分
    """
    # 参考文献标题模式
    ref_patterns = [
        r'\n\s*#{0,3}\s*References?\s*\n',
        r'\n\s*#{0,3}\s*REFERENCES?\s*\n',
        r'\n\s*#{0,3}\s*Bibliography\s*\n',
        r'\n\s*#{0,3}\s*参考文献\s*\n',
        r'\n\s*#{0,3}\s*Works\s+Cited\s*\n',
        r'\n\s*\d+\.?\s*References?\s*\n',
        r'\n\s*\d+\.?\s*REFERENCES?\s*\n',
    ]

    # 参考文献之后可能出现的章节标题（附录、致谢等）
    next_section_patterns = [
        r'\n\s*#{0,3}\s*Appendix',
        r'\n\s*#{0,3}\s*APPENDIX',
        r'\n\s*#{0,3}\s*Supplementary',
        r'\n\s*#{0,3}\s*SUPPLEMENTARY',
        r'\n\s*#{0,3}\s*Acknowledgment',
        r'\n\s*#{0,3}\s*ACKNOWLEDGMENT',
        r'\n\s*#{0,3}\s*附录',
        r'\n\s*#{0,3}\s*致谢',
        r'\n\s*#{0,3}\s*Supporting\s+Information',
        r'\n\s*[A-Z]\.\s+',  # 附录编号如 "A. xxx"
        r'\n\s*Appendix\s+[A-Z]',
    ]

    # 1. 找到 References 的位置
    ref_start = None
    for pattern in ref_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if ref_start is None or match.start() < ref_start:
                ref_start = match.start()

    if ref_start is None:
        # 没找到参考文献部分
        return text

    # 2. 在 References 之后找下一个章节
    text_after_ref = text[ref_start + 1:]  # +1 跳过换行符
    ref_end = len(text)  # 默认到文档末尾

    for pattern in next_section_patterns:
        match = re.search(pattern, text_after_ref, re.IGNORECASE)
        if match:
            candidate_end = ref_start + 1 + match.start()
            if candidate_end < ref_end:
                ref_end = candidate_end

    # 3. 删除 References 部分，拼接前后内容
    before_ref = text[:ref_start].rstrip()
    after_ref = text[ref_end:].lstrip() if ref_end < len(text) else ""

    # 记录日志
    removed_chars = ref_end - ref_start
    logger.debug(f"移除参考文献部分 | 删除字符数: {removed_chars}")

    if after_ref:
        return before_ref + "\n\n" + after_ref
    else:
        return before_ref + "\n"


def clean_markdown_text(text: str) -> str:
    """
    清洗 Markdown 文本

    处理步骤：
    1. 移除参考文献部分
    2. 规范化空白字符

    Args:
        text: 原始 Markdown 文本

    Returns:
        清洗后的 Markdown 文本
    """
    original_len = len(text)

    # 1. 移除参考文献部分
    text = _remove_references_section(text)

    # 2. 规范化空白字符
    text = _normalize_whitespace(text)

    cleaned_len = len(text)
    logger.info(
        f"Markdown 清洗完成 | 原始长度: {original_len} | "
        f"清洗后长度: {cleaned_len} | 减少: {original_len - cleaned_len}"
    )

    return text.strip()


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


# 创建全局服务实例
_parser_service: MinerUParserService | None = None


def get_parser_service() -> MinerUParserService:
    """获取解析服务单例"""
    global _parser_service
    if _parser_service is None:
        _parser_service = MinerUParserService()
    return _parser_service
