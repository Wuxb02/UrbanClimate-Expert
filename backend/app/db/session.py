"""
数据库连接和会话管理

提供:
- 异步引擎和会话工厂
- 依赖注入函数 get_async_session() (用于 FastAPI)
- 上下文管理器 get_session_context() (用于后台任务)
- 数据库初始化和关闭函数
"""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# 全局异步引擎和会话工厂
_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    获取或创建异步引擎

    使用全局单例模式,避免重复创建引擎
    """
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.mysql_dsn,
            echo=settings.environment == "development",  # 开发环境打印 SQL
            pool_size=10,  # 连接池大小
            max_overflow=20,  # 最大溢出连接数
            pool_pre_ping=True,  # 连接前检查是否存活
            pool_recycle=3600,  # 1小时回收连接(避免 MySQL timeout)
        )
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """
    获取或创建会话工厂

    使用全局单例模式
    """
    global _async_session_maker
    if _async_session_maker is None:
        engine = get_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,  # 提交后不过期对象
        )
    return _async_session_maker


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入函数,获取异步会话

    用法:
        @router.get("/documents")
        async def list_documents(
            db: AsyncSession = Depends(get_async_session)
        ):
            ...
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    上下文管理器方式获取会话(用于后台任务)

    用法:
        async with get_session_context() as db:
            ...
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session


async def init_db() -> None:
    """
    初始化数据库(创建所有表)

    在应用启动时调用
    """
    from app.db.models import Base

    engine = get_engine()
    async with engine.begin() as conn:
        # 创建所有表
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    关闭数据库连接

    在应用关闭时调用
    """
    global _engine, _async_session_maker
    if _engine:
        await _engine.dispose()
        _engine = None
    _async_session_maker = None
