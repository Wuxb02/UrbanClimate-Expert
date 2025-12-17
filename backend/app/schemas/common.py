"""
通用 Schema 定义

包含:
- ErrorResponse: 错误响应
- SuccessResponse: 成功响应
"""
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """错误响应"""

    detail: str = Field(..., description="错误详情")
    error_code: str = Field(..., description="错误代码")


class SuccessResponse(BaseModel):
    """成功响应"""

    message: str = Field(..., description="成功消息")
