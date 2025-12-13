import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, WebAppInfo
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Import configuration
from config import (
    API_KEY, TOKEN, TODO_LIST_ID, DOING_LIST_ID, DONE_LIST_ID, MY_MEMBER_ID,
    TELEGRAM_BOT_TOKEN, MORTEZAS_CHAT_ID, CHAT_IDS,
    ALLOWED_GROUP_ID, MINI_APP_URL
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)



def is_allowed_group(update: Update) -> bool:
    """Check if the message is from the allowed group"""
    if update.effective_chat:
        chat_id = update.effective_chat.id
        if chat_id != ALLOWED_GROUP_ID:
            logger.warning(f"Unauthorized access attempt from chat_id: {chat_id}")
            return False
    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command and show mini app button"""
    # Check if message is from allowed group
    if not is_allowed_group(update):
        return

    # Create button that opens the mini app
    keyboard = [
        [InlineKeyboardButton("🚀 Open Menu", web_app=WebAppInfo(url=MINI_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Welcome to Trello Bot! 👋\n\n"
        "Click the button below to open the menu:",
        reply_markup=reply_markup
    )


async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /show command"""
    # Check if message is from allowed group
    if not is_allowed_group(update):
        return

    await update.message.reply_text(
        "Command received: show"
    )


async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle data sent from the mini app"""
    # Check if message is from allowed group
    if not is_allowed_group(update):
        return

    # Get the data sent from the mini app
    data = update.message.web_app_data.data

    # Send message to group with the button name
    await update.message.reply_text(
        f"You clicked: {data}"
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks from inline keyboard"""
    # Check if message is from allowed group
    if not is_allowed_group(update):
        return

    query = update.callback_query
    await query.answer()  # Acknowledge the button click

    if query.data == 'start_action':
        await query.edit_message_text(
            "You clicked: START button ✅\n\n"
            "Command received: start"
        )
    elif query.data == 'show_action':
        await query.edit_message_text(
            "You clicked: SHOW button ✅\n\n"
            "Command received: show"
        )


async def setup_commands(app: Application):
    """Set up bot commands for the menu button"""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("show", "Show something")
    ]
    await app.bot.set_my_commands(commands)
    logger.info("Bot commands set up successfully")


async def post_init(app: Application):
    """Initialize bot commands after startup"""
    await setup_commands(app)


def main():
    """Start the bot"""
    # Create application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("show", show))

    # Add web app data handler
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))

    # Add button callback handler (for future use)
    app.add_handler(CallbackQueryHandler(button_handler))

    # Start polling
    logger.info("Bot started! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
