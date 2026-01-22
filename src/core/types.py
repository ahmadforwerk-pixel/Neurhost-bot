"""Type definitions for NeuroHost."""

from typing import TypedDict, Optional, Literal
from datetime import datetime


class UserData(TypedDict):
    """User database record."""
    id: int
    username: str
    status: Literal["pending", "approved", "blocked"]
    plan: Literal["free", "pro", "ultra"]
    joined_at: datetime
    approved_at: Optional[datetime]


class BotData(TypedDict):
    """Bot database record."""
    id: int
    user_id: int
    name: str
    status: Literal["stopped", "running", "sleeping"]
    token_encrypted: str
    created_at: datetime
    
    # Time tracking
    total_seconds: int
    remaining_seconds: int
    start_time: Optional[datetime]
    
    # Power tracking
    power_max: float
    power_remaining: float
    
    # Sleep mode
    sleep_mode: bool
    sleep_reason: Optional[str]
    
    # Restart tracking
    restart_count: int
    last_restart_at: Optional[datetime]
    
    # Container
    container_id: Optional[str]


class AuditLogData(TypedDict):
    """Audit log record."""
    id: int
    user_id: int
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    status: Literal["success", "failure"]
    error_code: Optional[str]
    ip_address: Optional[str]
    details: dict
    created_at: datetime
