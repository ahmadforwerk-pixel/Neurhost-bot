"""Bot management handlers - start, stop, delete, manage."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.telegram_handlers.base_handler import BaseHandler
from src.utils import seconds_to_human, render_bar

logger = logging.getLogger(__name__)


class BotManagementHandlers(BaseHandler):
    """Handle bot management commands."""
    
    async def my_bots(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                     user_repo=None, bot_repo=None):
        """Show user's bots list."""
        user_id = update.effective_user.id
        
        # Check auth
        if not await self.check_auth(user_id, user_repo):
            await update.callback_query.answer("❌ Not authenticated")
            return
        
        # Get user's bots
        bots = []
        if bot_repo:
            bots = await bot_repo.get_user_bots(user_id)
        
        if not bots:
            keyboard = [
                [InlineKeyboardButton("➕ Upload Bot", callback_data="bot_upload")],
                [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.callback_query.edit_message_text(
                "📂 *My Bots*\n\n"
                "You don't have any bots yet.\n"
                "Upload your first bot!",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            return
        
        # Build bots list
        keyboard = []
        for bot in bots:
            status_icon = "🟢" if bot.status == "running" else "🔴"
            remaining = seconds_to_human(bot.remaining_seconds) if bot.remaining_seconds > 0 else "Expired"
            
            label = f"{status_icon} {bot.name} - {remaining}"
            keyboard.append([
                InlineKeyboardButton(label, callback_data=f"bot_manage_{bot.id}")
            ])
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "📂 *My Bots*\n\n"
            "Select a bot to manage:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        await self.log_action(user_id, "bot.list_viewed", "bot", status="success")
    
    async def manage_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                        bot_repo=None):
        """Show bot management menu."""
        user_id = update.effective_user.id
        
        # Extract bot ID from callback data
        bot_id = int(update.callback_query.data.split("_")[2])
        
        # Check permission
        if not await self.check_permission(user_id, bot_id, bot_repo):
            await update.callback_query.answer("❌ Permission denied")
            return
        
        # Get bot info
        bot = None
        if bot_repo:
            bot = await bot_repo.get_by_id(bot_id)
        
        if not bot:
            await update.callback_query.answer("❌ Bot not found", show_alert=True)
            return
        
        # Build management menu
        keyboard = []
        
        if bot.status == "stopped":
            keyboard.append([InlineKeyboardButton("▶️ Start", callback_data=f"bot_start_{bot_id}")])
        else:
            keyboard.append([InlineKeyboardButton("⏹️ Stop", callback_data=f"bot_stop_{bot_id}")])
        
        keyboard.extend([
            [InlineKeyboardButton("📊 Details", callback_data=f"bot_details_{bot_id}")],
            [InlineKeyboardButton("⏱️ Add Time", callback_data=f"bot_addtime_{bot_id}")],
            [InlineKeyboardButton("⚡ Add Power", callback_data=f"bot_addpower_{bot_id}")],
            [InlineKeyboardButton("🗑️ Delete", callback_data=f"bot_confirm_del_{bot_id}")],
            [InlineKeyboardButton("🔙 Back", callback_data="my_bots")]
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Calculate status bar
        time_bar = render_bar(
            (bot.remaining_seconds / bot.total_seconds * 100) if bot.total_seconds > 0 else 0
        )
        power_bar = render_bar(
            (bot.power_remaining / bot.power_max * 100) if bot.power_max > 0 else 0
        )
        
        text = (
            f"🤖 *{bot.name}*\n\n"
            f"Status: `{bot.status}`\n\n"
            f"⏱️ Time\n"
            f"{time_bar}\n"
            f"Remaining: `{seconds_to_human(bot.remaining_seconds)}`\n\n"
            f"⚡ Power\n"
            f"{power_bar}\n"
            f"Remaining: `{bot.power_remaining:.1f}%`"
        )
        
        await update.callback_query.edit_message_text(
            text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def bot_details(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                         bot_repo=None):
        """Show detailed bot information."""
        user_id = update.effective_user.id
        
        # Extract bot ID
        bot_id = int(update.callback_query.data.split("_")[2])
        
        # Check permission
        if not await self.check_permission(user_id, bot_id, bot_repo):
            await update.callback_query.answer("❌ Permission denied")
            return
        
        # Get bot info
        bot = None
        if bot_repo:
            bot = await bot_repo.get_by_id(bot_id)
        
        if not bot:
            await update.callback_query.answer("❌ Bot not found", show_alert=True)
            return
        
        details_text = (
            f"🤖 *Bot Details: {bot.name}*\n\n"
            f"🔧 *Configuration*\n"
            f"• ID: `{bot.id}`\n"
            f"• Created: `{bot.created_at.strftime('%Y-%m-%d %H:%M')}`\n"
            f"• Status: `{bot.status}`\n\n"
            f"⏱️ *Hosting Time*\n"
            f"• Total: `{seconds_to_human(bot.total_seconds)}`\n"
            f"• Remaining: `{seconds_to_human(bot.remaining_seconds)}`\n"
            f"• Running since: `{bot.start_time.strftime('%Y-%m-%d %H:%M') if bot.start_time else 'N/A'}`\n\n"
            f"⚡ *Power*\n"
            f"• Max: `{bot.power_max:.1f}%`\n"
            f"• Current: `{bot.power_remaining:.1f}%`\n"
            f"• CPU Usage: `{bot.cpu_usage_percent:.1f}%`\n"
            f"• Memory: `{bot.memory_usage_mb:.1f} MB`"
        )
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back", callback_data=f"bot_manage_{bot_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            details_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
        await self.log_action(user_id, "bot.details_viewed", "bot", 
                            resource_id=str(bot_id), status="success")
    
    async def start_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                       bot_repo=None, audit_logger=None):
        """Start a bot."""
        user_id = update.effective_user.id
        
        # Extract bot ID
        bot_id = int(update.callback_query.data.split("_")[2])
        
        # Check permission
        if not await self.check_permission(user_id, bot_id, bot_repo):
            await update.callback_query.answer("❌ Permission denied")
            return
        
        # Get bot info
        bot = None
        if bot_repo:
            bot = await bot_repo.get_by_id(bot_id)
        
        if not bot:
            await update.callback_query.answer("❌ Bot not found", show_alert=True)
            return
        
        # Check if bot can be started
        if bot.remaining_seconds <= 0:
            await update.callback_query.answer(
                "❌ No hosting time remaining",
                show_alert=True
            )
            await self.log_action(user_id, "bot.start_denied", "bot",
                                resource_id=str(bot_id), status="failure",
                                error_code="NO_TIME")
            return
        
        if bot.power_remaining <= 0:
            await update.callback_query.answer(
                "❌ No power remaining",
                show_alert=True
            )
            await self.log_action(user_id, "bot.start_denied", "bot",
                                resource_id=str(bot_id), status="failure",
                                error_code="NO_POWER")
            return
        
        # TODO: Start bot in container (will be implemented in services)
        try:
            await update.callback_query.answer("⏳ Starting bot...")
            
            # For now, just update status to running
            if bot_repo:
                await bot_repo.update_status(bot_id, "running")
            
            await update.callback_query.edit_message_text(
                f"✅ Bot '{bot.name}' started successfully!"
            )
            
            await self.log_action(user_id, "bot.start_success", "bot",
                                resource_id=str(bot_id), status="success")
        
        except Exception as e:
            logger.error(f"Error starting bot {bot_id}: {e}")
            await update.callback_query.answer("❌ Error starting bot", show_alert=True)
            await self.log_action(user_id, "bot.start_error", "bot",
                                resource_id=str(bot_id), status="failure",
                                error_code="LAUNCH_ERROR")
    
    async def stop_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                      bot_repo=None, audit_logger=None):
        """Stop a running bot."""
        user_id = update.effective_user.id
        
        # Extract bot ID
        bot_id = int(update.callback_query.data.split("_")[2])
        
        # Check permission
        if not await self.check_permission(user_id, bot_id, bot_repo):
            await update.callback_query.answer("❌ Permission denied")
            return
        
        # Get bot info
        bot = None
        if bot_repo:
            bot = await bot_repo.get_by_id(bot_id)
        
        if not bot:
            await update.callback_query.answer("❌ Bot not found", show_alert=True)
            return
        
        # TODO: Stop bot container (will be implemented in services)
        try:
            await update.callback_query.answer("⏳ Stopping bot...")
            
            # For now, just update status
            if bot_repo:
                await bot_repo.update_status(bot_id, "stopped")
            
            await update.callback_query.edit_message_text(
                f"✅ Bot '{bot.name}' stopped successfully!"
            )
            
            await self.log_action(user_id, "bot.stop_success", "bot",
                                resource_id=str(bot_id), status="success")
        
        except Exception as e:
            logger.error(f"Error stopping bot {bot_id}: {e}")
            await update.callback_query.answer("❌ Error stopping bot", show_alert=True)
            await self.log_action(user_id, "bot.stop_error", "bot",
                                resource_id=str(bot_id), status="failure",
                                error_code="STOP_ERROR")
    
    async def delete_bot_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ask confirmation for deleting bot."""
        # Extract bot ID
        bot_id = int(update.callback_query.data.split("_")[3])
        
        keyboard = [
            [
                InlineKeyboardButton("✅ Yes, Delete", callback_data=f"bot_delete_{bot_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"bot_manage_{bot_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.callback_query.edit_message_text(
            "🗑️ *Delete Bot*\n\n"
            "⚠️ Are you sure? This cannot be undone!",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    async def delete_bot(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                        bot_repo=None, audit_logger=None):
        """Delete a bot."""
        user_id = update.effective_user.id
        
        # Extract bot ID
        bot_id = int(update.callback_query.data.split("_")[2])
        
        # Check permission
        if not await self.check_permission(user_id, bot_id, bot_repo):
            await update.callback_query.answer("❌ Permission denied")
            return
        
        # Delete bot
        try:
            if bot_repo:
                await bot_repo.delete(bot_id)
            
            await update.callback_query.edit_message_text(
                "✅ Bot deleted successfully!"
            )
            
            # Show back to my bots
            await self.my_bots(update, context, bot_repo=bot_repo)
            
            await self.log_action(user_id, "bot.deleted", "bot",
                                resource_id=str(bot_id), status="success")
        
        except Exception as e:
            logger.error(f"Error deleting bot {bot_id}: {e}")
            await update.callback_query.answer("❌ Error deleting bot", show_alert=True)
            await self.log_action(user_id, "bot.delete_error", "bot",
                                resource_id=str(bot_id), status="failure",
                                error_code="DELETE_ERROR")
