"""Schema 模块"""
from app.schemas.chat import ChatChunk, ChatRequest, ChatResponse, Citation
from app.schemas.common import ErrorResponse, SuccessResponse
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)

__all__ = [
    # Chat schemas
    "Citation",
    "ChatRequest",
    "ChatChunk",
    "ChatResponse",
    # Document schemas
    "DocumentUploadResponse",
    "DocumentStatusResponse",
    "DocumentListItem",
    "DocumentListResponse",
    "DocumentDeleteResponse",
    # Common schemas
    "ErrorResponse",
    "SuccessResponse",
]
