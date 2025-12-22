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
import task_functions
from task_functions import (
    get_json_path, fetch_all_trello_tasks, fetch_tasks_from_trello_api,
    fetch_tasks_from_json, create_task, update_task, get_report, get_card_details
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
        # Check day_started and week_started status for dynamic buttons
        day_started = False
        week_started = False
        if get_json_path():
            with open(task_functions.json_path, 'r') as f:
                data = json.load(f)
                day_started = data.get('day_started', False)
                week_started = data.get('week_started', False)

        day_button_text = "End day" if day_started else "Start day"
        week_button_text = "End week" if week_started else "Start week"

        keyboard = [
            [KeyboardButton("Get tasks"), KeyboardButton("Get cached tasks")],
            [KeyboardButton(day_button_text), KeyboardButton(week_button_text)],
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
    # Check authorization
    if not is_with_allowed_group(update):
        return

    # Fetch top 10 tasks
    sorted_tasks = GetTopTasks(10, True)

    # Format plain text message
    if sorted_tasks:
        message = "📋 **Current Tasks:**\n\n"
        for i, task in enumerate(sorted_tasks, 1):
            task_name = task.get('name', 'Untitled')
            priority_label = task.get('labels')
            emoji = get_priority_emoji(priority_label)
            message += f"{i}. {emoji}{task_name}\n"

        message += "\n💡 Run /task to create new tasks"
    else:
        message = "📋 No tasks available.\n\n💡 Run /task to create new tasks"

    await update.message.reply_text(message, parse_mode="Markdown")


async def trello_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trello command"""
    if not update.message:
        return

    chat_type = update.effective_chat.type

    # Only work in group chats
    if chat_type in ["group", "supergroup"]:
        await public_trello_handler(update, context)


def get_priority_emoji(priority_label: str) -> str:
    """Get emoji for priority label

    Args:
        priority_label: Priority label text (e.g., "High Priority")

    Returns:
        Emoji string: 🔴 for high, 🟡 for medium, 🔵 for low, empty for none
    """
    if not priority_label:
        return ""

    if "High" in priority_label:
        return "🔴 "
    elif "Medium" in priority_label:
        return "🟡 "
    elif "Low" in priority_label:
        return "🔵 "
    return ""


def generate_day_report() -> tuple:
    """Generate day report with completed and in-progress tasks

    Returns:
        Tuple of (report_message: str, has_data: bool)
    """
    from datetime import datetime, timezone, timedelta
    from config import TRELLO_MY_MEMBER_ID

    # Read day_start_date from JSON
    if not get_json_path():
        return ("⚠️ No data available. Please start your day first.", False)

    with open(task_functions.json_path, 'r') as f:
        data = json.load(f)

    day_start_date_str = data.get('day_start_date')
    if not day_start_date_str:
        return ("⚠️ No day started. Please start your day first.", False)

    # Parse day_start_date
    try:
        day_start = datetime.fromisoformat(day_start_date_str)
        if day_start.tzinfo is None:
            day_start = day_start.replace(tzinfo=timezone.utc)
        else:
            day_start = day_start.astimezone(timezone.utc)

        # Create date range (start of day to end of day)
        day_end = day_start + timedelta(days=1)
    except Exception as e:
        logger.error(f"Error parsing day_start_date: {e}")
        return ("⚠️ Error parsing day start date.", False)

    # Get completed tasks from DONE and REVIEW
    done_tasks = get_report(Status.DONE, day_start, day_end)
    review_tasks = get_report(Status.REVIEW, day_start, day_end)

    # Filter by user membership
    completed_tasks = []
    for task in done_tasks + review_tasks:
        if TRELLO_MY_MEMBER_ID in task.get('idMembers', []):
            completed_tasks.append(task)

    # Get all DOING tasks
    doing_tasks = fetch_tasks_from_json(100, Status.DOING)

    # Format message
    date_str = day_start.strftime("%Y-%m-%d")
    message = f"📊 **Day Report for {date_str}**\n\n"

    message += f"✅ **Completed (DONE/REVIEW): {len(completed_tasks)}**\n"
    if completed_tasks:
        for task in completed_tasks:
            task_name = task.get('name', 'Untitled')
            short_url = task.get('shortUrl', '')
            message += f"• [{task_name}]({short_url})\n"
    else:
        message += "_No completed tasks_\n"

    message += f"\n🔄 **In Progress (DOING): {len(doing_tasks)}**\n"
    if doing_tasks:
        for task in doing_tasks:
            task_name = task.get('name', 'Untitled')
            short_url = task.get('shortUrl', '')
            message += f"• [{task_name}]({short_url})\n"
    else:
        message += "_No tasks in progress_\n"

    return (message, True)


def generate_week_report() -> tuple:
    """Generate week report with completed and in-progress tasks

    Returns:
        Tuple of (report_message: str, has_data: bool)
    """
    from datetime import datetime, timezone
    from config import TRELLO_MY_MEMBER_ID

    # Read week_start_date from JSON
    if not get_json_path():
        return ("⚠️ No data available. Please start your week first.", False)

    with open(task_functions.json_path, 'r') as f:
        data = json.load(f)

    week_start_date_str = data.get('week_start_date')
    if not week_start_date_str:
        return ("⚠️ No week started. Please start your week first.", False)

    # Parse week_start_date
    try:
        week_start = datetime.fromisoformat(week_start_date_str)
        if week_start.tzinfo is None:
            week_start = week_start.replace(tzinfo=timezone.utc)
        else:
            week_start = week_start.astimezone(timezone.utc)

        # End date is now
        week_end = datetime.now(timezone.utc)
    except Exception as e:
        logger.error(f"Error parsing week_start_date: {e}")
        return ("⚠️ Error parsing week start date.", False)

    # Get completed tasks from DONE and REVIEW
    done_tasks = get_report(Status.DONE, week_start, week_end)
    review_tasks = get_report(Status.REVIEW, week_start, week_end)

    # Filter by user membership
    completed_tasks = []
    for task in done_tasks + review_tasks:
        if TRELLO_MY_MEMBER_ID in task.get('idMembers', []):
            completed_tasks.append(task)

    # Get all DOING tasks
    doing_tasks = fetch_tasks_from_json(100, Status.DOING)

    # Format message
    week_start_str = week_start.strftime("%Y-%m-%d")
    message = f"📊 **Week Report (from {week_start_str})**\n\n"

    message += f"✅ **Completed (DONE/REVIEW): {len(completed_tasks)}**\n"
    if completed_tasks:
        for task in completed_tasks:
            task_name = task.get('name', 'Untitled')
            short_url = task.get('shortUrl', '')
            message += f"• [{task_name}]({short_url})\n"
    else:
        message += "_No completed tasks_\n"

    message += f"\n🔄 **In Progress (DOING): {len(doing_tasks)}**\n"
    if doing_tasks:
        for task in doing_tasks:
            task_name = task.get('name', 'Untitled')
            short_url = task.get('shortUrl', '')
            message += f"• [{task_name}]({short_url})\n"
    else:
        message += "_No tasks in progress_\n"

    return (message, True)


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
            priority_label = task.get('labels')
            emoji = get_priority_emoji(priority_label)
            button = InlineKeyboardButton(f"{emoji}{task_name}", callback_data=f'task_{task_id}')
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
            priority_label = task.get('labels')
            emoji = get_priority_emoji(priority_label)
            button = InlineKeyboardButton(f"{emoji}{task_name}", callback_data=f'task_{task_id}')
            keyboard.append([button])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("📋 Cached Tasks:", reply_markup=reply_markup)

    elif text == "Start day":
        # Update day_started to true and save current date
        from datetime import datetime
        if get_json_path():
            with open(task_functions.json_path, 'r') as f:
                data = json.load(f)
        else:
            data = {"todo": [], "doing": [], "done": []}

        data['day_started'] = True
        data['day_start_date'] = datetime.now().isoformat()
        with open(task_functions.json_path, 'w') as f:
            json.dump(data, f, indent=2)

        # Send message with "send to group" button
        keyboard = [[InlineKeyboardButton("Send to group", callback_data='send_day_start')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("✅ Day started!", reply_markup=reply_markup)

        # Update keyboard to show "End day"
        # Check week_started status
        week_started = data.get('week_started', False)
        week_button_text = "End week" if week_started else "Start week"

        keyboard = [
            [KeyboardButton("Get tasks"), KeyboardButton("Get cached tasks")],
            [KeyboardButton("End day"), KeyboardButton(week_button_text)],
            [KeyboardButton("Get day report"), KeyboardButton("Get week report")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        msg = await update.message.reply_text("Keyboard updated", reply_markup=reply_markup)
        await asyncio.sleep(1)
        await msg.delete()

    elif text == "End day":
        # Update day_started to false
        if get_json_path():
            with open(task_functions.json_path, 'r') as f:
                data = json.load(f)
        else:
            data = {"todo": [], "doing": [], "done": []}

        data['day_started'] = False
        with open(task_functions.json_path, 'w') as f:
            json.dump(data, f, indent=2)

        # Generate day report
        report_message, has_data = generate_day_report()

        # Send report with "send to group" button
        keyboard = [[InlineKeyboardButton("Send to group", callback_data='send_day_report')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Store report in context for later send to group
        context.user_data['last_day_report'] = report_message

        await update.message.reply_text(
            report_message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        # Update keyboard to show "Start day"
        # Check week_started status
        week_started = data.get('week_started', False)
        week_button_text = "End week" if week_started else "Start week"

        keyboard = [
            [KeyboardButton("Get tasks"), KeyboardButton("Get cached tasks")],
            [KeyboardButton("Start day"), KeyboardButton(week_button_text)],
            [KeyboardButton("Get day report"), KeyboardButton("Get week report")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        msg = await update.message.reply_text("Keyboard updated", reply_markup=reply_markup)
        await asyncio.sleep(1)
        await msg.delete()

    elif text == "Start week":
        # Save week start date
        from datetime import datetime
        if get_json_path():
            with open(task_functions.json_path, 'r') as f:
                data = json.load(f)
        else:
            data = {"todo": [], "doing": [], "done": []}

        data['week_started'] = True
        data['week_start_date'] = datetime.now().isoformat()
        with open(task_functions.json_path, 'w') as f:
            json.dump(data, f, indent=2)

        # Send message with "send to group" button
        keyboard = [[InlineKeyboardButton("Send to group", callback_data='send_week_start')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("✅ Week started!", reply_markup=reply_markup)

        # Update keyboard to show "End week"
        # Check day_started status
        day_started = data.get('day_started', False)
        day_button_text = "End day" if day_started else "Start day"

        keyboard = [
            [KeyboardButton("Get tasks"), KeyboardButton("Get cached tasks")],
            [KeyboardButton(day_button_text), KeyboardButton("End week")],
            [KeyboardButton("Get day report"), KeyboardButton("Get week report")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        msg = await update.message.reply_text("Keyboard updated", reply_markup=reply_markup)
        await asyncio.sleep(1)
        await msg.delete()

    elif text == "End week":
        # Update week_started to false
        if get_json_path():
            with open(task_functions.json_path, 'r') as f:
                data = json.load(f)
        else:
            data = {"todo": [], "doing": [], "done": []}

        data['week_started'] = False
        with open(task_functions.json_path, 'w') as f:
            json.dump(data, f, indent=2)

        # Generate week report
        report_message, has_data = generate_week_report()

        # Send report with "send to group" button
        keyboard = [[InlineKeyboardButton("Send to group", callback_data='send_week_report')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Store report in context for later send to group
        context.user_data['last_week_report'] = report_message

        await update.message.reply_text(
            report_message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        # Update keyboard to show "Start week"
        # Check day_started status
        day_started = data.get('day_started', False)
        day_button_text = "End day" if day_started else "Start day"

        keyboard = [
            [KeyboardButton("Get tasks"), KeyboardButton("Get cached tasks")],
            [KeyboardButton(day_button_text), KeyboardButton("Start week")],
            [KeyboardButton("Get day report"), KeyboardButton("Get week report")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        msg = await update.message.reply_text("Keyboard updated", reply_markup=reply_markup)
        await asyncio.sleep(1)
        await msg.delete()

    elif text == "Get day report":
        # Generate and display day report
        report_message, has_data = generate_day_report()

        if has_data:
            # Send report with "send to group" button
            keyboard = [[InlineKeyboardButton("Send to group", callback_data='send_day_report')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            # Store report in context for later send to group
            context.user_data['last_day_report'] = report_message
            await update.message.reply_text(
                report_message,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(report_message)

    elif text == "Get week report":
        # Generate and display week report
        report_message, has_data = generate_week_report()

        if has_data:
            # Send report with "send to group" button
            keyboard = [[InlineKeyboardButton("Send to group", callback_data='send_week_report')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            # Store report in context for later send to group
            context.user_data['last_week_report'] = report_message
            await update.message.reply_text(
                report_message,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(report_message)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks from inline keyboard"""
    query = update.callback_query
    await query.answer()

    # Handle send to group buttons
    if query.data == 'send_day_start':
        await context.bot.send_message(chat_id=TELEGRAM_GROUP_CHAT_ID, text="✅ Day started!")
        await query.message.edit_text("✅ Sent to group: Day started!")
        return

    elif query.data == 'send_week_start':
        await context.bot.send_message(chat_id=TELEGRAM_GROUP_CHAT_ID, text="✅ Week started!")
        await query.message.edit_text("✅ Sent to group: Week started!")
        return

    elif query.data == 'send_day_report':
        # Get report from context
        report_message = context.user_data.get('last_day_report', '')
        if report_message:
            await context.bot.send_message(
                chat_id=TELEGRAM_GROUP_CHAT_ID,
                text=report_message,
                parse_mode="Markdown"
            )
            await query.message.edit_text("✅ Day report sent to group!")
        else:
            await query.message.edit_text("❌ No report available to send.")
        return

    elif query.data == 'send_week_report':
        # Get report from context
        report_message = context.user_data.get('last_week_report', '')
        if report_message:
            await context.bot.send_message(
                chat_id=TELEGRAM_GROUP_CHAT_ID,
                text=report_message,
                parse_mode="Markdown"
            )
            await query.message.edit_text("✅ Week report sent to group!")
        else:
            await query.message.edit_text("❌ No report available to send.")
        return

    # Handle task button clicks - show task details and movement options
    elif query.data.startswith('task_'):
        task_id = query.data.replace('task_', '')

        # Fetch task details
        task_card = get_card_details(task_id)

        if task_card:
            # Format task details message
            message = f"**{task_card.name}**\n\n"

            # Add priority label if exists
            if task_card.labels:
                priority_emoji = get_priority_emoji(task_card.labels)
                message += f"{priority_emoji}**Priority:** {task_card.labels}\n\n"

            # Add description if exists
            if task_card.description:
                message += f"**Description:**\n{task_card.description}\n\n"

            # Add due date if exists
            if task_card.dueDate:
                due_str = task_card.dueDate.strftime("%Y-%m-%d %H:%M")
                status = "✅ Complete" if task_card.dueComplete else "⏳ Pending"
                message += f"**Due Date:** {due_str} ({status})\n\n"

            # Add comments if exist
            if task_card.comments:
                message += f"**Comments ({len(task_card.comments)}):**\n"
                for i, comment in enumerate(task_card.comments[:3], 1):  # Show first 3
                    comment_preview = comment[:100] + "..." if len(comment) > 100 else comment
                    message += f"{i}. {comment_preview}\n"
                if len(task_card.comments) > 3:
                    message += f"_...and {len(task_card.comments) - 3} more_\n"
                message += "\n"

            # Add task link
            message += f"[View on Trello]({task_card.shortUrl})"

            # Create movement buttons
            keyboard = [
                [InlineKeyboardButton("Move to TODO", callback_data=f'move_{task_id}_todo')],
                [InlineKeyboardButton("Move to DOING", callback_data=f'move_{task_id}_doing')],
                [InlineKeyboardButton("Move to DONE", callback_data=f'move_{task_id}_done')],
                [InlineKeyboardButton("Move to REVIEW", callback_data=f'move_{task_id}_review')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Update message to show task details and movement options
            await query.message.edit_text(
                message,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        else:
            await query.message.edit_text("❌ Failed to fetch task details.")
        return

    # Handle task movement
    elif query.data.startswith('move_'):
        # Parse callback data: move_{task_id}_{status}
        parts = query.data.split('_')
        if len(parts) == 3:
            task_id = parts[1]
            status_str = parts[2]

            # Map status string to Status enum
            status_map = {
                'todo': Status.TODO,
                'doing': Status.DOING,
                'done': Status.DONE,
                'review': Status.REVIEW
            }
            target_status = status_map.get(status_str)

            if target_status:
                # Read day_start_date from JSON for DONE/REVIEW
                due_date = None
                if target_status in [Status.DONE, Status.REVIEW]:
                    if get_json_path():
                        with open(task_functions.json_path, 'r') as f:
                            data = json.load(f)
                        due_date = data.get('day_start_date')

                # Update the task
                success = update_task(task_id, target_status, due_date=due_date)

                if success:
                    await query.message.edit_text(f"✅ Task moved to {status_str.upper()}!")
                else:
                    await query.message.edit_text(f"❌ Failed to move task.")
            else:
                await query.message.edit_text("❌ Invalid status.")
        return


async def delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /delete command - deletes the message that was replied to"""
    message = update.message

    # Check if this is a reply to a message
    if not message.reply_to_message:
        await message.reply_text("⚠️ Please reply to a message with /delete to delete it.")
        return

    # Check if the replied-to message is from the bot
    if message.reply_to_message.from_user.id != context.bot.id:
        await message.reply_text("⚠️ I can only delete my own messages.")
        return

    try:
        # Delete the replied-to message
        await message.reply_to_message.delete()
        # Also delete the command message
        await message.delete()
    except Exception as e:
        await message.reply_text(f"❌ Failed to delete message: {str(e)}")


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
    app.add_handler(CommandHandler("delete", delete_handler))

    # Add button callback handler
    app.add_handler(CallbackQueryHandler(button_handler))

    # Add keyboard message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyboard_handler))

    # Start polling
    logger.info("Bot started! Press Ctrl+C to stop. version 0.1")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
