"""Data access layer using repository pattern."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class UserRepository:
    """Data access for users."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, user_id: int):
        """Get user by ID."""
        from src.db.models import User
        
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalars().first()
    
    async def get_by_username(self, username: str):
        """Get user by username."""
        from src.db.models import User
        
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalars().first()
    
    async def create(self, user_id: int, username: str, status: str = "pending"):
        """Create new user."""
        from src.db.models import User
        
        user = User(id=user_id, username=username, status=status)
        self.session.add(user)
        await self.session.commit()
        return user
    
    async def update_status(self, user_id: int, status: str):
        """Update user status."""
        from src.db.models import User
        
        await self.session.execute(
            update(User).where(User.id == user_id).values(status=status)
        )
        await self.session.commit()
    
    async def get_pending_users(self, limit: int = 100):
        """Get pending users."""
        from src.db.models import User
        
        result = await self.session.execute(
            select(User).where(User.status == 'pending').limit(limit)
        )
        return result.scalars().all()


class BotRepository:
    """Data access for bots."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_by_id(self, bot_id: int):
        """Get bot by ID."""
        from src.db.models import Bot
        
        result = await self.session.execute(
            select(Bot).where(Bot.id == bot_id)
        )
        return result.scalars().first()
    
    async def get_user_bots(self, user_id: int):
        """Get all bots for user."""
        from src.db.models import Bot
        
        result = await self.session.execute(
            select(Bot).where(Bot.user_id == user_id)
        )
        return result.scalars().all()
    
    async def get_running_bots(self):
        """Get all running bots."""
        from src.db.models import Bot
        
        result = await self.session.execute(
            select(Bot).where(Bot.status == 'running')
        )
        return result.scalars().all()
    
    async def create(
        self,
        user_id: int,
        name: str,
        token_encrypted: str,
        total_seconds: int,
        power_max: float,
        folder: str,
        main_file: str = "main.py",
    ):
        """Create new bot."""
        from src.db.models import Bot
        
        bot = Bot(
            user_id=user_id,
            name=name,
            token_encrypted=token_encrypted,
            total_seconds=total_seconds,
            remaining_seconds=total_seconds,
            power_max=power_max,
            power_remaining=power_max,
            folder=folder,
            main_file=main_file,
        )
        self.session.add(bot)
        await self.session.commit()
        return bot
    
    async def update_status(self, bot_id: int, status: str, container_id: str = None):
        """Update bot status."""
        from src.db.models import Bot
        
        await self.session.execute(
            update(Bot).where(Bot.id == bot_id).values(
                status=status,
                container_id=container_id,
            )
        )
        await self.session.commit()
    
    async def update_resources(
        self,
        bot_id: int,
        remaining_seconds: int = None,
        power_remaining: float = None,
    ):
        """Update bot time and power."""
        from src.db.models import Bot
        
        values = {"last_checked": datetime.utcnow()}
        if remaining_seconds is not None:
            values["remaining_seconds"] = remaining_seconds
        if power_remaining is not None:
            values["power_remaining"] = power_remaining
        
        await self.session.execute(
            update(Bot).where(Bot.id == bot_id).values(**values)
        )
        await self.session.commit()
    
    async def set_sleep_mode(self, bot_id: int, sleep: bool = True, reason: str = None):
        """Set bot sleep mode."""
        from src.db.models import Bot
        
        await self.session.execute(
            update(Bot).where(Bot.id == bot_id).values(
                sleep_mode=sleep,
                sleep_reason=reason,
                sleep_since=datetime.utcnow() if sleep else None,
                status='stopped' if sleep else 'stopped',
            )
        )
        await self.session.commit()
    
    async def delete(self, bot_id: int):
        """Delete bot and related records."""
        from src.db.models import Bot
        
        await self.session.execute(
            delete(Bot).where(Bot.id == bot_id)
        )
        await self.session.commit()


class AuditLogRepository:
    """Data access for audit logs (READ ONLY)."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_for_user(self, user_id: int, limit: int = 100):
        """Get audit logs for user."""
        from src.db.models import AuditLog
        
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_recent(self, hours: int = 24, limit: int = 1000):
        """Get recent audit logs."""
        from src.db.models import AuditLog
        
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.created_at >= cutoff)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
