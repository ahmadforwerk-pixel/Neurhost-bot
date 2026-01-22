"""Telegram token validation against Telegram API."""

import aiohttp
import asyncio
from typing import Tuple
import logging

logger = logging.getLogger(__name__)


class TelegramTokenValidator:
    """
    Verify Telegram bot token is valid before accepting it.
    
    Prevents acceptance of fake/inactive tokens and resource waste.
    """
    
    TELEGRAM_API_BASE = "https://api.telegram.org"
    VALIDATION_TIMEOUT = 5  # seconds
    
    async def validate_token(self, token: str) -> Tuple[bool, str]:
        """
        Validate token by calling Telegram API.
        
        Args:
            token: Telegram bot token to verify
        
        Returns:
            (is_valid: bool, error_message: str)
        
        Examples:
            >>> validator = TelegramTokenValidator()
            >>> is_valid, msg = await validator.validate_token("123:ABC")
            >>> if not is_valid:
            ...     print(f"Invalid: {msg}")
        """
        
        # Basic format check
        if not token or len(token) < 20:
            return False, "Token too short or empty"
        
        if ':' not in token:
            return False, "Invalid token format (missing colon)"
        
        try:
            url = f"{self.TELEGRAM_API_BASE}/bot{token}/getMe"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=self.VALIDATION_TIMEOUT)
                ) as resp:
                    
                    if resp.status != 200:
                        return False, f"Telegram API error: HTTP {resp.status}"
                    
                    data = await resp.json()
                    
                    if not data.get("ok"):
                        error = data.get("description", "Unknown error")
                        return False, f"Invalid token: {error}"
                    
                    result = data.get("result")
                    if not result or not result.get("is_bot"):
                        return False, "Token is valid but not a bot"
                    
                    # Success
                    bot_username = result.get("username", "unknown")
                    logger.info(f"Token validated for bot @{bot_username}")
                    return True, ""
        
        except asyncio.TimeoutError:
            return False, "Telegram API timeout - please try again"
        except aiohttp.ClientError as e:
            return False, f"Network error: {str(e)[:100]}"
        except Exception as e:
            logger.exception(f"Token validation error: {e}")
            return False, "Validation error - please try again later"
