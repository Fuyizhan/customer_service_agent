"""数据库连接与 Session 管理。"""
from __future__ import annotations
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text
from customer_service_agent.config import settings

# 所有ORM模型基类
class Base(DeclarativeBase):
    pass

# 全局占位，懒加载
engine = None
async_session_factory: async_sessionmaker[AsyncSession] | None = None

def init_db_engine(database_url: str) -> None:
    """【同步函数】只初始化引擎和session工厂，lifespan调用，不建表"""
    global engine, async_session_factory
    engine = create_async_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,  # 探测连接，生产很关键
    )
    async_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

async def create_tables_and_extension():
    """【异步函数】单独：开启pgvector扩展 + 建表，lifespan调用"""
    if engine is None:
        raise RuntimeError("引擎未初始化，请先调用 init_db_engine")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

# FastAPI 依赖注入 get_db
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if async_session_factory is None:
        raise RuntimeError("数据库工厂未初始化，请先执行 init_db_engine")
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()
