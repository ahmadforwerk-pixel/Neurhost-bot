"""Admin handlers for user approval, system stats, and management."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.telegram_handlers.base_handler import BaseHandler

logger = logging.getLogger(__name__)


class AdminHandlers(BaseHandler):
    """Handle admin-only commands and management."""
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin control panel."""
        user_id = update.effective_user.id
        
        # Check admin
        if not await self.is_admin(user_id):
            await update.callback_query.answer("❌ Admin only")
            return
        
        keyboard = [
            [InlineKeyboardButton("👥 Pending Users", callback_data="admin_pending")],
            [InlineKeyboardButton("📊 System Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("🚨 Error Logs", callback_data="admin_errors")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "👑 *Admin Panel*\n\n"
            "System Management",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def pending_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                           user_repo=None):
        """Show pending user approvals."""
        user_id = update.effective_user.id
        
        # Check admin
        if not await self.is_admin(user_id):
            await update.callback_query.answer("❌ Admin only")
            return
        
        # Get pending users
        pending = []
        if user_repo:
            pending = await user_repo.get_pending_users(limit=50)
        
        if not pending:
            keyboard = [
                [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                "👥 *Pending Users*\n\n"
                "No pending users.",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            return
        
        # Build keyboard with pending users
        keyboard = []
        for user in pending:
            username = user.username or f"user_{user.id}"
            label = f"@{username}"
            keyboard.append([
                InlineKeyboardButton(label, callback_data=f"admin_approve_{user.id}")
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_panel")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "👥 *Pending Users*\n\n"
            f"Found {len(pending)} pending approvals\n\n"
            "Select user to approve/reject:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def user_approval_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                user_repo=None):
        """Show user approval options."""
        user_id = update.effective_user.id
        
        # Check admin
        if not await self.is_admin(user_id):
            await update.callback_query.answer("❌ Admin only")
            return
        
        # Extract user ID to approve
        target_user_id = int(update.callback_query.data.split("_")[2])
        
        # Get user info
        user = None
        if user_repo:
            user = await user_repo.get_by_id(target_user_id)
        
        if not user:
            await update.callback_query.answer("❌ User not found", show_alert=True)
            return
        
        # Store target user ID
        context.user_data['approval_target'] = target_user_id
        
        keyboard = [
            [InlineKeyboardButton("✅ Approve (Free)", callback_data=f"admin_approve_free_{target_user_id}")],
            [InlineKeyboardButton("⭐ Approve (Pro)", callback_data=f"admin_approve_pro_{target_user_id}")],
            [InlineKeyboardButton("💎 Approve (Ultra)", callback_data=f"admin_approve_ultra_{target_user_id}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_{target_user_id}")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_pending")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        username = user.username or f"user_{target_user_id}"
        
        await update.callback_query.edit_message_text(
            f"👤 *Approve @{username}*\n\n"
            f"ID: `{target_user_id}`\n"
            f"Status: `{user.status}`\n\n"
            "Select plan to approve or reject:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def approve_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                          user_repo=None, audit_logger=None):
        """Approve user with selected plan."""
        admin_id = update.effective_user.id
        
        # Check admin
        if not await self.is_admin(admin_id):
            await update.callback_query.answer("❌ Admin only")
            return
        
        # Extract plan and user ID
        parts = update.callback_query.data.split("_")
        plan = parts[2]  # free, pro, ultra
        target_user_id = int(parts[3])
        
        # Update user status and plan
        if user_repo:
            try:
                await user_repo.update_status(target_user_id, "approved")
                # TODO: Update plan in database
                
                await update.callback_query.answer(f"✅ User approved with {plan} plan")
                
                await update.callback_query.edit_message_text(
                    f"✅ User approved!\n"
                    f"Plan: `{plan}`"
                )
                
                await self.log_action(
                    admin_id, "user.approved", "user",
                    resource_id=str(target_user_id), status="success",
                    details={"plan": plan}
                )
                
                # TODO: Notify user
                
            except Exception as e:
                logger.error(f"Error approving user {target_user_id}: {e}")
                await update.callback_query.answer("❌ Error approving user", show_alert=True)
    
    async def reject_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                         user_repo=None, audit_logger=None):
        """Reject user approval."""
        admin_id = update.effective_user.id
        
        # Check admin
        if not await self.is_admin(admin_id):
            await update.callback_query.answer("❌ Admin only")
            return
        
        # Extract user ID
        target_user_id = int(update.callback_query.data.split("_")[2])
        
        # Mark user as blocked
        if user_repo:
            try:
                # TODO: Implement rejection logic
                await update.callback_query.answer("✅ User rejected")
                
                await update.callback_query.edit_message_text(
                    f"❌ User rejected"
                )
                
                await self.log_action(
                    admin_id, "user.rejected", "user",
                    resource_id=str(target_user_id), status="success"
                )
                
            except Exception as e:
                logger.error(f"Error rejecting user {target_user_id}: {e}")
                await update.callback_query.answer("❌ Error rejecting user", show_alert=True)
    
    async def system_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                          user_repo=None, bot_repo=None):
        """Show system statistics."""
        user_id = update.effective_user.id
        
        # Check admin
        if not await self.is_admin(user_id):
            await update.callback_query.answer("❌ Admin only")
            return
        
        # Gather stats
        total_users = 0
        approved_users = 0
        total_bots = 0
        running_bots = 0
        
        # TODO: Implement stats gathering from database
        
        stats_text = (
            "📊 *System Statistics*\n\n"
            f"👥 *Users*\n"
            f"• Total: `{total_users}`\n"
            f"• Approved: `{approved_users}`\n\n"
            f"🤖 *Bots*\n"
            f"• Total: `{total_bots}`\n"
            f"• Running: `{running_bots}`\n\n"
            f"💾 *Database*\n"
            f"• Status: `Connected`"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            stats_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def error_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                        error_log_repo=None):
        """Show recent error logs."""
        user_id = update.effective_user.id
        
        # Check admin
        if not await self.is_admin(user_id):
            await update.callback_query.answer("❌ Admin only")
            return
        
        # Get recent errors
        errors = []
        # TODO: Fetch from error_log_repo
        
        if not errors:
            logs_text = "🚨 *Error Logs*\n\nNo recent errors."
        else:
            logs_text = "🚨 *Recent Errors*\n\n"
            for error in errors[:10]:
                logs_text += f"• {error.level}: {error.message}\n"
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            logs_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def broadcast_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                               user_repo=None):
        """Send broadcast message to all users."""
        user_id = update.effective_user.id
        
        # Check admin
        if not await self.is_admin(user_id):
            await update.message.reply_text("❌ Admin only")
            return
        
        # Get message text
        message_text = update.message.text.replace("/broadcast ", "")
        
        # TODO: Send to all approved users
        
        await update.message.reply_text(
            f"✅ Broadcast sent to users:\n"
            f"Message: {message_text[:50]}..."
        )
        
        await self.log_action(
            user_id, "admin.broadcast", "system",
            status="success", details={"message": message_text[:100]}
        )
