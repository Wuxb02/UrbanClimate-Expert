from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import chat, documents, graph
from app.core.config import settings
from app.core.logger import logger, setup_logging
from app.db import close_db, init_db
from app.middleware import RequestLoggingMiddleware

# 初始化日志系统（在应用创建之前）
setup_logging(
    log_level=settings.log_level,
    log_dir=settings.log_dir,
    log_rotation=settings.log_rotation,
    log_retention=settings.log_retention,
    environment=settings.environment,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info(f"应用启动中... | 环境: {settings.environment}")
    logger.info("初始化数据库...")
    await init_db()
    logger.info("数据库初始化完成")

    yield

    # 关闭时
    logger.info("应用关闭中...")
    logger.info("关闭数据库连接...")
    await close_db()
    logger.info("数据库连接已关闭")
    logger.info("应用已优雅关闭")


app = FastAPI(
    title="UrbanClimate-Expert API",
    version="0.2.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 请求日志中间件（放在 CORS 之后）
app.add_middleware(RequestLoggingMiddleware)

app.include_router(chat.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(graph.router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    """根路径欢迎页面"""
    return {
        "message": "UrbanClimate-Expert API",
        "version": "0.2.0",
        "docs": "/docs",
        "health": "/health",
        "api": "/api/v1"
    }


@app.get("/health")
async def health() -> dict[str, str]:
    """健康检查端点"""
    return {"status": "ok"}
