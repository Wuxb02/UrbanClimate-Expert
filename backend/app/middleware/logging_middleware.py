"""
请求日志中间件

记录所有 HTTP 请求的详细信息：
- 请求方法、路径、客户端 IP
- 响应状态码、耗时
- 自动生成请求 ID（X-Request-ID）
"""
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logger import logger

# 排除的路径（不记录详细日志，减少噪音）
EXCLUDED_PATHS = {
    "/health",
    "/",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """HTTP 请求日志中间件"""

    async def dispatch(self, request: Request, call_next) -> Response:
        # 生成唯一请求 ID
        request_id = request.headers.get(
            "X-Request-ID",
            str(uuid.uuid4())[:8]
        )

        # 存储到 request.state，供后续使用
        request.state.request_id = request_id

        # 排除特定路径的详细日志
        path = request.url.path
        if path in EXCLUDED_PATHS:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response

        # 获取客户端 IP
        client_ip = "unknown"
        if request.client:
            client_ip = request.client.host

        # 记录请求开始
        start_time = time.perf_counter()
        logger.info(
            f"请求开始 | ID: {request_id} | "
            f"方法: {request.method} | "
            f"路径: {path} | "
            f"客户端: {client_ip}"
        )

        try:
            response = await call_next(request)

            # 计算耗时
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # 判断是否为流式响应（SSE）
            content_type = response.headers.get("Content-Type", "")
            is_streaming = "text/event-stream" in content_type

            if is_streaming:
                # 流式响应只记录初始化耗时
                logger.info(
                    f"流式响应开始 | ID: {request_id} | "
                    f"路径: {path} | "
                    f"初始化耗时: {elapsed_ms:.2f}ms"
                )
            else:
                # 常规响应，根据状态码选择日志级别
                log_level = "INFO"
                if response.status_code >= 400:
                    log_level = "WARNING"
                if response.status_code >= 500:
                    log_level = "ERROR"

                logger.log(
                    log_level,
                    f"请求完成 | ID: {request_id} | "
                    f"路径: {path} | "
                    f"状态码: {response.status_code} | "
                    f"耗时: {elapsed_ms:.2f}ms"
                )

            # 添加请求 ID 到响应头（便于客户端追踪）
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"请求异常 | ID: {request_id} | "
                f"路径: {path} | "
                f"耗时: {elapsed_ms:.2f}ms | "
                f"错误: {e}"
            )
            raise
