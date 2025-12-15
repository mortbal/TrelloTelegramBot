import logging
import requests
import json
import os
from datetime import datetime, timedelta
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


def get_json_path():
    """Get the path to TrelloTasks.json"""
    script_dir = os.path.dirname(__file__)
    return os.path.join(script_dir, "TrelloTasks.json")


def is_day_started():
    """Check if day is started by checking boolean flag in JSON"""
    json_path = get_json_path()
    if not os.path.exists(json_path):
        return False

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            return data.get('day_started', False)
    except:
        return False


def is_week_started():
    """Check if week is started by checking boolean flag in JSON"""
    json_path = get_json_path()
    if not os.path.exists(json_path):
        return False

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            return data.get('week_started', False)
    except:
        return False


def start_day(chat_id=None):
    """Fetch tasks from Trello and save to JSON (equivalent to Start() in old file)"""
    # Send message immediately if chat_id provided
    if chat_id:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': "✅ Morteza has started his workday"
        }
        requests.post(url, data=data)

    tasks_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "day_started": True,
        "todo": [],
        "doing": [],
        "done": []
    }

    params = {'key': API_KEY, 'token': TOKEN}

    # Process TODO list
    url = f"https://api.trello.com/1/lists/{TODO_LIST_ID}/cards"
    response = requests.get(url, params=params)

    if response.status_code == 200:
        cards = response.json()
        for card in cards:
            card_id = card['id']
            member_ids = card.get('idMembers', [])

            if MY_MEMBER_ID not in member_ids:
                # Add me to card
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
                "description": card.get('desc', ''),
                "comments": comments
            })

    # Process DOING list
    url = f"https://api.trello.com/1/lists/{DOING_LIST_ID}/cards"
    response = requests.get(url, params=params)

    if response.status_code == 200:
        cards = response.json()
        for card in cards:
            member_ids = card.get('idMembers', [])
            if MY_MEMBER_ID in member_ids:
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
                    "description": card.get('desc', ''),
                    "comments": comments
                })

    # Process DONE list
    url = f"https://api.trello.com/1/lists/{DONE_LIST_ID}/cards"
    response = requests.get(url, params=params)

    if response.status_code == 200:
        cards = response.json()
        for card in cards:
            member_ids = card.get('idMembers', [])
            if MY_MEMBER_ID in member_ids:
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
                    "description": card.get('desc', ''),
                    "comments": comments
                })

    # Save to file
    json_path = get_json_path()
    with open(json_path, 'w') as f:
        json.dump(tasks_data, f, indent=2)


def get_my_tasks():
    """Get tasks from JSON file"""
    json_path = get_json_path()

    if not os.path.exists(json_path):
        return None

    with open(json_path, 'r') as f:
        return json.load(f)


def fetch_tasks_from_trello():
    """Fetch tasks from Trello and return data"""
    tasks_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "day_started": is_day_started(),
        "week_started": is_week_started(),
        "todo": [],
        "doing": [],
        "done": []
    }

    params = {'key': API_KEY, 'token': TOKEN}

    # Process TODO list
    url = f"https://api.trello.com/1/lists/{TODO_LIST_ID}/cards"
    response = requests.get(url, params=params)

    if response.status_code == 200:
        cards = response.json()
        for card in cards:
            card_id = card['id']
            member_ids = card.get('idMembers', [])

            if MY_MEMBER_ID not in member_ids:
                # Add me to card
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
                "description": card.get('desc', ''),
                "shortUrl": card.get('shortUrl', ''),
                "due": card.get('due', ''),
                "labels": card.get('labels', []),
                "comments": comments
            })

    # Process DOING list - only my tasks
    url = f"https://api.trello.com/1/lists/{DOING_LIST_ID}/cards"
    response = requests.get(url, params=params)

    if response.status_code == 200:
        cards = response.json()
        for card in cards:
            member_ids = card.get('idMembers', [])
            if MY_MEMBER_ID in member_ids:
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
                    "description": card.get('desc', ''),
                    "shortUrl": card.get('shortUrl', ''),
                    "due": card.get('due', ''),
                    "labels": card.get('labels', []),
                    "comments": comments
                })

    # Process DONE list
    url = f"https://api.trello.com/1/lists/{DONE_LIST_ID}/cards"
    response = requests.get(url, params=params)

    if response.status_code == 200:
        cards = response.json()
        for card in cards:
            member_ids = card.get('idMembers', [])
            if MY_MEMBER_ID in member_ids:
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
                    "description": card.get('desc', ''),
                    "shortUrl": card.get('shortUrl', ''),
                    "due": card.get('due', ''),
                    "labels": card.get('labels', []),
                    "comments": comments
                })

    return tasks_data


def save_tasks_to_json(tasks_data):
    """Save tasks data to JSON file"""
    json_path = get_json_path()
    with open(json_path, 'w') as f:
        json.dump(tasks_data, f, indent=2)


def create_task_buttons(tasks_data):
    """Read tasks from JSON and create task buttons"""
    # Get top 10 tasks (DOING first, then TODO)
    doing_tasks = tasks_data.get('doing', []) if tasks_data else []
    todo_tasks = tasks_data.get('todo', []) if tasks_data else []

    # Combine DOING and TODO with list type, take top 10
    all_tasks = []
    for task in doing_tasks:
        all_tasks.append(('DOING', task))
    for task in todo_tasks:
        all_tasks.append(('TODO', task))

    top_tasks_with_type = all_tasks[:10]

    if not top_tasks_with_type:
        return None, None

    # Create buttons for each task
    keyboard = []
    top_tasks_info = []
    for i, (list_type, task) in enumerate(top_tasks_with_type):
        # Get priority indicator
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

        button_text = f"{priority_emoji}{list_type}: {task['name']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'task_{i}')])
        top_tasks_info.append({'list_type': list_type, 'task': task})

    # Add cancel button
    keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data='cancel_tasks')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    return reply_markup, top_tasks_info


def generate_previous_day_report():
    """Generate previous day report"""
    yesterday = (datetime.now() - timedelta(days=1)).date()

    # Fetch DONE tasks from Trello
    params = {'key': API_KEY, 'token': TOKEN}
    url = f"https://api.trello.com/1/lists/{DONE_LIST_ID}/cards"
    response = requests.get(url, params=params)

    tasks = []
    if response.status_code == 200:
        cards = response.json()
        for card in cards:
            if MY_MEMBER_ID in card.get('idMembers', []):
                due_date = card.get('due')
                if due_date:
                    task_date = datetime.fromisoformat(due_date.replace('Z', '+00:00')).date()
                    if task_date == yesterday:
                        tasks.append({
                            'name': card['name'],
                            'shortUrl': card.get('shortUrl', ''),
                            'due': due_date
                        })

    # Format report
    if tasks:
        message = f"📅 <b>Previous Day Report ({yesterday})</b>\n\n"
        for task in tasks:
            message += f"• {task['name']} - <a href=\"{task['shortUrl']}\">🔗 open</a>\n"
    else:
        message = f"No tasks completed on {yesterday}"

    return message


def generate_today_report(start_time=None, end_time=None):
    """Generate today's report - optionally filter by time range"""
    if start_time and end_time:
        # Use provided time range
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
    else:
        # Default: use today
        today = datetime.now().date()
        start_dt = datetime.combine(today, datetime.min.time())
        end_dt = datetime.now()

    # Fetch DONE tasks from Trello
    params = {'key': API_KEY, 'token': TOKEN}
    url = f"https://api.trello.com/1/lists/{DONE_LIST_ID}/cards"
    response = requests.get(url, params=params)

    tasks = []
    if response.status_code == 200:
        cards = response.json()
        for card in cards:
            if MY_MEMBER_ID in card.get('idMembers', []):
                due_date = card.get('due')
                if due_date:
                    task_dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                    if start_dt <= task_dt <= end_dt:
                        tasks.append({
                            'name': card['name'],
                            'shortUrl': card.get('shortUrl', ''),
                            'due': due_date
                        })

    # Format report
    if tasks:
        message = f"📊 <b>Today's Report</b>\n\n"
        for task in tasks:
            message += f"• {task['name']} - <a href=\"{task['shortUrl']}\">🔗 open</a>\n"
    else:
        message = f"No tasks completed"

    return message


def generate_previous_week_report(start_time=None, end_time=None):
    """Generate previous week report - optionally filter by time range"""
    if start_time and end_time:
        # Use provided time range
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
    else:
        # Default: last 7 days
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=7)

    # Fetch DONE tasks from Trello
    params = {'key': API_KEY, 'token': TOKEN}
    url = f"https://api.trello.com/1/lists/{DONE_LIST_ID}/cards"
    response = requests.get(url, params=params)

    tasks = []
    if response.status_code == 200:
        cards = response.json()
        for card in cards:
            if MY_MEMBER_ID in card.get('idMembers', []):
                due_date = card.get('due')
                if due_date:
                    task_dt = datetime.fromisoformat(due_date.replace('Z', '+00:00'))
                    if start_dt <= task_dt <= end_dt:
                        tasks.append({
                            'name': card['name'],
                            'shortUrl': card.get('shortUrl', ''),
                            'due': task_dt
                        })

    # Sort by date
    tasks.sort(key=lambda x: x['due'])

    # Format report
    if tasks:
        message = f"📈 <b>Week Report</b>\n\n"
        for task in tasks:
            task_date = task['due'].strftime('%Y-%m-%d')
            message += f"• {task['name']} ({task_date}) - <a href=\"{task['shortUrl']}\">🔗 open</a>\n"
    else:
        message = f"No tasks completed"

    return message


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    if not update.message:
        return

    if not is_allowed_group(update):
        return

    await update.message.reply_text(
        "Welcome to Trello Bot! 👋\n\n"
        "Use /trello to access Trello management menu."
    )


async def trello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /trello command"""
    if not update.message:
        return

    if not is_allowed_group(update):
        return

    keyboard = [
        [InlineKeyboardButton("📋 Get Tasks", callback_data='get_tasks_list_btn')],
        [InlineKeyboardButton("📅 Previous Day Report", callback_data='prev_day_report_btn')],
        [InlineKeyboardButton("📊 Today Report", callback_data='today_report_btn')],
        [InlineKeyboardButton("📈 Previous Week Report", callback_data='prev_week_report_btn')],
        [InlineKeyboardButton("❌ Cancel", callback_data='cancel_reports')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Select a report:",
        reply_markup=reply_markup
    )


async def mytrello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /mytrello command"""
    if not update.message:
        return

    if not is_allowed_group(update):
        return

    keyboard = []

    # Day button - show Start OR End based on state
    if is_day_started():
        keyboard.append([InlineKeyboardButton("🌙 End Day", callback_data='end_day_btn')])
    else:
        keyboard.append([InlineKeyboardButton("🌅 Start Day", callback_data='start_day_btn')])

    # Week button - show Start OR End based on state
    if is_week_started():
        keyboard.append([InlineKeyboardButton("📊 End Week", callback_data='end_week_btn')])
    else:
        keyboard.append([InlineKeyboardButton("📅 Start Week", callback_data='start_week_btn')])

    # Task buttons - always show
    keyboard.append([InlineKeyboardButton("📋 Get Tasks", callback_data='get_tasks_btn')])
    keyboard.append([InlineKeyboardButton("⚡ Show Cached Tasks", callback_data='show_cached_tasks_btn')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="my trello",
        reply_markup=reply_markup
    )


async def create_task(update: Update, context: ContextTypes.DEFAULT_TYPE, priority: str, label_name: str):
    """Create a new task in Trello with specified priority"""
    if not update.message:
        return

    if not is_allowed_group(update):
        return

    # Get title from command arguments
    title = ' '.join(context.args) if context.args else "new task"

    # Get description from replied-to message
    description = ""
    if update.message.reply_to_message and update.message.reply_to_message.text:
        description = update.message.reply_to_message.text

    # Get all cards in TODO list to find positioning
    params = {'key': API_KEY, 'token': TOKEN}
    url = f"https://api.trello.com/1/lists/{TODO_LIST_ID}/cards"
    response = requests.get(url, params=params)

    position = "bottom"  # Default position
    if response.status_code == 200:
        cards = response.json()
        # Find last card with same priority
        last_card_pos = None
        for card in cards:
            labels = card.get('labels', [])
            for label in labels:
                if label.get('name') == label_name:
                    last_card_pos = card.get('pos')
                    break

        # If found a card with same priority, position after it
        if last_card_pos is not None:
            position = last_card_pos + 1

    # Create the card
    create_url = "https://api.trello.com/1/cards"
    create_params = {
        'key': API_KEY,
        'token': TOKEN,
        'idList': TODO_LIST_ID,
        'name': title,
        'desc': description,
        'pos': position,
        'idMembers': [MY_MEMBER_ID]
    }

    create_response = requests.post(create_url, params=create_params)

    if create_response.status_code == 200:
        card_data = create_response.json()
        card_id = card_data['id']

        # Get the label ID for the priority
        board_url = f"https://api.trello.com/1/boards/{card_data['idBoard']}/labels"
        board_params = {'key': API_KEY, 'token': TOKEN}
        labels_response = requests.get(board_url, params=board_params)

        if labels_response.status_code == 200:
            labels = labels_response.json()
            label_id = None
            for label in labels:
                if label.get('name') == label_name:
                    label_id = label.get('id')
                    break

            # Add label to card
            if label_id:
                label_url = f"https://api.trello.com/1/cards/{card_id}/idLabels"
                label_params = {'key': API_KEY, 'token': TOKEN, 'value': label_id}
                requests.post(label_url, params=label_params)

        short_url = card_data.get('shortUrl', '')
        message = f'✅ Task created: "{title}"\nPriority: {priority}\n<a href="{short_url}">🔗 open</a>'
        await update.message.reply_text(message, parse_mode='HTML')
    else:
        await update.message.reply_text("❌ Error creating task")


async def task_high(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /task-high command"""
    await create_task(update, context, "High Priority", "High Priority")


async def task_med(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /task-med command"""
    await create_task(update, context, "Medium Priority", "Medium Priority")


async def task_low(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /task-low command"""
    await create_task(update, context, "Low Priority", "Low Priority")


async def task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /task command (alias for /task-med)"""
    await create_task(update, context, "Medium Priority", "Medium Priority")


async def show(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /show command"""
    # Check if message exists
    if not update.message:
        return

    # Check if message is from allowed group
    if not is_allowed_group(update):
        return

    await update.message.reply_text(
        "Command received: show"
    )


async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle data sent from the mini app"""
    # Check if message exists
    if not update.message:
        return

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
    if not is_allowed_group(update):
        return

    query = update.callback_query
    await query.answer()  # Acknowledge the button click

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


async def setup_commands(app: Application):
    """Set up bot commands for the menu button"""
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("trello", "Trello bot info"),
        BotCommand("mytrello", "Manage your Trello tasks"),
        BotCommand("task", "Create medium priority task"),
        BotCommand("task_high", "Create high priority task"),
        BotCommand("task_med", "Create medium priority task"),
        BotCommand("task_low", "Create low priority task")
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
    app.add_handler(CommandHandler("trello", trello))
    app.add_handler(CommandHandler("mytrello", mytrello))
    app.add_handler(CommandHandler("task_high", task_high))
    app.add_handler(CommandHandler("task_med", task_med))
    app.add_handler(CommandHandler("task_low", task_low))
    app.add_handler(CommandHandler("task", task))
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
