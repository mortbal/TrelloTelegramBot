import logging
import requests
import json
import os
from datetime import datetime, timedelta
from enum import Enum
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes


# Import configuration
from config import (
    API_KEY, TOKEN, TODO_LIST_ID, DOING_LIST_ID, UNDER_REVIEW_LIST_ID, DONE_LIST_ID, MY_MEMBER_ID,
    TELEGRAM_BOT_TOKEN, PERSONAL_CHAT_ID, GROUP_CHAT_ID
)

# Label enum
class TaskLabel(Enum):
    HIGH_PRIORITY = "High Priority"
    MEDIUM_PRIORITY = "Medium Priority"
    LOW_PRIORITY = "Low Priority"
    BLOCKED = "Blocked"

# List enum
class TaskList(Enum):
    TODO = TODO_LIST_ID
    DOING = DOING_LIST_ID
    REVIEW = UNDER_REVIEW_LIST_ID
    DONE = DONE_LIST_ID

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


"""
Security code 
only allows bot to work with one group and one private chat 
"""
def is_with_allowed_group(update: Update) -> bool:
    """Check if the message is from the allowed group"""
    if update.effective_chat:
        chat_id = update.effective_chat.id
        if chat_id != GROUP_CHAT_ID:
            logger.warning(f"Unauthorized access attempt from chat_id: {chat_id}")
            return False
    return True

def is_with_allowed_user(update: Update) -> bool:
    """Check if the message is from the allowed user"""
    if update.effective_chat:
        chat_id = update.effective_chat.id
        if chat_id != PERSONAL_CHAT_ID:
            logger.warning(f"Unauthorized access attempt from chat_id: {chat_id}")
            return False
    return True



json_path=""
def get_json_path()->bool:
    global json_path
    if json_path == "":
        """Get the path to TrelloTasks.json"""
        script_dir = os.path.dirname(__file__)
        json_path = os.path.join(script_dir, "TrelloTasks.json")
    if not os.path.exists(json_path):
        return False
    else :
        return True


def fetch_trello_tasks():
    """Fetch tasks from Trello and update JSON file"""
    tasks_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "todo": [],
        "doing": [],
        "done": []
    }

    params = {'key': API_KEY, 'token': TOKEN}

    # Fetch TODO tasks
    url = f"https://api.trello.com/1/lists/{TODO_LIST_ID}/cards"
    response = requests.get(url, params=params)
    if response.status_code == 200:
        for card in response.json():
            card_id = card['id']

            # Add me as member if not already added
            if MY_MEMBER_ID not in card.get('idMembers', []):
                add_url = f"https://api.trello.com/1/cards/{card_id}/idMembers"
                add_params = {'key': API_KEY, 'token': TOKEN, 'value': MY_MEMBER_ID}
                requests.post(add_url, params=add_params)

            # Get comments
            comments_url = f"https://api.trello.com/1/cards/{card_id}/actions"
            comments_params = {'key': API_KEY, 'token': TOKEN, 'filter': 'commentCard'}
            comments_response = requests.get(comments_url, params=comments_params)
            comments = []
            if comments_response.status_code == 200:
                for comment in comments_response.json():
                    comments.append({
                        "author": comment['memberCreator']['fullName'],
                        "text": comment['data']['text']
                    })

            tasks_data["todo"].append({
                "id": card_id,
                "name": card['name'],
                "labels": card.get('labels', []),
                "description": card.get('desc', ''),
                "comments": comments,
                "shortUrl": card.get('shortUrl', '')
            })

    # Fetch DOING tasks
    url = f"https://api.trello.com/1/lists/{DOING_LIST_ID}/cards"
    response = requests.get(url, params=params)
    if response.status_code == 200:
        for card in response.json():
            if MY_MEMBER_ID in card.get('idMembers', []):
                card_id = card['id']

                # Get comments
                comments_url = f"https://api.trello.com/1/cards/{card_id}/actions"
                comments_params = {'key': API_KEY, 'token': TOKEN, 'filter': 'commentCard'}
                comments_response = requests.get(comments_url, params=comments_params)
                comments = []
                if comments_response.status_code == 200:
                    for comment in comments_response.json():
                        comments.append({
                            "author": comment['memberCreator']['fullName'],
                            "text": comment['data']['text']
                        })

                tasks_data["doing"].append({
                    "id": card_id,
                    "name": card['name'],
                    "labels": card.get('labels', []),
                    "description": card.get('desc', ''),
                    "comments": comments,
                    "shortUrl": card.get('shortUrl', '')
                })

    # Fetch DONE tasks
    url = f"https://api.trello.com/1/lists/{DONE_LIST_ID}/cards"
    response = requests.get(url, params=params)
    if response.status_code == 200:
        for card in response.json():
            if MY_MEMBER_ID in card.get('idMembers', []):
                card_id = card['id']

                # Get comments
                comments_url = f"https://api.trello.com/1/cards/{card_id}/actions"
                comments_params = {'key': API_KEY, 'token': TOKEN, 'filter': 'commentCard'}
                comments_response = requests.get(comments_url, params=comments_params)
                comments = []
                if comments_response.status_code == 200:
                    for comment in comments_response.json():
                        comments.append({
                            "author": comment['memberCreator']['fullName'],
                            "text": comment['data']['text']
                        })

                tasks_data["done"].append({
                    "id": card_id,
                    "name": card['name'],
                    "labels": card.get('labels', []),
                    "description": card.get('desc', ''),
                    "comments": comments,
                    "shortUrl": card.get('shortUrl', '')
                })

    # Update JSON file
    with open(json_path, 'w') as f:
        json.dump(tasks_data, f, indent=2)


def create_task(title, label_name=None, description=""):
    """Create a new task in Trello TODO list"""
    params = {
        'key': API_KEY,
        'token': TOKEN,
        'idList': TODO_LIST_ID,
        'name': title,
        'desc': description,
        'idMembers': [MY_MEMBER_ID]
    }

    # Create the card
    url = "https://api.trello.com/1/cards"
    response = requests.post(url, params=params)

    if response.status_code == 200:
        card_data = response.json()
        card_id = card_data['id']

        # Add label if provided
        if label_name:
            board_id = card_data['idBoard']
            labels_url = f"https://api.trello.com/1/boards/{board_id}/labels"
            labels_params = {'key': API_KEY, 'token': TOKEN}
            labels_response = requests.get(labels_url, params=labels_params)

            if labels_response.status_code == 200:
                labels = labels_response.json()
                for label in labels:
                    if label.get('name') == label_name:
                        label_id = label.get('id')
                        # Add label to card
                        label_url = f"https://api.trello.com/1/cards/{card_id}/idLabels"
                        label_params = {'key': API_KEY, 'token': TOKEN, 'value': label_id}
                        requests.post(label_url, params=label_params)
                        break

        # Fetch and update tasks
        fetch_trello_tasks()

        return card_data
    return None


def update_task(task_id, target_column, new_comment=""):
    """Move a task to target column and optionally add a comment"""
    params = {'key': API_KEY, 'token': TOKEN}

    if target_column in [TaskList.TODO, TaskList.DOING]:
        # Move to TODO or DOING: just move and unmark as complete
        update_params = {
            'key': API_KEY,
            'token': TOKEN,
            'idList': target_column.value,
            'dueComplete': 'false'
        }
        url = f"https://api.trello.com/1/cards/{task_id}"
        response = requests.put(url, params=update_params)
        success = response.status_code == 200

    elif target_column in [TaskList.REVIEW, TaskList.DONE]:
        # Get current card to find labels
        card_url = f"https://api.trello.com/1/cards/{task_id}"
        card_response = requests.get(card_url, params=params)

        if card_response.status_code == 200:
            card_data = card_response.json()
            label_ids = [label['id'] for label in card_data.get('idLabels', [])]

            # Remove all labels
            for label_id in label_ids:
                delete_label_url = f"https://api.trello.com/1/cards/{task_id}/idLabels/{label_id}"
                requests.delete(delete_label_url, params=params)

            # Move to REVIEW/DONE, set due date as today, mark as complete
            today = datetime.now().isoformat()
            update_params = {
                'key': API_KEY,
                'token': TOKEN,
                'idList': target_column.value,
                'due': today,
                'dueComplete': 'true'
            }
            url = f"https://api.trello.com/1/cards/{task_id}"
            response = requests.put(url, params=update_params)
            success = response.status_code == 200
        else:
            success = False
    else:
        success = False

    # Add comment if provided
    if success and new_comment:
        comment_url = f"https://api.trello.com/1/cards/{task_id}/actions/comments"
        comment_params = {'key': API_KEY, 'token': TOKEN, 'text': new_comment}
        requests.post(comment_url, params=comment_params)

    # Fetch and update tasks
    if success:
        fetch_trello_tasks()

    return success


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        await update.message.reply_text(
            f"Hello {first_name}, start getting the menu by typing /trello or create new tasks using /task {{task title}} "
            f"or replying to a message with /task. You can also use /task_high or /task_low to set priority."
        )


async def task(update: Update, context: ContextTypes.DEFAULT_TYPE, priority=None):
    """Handle task commands"""
    label_map = {
        "high": "High Priority",
        "med": "Medium Priority",
        "low": "Low Priority"
    }
    label = label_map.get(priority) if priority else None
    create_task("New Task", label, "")


async def task_high(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /task_high command"""
    await task(update, context, "high")


async def task_med(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /task_med command"""
    await task(update, context, "med")


async def task_low(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /task_low command"""
    await task(update, context, "low")


async def public_trello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trello in group chat"""
    await update.message.reply_text("Public Trello function")


async def trello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trello command"""
    if not update.message:
        return

    chat_type = update.effective_chat.type

    # Only work in group chats
    if chat_type in ["group", "supergroup"]:
        await public_trello(update, context)



async def keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle fixed keyboard button clicks in private chat"""
    if not update.message or not update.message.text:
        return

    chat_type = update.effective_chat.type
    if chat_type != "private":
        return

    text = update.message.text
    first_name = update.effective_user.first_name

    if text == "Start day":
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
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=message_text)
        await query.message.delete()
        return

    elif query.data == 'send_to_group_end':
        first_name = update.effective_user.first_name
        message_text = f"{first_name} finished working"
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=message_text)
        await query.message.delete()
        return

    # Group chat buttons - check authorization
    if not is_with_allowed_group(update):
        return

    # Handle Start Day button
    if query.data == 'start_day_btn':
        await query.message.delete()

        # Update JSON to set day_started = true and record start time
        json_path = get_json_path()
        start_time = datetime.now().isoformat()

        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data = json.load(f)
            data['day_started'] = True
            data['day_start_time'] = start_time
            data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "day_started": True,
                "day_start_time": start_time,
                "todo": [],
                "doing": [],
                "done": []
            }

        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)

    # Handle End Day button
    elif query.data == 'end_day_btn':
        chat_id = query.message.chat_id
        await query.message.delete()

        # Update JSON to set day_started = false
        json_path = get_json_path()
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data = json.load(f)

            # Get start time for report (default to yesterday at 7 AM if not found)
            start_time = data.get('day_start_time')
            if not start_time:
                yesterday_7am = (datetime.now() - timedelta(days=1)).replace(hour=7, minute=0, second=0, microsecond=0)
                start_time = yesterday_7am.isoformat()

            end_time = datetime.now().isoformat()

            data['day_started'] = False
            data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(json_path, 'w') as f:
                json.dump(data, f, indent=2)

            # Generate today's report using actual work period
            message = generate_today_report(start_time, end_time)
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')

    # Handle Get Tasks button
    elif query.data == 'get_tasks_btn':
        # Edit message to show loading
        await query.message.edit_text("Getting tasks...")

        # Step 1: Fetch tasks from Trello
        tasks_data = fetch_tasks_from_trello()

        # Step 2: Save to JSON
        save_tasks_to_json(tasks_data)

        # Step 3: Read from JSON
        tasks_data = get_my_tasks()

        # Step 4: Create task buttons
        reply_markup, top_tasks = create_task_buttons(tasks_data)

        if reply_markup:
            # Store tasks in context for later use
            context.user_data['current_tasks'] = top_tasks

            await query.message.edit_text(
                "Here are your top tasks:",
                reply_markup=reply_markup
            )
        else:
            await query.message.edit_text("No tasks found.")

    # Handle Start Week button
    elif query.data == 'start_week_btn':
        await query.message.delete()

        # Update JSON to set week_started = true and record start time
        json_path = get_json_path()
        start_time = datetime.now().isoformat()

        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data = json.load(f)
            data['week_started'] = True
            data['week_start_time'] = start_time
            data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            data = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "day_started": False,
                "week_started": True,
                "week_start_time": start_time,
                "todo": [],
                "doing": [],
                "done": []
            }

        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)

    # Handle End Week button
    elif query.data == 'end_week_btn':
        chat_id = query.message.chat_id
        await query.message.delete()

        # Update JSON to set week_started = false
        json_path = get_json_path()
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data = json.load(f)

            # Get start time for report (default to 7 days ago at 7 AM if not found)
            start_time = data.get('week_start_time')
            if not start_time:
                seven_days_ago_7am = (datetime.now() - timedelta(days=7)).replace(hour=7, minute=0, second=0, microsecond=0)
                start_time = seven_days_ago_7am.isoformat()

            end_time = datetime.now().isoformat()

            data['week_started'] = False
            data['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            with open(json_path, 'w') as f:
                json.dump(data, f, indent=2)

            # Generate week report using actual work period
            message = generate_previous_week_report(start_time, end_time)
            await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')

    # Handle task button clicks
    elif query.data.startswith('task_'):
        task_index = int(query.data.split('_')[1])
        tasks_info = context.user_data.get('current_tasks', [])

        if task_index < len(tasks_info):
            list_type = tasks_info[task_index]['list_type']
            task = tasks_info[task_index]['task']
            task_id = task['id']
            task_name = task['name']
            task_description = task.get('description', 'No description')
            short_url = task.get('shortUrl', '')

            params = {'key': API_KEY, 'token': TOKEN}

            if list_type == 'TODO':
                # Move TODO task to DOING
                add_url = f"https://api.trello.com/1/cards/{task_id}/idMembers"
                add_params = {'key': API_KEY, 'token': TOKEN, 'value': MY_MEMBER_ID}
                requests.post(add_url, params=add_params)

                # Move to DOING list
                move_url = f"https://api.trello.com/1/cards/{task_id}"
                move_params = {'key': API_KEY, 'token': TOKEN, 'idList': DOING_LIST_ID}
                move_response = requests.put(move_url, params=move_params)

                if move_response.status_code == 200:
                    message = f'Doing Task "{task_name}"\n\n{task_description}\n\n<a href="{short_url}">🔗 open this task in trello</a>'
                    chat_id = query.message.chat_id
                    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
                else:
                    chat_id = query.message.chat_id
                    await context.bot.send_message(chat_id=chat_id, text=f"❌ Error moving task: {task_name}")

            else:  # DOING
                # Move DOING task to DONE
                # Set due date to today and mark as complete
                today = datetime.now().isoformat()
                complete_url = f"https://api.trello.com/1/cards/{task_id}"
                complete_params = {'key': API_KEY, 'token': TOKEN, 'due': today, 'dueComplete': 'true'}
                requests.put(complete_url, params=complete_params)

                # Move to DONE list
                move_url = f"https://api.trello.com/1/cards/{task_id}"
                move_params = {'key': API_KEY, 'token': TOKEN, 'idList': DONE_LIST_ID}
                move_response = requests.put(move_url, params=move_params)

                if move_response.status_code == 200:
                    message = f'✅ task completed "{task_name}"\n<a href="{short_url}">🔗 open this task in trello</a>'
                    chat_id = query.message.chat_id
                    await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
                else:
                    chat_id = query.message.chat_id
                    await context.bot.send_message(chat_id=chat_id, text=f"❌ Error moving task: {task_name}")

    # Handle cancel tasks button
    elif query.data == 'cancel_tasks':
        await query.message.delete()

    # Handle cancel reports button
    elif query.data == 'cancel_reports':
        await query.message.delete()

    # Handle Get Tasks List button (from /trello)
    elif query.data == 'get_tasks_list_btn':
        await query.message.edit_text("Getting tasks...")

        # Fetch tasks from Trello
        tasks_data = fetch_tasks_from_trello()
        save_tasks_to_json(tasks_data)

        # Get tasks by list and priority
        doing_tasks = tasks_data.get('doing', [])
        todo_tasks = tasks_data.get('todo', [])

        # Separate TODO tasks by priority
        high_priority = []
        medium_priority = []
        low_priority = []
        no_priority = []

        for task in todo_tasks:
            labels = task.get('labels', [])
            priority_found = False
            for label in labels:
                label_name = label.get('name', '').lower()
                if 'high priority' in label_name:
                    high_priority.append(task)
                    priority_found = True
                    break
                elif 'medium priority' in label_name:
                    medium_priority.append(task)
                    priority_found = True
                    break
                elif 'low priority' in label_name:
                    low_priority.append(task)
                    priority_found = True
                    break
            if not priority_found:
                no_priority.append(task)

        # Combine in order: DOING → High → Medium → Low → No Priority
        ordered_tasks = []

        # Add DOING tasks
        for task in doing_tasks:
            ordered_tasks.append(('DOING', task))

        # Add High Priority
        for task in high_priority:
            ordered_tasks.append(('TODO', task))

        # Add Medium Priority
        for task in medium_priority:
            ordered_tasks.append(('TODO', task))

        # Add Low Priority
        for task in low_priority:
            ordered_tasks.append(('TODO', task))

        # Add No Priority
        for task in no_priority:
            ordered_tasks.append(('TODO', task))

        # Take first 10
        ordered_tasks = ordered_tasks[:10]

        if ordered_tasks:
            message = "<b>📋 Your Tasks:</b>\n\n"
            for i, (list_type, task) in enumerate(ordered_tasks, 1):
                # Get priority emoji
                priority_emoji = ""
                labels = task.get('labels', [])
                for label in labels:
                    label_name = label.get('name', '').lower()
                    if 'high priority' in label_name:
                        priority_emoji = "🔴 "
                        break
                    elif 'medium priority' in label_name:
                        priority_emoji = "🟡 "
                        break
                    elif 'low priority' in label_name:
                        priority_emoji = "🔵 "
                        break

                task_name = task['name']
                short_url = task.get('shortUrl', '')
                message += f"{i}. {priority_emoji}{list_type}: <a href=\"{short_url}\">{task_name}</a>\n"
        else:
            message = "No tasks found."

        chat_id = query.message.chat_id
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
        await query.message.delete()

    # Handle Previous Day Report button
    elif query.data == 'prev_day_report_btn':
        await query.message.edit_text("Generating previous day report...")

        message = generate_previous_day_report()
        chat_id = query.message.chat_id
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
        await query.message.delete()

    # Handle Today Report button
    elif query.data == 'today_report_btn':
        await query.message.edit_text("Generating today's report...")

        message = generate_today_report()
        chat_id = query.message.chat_id
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
        await query.message.delete()

    # Handle Previous Week Report button
    elif query.data == 'prev_week_report_btn':
        await query.message.edit_text("Generating previous week report...")

        message = generate_previous_week_report()
        chat_id = query.message.chat_id
        await context.bot.send_message(chat_id=chat_id, text=message, parse_mode='HTML')
        await query.message.delete()

    # Handle Show Cached Tasks button
    elif query.data == 'show_cached_tasks_btn':
        # Read from JSON (no API call)
        tasks_data = get_my_tasks()

        if not tasks_data:
            await query.message.edit_text("No cached tasks found. Use 'Get Tasks' first.")
            return

        # Create task buttons
        reply_markup, top_tasks = create_task_buttons(tasks_data)

        if reply_markup:
            # Store tasks in context for later use
            context.user_data['current_tasks'] = top_tasks

            await query.message.edit_text(
                "Here are your top tasks:",
                reply_markup=reply_markup
            )
        else:
            await query.message.edit_text("No tasks found.")



def main():
    """Start the bot"""
    # Create application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("trello", trello))
    app.add_handler(CommandHandler("task_high", task_high))
    app.add_handler(CommandHandler("task_med", task_med))
    app.add_handler(CommandHandler("task_low", task_low))
    app.add_handler(CommandHandler("task", task))

    # Add button callback handler
    app.add_handler(CallbackQueryHandler(button_handler))

    # Add keyboard message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyboard_handler))

    # Start polling
    logger.info("Bot started! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
