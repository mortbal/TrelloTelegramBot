import requests
import json
import os
import sys
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, List
from dateutil import parser as date_parser
from config import (
    TRELLO_API_KEY, TRELLO_TOKEN, TRELLO_TODO_LIST_ID, TRELLO_DOING_LIST_ID,
    TRELLO_UNDER_REVIEW_LIST_ID, TRELLO_DONE_LIST_ID, TRELLO_MY_MEMBER_ID
)

from trello_enums import Priority, Status

@dataclass
class TrelloCard:
    """Structured representation of a Trello card with UTC datetime handling"""
    id: str
    name: str
    shortUrl: str
    labels: Optional[str] = None  # Priority label text (e.g., "High Priority")
    description: Optional[str] = None
    comments: Optional[List[str]] = None
    dueDate: Optional[datetime] = None  # UTC timezone-aware datetime
    dueComplete: Optional[datetime] = None  # UTC timezone-aware datetime when task was completed
    idMembers: Optional[List[str]] = None  # Member IDs for filtering

# Global json path
json_path = ""




def get_json_path() -> bool:
    """Get the path to TrelloTasks.json and check if it exists"""
    global json_path
    if json_path == "":
        # Get the directory where the executable/script is located
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            script_dir = os.path.dirname(sys.executable)
        else:
            # Running as script
            script_dir = os.path.dirname(__file__)
        json_path = os.path.join(script_dir, "TrelloTasks.json")
    return os.path.exists(json_path)

def fetch_tasks_from_json(n: int, status: Status) -> List[dict]:
    """Read JSON file and return n task cards from specified status

    Args:
        n: Number of tasks to return
        status: Status enum (TODO, DOING, DONE, REVIEW)

    Returns:
        List of task cards (returns as many as available if fewer than n exist)
    """
    if not get_json_path():
        print("JSON file not found")
        return []

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)

        # Get tasks for the specified status
        status_key = status.value
        tasks = data.get(status_key, [])

        # Return up to n tasks
        return tasks[:n]

    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return []

def get_card_details(card_id: str) -> Optional[TrelloCard]:
    """Fetch full details for a single card and return as TrelloCard object"""
    url = f"https://api.trello.com/1/cards/{card_id}"
    params = {
        'key': TRELLO_API_KEY,
        'token': TRELLO_TOKEN,
        'actions': 'commentCard',
        'fields': 'id,name,desc,shortUrl,labels,due,dueComplete,idMembers'
    }

    response = requests.get(url, params=params)

    if response.status_code != 200:
        print(f"Error fetching card {card_id}: {response.status_code}")
        return None

    card = response.json()

    # Extract comments as array of strings
    comments = []
    for action in card.get('actions', []):
        comment_text = action.get('data', {}).get('text', '')
        if comment_text:
            comments.append(comment_text)

    # Extract only the first priority label text
    priority_label_text = None
    if card.get('labels'):
        for label in card['labels']:
            label_name = label.get('name', '')
            if 'Priority' in label_name:
                priority_label_text = label_name
                break

    # Handle due date - convert to UTC if present
    due_date = None
    if card.get('due'):
        try:
            parsed_date = date_parser.isoparse(card['due'])
            if parsed_date.tzinfo is None:
                due_date = parsed_date.replace(tzinfo=timezone.utc)
            else:
                due_date = parsed_date.astimezone(timezone.utc)
        except Exception as e:
            print(f"Warning: Could not parse due date for card {card_id}: {e}")

    # Handle dueComplete date - convert to UTC if present
    due_complete_date = None
    if card.get('due') and card.get('dueComplete'):
        try:
            parsed_date = date_parser.isoparse(card['due'])
            if parsed_date.tzinfo is None:
                due_complete_date = parsed_date.replace(tzinfo=timezone.utc)
            else:
                due_complete_date = parsed_date.astimezone(timezone.utc)
        except Exception as e:
            print(f"Warning: Could not parse dueComplete date for card {card_id}: {e}")

    # Create and return TrelloCard object
    return TrelloCard(
        id=card.get('id'),
        name=card.get('name'),
        shortUrl=card.get('shortUrl'),
        labels=priority_label_text,
        description=card.get('desc'),
        comments=comments if comments else None,
        dueDate=due_date,
        dueComplete=due_complete_date,
        idMembers=card.get('idMembers', [])
    )

def transform_trello_card(raw_card: dict) -> dict:
    """Transform raw Trello API card response to match TrelloCard structure

    Args:
        raw_card: Raw card dict from Trello API

    Returns:
        Transformed card dict with correct field names and simplified labels
    """
    # Extract only the first priority label text
    priority_label_text = None
    if raw_card.get('labels'):
        for label in raw_card['labels']:
            label_name = label.get('name', '')
            # Check if this is a priority label
            if 'Priority' in label_name:
                priority_label_text = label_name
                break  # Only keep the first priority label

    # Parse dueComplete date - convert to UTC timezone-aware datetime
    due_complete_date = None
    if raw_card.get('due') and raw_card.get('dueComplete'):
        try:
            parsed_date = date_parser.isoparse(raw_card['due'])
            if parsed_date.tzinfo is None:
                due_complete_date = parsed_date.replace(tzinfo=timezone.utc)
            else:
                due_complete_date = parsed_date.astimezone(timezone.utc)
        except Exception:
            pass  # Silently ignore parse errors

    # Transform field names to match TrelloCard dataclass
    transformed = {
        'id': raw_card.get('id'),
        'name': raw_card.get('name'),
        'shortUrl': raw_card.get('shortUrl'),
        'labels': priority_label_text,
        'description': raw_card.get('desc'),  # desc -> description
        'dueDate': raw_card.get('due'),  # due -> dueDate
        'dueComplete': due_complete_date,  # Parsed UTC datetime
        'idMembers': raw_card.get('idMembers', [])  # Keep member IDs for filtering
    }

    return transformed

def fetch_tasks_from_trello_api(status: Status) -> List[dict]:
    """Fetch Trello tasks from API and save to JSON

    Args:
        status: Status enum (TODO, DOING, DONE, REVIEW)
        filter_by_member: If True, only return cards where user is a member

    Returns:
        List of task cards
    """
    # Map status to list ID
    list_id_map = {
        Status.TODO: TRELLO_TODO_LIST_ID,
        Status.DOING: TRELLO_DOING_LIST_ID,
        Status.DONE: TRELLO_DONE_LIST_ID,
        Status.REVIEW: TRELLO_UNDER_REVIEW_LIST_ID
    }
    if status==Status.TODO :
        filter_by_member= False
    else :
        filter_by_member=True
    list_id = list_id_map[status]

    # Fetch from API
    url = f"https://api.trello.com/1/lists/{list_id}/cards"
    params = {
        'key': TRELLO_API_KEY,
        'token': TRELLO_TOKEN,
        'fields': 'id,name,shortUrl,labels,desc,due,dueComplete,idMembers'
    }
    response = requests.get(url, params=params)

    if response.status_code == 200:
        raw_cards = response.json()

        # Filter by member if needed
        if filter_by_member:
            filtered_cards = []
            for card in raw_cards:
                if TRELLO_MY_MEMBER_ID in card.get('idMembers', []):
                    filtered_cards.append(card)
            raw_cards = filtered_cards

        # Transform cards
        transformed_cards = []
        for card in raw_cards:
            transformed = transform_trello_card(card)
            transformed_cards.append(transformed)

        # Save to JSON
        file_exists = get_json_path()
        if file_exists:
            with open(json_path, 'r') as f:
                data = json.load(f)
        else:
            data = {}

        data[status.value] = transformed_cards

        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)

        return transformed_cards
    return []

def fetch_all_trello_tasks():
    fetch_tasks_from_trello_api(Status)
    fetch_tasks_from_trello_api(Status)
    fetch_tasks_from_trello_api(Status)
    fetch_tasks_from_trello_api(Status)

def create_task(title: str, priority: Optional[Priority] = None, description: str = ""):
    """Create a new task in Trello TODO list

    Args:
        title: Task title
        priority: Priority enum (HIGH, MEDIUM, LOW, or None)
        description: Task description
    """
    params = {
        'key': TRELLO_API_KEY,
        'token': TRELLO_TOKEN,
        'idList': TRELLO_TODO_LIST_ID,
        'name': title,
        'desc': description,
        'idMembers': [TRELLO_MY_MEMBER_ID]
    }

    # Create the card
    url = "https://api.trello.com/1/cards"
    response = requests.post(url, params=params)

    if response.status_code == 200:
        card_data = response.json()
        card_id = card_data['id']

        # Add label if priority provided
        if priority:
            label_name = priority.value
            board_id = card_data['idBoard']
            labels_url = f"https://api.trello.com/1/boards/{board_id}/labels"
            labels_params = {'key': TRELLO_API_KEY, 'token': TRELLO_TOKEN}
            labels_response = requests.get(labels_url, params=labels_params)

            if labels_response.status_code == 200:
                labels = labels_response.json()
                for label in labels:
                    if label.get('name') == label_name:
                        label_id = label.get('id')
                        # Add label to card
                        label_url = f"https://api.trello.com/1/cards/{card_id}/idLabels"
                        label_params = {'key': TRELLO_API_KEY, 'token': TRELLO_TOKEN, 'value': label_id}
                        requests.post(label_url, params=label_params)
                        break

        # Fetch and update tasks
        fetch_all_trello_tasks()

        return card_data
    return None

def update_task(task_id, target_status: Status, new_comment="", due_date: str = None):
    """Move a task to target status and optionally add a comment

    Args:
        task_id: ID of the task to update
        target_status: Target status (TODO, DOING, DONE, REVIEW)
        new_comment: Optional comment to add
        due_date: Optional due date (ISO format string) to set when moving to DONE/REVIEW
    """
    params = {'key': TRELLO_API_KEY, 'token': TRELLO_TOKEN}

    # Map status to list ID
    list_id_map = {
        Status.TODO: TRELLO_TODO_LIST_ID,
        Status.DOING: TRELLO_DOING_LIST_ID,
        Status.DONE: TRELLO_DONE_LIST_ID,
        Status.REVIEW: TRELLO_UNDER_REVIEW_LIST_ID
    }

    target_list_id = list_id_map.get(target_status)
    if not target_list_id:
        return False

    if target_status in [Status.TODO, Status.DOING]:
        # Move to TODO or DOING: just move and unmark as complete
        update_params = {
            'key': TRELLO_API_KEY,
            'token': TRELLO_TOKEN,
            'idList': target_list_id,
            'dueComplete': 'false'
        }
        url = f"https://api.trello.com/1/cards/{task_id}"
        response = requests.put(url, params=update_params)
        success = response.status_code == 200

    elif target_status in [Status.REVIEW, Status.DONE]:
        # Get current card to find labels
        card_url = f"https://api.trello.com/1/cards/{task_id}"
        card_response = requests.get(card_url, params=params)

        if card_response.status_code == 200:
            card_data = card_response.json()
            label_ids = [label['id'] for label in card_data.get('labels', [])]

            # Remove all labels
            for label_id in label_ids:
                delete_label_url = f"https://api.trello.com/1/cards/{task_id}/idLabels/{label_id}"
                requests.delete(delete_label_url, params=params)

            # Move to REVIEW/DONE, set due date (use provided or today), mark as complete
            due_date_value = due_date if due_date else datetime.now().isoformat()
            update_params = {
                'key': TRELLO_API_KEY,
                'token': TRELLO_TOKEN,
                'idList': target_list_id,
                'due': due_date_value,
                'dueComplete': 'true'
            }
            url = f"https://api.trello.com/1/cards/{task_id}"
            response = requests.put(url, params=update_params)
            success = response.status_code == 200
        else:
            success = False
    else:
        success = False

    # Add user as member if successful
    if success:
        # Get current card to check members
        card_url = f"https://api.trello.com/1/cards/{task_id}"
        card_params = {'key': TRELLO_API_KEY, 'token': TRELLO_TOKEN, 'fields': 'idMembers'}
        card_response = requests.get(card_url, params=card_params)

        if card_response.status_code == 200:
            card_data = card_response.json()
            current_members = card_data.get('idMembers', [])

            # Add user as member if not already added
            if TRELLO_MY_MEMBER_ID not in current_members:
                add_member_url = f"https://api.trello.com/1/cards/{task_id}/idMembers"
                add_member_params = {'key': TRELLO_API_KEY, 'token': TRELLO_TOKEN, 'value': TRELLO_MY_MEMBER_ID}
                requests.post(add_member_url, params=add_member_params)

    # Add comment if provided
    if success and new_comment:
        comment_url = f"https://api.trello.com/1/cards/{task_id}/actions/comments"
        comment_params = {'key': TRELLO_API_KEY, 'token': TRELLO_TOKEN, 'text': new_comment}
        requests.post(comment_url, params=comment_params)

    # Fetch and update tasks
    if success:
        fetch_all_trello_tasks()

    return success

def get_report(status: Status, start_date: datetime, end_date: datetime) -> List[dict]:
    """Get tasks completed within a date range for a specific status

    Args:
        status: Status enum (TODO, DOING, DONE, REVIEW)
        start_date: Start of date range (timezone-aware datetime)
        end_date: End of date range (timezone-aware datetime)

    Returns:
        List of cards with dueComplete date within the specified range
    """
    # Ensure dates are timezone-aware (convert to UTC if needed)
    if start_date.tzinfo is None:
        start_date = start_date.replace(tzinfo=timezone.utc)
    else:
        start_date = start_date.astimezone(timezone.utc)

    if end_date.tzinfo is None:
        end_date = end_date.replace(tzinfo=timezone.utc)
    else:
        end_date = end_date.astimezone(timezone.utc)

    # Map status to list ID
    list_id_map = {
        Status.TODO: TRELLO_TODO_LIST_ID,
        Status.DOING: TRELLO_DOING_LIST_ID,
        Status.DONE: TRELLO_DONE_LIST_ID,
        Status.REVIEW: TRELLO_UNDER_REVIEW_LIST_ID
    }

    list_id = list_id_map.get(status)
    if not list_id:
        return []

    # Fetch from API
    url = f"https://api.trello.com/1/lists/{list_id}/cards"
    params = {
        'key': TRELLO_API_KEY,
        'token': TRELLO_TOKEN,
        'fields': 'id,name,shortUrl,labels,desc,due,dueComplete,idMembers'
    }
    response = requests.get(url, params=params)

    if response.status_code != 200:
        return []

    raw_cards = response.json()

    # Transform and filter cards by dueComplete date range
    filtered_cards = []
    for card in raw_cards:
        transformed = transform_trello_card(card)

        # Check if dueComplete is within range
        if transformed.get('dueComplete'):
            due_complete = transformed['dueComplete']
            if start_date <= due_complete <= end_date:
                filtered_cards.append(transformed)

    return filtered_cards
