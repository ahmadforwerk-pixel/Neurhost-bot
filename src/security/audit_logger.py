"""Immutable audit logging to PostgreSQL."""

from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Immutable audit trail (INSERT only, NEVER DELETE/UPDATE).
    
    Records all security-relevant actions for compliance and debugging.
    """
    
    def __init__(self, db_session):
        """
        Initialize audit logger.
        
        Args:
            db_session: SQLAlchemy async session
        """
        self.db = db_session
    
    async def log(
        self,
        user_id: int,
        action: str,
        status: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """
        Log action to immutable audit trail.
        
        Args:
            user_id: Who performed the action
            action: What action (e.g., "bot.start_requested")
            status: "success" or "failure"
            resource_type: "bot", "user", or "system"
            resource_id: ID of affected resource
            error_code: Error code if failed
            details: Additional context as dict
            ip_address: Source IP address (if available)
        
        Examples:
            >>> await audit_log(
            ...     user_id=123,
            ...     action="bot.start_requested",
            ...     status="success",
            ...     resource_type="bot",
            ...     resource_id="456",
            ...     details={"cpu_limit": "500m"}
            ... )
        """
        
        try:
            from src.db.models import AuditLog as AuditLogModel
            
            log_entry = AuditLogModel(
                user_id=user_id,
                action=action,
                status=status,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id else None,
                error_code=error_code,
                ip_address=ip_address,
                details=details or {},
                created_at=datetime.utcnow()
            )
            
            self.db.add(log_entry)
            await self.db.commit()
            
            logger.info(
                f"AUDIT: {action} | user={user_id} | status={status} | "
                f"resource={resource_type}:{resource_id}"
            )
        
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
            # Don't raise - audit failure shouldn't break application
            # But definitely log it
            logger.critical(
                f"AUDIT_FAILURE: Could not log {action} for user {user_id}: {e}"
            )
