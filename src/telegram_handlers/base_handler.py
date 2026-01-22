"""Base handler with security checks and permissions."""

import logging
from typing import Optional, Callable, Any
from telegram import Update
from telegram.ext import ContextTypes
from functools import wraps

logger = logging.getLogger(__name__)


class BaseHandler:
    """
    Base handler for all Telegram commands.
    
    Provides:
    - Authentication checking
    - Permission verification
    - Rate limiting
    - Audit logging
    - Error handling
    """
    
    def __init__(self, admin_id: int, rate_limiter=None, audit_logger=None, permission_checker=None):
        """
        Initialize base handler.
        
        Args:
            admin_id: Telegram user ID of admin
            rate_limiter: RateLimiter instance
            audit_logger: AuditLogger instance
            permission_checker: PermissionChecker instance
        """
        self.admin_id = admin_id
        self.rate_limiter = rate_limiter
        self.audit_logger = audit_logger
        self.permission_checker = permission_checker
    
    async def check_auth(self, user_id: int, user_repo=None) -> bool:
        """
        Check if user is authenticated.
        
        Args:
            user_id: Telegram user ID
            user_repo: UserRepository instance
        
        Returns:
            True if user is approved or is admin
        """
        # Admin is always approved
        if user_id == self.admin_id:
            return True
        
        # Check if user exists and is approved
        if user_repo:
            user = await user_repo.get_by_id(user_id)
            if user and user.status == "approved":
                return True
        
        return False
    
    async def check_rate_limit(self, user_id: int, action: str, limit: int = 10, window: int = 60) -> tuple:
        """
        Check rate limit for action.
        
        Args:
            user_id: User ID
            action: Action name (e.g., 'start', 'upload_bot')
            limit: Max requests per window
            window: Time window in seconds
        
        Returns:
            (allowed: bool, retry_after: int or None)
        """
        if not self.rate_limiter:
            return True, None
        
        key = f"user:{user_id}:{action}"
        allowed, retry_after = await self.rate_limiter.check_limit(key, limit, window)
        
        return allowed, retry_after
    
    async def log_action(self, user_id: int, action: str, resource_type: str = "user",
                        resource_id: Optional[str] = None, status: str = "success",
                        error_code: Optional[str] = None, details: Optional[dict] = None):
        """
        Log action to audit trail.
        
        Args:
            user_id: User ID
            action: Action name (e.g., 'bot.start')
            resource_type: Type of resource (user, bot, deployment)
            resource_id: ID of resource
            status: success, failure, warning
            error_code: Error code if status is failure
            details: Additional details
        """
        if not self.audit_logger:
            return
        
        await self.audit_logger.log_action(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            error_code=error_code,
            details=details or {}
        )
    
    async def check_permission(self, user_id: int, resource_id: int, bot_repo=None) -> bool:
        """
        Check if user owns/can access resource.
        
        Args:
            user_id: User ID
            resource_id: Bot ID or resource ID
            bot_repo: BotRepository instance
        
        Returns:
            True if user owns resource
        """
        if user_id == self.admin_id:
            return True
        
        if bot_repo:
            bot = await bot_repo.get_by_id(resource_id)
            if bot and bot.user_id == user_id:
                return True
        
        return False
    
    async def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id == self.admin_id
    
    def require_auth(self, func: Callable) -> Callable:
        """Decorator: require authentication."""
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            user_repo = kwargs.get('user_repo')
            
            if not await self.check_auth(user_id, user_repo):
                await update.message.reply_text(
                    "❌ You don't have access. Please request approval from admin."
                )
                return
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    
    def require_admin(self, func: Callable) -> Callable:
        """Decorator: require admin access."""
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            if not await self.is_admin(user_id):
                await update.message.reply_text(
                    "❌ Admin only."
                )
                return
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper
    
    def require_rate_limit(self, action: str, limit: int = 10, window: int = 60):
        """Decorator: require rate limit check."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
                user_id = update.effective_user.id
                
                allowed, retry_after = await self.check_rate_limit(user_id, action, limit, window)
                if not allowed:
                    await update.message.reply_text(
                        f"⏱️ Rate limited. Please try again in {retry_after} seconds."
                    )
                    return
                
                return await func(update, context, *args, **kwargs)
            
            return wrapper
        
        return decorator
    
    def require_permission(self, func: Callable) -> Callable:
        """Decorator: require resource ownership."""
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            # Get resource ID from context data
            resource_id = context.user_data.get('resource_id')
            bot_repo = kwargs.get('bot_repo')
            
            if resource_id and not await self.check_permission(user_id, resource_id, bot_repo):
                await update.message.reply_text(
                    "❌ You don't have permission to access this resource."
                )
                return
            
            return await func(update, context, *args, **kwargs)
        
        return wrapper


def security_handler(auth=True, admin=False, rate_limit=None, log_action=None):
    """
    Decorator combining all security checks.
    
    Args:
        auth: Require authentication
        admin: Require admin access
        rate_limit: (action, limit, window) tuple for rate limiting
        log_action: (action, resource_type) tuple for logging
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user_id = update.effective_user.id
            
            # Check admin if required
            if admin:
                if not await self.is_admin(user_id):
                    await update.message.reply_text("❌ Admin only.")
                    return
            
            # Check auth if required (and not admin)
            elif auth:
                user_repo = kwargs.get('user_repo')
                if not await self.check_auth(user_id, user_repo):
                    await update.message.reply_text(
                        "❌ You don't have access. Please request approval."
                    )
                    return
            
            # Check rate limit
            if rate_limit:
                action, limit, window = rate_limit
                allowed, retry_after = await self.check_rate_limit(user_id, action, limit, window)
                if not allowed:
                    await update.message.reply_text(
                        f"⏱️ Rate limited. Retry in {retry_after}s."
                    )
                    return
            
            # Log action
            if log_action:
                action_name, resource_type = log_action
                try:
                    await func(update, context, *args, **kwargs)
                    await self.log_action(user_id, action_name, resource_type, status="success")
                except Exception as e:
                    await self.log_action(
                        user_id, action_name, resource_type,
                        status="failure", error_code="HANDLER_ERROR"
                    )
                    raise
            else:
                return await func(update, context, *args, **kwargs)
        
        return wrapper
    
    return decorator
