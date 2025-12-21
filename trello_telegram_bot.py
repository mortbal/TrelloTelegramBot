import logging
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from google import genai
from pydantic import BaseModel, Field

# Import configuration
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_GROUP_CHAT_ID, TELEGRAM_PERSONAL_CHAT_ID, GEMINI_API_KEY

# Import Trello functions
from task_functions import (
    get_json_path, json_path, fetch_all_trello_tasks, fetch_tasks_from_trello_api,
    fetch_tasks_from_json, create_task, update_task
)
from trello_enums import Priority, Status

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# Pydantic model for Gemini API response
class TrelloTaskSchema(BaseModel):
    title: str = Field(description="Name of the task.")
    description: str = Field(description="Description of the task")


def extract_title_with_gemini(message_body: str) -> str:
    """Extract task title from message body using Gemini API

    Args:
        message_body: The message text to extract title from

    Returns:
        Extracted title or "New Task" if extraction fails
    """
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"Please extract a title and an optional description for a task on Trello from the following message: {message_body}"

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": TrelloTaskSchema.model_json_schema(),
            },
        )

        trello_task = TrelloTaskSchema.model_validate_json(response.text)
        return trello_task.title if trello_task.title else "New Task"
    except Exception as e:
        logger.error(f"Failed to extract title with Gemini: {e}")
        return "New Task"


"""
Security code
only allows bot to work with one group and one private chat
"""
def is_with_allowed_group(update: Update) -> bool:
    """Check if the message is from the allowed group"""
    if update.effective_chat:
        chat_id = update.effective_chat.id
        if chat_id != TELEGRAM_GROUP_CHAT_ID:
            logger.error(f"Unauthorized group access from chat_id: {chat_id}")
            return False
    return True


def is_with_allowed_user(update: Update) -> bool:
    """Check if the message is from the allowed user"""
    if update.effective_chat:
        chat_id = update.effective_chat.id
        if chat_id != TELEGRAM_PERSONAL_CHAT_ID:
            logger.error(f"Unauthorized user access from chat_id: {chat_id}")
            return False
    return True


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    if not update.message:
        return

    first_name = update.effective_user.first_name
    chat_type = update.effective_chat.type

    # Show fixed keyboard in private chats
    if chat_type == "private":
        # Check day_started status for dynamic button
        day_started = False
        if get_json_path():
            with open(json_path, 'r') as f:
                data = json.load(f)
                day_started = data.get('day_started', False)

        day_button_text = "End day" if day_started else "Start day"

        keyboard = [
            [KeyboardButton("Get tasks"), KeyboardButton("Get cached tasks")],
            [KeyboardButton(day_button_text), KeyboardButton("Start week")],
            [KeyboardButton("Get day report"), KeyboardButton("Get week report")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            f"Hello {first_name}, use the buttons below to manage your tasks or create new tasks using /task {{task title}}. "
            f"You can also use /task_high or /task_low to set priority.",
            reply_markup=reply_markup
        )
    else:
        sent_message = await update.message.reply_text(
            f"Hello {first_name}, start getting the menu by typing /trello or create new tasks using /task {{task title}} "
            f"or replying to a message with /task. You can also use /task_high or /task_low to set priority."
        )
        # Delete message after 15 seconds
        await asyncio.sleep(15)
        await sent_message.delete()


async def task_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, priority=None):
    """Handle task commands"""
    if not update.message:
        return

    # Check authorization
    chat_type = update.effective_chat.type
    if chat_type == "private":
        if not is_with_allowed_user(update):
            return
    elif chat_type in ["group", "supergroup"]:
        if not is_with_allowed_group(update):
            return

    # Temporary variables
    task_title = ""
    replied_message_body = ""

    # Get command arguments (text after /task)
    if context.args:
        task_title = " ".join(context.args)

    # Check if user replied to a message
    if update.message.reply_to_message:
        replied_msg = update.message.reply_to_message

        # Get text or caption from replied message
        if replied_msg.text:
            replied_message_body = replied_msg.text
        elif replied_msg.caption:
            replied_message_body = replied_msg.caption

        # Scenario 3: If no task_title from command, extract title using Gemini
        if not task_title and replied_message_body:
            task_title = extract_title_with_gemini(replied_message_body)
            # Keep replied_message_body as description (don't clear it)

    # Check if both task_title and replied_message_body are empty
    if not task_title and not replied_message_body:
        await update.message.reply_text(
            "Please provide a task title or reply to a message to create a task.\n"
            "Usage: /task {title} or reply to a message with /task"
        )
        return

    # Map priority string to Priority enum
    priority_map = {
        "high": Priority.HIGH,
        "med": Priority.MEDIUM,
        "low": Priority.LOW
    }
    priority_enum = priority_map.get(priority) if priority else None

    # Create task if we have a title (description can be empty)
    if task_title:
        create_task(task_title, priority_enum, replied_message_body)


async def task_high_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /task_high command"""
    await task_handler(update, context, "high")


async def task_med_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /task_med command"""
    await task_handler(update, context, "med")


async def task_low_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /task_low command"""
    await task_handler(update, context, "low")


async def public_trello_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trello in group chat"""
    await update.message.reply_text("Public Trello function")


async def trello_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trello command"""
    if not update.message:
        return

    chat_type = update.effective_chat.type

    # Only work in group chats
    if chat_type in ["group", "supergroup"]:
        await public_trello_handler(update, context)


def GetTopTasks(limit: int = 10 , refresh:bool =True) -> list:
    """Sort tasks by priority: DOING first, then TODO high priority, then others

    Args:
        todo_tasks: List of TODO tasks
        doing_tasks: List of DOING tasks
        limit: Maximum number of tasks to return

    Returns:
        Sorted and limited list of tasks
    """
    if refresh :
        # Fetch tasks from Trello API for TODO and DOING
        fetch_tasks_from_trello_api(Status.TODO)
        fetch_tasks_from_trello_api(Status.DOING)
        
    # Get the fetched tasks from JSON
    todo_tasks = fetch_tasks_from_json(limit, Status.TODO)
    doing_tasks = fetch_tasks_from_json(limit, Status.DOING)
    sorted_tasks = []

    # First: All DOING tasks
    sorted_tasks.extend(doing_tasks)

    # Second: TODO tasks with high priority
    todo_high_priority = [task for task in todo_tasks if task.get('labels') == 'High Priority']
    sorted_tasks.extend(todo_high_priority)

    # Third: Remaining TODO tasks (not high priority)
    todo_other = [task for task in todo_tasks if task.get('labels') != 'High Priority']
    sorted_tasks.extend(todo_other)

    # Return limited list
    return sorted_tasks[:limit]


async def keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle fixed keyboard button clicks in private chat"""
    if not update.message or not update.message.text:
        return

    chat_type = update.effective_chat.type
    if chat_type != "private":
        return

    text = update.message.text
    first_name = update.effective_user.first_name

    if text == "Get tasks":

        # get top 10 tasks with refresh
        sorted_tasks = GetTopTasks (10,True)

        # Create inline keyboard buttons
        keyboard = []
        for task in sorted_tasks:
            task_name = task.get('name', 'Untitled')
            task_id = task.get('id', '')
            button = InlineKeyboardButton(task_name, callback_data=f'task_{task_id}')
            keyboard.append([button])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("✅ Tasks fetched from Trello:", reply_markup=reply_markup)

    elif text == "Get cached tasks":
        # get top 10 tasks without refresh
        sorted_tasks = GetTopTasks (10,False)

        # Create inline keyboard buttons
        keyboard = []
        for task in sorted_tasks:
            task_name = task.get('name', 'Untitled')
            task_id = task.get('id', '')
            button = InlineKeyboardButton(task_name, callback_data=f'task_{task_id}')
            keyboard.append([button])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📋 Cached Tasks:", reply_markup=reply_markup)

    elif text == "Start day":
        # Update day_started to true
        if get_json_path():
            with open(json_path, 'r') as f:
                data = json.load(f)
        else:
            data = {"todo": [], "doing": [], "done": []}

        data['day_started'] = True
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)

        # Send message with "send to group" button
        keyboard = [[InlineKeyboardButton("Send to group", callback_data='send_to_group_start')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"{first_name} started working",
            reply_markup=reply_markup
        )

        # Update keyboard to show "End day"
        keyboard = [
            [KeyboardButton("Get tasks"), KeyboardButton("Get cached tasks")],
            [KeyboardButton("End day"), KeyboardButton("Start week")],
            [KeyboardButton("Get day report"), KeyboardButton("Get week report")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Keyboard updated", reply_markup=reply_markup)

    elif text == "End day":
        # Update day_started to false
        if get_json_path():
            with open(json_path, 'r') as f:
                data = json.load(f)
        else:
            data = {"todo": [], "doing": [], "done": []}

        data['day_started'] = False
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)

        # Send message with "send to group" button
        keyboard = [[InlineKeyboardButton("Send to group", callback_data='send_to_group_end')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"{first_name} finished working",
            reply_markup=reply_markup
        )

        # Update keyboard to show "Start day"
        keyboard = [
            [KeyboardButton("Get tasks"), KeyboardButton("Get cached tasks")],
            [KeyboardButton("Start day"), KeyboardButton("Start week")],
            [KeyboardButton("Get day report"), KeyboardButton("Get week report")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Keyboard updated", reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks from inline keyboard"""
    query = update.callback_query
    await query.answer()

    # Handle send to group buttons
    if query.data == 'send_to_group_start':
        first_name = update.effective_user.first_name
        message_text = f"{first_name} started working"
        await context.bot.send_message(chat_id=TELEGRAM_GROUP_CHAT_ID, text=message_text)
        await query.message.delete()
        return

    elif query.data == 'send_to_group_end':
        first_name = update.effective_user.first_name
        message_text = f"{first_name} finished working"
        await context.bot.send_message(chat_id=TELEGRAM_GROUP_CHAT_ID, text=message_text)
        await query.message.delete()
        return


def main():
    """Start the bot"""
    # Create application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("trello", trello_handler))
    app.add_handler(CommandHandler("task_high", task_high_handler))
    app.add_handler(CommandHandler("task_med", task_med_handler))
    app.add_handler(CommandHandler("task_low", task_low_handler))
    app.add_handler(CommandHandler("task", task_handler))

    # Add button callback handler
    app.add_handler(CallbackQueryHandler(button_handler))

    # Add keyboard message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyboard_handler))

    # Start polling
    logger.info("Bot started! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
