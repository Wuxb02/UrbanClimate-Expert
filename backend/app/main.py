from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import chat, documents, graph
from app.core.config import settings
from app.core.logger import logger, setup_logging
from app.db import close_db, init_db
from app.middleware import RequestLoggingMiddleware
from app.services.neo4j_service import get_neo4j_service

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

    # 初始化 MySQL
    logger.info("初始化 MySQL 数据库...")
    await init_db()
    logger.info("MySQL 数据库初始化完成")

    # 初始化 Neo4j (必需)
    logger.info("初始化 Neo4j 图数据库...")
    try:
        get_neo4j_service()
        logger.info("Neo4j 图数据库初始化完成")
    except Exception as e:
        logger.error(f"Neo4j 初始化失败 | 错误: {e}")
        logger.warning("应用将在没有 Neo4j 的情况下启动 (图查询功能不可用)")

    yield

    # 关闭时
    logger.info("应用关闭中...")

    # 关闭 Neo4j
    logger.info("关闭 Neo4j 连接...")
    try:
        neo4j_service = get_neo4j_service()
        neo4j_service.close()
        logger.info("Neo4j 连接已关闭")
    except Exception as e:
        logger.warning(f"Neo4j 关闭失败 | 错误: {e}")

    # 关闭 MySQL
    logger.info("关闭 MySQL 连接...")
    await close_db()
    logger.info("MySQL 连接已关闭")

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
