"""Async database connection and session management."""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
import logging

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Manage async database connections and sessions."""
    
    def __init__(self, database_url: str):
        """
        Initialize database connection.
        
        Args:
            database_url: PostgreSQL URL (async driver)
                Example: postgresql+asyncpg://user:pass@host:5432/db
        """
        # Create async engine
        self.engine = create_async_engine(
            database_url,
            echo=False,  # Set to True for SQL logging
            pool_pre_ping=True,  # Check connections before use
            pool_size=20,
            max_overflow=40,
        )
        
        # Create session factory
        self.SessionLocal = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    
    async def get_session(self) -> AsyncSession:
        """Get new database session."""
        return self.SessionLocal()
    
    async def close(self):
        """Close database engine."""
        await self.engine.dispose()
    
    async def create_tables(self):
        """Create all tables (idempotent)."""
        from src.db.models import Base
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created")
    
    async def drop_tables(self):
        """Drop all tables (WARNING: destructive)."""
        from src.db.models import Base
        
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            logger.warning("All database tables dropped")
