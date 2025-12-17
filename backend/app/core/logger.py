"""
统一日志配置模块

使用 loguru 作为日志框架，提供：
- 环境感知的日志格式（开发环境彩色控制台/生产环境 JSON 文件）
- 日志文件轮转
- 敏感信息自动脱敏
- 性能监控装饰器
"""
import inspect
import re
import sys
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable

from loguru import logger


def _sanitize_message(message: str) -> str:
    """
    清理日志消息中的敏感信息

    自动脱敏：
    - API Keys (api_key, openai_api_key, rerank_api_key)
    - 密码 (password, passwd, pwd)
    - Token (token, access_token, refresh_token, Bearer)
    """
    patterns = [
        # API Keys
        (r'(api[_-]?key["\s:=]+)([a-zA-Z0-9_-]{20,})', r'\1***REDACTED***'),
        (r'(sk-[a-zA-Z0-9]{20,})', r'***REDACTED***'),
        # 密码
        (r'(password["\s:=]+)([^\s,}"\']+)', r'\1***REDACTED***'),
        (r'(passwd["\s:=]+)([^\s,}"\']+)', r'\1***REDACTED***'),
        (r'(pwd["\s:=]+)([^\s,}"\']+)', r'\1***REDACTED***'),
        # Token
        (r'(token["\s:=]+)([a-zA-Z0-9_-]{20,})', r'\1***REDACTED***'),
        (r'(Bearer\s+)([a-zA-Z0-9_.-]+)', r'\1***REDACTED***'),
    ]

    for pattern, replacement in patterns:
        message = re.sub(pattern, replacement, message, flags=re.IGNORECASE)

    return message


def _format_record(record: dict) -> str:
    """自定义日志格式化函数，用于脱敏处理"""
    record["extra"]["sanitized_message"] = _sanitize_message(record["message"])
    return (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{extra[sanitized_message]}</level>\n"
        "{exception}"
    )


def _format_record_json(record: dict) -> str:
    """JSON 格式日志（用于生产环境）"""
    record["extra"]["sanitized_message"] = _sanitize_message(record["message"])
    return (
        "{time:YYYY-MM-DDTHH:mm:ss.SSSZ} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{extra[sanitized_message]}\n"
        "{exception}"
    )


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "./logs",
    log_rotation: str = "00:00",
    log_retention: str = "30 days",
    environment: str = "development",
) -> None:
    """
    配置日志系统

    Args:
        log_level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
        log_dir: 日志文件目录（仅生产环境使用）
        log_rotation: 日志轮转时间（如 "00:00" 每天午夜）
        log_retention: 日志保留时间（如 "30 days"）
        environment: 运行环境 (development/production)
    """
    # 移除默认处理器
    logger.remove()

    # 开发环境：彩色控制台输出
    if environment == "development":
        logger.add(
            sys.stderr,
            format=_format_record,
            level=log_level,
            colorize=True,
            enqueue=True,
            backtrace=True,
            diagnose=True,
        )
    else:
        # 生产环境：文件输出
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # 主日志文件
        logger.add(
            log_path / "app.log",
            format=_format_record_json,
            level=log_level,
            rotation=log_rotation,
            retention=log_retention,
            compression="gz",
            enqueue=True,
            encoding="utf-8",
        )

        # 错误日志单独文件
        logger.add(
            log_path / "error.log",
            format=_format_record_json,
            level="ERROR",
            rotation="10 MB",
            retention="90 days",
            compression="gz",
            enqueue=True,
            backtrace=True,
            diagnose=True,
            encoding="utf-8",
        )

        # 同时输出到控制台（简化格式）
        logger.add(
            sys.stderr,
            format=_format_record_json,
            level=log_level,
            colorize=False,
            enqueue=True,
        )

    logger.info(f"日志系统初始化完成 | 级别: {log_level} | 环境: {environment}")


def log_performance(
    log_level: str = "INFO",
    threshold_ms: float = 0,
):
    """
    性能监控装饰器，记录函数执行耗时

    Args:
        log_level: 日志级别
        threshold_ms: 耗时阈值（毫秒），超过此阈值才记录日志，0 表示总是记录

    用法:
        @log_performance(log_level="DEBUG", threshold_ms=100)
        async def slow_function():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            func_name = func.__name__

            try:
                result = await func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000

                if elapsed_ms >= threshold_ms:
                    logger.log(
                        log_level,
                        f"{func_name} 完成 | 耗时: {elapsed_ms:.2f}ms"
                    )

                return result

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.error(
                    f"{func_name} 失败 | 耗时: {elapsed_ms:.2f}ms | 错误: {e}"
                )
                raise

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            func_name = func.__name__

            try:
                result = func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - start) * 1000

                if elapsed_ms >= threshold_ms:
                    logger.log(
                        log_level,
                        f"{func_name} 完成 | 耗时: {elapsed_ms:.2f}ms"
                    )

                return result

            except Exception as e:
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.error(
                    f"{func_name} 失败 | 耗时: {elapsed_ms:.2f}ms | 错误: {e}"
                )
                raise

        # 根据函数类型返回对应的包装器
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# 导出
__all__ = ["logger", "setup_logging", "log_performance"]
