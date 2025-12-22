# Configuration file loader
# Loads API keys and tokens from config.json
# DO NOT commit config.json to git!

import json
import os
import sys

# Get the directory where the executable/script is located
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    _config_dir = os.path.dirname(sys.executable)
else:
    # Running as script
    _config_dir = os.path.dirname(os.path.abspath(__file__))

_config_file = os.path.join(_config_dir, "config.json")

# Load configuration from JSON file
with open(_config_file, "r") as f:
    _config = json.load(f)

# Trello API credentials
TRELLO_API_KEY = _config["trello"]["api_key"]
TRELLO_TOKEN = _config["trello"]["token"]
TRELLO_TODO_LIST_ID = _config["trello"]["todo_list_id"]
TRELLO_DOING_LIST_ID = _config["trello"]["doing_list_id"]
TRELLO_UNDER_REVIEW_LIST_ID = _config["trello"]["under_review_list_id"]
TRELLO_DONE_LIST_ID = _config["trello"]["done_list_id"]
TRELLO_MY_MEMBER_ID = _config["trello"]["my_member_id"]

# Telegram Bot credentials
TELEGRAM_BOT_TOKEN = _config["telegram"]["bot_token"]
TELEGRAM_PERSONAL_CHAT_ID = _config["telegram"]["personal_chat_id"]
TELEGRAM_GROUP_CHAT_ID = _config["telegram"]["group_chat_id"]

# Gemini API credentials
GEMINI_API_KEY = _config["gemini"]["api_key"]