from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import chat, documents, graph
from app.db import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    print("🚀 初始化数据库...")
    await init_db()
    print("✅ 数据库初始化完成")

    yield

    # 关闭时
    print("🔒 关闭数据库连接...")
    await close_db()
    print("✅ 数据库连接已关闭")


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
