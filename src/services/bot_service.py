"""Bot service for bot management and lifecycle."""

import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class BotService:
    """Handle bot-related business logic."""
    
    def __init__(self, bot_repo, container_manager=None, secrets_manager=None,
                 code_scanner=None, audit_logger=None):
        """
        Initialize bot service.
        
        Args:
            bot_repo: BotRepository instance
            container_manager: DockerContainerManager instance
            secrets_manager: SecretsManager instance
            code_scanner: CodeSecurityScanner instance
            audit_logger: AuditLogger instance
        """
        self.bot_repo = bot_repo
        self.container_manager = container_manager
        self.secrets_manager = secrets_manager
        self.code_scanner = code_scanner
        self.audit_logger = audit_logger
    
    async def create_bot(self, user_id: int, name: str, token: str, plan: str) -> dict:
        """
        Create new hosted bot.
        
        Args:
            user_id: Owner user ID
            name: Bot name
            token: Telegram bot token (will be encrypted)
            plan: User plan (free, pro, ultra)
        
        Returns:
            Success dict with bot data
        """
        try:
            # Encrypt token
            if self.secrets_manager:
                token_encrypted = self.secrets_manager.encrypt_token(token)
            else:
                token_encrypted = token
            
            # Calculate time/power based on plan
            plan_limits = {
                "free": {"time": 86400, "power": 30.0},  # 1 day, 30%
                "pro": {"time": 604800, "power": 60.0},  # 7 days, 60%
                "ultra": {"time": 31536000, "power": 100.0},  # 365 days, 100%
            }
            
            limits = plan_limits.get(plan, plan_limits["free"])
            
            # Create bot
            bot = await self.bot_repo.create(
                user_id=user_id,
                name=name,
                token_encrypted=token_encrypted,
                total_seconds=limits["time"],
                remaining_seconds=limits["time"],
                power_max=limits["power"],
                power_remaining=limits["power"]
            )
            
            if self.audit_logger:
                await self.audit_logger.log_action(
                    user_id=user_id,
                    action="bot.created",
                    resource_type="bot",
                    resource_id=str(bot.id),
                    status="success",
                    details={"name": name, "plan": plan}
                )
            
            logger.info(f"Created bot {bot.id} for user {user_id}")
            
            return {
                "success": True,
                "bot_id": bot.id,
                "name": bot.name,
                "status": bot.status,
                "time_remaining": bot.remaining_seconds,
                "power_remaining": bot.power_remaining,
            }
        
        except Exception as e:
            logger.error(f"Error creating bot: {e}")
            return {"success": False, "error": str(e)}
    
    async def start_bot(self, bot_id: int, user_id: int) -> dict:
        """
        Start a bot in container.
        
        Args:
            bot_id: Bot ID
            user_id: User ID (for permission check)
        
        Returns:
            Success dict
        """
        try:
            # Get bot
            bot = await self.bot_repo.get_by_id(bot_id)
            
            if not bot:
                return {"success": False, "error": "Bot not found"}
            
            if bot.user_id != user_id:
                return {"success": False, "error": "Permission denied"}
            
            # Check resources
            if bot.remaining_seconds <= 0:
                return {"success": False, "error": "No time remaining"}
            
            if bot.power_remaining <= 0:
                return {"success": False, "error": "No power remaining"}
            
            # Decrypt token
            if self.secrets_manager:
                token = self.secrets_manager.decrypt_token(bot.token_encrypted)
            else:
                token = bot.token_encrypted
            
            # Launch container
            if self.container_manager:
                try:
                    container_id = await self.container_manager.launch_bot_container(
                        bot_id=bot_id,
                        token=token,
                        time_limit=bot.remaining_seconds
                    )
                    
                    # Update bot status
                    await self.bot_repo.update_status(bot_id, "running", container_id)
                
                except Exception as e:
                    logger.error(f"Container launch error: {e}")
                    return {"success": False, "error": f"Container error: {str(e)[:50]}"}
            else:
                # For testing without Docker
                await self.bot_repo.update_status(bot_id, "running")
            
            if self.audit_logger:
                await self.audit_logger.log_action(
                    user_id=user_id,
                    action="bot.started",
                    resource_type="bot",
                    resource_id=str(bot_id),
                    status="success"
                )
            
            logger.info(f"Started bot {bot_id}")
            return {"success": True, "bot_id": bot_id}
        
        except Exception as e:
            logger.error(f"Error starting bot {bot_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def stop_bot(self, bot_id: int, user_id: int) -> dict:
        """
        Stop a running bot.
        
        Args:
            bot_id: Bot ID
            user_id: User ID (for permission check)
        
        Returns:
            Success dict
        """
        try:
            # Get bot
            bot = await self.bot_repo.get_by_id(bot_id)
            
            if not bot:
                return {"success": False, "error": "Bot not found"}
            
            if bot.user_id != user_id:
                return {"success": False, "error": "Permission denied"}
            
            # Stop container
            if self.container_manager and bot.container_id:
                try:
                    await self.container_manager.stop_container(bot.container_id)
                except Exception as e:
                    logger.error(f"Error stopping container: {e}")
            
            # Update status
            await self.bot_repo.update_status(bot_id, "stopped")
            
            if self.audit_logger:
                await self.audit_logger.log_action(
                    user_id=user_id,
                    action="bot.stopped",
                    resource_type="bot",
                    resource_id=str(bot_id),
                    status="success"
                )
            
            logger.info(f"Stopped bot {bot_id}")
            return {"success": True, "bot_id": bot_id}
        
        except Exception as e:
            logger.error(f"Error stopping bot {bot_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def delete_bot(self, bot_id: int, user_id: int) -> dict:
        """
        Delete a bot permanently.
        
        Args:
            bot_id: Bot ID
            user_id: User ID (for permission check)
        
        Returns:
            Success dict
        """
        try:
            # Get bot
            bot = await self.bot_repo.get_by_id(bot_id)
            
            if not bot:
                return {"success": False, "error": "Bot not found"}
            
            if bot.user_id != user_id:
                return {"success": False, "error": "Permission denied"}
            
            # Stop container if running
            if bot.status == "running" and self.container_manager:
                try:
                    await self.container_manager.stop_container(bot.container_id)
                except Exception as e:
                    logger.warning(f"Error stopping container during delete: {e}")
            
            # Delete bot
            await self.bot_repo.delete(bot_id)
            
            if self.audit_logger:
                await self.audit_logger.log_action(
                    user_id=user_id,
                    action="bot.deleted",
                    resource_type="bot",
                    resource_id=str(bot_id),
                    status="success"
                )
            
            logger.info(f"Deleted bot {bot_id}")
            return {"success": True}
        
        except Exception as e:
            logger.error(f"Error deleting bot {bot_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def add_time(self, bot_id: int, user_id: int, hours: int) -> dict:
        """
        Add hosting time to bot.
        
        Args:
            bot_id: Bot ID
            user_id: User ID
            hours: Hours to add
        
        Returns:
            Success dict
        """
        try:
            bot = await self.bot_repo.get_by_id(bot_id)
            
            if not bot or bot.user_id != user_id:
                return {"success": False, "error": "Bot not found or permission denied"}
            
            # Add time
            seconds_to_add = hours * 3600
            new_remaining = bot.remaining_seconds + seconds_to_add
            
            await self.bot_repo.update_resources(
                bot_id=bot_id,
                remaining_seconds=new_remaining
            )
            
            if self.audit_logger:
                await self.audit_logger.log_action(
                    user_id=user_id,
                    action="bot.time_added",
                    resource_type="bot",
                    resource_id=str(bot_id),
                    status="success",
                    details={"hours": hours}
                )
            
            logger.info(f"Added {hours}h to bot {bot_id}")
            return {"success": True, "new_remaining": new_remaining}
        
        except Exception as e:
            logger.error(f"Error adding time: {e}")
            return {"success": False, "error": str(e)}
    
    async def add_power(self, bot_id: int, user_id: int, percentage: float) -> dict:
        """
        Add power to bot.
        
        Args:
            bot_id: Bot ID
            user_id: User ID
            percentage: Power percentage to add
        
        Returns:
            Success dict
        """
        try:
            bot = await self.bot_repo.get_by_id(bot_id)
            
            if not bot or bot.user_id != user_id:
                return {"success": False, "error": "Bot not found or permission denied"}
            
            # Add power (capped at max)
            new_power = min(bot.power_remaining + percentage, bot.power_max)
            
            await self.bot_repo.update_resources(
                bot_id=bot_id,
                power_remaining=new_power
            )
            
            if self.audit_logger:
                await self.audit_logger.log_action(
                    user_id=user_id,
                    action="bot.power_added",
                    resource_type="bot",
                    resource_id=str(bot_id),
                    status="success",
                    details={"percentage": percentage}
                )
            
            logger.info(f"Added {percentage}% power to bot {bot_id}")
            return {"success": True, "new_power": new_power}
        
        except Exception as e:
            logger.error(f"Error adding power: {e}")
            return {"success": False, "error": str(e)}
