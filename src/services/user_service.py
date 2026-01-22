"""User service for user management."""

import logging
from typing import Optional, Literal
from datetime import datetime

logger = logging.getLogger(__name__)


class UserService:
    """Handle user-related business logic."""
    
    def __init__(self, user_repo, audit_logger=None):
        """
        Initialize user service.
        
        Args:
            user_repo: UserRepository instance
            audit_logger: AuditLogger instance
        """
        self.user_repo = user_repo
        self.audit_logger = audit_logger
    
    async def create_user(self, user_id: int, username: str) -> dict:
        """
        Create new user account.
        
        Args:
            user_id: Telegram user ID
            username: Username
        
        Returns:
            User data dict or error
        """
        try:
            user = await self.user_repo.create(user_id, username, status="pending")
            
            if self.audit_logger:
                await self.audit_logger.log_action(
                    user_id=user_id,
                    action="user.created",
                    resource_type="user",
                    status="success"
                )
            
            logger.info(f"Created user {user_id}")
            return {"success": True, "user": user}
        
        except Exception as e:
            logger.error(f"Error creating user {user_id}: {e}")
            if self.audit_logger:
                await self.audit_logger.log_action(
                    user_id=user_id,
                    action="user.create_error",
                    resource_type="user",
                    status="failure",
                    error_code="DB_ERROR"
                )
            return {"success": False, "error": str(e)}
    
    async def approve_user(self, user_id: int, plan: Literal["free", "pro", "ultra"],
                          approver_id: int) -> dict:
        """
        Approve user for access.
        
        Args:
            user_id: User to approve
            plan: Plan to assign
            approver_id: Admin ID approving
        
        Returns:
            Success dict
        """
        try:
            # Update user status
            await self.user_repo.update_status(user_id, "approved")
            
            # TODO: Update plan in database
            
            if self.audit_logger:
                await self.audit_logger.log_action(
                    user_id=approver_id,
                    action="user.approved",
                    resource_type="user",
                    resource_id=str(user_id),
                    status="success",
                    details={"plan": plan}
                )
            
            logger.info(f"Approved user {user_id} with plan {plan}")
            return {"success": True, "plan": plan}
        
        except Exception as e:
            logger.error(f"Error approving user {user_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def reject_user(self, user_id: int, reason: str, rejector_id: int) -> dict:
        """
        Reject user access.
        
        Args:
            user_id: User to reject
            reason: Rejection reason
            rejector_id: Admin ID rejecting
        
        Returns:
            Success dict
        """
        try:
            # TODO: Update user status and reason
            
            if self.audit_logger:
                await self.audit_logger.log_action(
                    user_id=rejector_id,
                    action="user.rejected",
                    resource_type="user",
                    resource_id=str(user_id),
                    status="success",
                    details={"reason": reason}
                )
            
            logger.info(f"Rejected user {user_id}")
            return {"success": True}
        
        except Exception as e:
            logger.error(f"Error rejecting user {user_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def block_user(self, user_id: int, reason: str, blocker_id: int) -> dict:
        """
        Block user from accessing system.
        
        Args:
            user_id: User to block
            reason: Block reason
            blocker_id: Admin ID blocking
        
        Returns:
            Success dict
        """
        try:
            # TODO: Update user status to blocked with reason
            
            if self.audit_logger:
                await self.audit_logger.log_action(
                    user_id=blocker_id,
                    action="user.blocked",
                    resource_type="user",
                    resource_id=str(user_id),
                    status="success",
                    details={"reason": reason}
                )
            
            logger.info(f"Blocked user {user_id}: {reason}")
            return {"success": True}
        
        except Exception as e:
            logger.error(f"Error blocking user {user_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_user_info(self, user_id: int) -> dict:
        """
        Get user information.
        
        Args:
            user_id: User ID
        
        Returns:
            User dict
        """
        try:
            user = await self.user_repo.get_by_id(user_id)
            
            if not user:
                return {"success": False, "error": "User not found"}
            
            return {
                "success": True,
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "status": user.status,
                    "plan": user.plan,
                    "joined_at": user.joined_at.isoformat(),
                }
            }
        
        except Exception as e:
            logger.error(f"Error getting user {user_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_pending_users(self, limit: int = 100) -> dict:
        """
        Get list of pending users.
        
        Args:
            limit: Max results
        
        Returns:
            List of users
        """
        try:
            users = await self.user_repo.get_pending_users(limit)
            
            return {
                "success": True,
                "count": len(users),
                "users": [
                    {
                        "id": u.id,
                        "username": u.username,
                        "joined_at": u.joined_at.isoformat(),
                    }
                    for u in users
                ]
            }
        
        except Exception as e:
            logger.error(f"Error getting pending users: {e}")
            return {"success": False, "error": str(e)}
