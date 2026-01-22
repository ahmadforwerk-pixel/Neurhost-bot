"""Redis-backed rate limiting."""

from typing import Tuple
import redis
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Redis-backed rate limiting.
    
    Prevents UI spam, brute force, and resource exhaustion.
    """
    
    def __init__(self, redis_client: redis.Redis):
        """
        Initialize rate limiter.
        
        Args:
            redis_client: Connected Redis client
        """
        self.redis = redis_client
    
    async def check_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> Tuple[bool, int]:
        """
        Check if action is rate-limited.
        
        Args:
            key: Unique identifier (e.g., "user:123:start_bot")
            limit: Max requests allowed
            window_seconds: Time window
        
        Returns:
            (is_allowed: bool, retry_after_seconds: int)
        
        Examples:
            >>> limiter = RateLimiter(redis_client)
            >>> allowed, retry = await limiter.check_limit(
            ...     key="user:123:action",
            ...     limit=5,
            ...     window_seconds=60
            ... )
            >>> if not allowed:
            ...     print(f"Try again in {retry}s")
        """
        
        now = datetime.utcnow()
        window_key = f"ratelimit:{key}:{int(now.timestamp()) // window_seconds}"
        
        try:
            pipe = self.redis.pipeline()
            pipe.incr(window_key)
            pipe.expire(window_key, window_seconds * 2)
            results = pipe.execute()
            
            current_count = results[0]
            
            if current_count <= limit:
                logger.debug(f"Rate limit OK: {key} ({current_count}/{limit})")
                return True, 0
            else:
                # Calculate seconds until next window
                retry_after = window_seconds - (int(now.timestamp()) % window_seconds)
                logger.warning(f"Rate limit EXCEEDED: {key} ({current_count}/{limit})")
                return False, retry_after
        
        except redis.RedisError as e:
            logger.error(f"Rate limiter error: {e}")
            # Fail open (allow if Redis down, log issue)
            return True, 0
        except Exception as e:
            logger.error(f"Unexpected rate limiter error: {e}")
            return True, 0
