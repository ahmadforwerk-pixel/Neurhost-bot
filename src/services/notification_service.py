"""Notification service for sending messages to users."""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


class NotificationService:
    """Handle sending notifications to users."""
    
    def __init__(self, bot_application=None):
        """
        Initialize notification service.
        
        Args:
            bot_application: Telegram Application instance for sending messages
        """
        self.bot_application = bot_application
    
    async def notify_user(self, user_id: int, message: str, parse_mode: str = "Markdown") -> bool:
        """
        Send message to user.
        
        Args:
            user_id: Telegram user ID
            message: Message text
            parse_mode: Markdown or HTML
        
        Returns:
            Success status
        """
        if not self.bot_application:
            logger.warning(f"Bot application not available for notification to {user_id}")
            return False
        
        try:
            await self.bot_application.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode=parse_mode
            )
            logger.info(f"Sent notification to user {user_id}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending notification to {user_id}: {e}")
            return False
    
    async def notify_bot_started(self, user_id: int, bot_name: str) -> bool:
        """Notify user that bot started."""
        message = f"✅ Your bot '{bot_name}' has started successfully!"
        return await self.notify_user(user_id, message)
    
    async def notify_bot_stopped(self, user_id: int, bot_name: str) -> bool:
        """Notify user that bot stopped."""
        message = f"⏹️ Your bot '{bot_name}' has stopped."
        return await self.notify_user(user_id, message)
    
    async def notify_bot_error(self, user_id: int, bot_name: str, error: str) -> bool:
        """Notify user of bot error."""
        message = f"🚨 Error with bot '{bot_name}':\n{error[:100]}"
        return await self.notify_user(user_id, message)
    
    async def notify_time_running_out(self, user_id: int, bot_name: str,
                                     hours_remaining: int) -> bool:
        """Notify user that hosting time is running out."""
        message = (
            f"⏳ Attention: Your bot '{bot_name}' has only "
            f"`{hours_remaining}` hours of hosting time left!"
        )
        return await self.notify_user(user_id, message)
    
    async def notify_power_low(self, user_id: int, bot_name: str,
                             power_percent: float) -> bool:
        """Notify user that power is running low."""
        message = (
            f"⚡ Warning: Your bot '{bot_name}' power is low (`{power_percent:.1f}%`).\n"
            f"It will enter sleep mode when power reaches 0%."
        )
        return await self.notify_user(user_id, message)
    
    async def notify_sleep_mode(self, user_id: int, bot_name: str, reason: str) -> bool:
        """Notify user that bot entered sleep mode."""
        message = f"🛌 Your bot '{bot_name}' entered sleep mode.\nReason: {reason}"
        return await self.notify_user(user_id, message)
    
    async def notify_user_approved(self, user_id: int, plan: str) -> bool:
        """Notify user that account was approved."""
        message = (
            f"🎉 Welcome! Your account has been approved!\n"
            f"Plan: `{plan}`\n\n"
            f"You can now upload and host your bots."
        )
        return await self.notify_user(user_id, message)
    
    async def notify_user_rejected(self, user_id: int, reason: Optional[str] = None) -> bool:
        """Notify user that account was rejected."""
        message = "❌ Your account application was rejected."
        if reason:
            message += f"\nReason: {reason}"
        
        return await self.notify_user(user_id, message)
    
    async def broadcast(self, user_ids: List[int], message: str,
                       parse_mode: str = "Markdown") -> dict:
        """
        Send message to multiple users.
        
        Args:
            user_ids: List of user IDs
            message: Message text
            parse_mode: Markdown or HTML
        
        Returns:
            Stats dict
        """
        results = {
            "total": len(user_ids),
            "sent": 0,
            "failed": 0,
            "errors": []
        }
        
        for user_id in user_ids:
            success = await self.notify_user(user_id, message, parse_mode)
            if success:
                results["sent"] += 1
            else:
                results["failed"] += 1
        
        logger.info(f"Broadcast complete: {results['sent']}/{results['total']} sent")
        return results
