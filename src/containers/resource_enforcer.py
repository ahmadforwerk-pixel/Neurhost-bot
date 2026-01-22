"""Resource enforcement and power drain calculation."""

from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ResourceEnforcer:
    """
    Enforce resource limits and calculate power drain.
    
    Power drain formula:
    power_drain = (cpu_percent / 100) * elapsed_seconds * 0.02
    """
    
    POWER_DRAIN_FACTOR = 0.02
    IDLE_CPU_THRESHOLD = 2.0  # CPU% below which is considered idle
    IDLE_DRAIN_MULTIPLIER = 0.2  # Reduce drain for idle bots
    
    def __init__(self, container_manager, db_session):
        """
        Initialize resource enforcer.
        
        Args:
            container_manager: Docker container manager
            db_session: Database session
        """
        self.container_mgr = container_manager
        self.db = db_session
    
    async def update_power_drain(self, bot_id: int, elapsed_seconds: int) -> float:
        """
        Deduct power based on CPU usage over elapsed time.
        
        Args:
            bot_id: Bot ID
            elapsed_seconds: Seconds since last check
        
        Returns:
            New power_remaining value
        """
        from src.db.models import Bot
        from sqlalchemy import select, update
        
        try:
            # Get bot
            result = await self.db.execute(
                select(Bot).where(Bot.id == bot_id)
            )
            bot = result.scalars().first()
            
            if not bot or bot.status != 'running':
                return 0.0
            
            # Get container stats
            stats = self.container_mgr.get_container_stats(bot_id)
            cpu_percent = stats.get('cpu_percent', 0)
            
            # Calculate drain
            drain_factor = self.POWER_DRAIN_FACTOR
            
            # If CPU is low, reduce drain multiplier
            if cpu_percent < self.IDLE_CPU_THRESHOLD:
                drain_factor *= self.IDLE_DRAIN_MULTIPLIER
            
            power_drain = (cpu_percent / 100.0) * elapsed_seconds * drain_factor
            new_power = max(0.0, bot.power_remaining - power_drain)
            new_remaining_time = max(0, bot.remaining_seconds - elapsed_seconds)
            
            # Update database
            await self.db.execute(
                update(Bot).where(Bot.id == bot_id).values(
                    power_remaining=new_power,
                    remaining_seconds=new_remaining_time,
                    cpu_usage_percent=cpu_percent,
                    last_checked=datetime.utcnow()
                )
            )
            await self.db.commit()
            
            logger.debug(
                f"Bot {bot_id}: CPU={cpu_percent}%, "
                f"Drain={power_drain:.2f}%, Power={new_power:.1f}%"
            )
            
            return new_power
        
        except Exception as e:
            logger.error(f"Error updating power drain for bot {bot_id}: {e}")
            return 0.0
    
    async def enforce_limits(self, bot_id: int) -> bool:
        """
        Check if bot should be put to sleep due to resource exhaustion.
        
        Args:
            bot_id: Bot ID
        
        Returns:
            True if bot was put to sleep
        """
        from src.db.models import Bot
        from sqlalchemy import select, update
        
        try:
            result = await self.db.execute(
                select(Bot).where(Bot.id == bot_id)
            )
            bot = result.scalars().first()
            
            if not bot or bot.status != 'running':
                return False
            
            # Check if resources depleted
            if bot.remaining_seconds <= 0 or bot.power_remaining <= 0:
                await self.db.execute(
                    update(Bot).where(Bot.id == bot_id).values(
                        sleep_mode=True,
                        sleep_reason='expired_resources',
                        sleep_since=datetime.utcnow(),
                        status='stopped',
                    )
                )
                await self.db.commit()
                
                # Stop container
                self.container_mgr.stop_bot_container(bot_id)
                
                logger.info(f"Bot {bot_id} put to sleep: resources depleted")
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error enforcing limits for bot {bot_id}: {e}")
            return False
