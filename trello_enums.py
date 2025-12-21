from enum import Enum


class Priority(Enum):
    """Priority levels for Trello cards"""
    HIGH = "High Priority"
    MEDIUM = "Medium Priority"
    LOW = "Low Priority"
    NONE = "No Priority"


class Status(Enum):
    """Task status categories"""
    TODO = "todo"
    DOING = "doing"
    DONE = "done"
    REVIEW = "review"
