"""Permission and access control checks."""

import logging

logger = logging.getLogger(__name__)


class PermissionChecker:
    """Role-based permission checks."""
    
    def __init__(self, admin_id: int, db_session):
        """
        Initialize permission checker.
        
        Args:
            admin_id: ID of administrator user
            db_session: Database session
        """
        self.admin_id = admin_id
        self.db = db_session
    
    async def can_manage_bot(self, user_id: int, bot_id: int) -> bool:
        """Check if user owns bot."""
        try:
            from src.db.models import Bot
            
            bot = await self.db.query(Bot).filter(
                Bot.id == bot_id
            ).first()
            
            return bot and bot.user_id == user_id
        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            return False
    
    async def can_approve_user(self, user_id: int) -> bool:
        """Only ADMIN_ID can approve users."""
        return user_id == self.admin_id
    
    async def can_block_user(self, user_id: int) -> bool:
        """Only ADMIN_ID can block users."""
        return user_id == self.admin_id
    
    async def can_upload_bot(self, user_id: int) -> bool:
        """Check user status and bot limit."""
        try:
            from src.db.models import User, Bot
            from src.core.config import Constants
            
            user = await self.db.query(User).filter(
                User.id == user_id
            ).first()
            
            if not user or user.status != "approved":
                return False
            
            # Check bot count vs plan limit
            plan_limits = {
                "free": 3,
                "pro": 10,
                "ultra": 100,
            }
            
            bot_count = await self.db.query(Bot).filter(
                Bot.user_id == user_id
            ).count()
            
            limit = plan_limits.get(user.plan, 3)
            
            return bot_count < limit
        
        except Exception as e:
            logger.error(f"Bot upload permission check failed: {e}")
            return False
    
    async def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id == self.admin_id
