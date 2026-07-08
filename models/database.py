"""
資料庫配置
Database Configuration
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from config.settings import get_settings


# 建立異步引擎
settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    poolclass=NullPool,  # SQLite 不支援連線池，避免 greenlet 衝突
)

# 建立異步Session工廠
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """基礎模型類"""
    pass


async def get_db():
    """
    獲取資料庫Session
    
    用於FastAPI的依賴注入
    """
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """
    初始化資料庫
    
    建立所有表格
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
