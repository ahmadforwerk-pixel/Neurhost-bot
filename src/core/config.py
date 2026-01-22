"""Core configuration and environment loading."""

import os
from typing import Optional
from dotenv import load_dotenv

# Load .env file for development
load_dotenv()


class Config:
    """Application configuration."""
    
    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN env var not set")
    
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    if ADMIN_ID == 0:
        raise ValueError("ADMIN_ID env var not set")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL env var not set")
    
    DATABASE_SSL_MODE = os.getenv("DATABASE_SSL_MODE", "require")
    
    # Cache
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Secrets
    ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
    if not ENCRYPTION_KEY:
        raise ValueError("ENCRYPTION_KEY env var not set")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "/var/log/neurhost/app.log")
    
    # Docker
    DOCKER_HOST = os.getenv("DOCKER_HOST", "unix:///var/run/docker.sock")
    
    # Features
    ENABLE_GITHUB_DEPLOY = os.getenv("ENABLE_GITHUB_DEPLOY", "true").lower() == "true"
    ENABLE_USER_BOT_UPLOAD = os.getenv("ENABLE_USER_BOT_UPLOAD", "true").lower() == "true"
    RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    
    # Directories
    BOTS_DIR = os.getenv("BOTS_DIR", "/neurhost/bots")
    os.makedirs(BOTS_DIR, exist_ok=True)


class Constants:
    """Application constants."""
    
    # User plans
    PLAN_LIMITS = {
        "free": {
            "max_bots": 3,
            "max_time_seconds": 86400,  # 1 day
            "max_power": 30.0,
        },
        "pro": {
            "max_bots": 10,
            "max_time_seconds": 604800,  # 7 days
            "max_power": 60.0,
        },
        "ultra": {
            "max_bots": 100,
            "max_time_seconds": 10**12,  # Unlimited
            "max_power": 100.0,
        },
    }
    
    # Resource limits
    CONTAINER_CPU_LIMIT = "500m"
    CONTAINER_MEMORY_LIMIT = "512m"
    CONTAINER_DISK_LIMIT = "100m"
    
    # Timeouts
    BOT_STARTUP_TIMEOUT = 30  # seconds
    BOT_SHUTDOWN_TIMEOUT = 10  # seconds
    API_CALL_TIMEOUT = 5  # seconds
    
    # Rate limits
    RATE_LIMITS = {
        "user:start": {"limit": 10, "window": 60},
        "user:start_bot": {"limit": 5, "window": 60},
        "user:stop_bot": {"limit": 5, "window": 60},
        "user:upload_bot": {"limit": 10, "window": 3600},
        "user:deploy_github": {"limit": 5, "window": 3600},
    }
    
    # Restart policy
    MAX_RESTARTS_PER_HOUR = 3
    RESTART_BACKOFF_SECONDS = [1, 2, 4, 8, 16]  # Max 5 restarts
    RESTART_COST_SECONDS = 60  # 1 minute penalty per restart
    RESTART_COST_POWER = 2.0  # 2% power penalty
    
    # Power drain
    POWER_DRAIN_FACTOR = 0.02  # cpu% * seconds * factor
    
    # Error codes
    ERROR_CODES = {
        "UNAUTHORIZED": "User is not authorized for this action",
        "NOT_FOUND": "Resource not found",
        "RATE_LIMIT": "Too many requests, please try again later",
        "INVALID_TOKEN": "Invalid or expired token",
        "INSUFFICIENT_RESOURCES": "Insufficient time or power",
        "LAUNCH_ERROR": "Failed to launch bot container",
        "MALICIOUS_CODE": "Code contains forbidden imports or functions",
        "NO_TOKEN": "No Telegram bot token found",
        "INVALID_PLAN": "Invalid plan specified",
    }
