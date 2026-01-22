"""Input validation and sanitization utilities."""

import re
import logging

logger = logging.getLogger(__name__)


class InputValidator:
    """Validate and sanitize user input."""
    
    @staticmethod
    def validate_username(username: str) -> bool:
        """
        Validate Telegram username format.
        
        Args:
            username: Username to validate
        
        Returns:
            True if valid
        """
        if not username:
            return False
        
        # Remove @ if present
        username = username.lstrip('@')
        
        # Telegram usernames: 5-32 characters, alphanumeric and underscores
        pattern = r'^[a-zA-Z0-9_]{5,32}$'
        return bool(re.match(pattern, username))
    
    @staticmethod
    def validate_bot_name(name: str) -> bool:
        """
        Validate bot name format.
        
        Args:
            name: Bot name to validate
        
        Returns:
            True if valid
        """
        if not name or len(name) > 100:
            return False
        
        # Allow alphanumeric, spaces, hyphens, underscores
        pattern = r'^[a-zA-Z0-9\s_-]+$'
        return bool(re.match(pattern, name))
    
    @staticmethod
    def validate_bot_id(bot_id: str) -> bool:
        """
        Validate bot ID format.
        
        Args:
            bot_id: Bot ID to validate
        
        Returns:
            True if valid positive integer
        """
        try:
            bot_id_int = int(bot_id)
            return bot_id_int > 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def validate_user_id(user_id: str) -> bool:
        """
        Validate Telegram user ID format.
        
        Args:
            user_id: User ID to validate
        
        Returns:
            True if valid positive integer
        """
        try:
            user_id_int = int(user_id)
            return user_id_int > 0
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def sanitize_path(path: str, base_dir: str) -> bool:
        """
        Check if path is within base directory (no traversal).
        
        Args:
            path: Path to check
            base_dir: Base directory path
        
        Returns:
            True if path is safe
        """
        import os
        
        # Normalize both paths
        abs_path = os.path.abspath(path)
        abs_base = os.path.abspath(base_dir)
        
        # Check if path starts with base
        return abs_path.startswith(abs_base + os.sep)
    
    @staticmethod
    def validate_github_url(url: str) -> bool:
        """
        Validate GitHub repository URL format.
        
        Args:
            url: URL to validate
        
        Returns:
            True if valid GitHub URL
        """
        pattern = r'^https://github\.com/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$'
        return bool(re.match(pattern, url))
    
    @staticmethod
    def extract_bot_token(code: str) -> str:
        """
        Extract Telegram bot token from code via regex.
        
        Args:
            code: Python code to search
        
        Returns:
            Token string or empty string
        """
        # Telegram token format: digits:alphanumeric-_
        pattern = r'[0-9]{8,10}:[a-zA-Z0-9_-]{35}'
        match = re.search(pattern, code)
        
        return match.group(0) if match else ""
