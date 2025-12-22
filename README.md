# Trello Telegram Bot

A personal Trello task management bot for Telegram. This bot is designed for single-user use and helps you manage your Trello tasks directly from Telegram with interactive buttons and automated reporting.

**Note:** Due to security concerns, this bot is designed to work for a single person only. You can run this bot on your server or PC. When running from a PC, the bot only responds to Telegram messages when your PC is online and the script/executable is running.

## Quick Start (Using Packaged Build)

If you have the pre-built executable (`TrelloTelegramBot.exe`), you can run the bot without installing Python:

1. **Download the executable** or build it yourself (see "Building Executable" section below)
2. **modify configuration file** - modify the `config.json` file in the same directory as the exe (see "Configuration" section)
3. **Optional: Create task cache** - Place `TrelloTasks.json` in the same directory (will be auto-generated if missing)
4. **Run the bot** - Double-click `TrelloTelegramBot.exe` or run it from terminal:
   ```bash
   TrelloTelegramBot.exe
   ```
5. The bot will start and show "Bot started! Press Ctrl+C to stop."

**Important:** Keep `config.json` and `TrelloTasks.json` in the same folder as the executable!

## What can this bot do?

- **Day/Week Tracking**: Start and end your workday/week with timezone-aware tracking
- **Task Management**: View, start, and complete Trello tasks with one tap
- **Priority System**: Create and manage tasks with high, medium, and low priority levels (🔴 🟡 🔵)
- **Smart Task Flow**: TODO → DOING → DONE workflow with automatic member assignment
- **Automated Reports**: Generate daily and weekly completion reports
- **Quick Task Creation**: Create tasks via commands (`/task`, `/task_high`, `/task_med`, `/task_low`)
- **Reply-to-Create**: Create tasks by replying to messages (message becomes task description)
- **Cached Tasks**: Fast task access without API calls using local JSON cache
- **Message Deletion**: Delete bot messages with `/delete` command

## Setup (this section is for running python - not needed if running exe)

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

2. **List IDs** (TODO, DOING, UNDER_REVIEW, DONE):
   - Open your Trello board
   - Add `.json` to the end of the board URL (e.g., `https://trello.com/b/aBcDeFgH/my-board.json`)
   - Search for your list names and copy their `id` values
   - You need IDs for: TODO, DOING, UNDER_REVIEW (optional), and DONE lists

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

Create a `config.json` file (or modify the provided the sample) in the project directory with your credentials:

```json
{
  "trello": {
    "api_key": "your_trello_api_key_here",
    "token": "your_trello_token_here",
    "todo_list_id": "your_todo_list_id",
    "doing_list_id": "your_doing_list_id",
    "under_review_list_id": "your_under_review_list_id",
    "done_list_id": "your_done_list_id",
    "my_member_id": "your_trello_member_id"
  },
  "telegram": {
    "bot_token": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
    "personal_chat_id": "123456789",
    "group_chat_id": -1001234567890
  },
  "gemini": {
    "api_key": "your_gemini_api_key_or_leave_empty"
  }
}
```

Replace all placeholder values with your actual credentials.

**Note:** `config.json` is automatically ignored by git to protect your credentials.

## Running the Bot

```bash
python trello_telegram_bot.py
```

The bot will start and log "Bot started! Press Ctrl+C to stop."

## Usage

### Commands

- `/start` - Welcome message with bot introduction
- `/trello` - Quick access to reports and task management (works in both private and group chats)
- `/task [title]` - Create a medium priority task
- `/task_high [title]` - Create a high priority task
- `/task_med [title]` - Create a medium priority task
- `/task_low [title]` - Create a low priority task
- `/delete` - Reply to a bot message with this command to delete it

**Tip:** Reply to any message with a task command to use that message as the task description!

### Typical Workflow

1. **Start Your Day**: `/trello` → Click "Start Day"
2. **View Tasks**: `/trello` → Click "Get Tasks" → Select status (TODO, DOING, REVIEW, DONE)
3. **Start Working**: Click on a TODO task → It moves to DOING and shows description
4. **Complete Task**: Click on a DOING task → Choose REVIEW or DONE
5. **End Your Day**: `/trello` → Click "End Day" → Automatic report generated
6. **Weekly Reports**: Start/End Week buttons work the same way
7. **Delete Messages**: Reply to any bot message with `/delete` to remove it

## Features

### Timezone-Aware Tracking
The bot records actual start/end times for your workday/week, so reports are accurate regardless of server timezone differences.

### Priority-Based Task Display
Tasks are displayed with color-coded priority indicators for this to work you will need labels with names `High Priority` , `Medium Priority` or `Low Priority` in your trello board and at least one should be assigned to your card. if no label on card exists it will be treated as medium priority :
- 🔴 High Priority
- 🟡 Medium Priority
- 🔵 Low Priority

### Automatic Reports
When you end your day or week, the bot automatically generates a report of all completed tasks during that period.

## Building Executable

To build the executable yourself using PyInstaller:

1. **Install PyInstaller**:
   ```bash
   pip install pyinstaller
   ```

2. **Build the executable**:
   ```bash
   pyinstaller --onefile --name TrelloTelegramBot trello_telegram_bot.py
   ```

3. **Locate the executable**:
   - The exe will be created in the `dist` folder
   - Copy `TrelloTelegramBot.exe` to your desired location
   - Make sure `config.json` is in the same directory as the exe

## File Structure

```
TrelloTelegramBot/
├── trello_telegram_bot.py  # Main bot script
├── task_functions.py       # Trello task management functions
├── trello_enums.py         # Priority and Status enumerations
├── config.py               # Configuration loader (reads config.json)
├── config.json             # Your credentials (not in git)
├── TrelloTasks.json        # Local task cache (auto-generated)
├── mini_app.html           # Web interface (if applicable)
└── README.md               # This file
```

## Security Notes

- **Never commit `config.json`** to version control (it's automatically ignored by .gitignore)
- Keep your bot token and API credentials secure
- The bot is designed for single-user use only
- Only messages from configured chat IDs will be processed
- When sharing the executable, never include `config.json` with your credentials

## License

Personal use project - modify as needed for your workflow!
