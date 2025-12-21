# Trello Telegram Bot

A personal Trello task management bot for Telegram. This bot is designed for single-user use and helps you manage your Trello tasks directly from Telegram with interactive buttons and automated reporting.

**Note:** Due to security concerns, this bot is designed to work for a single person only. You can run this bot on your server or PC. When running from a PC, the bot only responds to Telegram messages when your PC is online and the script is running.

## What can this bot do?

- **Day/Week Tracking**: Start and end your workday/week with timezone-aware tracking
- **Task Management**: View, start, and complete Trello tasks with one tap
- **Priority System**: Create and manage tasks with high, medium, and low priority levels (🔴 🟡 🔵)
- **Smart Task Flow**: TODO → DOING → DONE workflow with automatic member assignment
- **Automated Reports**: Generate daily and weekly completion reports
- **Quick Task Creation**: Create tasks via commands (`/task`, `/task_high`, `/task_med`, `/task_low`)
- **Reply-to-Create**: Create tasks by replying to messages (message becomes task description)
- **Cached Tasks**: Fast task access without API calls using local JSON cache

## Setup

### 1. Install Python

Make sure you have Python 3.7 or higher installed on your system.

### 2. Install Dependencies

Install the required Python packages by running this in console/terminal:

```bash
pip install python-telegram-bot requests google-genai python-dateutil
```

### 3. Create a Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the instructions
3. Choose a name and username for your bot
4. Copy the **bot token** that BotFather provides (you'll need this for `TELEGRAM_BOT_TOKEN`)

### 4. Get Your Trello Credentials

1. **API Key & Token**:
   - Go to [https://trello.com/power-ups/admin](https://trello.com/power-ups/admin)
   - Get your API Key
   - Click on "Token" to generate your token

2. **List IDs** (TODO, DOING, DONE):
   - Open your Trello board
   - Add `.json` to the end of the board URL (e.g., `https://trello.com/b/aBcDeFgH/my-board.json`)
   - Search for your list names and copy their `id` values

3. **Member ID**:
   - In the same JSON from step 2, find the `members` array
   - Copy your `id` from your member object

### 5. Get Telegram Group/Chat ID

**Method 1: Using Bot API**
1. Send any message to your bot or add it to a group and send a message
2. Open this URL in your browser (replace `YOUR_BOT_TOKEN`):
   ```
   https://api.telegram.org/botYOUR_BOT_TOKEN/getUpdates
   ```
3. Look for `"chat":{"id":` in the response
   - For private chats: positive number (e.g., `123456789`)
   - For groups: negative number (e.g., `-1001234567890`)

**Method 2: Using Existing Bots**
- Message [@userinfobot](https://t.me/userinfobot) or [@get_id_bot](https://t.me/get_id_bot)
- They will tell you your user ID

## Configuration

Create a `config.py` file in the project directory with your credentials:

```python
# Trello API credentials
API_KEY = "your_trello_api_key_here"
TOKEN = "your_trello_token_here"
TODO_LIST_ID = "your_todo_list_id"
DOING_LIST_ID = "your_doing_list_id"
DONE_LIST_ID = "your_done_list_id"
MY_MEMBER_ID = "your_trello_member_id"

# Telegram Bot credentials
TELEGRAM_BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
PERSONAL_CHAT_ID = 123456789  # Your personal chat ID
CHAT_IDS = [123456789]  # List of allowed chat IDs

# Allowed group ID (use negative number for groups)
ALLOWED_GROUP_ID = -1001234567890

#Gememini API key : Leave this empty if you dont want to use ai to summarize tasks 
GEMINI_API_KEY = ""
```

Replace all placeholder values with your actual credentials.

## Running the Bot

```bash
python trello_telegram_bot.py
```

The bot will start and log "Bot started! Press Ctrl+C to stop."

## Usage

### Commands

- `/start` - Welcome message
- `/trello` - Quick access to reports and task list
- `/mytrello` - Main task management menu (start/end day/week, manage tasks)
- `/task [title]` - Create a medium priority task
- `/task_high [title]` - Create a high priority task
- `/task_med [title]` - Create a medium priority task
- `/task_low [title]` - Create a low priority task

**Tip:** Reply to any message with a task command to use that message as the task description!

### Typical Workflow

1. **Start Your Day**: `/mytrello` → Click "Start Day"
2. **View Tasks**: `/mytrello` → Click "Get Tasks"
3. **Start Working**: Click on a TODO task → It moves to DOING and shows description
4. **Complete Task**: Click on a DOING task → It moves to DONE
5. **End Your Day**: `/mytrello` → Click "End Day" → Automatic report generated
6. **Weekly Reports**: Start/End Week buttons work the same way

## Features

### Timezone-Aware Tracking
The bot records actual start/end times for your workday/week, so reports are accurate regardless of server timezone differences.

### Priority-Based Task Display
Tasks are displayed with color-coded priority indicators:
- 🔴 High Priority
- 🟡 Medium Priority
- 🔵 Low Priority

### Automatic Reports
When you end your day or week, the bot automatically generates a report of all completed tasks during that period.

## File Structure

```
TrelloTelegramBot/
├── trello_telegram_bot.py  # Main bot script
├── config.py               # Your credentials (not in git)
├── TrelloTasks.json        # Local task cache (auto-generated)
└── README.md               # This file
```

## Security Notes

- Never commit `config.py` to version control
- Keep your bot token and API credentials secure
- The bot is designed for single-user use only
- Only messages from `ALLOWED_GROUP_ID` will be processed

## License

Personal use project - modify as needed for your workflow!
