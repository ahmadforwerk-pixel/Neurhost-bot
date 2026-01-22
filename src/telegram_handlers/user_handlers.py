"""User handlers for start, help, and basic commands."""

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.telegram_handlers.base_handler import BaseHandler

logger = logging.getLogger(__name__)


class UserHandlers(BaseHandler):
    """Handle user-related commands and interactions."""
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                   user_repo=None, rate_limiter=None, audit_logger=None):
        """
        Handle /start command.
        
        Args:
            update: Telegram update
            context: Telegram context
            user_repo: UserRepository instance
            rate_limiter: RateLimiter instance
            audit_logger: AuditLogger instance
        """
        user = update.effective_user
        user_id = user.id
        
        # Rate limiting
        allowed, retry_after = await self.check_rate_limit(user_id, "user:start", limit=10, window=60)
        if not allowed:
            await update.message.reply_text(
                f"⏱️ Too many requests. Try again in {retry_after} seconds."
            )
            return
        
        # Check if user exists
        if user_repo:
            existing_user = await user_repo.get_by_id(user_id)
            
            if not existing_user:
                # New user - create pending account
                try:
                    await user_repo.create(user_id, user.username or f"user_{user_id}", "pending")
                    await update.message.reply_text(
                        "👋 Welcome to NeuroHost!\n\n"
                        "Your account is pending admin approval.\n"
                        "Please wait for approval before using features."
                    )
                    # Log new user signup
                    await self.log_action(user_id, "user.signup", "user", status="success")
                except Exception as e:
                    logger.error(f"Error creating user {user_id}: {e}")
                    await update.message.reply_text("❌ Error creating account.")
                    await self.log_action(user_id, "user.signup", "user", 
                                        status="failure", error_code="DB_ERROR")
                    return
            
            # Check if user is approved
            if existing_user and existing_user.status != "approved":
                if existing_user.status == "blocked":
                    await update.message.reply_text(
                        f"❌ Your account is blocked.\nReason: {existing_user.blocked_reason}"
                    )
                else:
                    await update.message.reply_text(
                        "⏳ Your account is still pending approval.\n"
                        "Please wait for admin to approve."
                    )
                return
        
        # Show main menu
        await self.show_main_menu(update, context)
        await self.log_action(user_id, "user.start", "user", status="success")
    
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main menu to user."""
        keyboard = [
            [
                InlineKeyboardButton("➕ Upload Bot", callback_data="bot_upload"),
                InlineKeyboardButton("🔁 GitHub Deploy", callback_data="bot_github"),
            ],
            [
                InlineKeyboardButton("📂 My Bots", callback_data="my_bots"),
                InlineKeyboardButton("📊 Dashboard", callback_data="dashboard"),
            ],
            [
                InlineKeyboardButton("💬 Feedback", callback_data="feedback"),
                InlineKeyboardButton("ℹ️ Help", callback_data="help"),
            ],
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(
                "🎮 *Main Menu*\n\n"
                "What would you like to do?",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                "🎮 *Main Menu*\n\n"
                "What would you like to do?",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help message."""
        help_text = """
🆘 *Help & Information*

*Commands:*
• `/start` - Show main menu
• `/help` - Show this message

*Features:*
🤖 *Upload Bot* - Upload your bot code directly
📦 *GitHub Deploy* - Deploy from GitHub repository
📂 *My Bots* - Manage your hosted bots
⏱️ *Time Tracking* - Monitor remaining hosting time
⚡ *Power System* - Track resource usage
🛌 *Sleep Mode* - Auto sleep when resources depleted

*Limits by Plan:*
Free: 1 day, 30% power, 3 bots
Pro: 7 days, 60% power, 10 bots
Ultra: Unlimited

*Need Help?*
Contact: @support or use Feedback button
"""
        
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                help_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                help_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    
    async def dashboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                       user_repo=None, bot_repo=None):
        """Show user dashboard with stats."""
        user_id = update.effective_user.id
        
        # Get user info
        user = None
        if user_repo:
            user = await user_repo.get_by_id(user_id)
        
        # Get user bots
        bots = []
        if bot_repo:
            bots = await bot_repo.get_user_bots(user_id)
        
        # Build dashboard
        dashboard_text = "📊 *Your Dashboard*\n\n"
        
        if user:
            dashboard_text += f"👤 *Account*\n"
            dashboard_text += f"• Plan: `{user.plan}`\n"
            dashboard_text += f"• Status: `{user.status}`\n"
            dashboard_text += f"• Member since: `{user.joined_at.strftime('%Y-%m-%d')}`\n\n"
        
        dashboard_text += f"🤖 *Bots*\n"
        dashboard_text += f"• Total: `{len(bots)}`\n"
        
        running = sum(1 for b in bots if b.status == "running")
        sleeping = sum(1 for b in bots if b.status == "sleeping")
        
        dashboard_text += f"• Running: `{running}`\n"
        dashboard_text += f"• Sleeping: `{sleeping}`\n"
        
        keyboard = [
            [InlineKeyboardButton("📂 My Bots", callback_data="my_bots")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                dashboard_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                dashboard_text,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
    
    async def feedback_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start feedback flow."""
        await update.callback_query.edit_message_text(
            "📝 *Send Feedback*\n\n"
            "Please share your feedback, suggestions, or report issues.\n"
            "Type your message and send:"
        )
        
        # Mark in context that we're waiting for feedback
        context.user_data['waiting_for_feedback'] = True
    
    async def feedback_receive(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                             audit_logger=None):
        """Receive feedback message."""
        user_id = update.effective_user.id
        feedback_text = update.message.text
        
        if not context.user_data.get('waiting_for_feedback'):
            return
        
        # Log feedback
        if audit_logger:
            await self.log_action(
                user_id, "user.feedback", "user",
                status="success", details={"feedback": feedback_text[:100]}
            )
        
        context.user_data['waiting_for_feedback'] = False
        
        await update.message.reply_text(
            "✅ Thank you for your feedback!\n"
            "We'll review it shortly."
        )
        
        # Show menu again
        await self.show_main_menu(update, context)
