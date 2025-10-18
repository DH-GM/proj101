"""
Data models for the social.vim application.
These models define the structure of data used throughout the app.
"""
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class User:
    """Represents a user in the system."""
    username: str
    display_name: str
    bio: str
    followers: int
    following: int
    posts_count: int
    avatar_ascii: str = ""


@dataclass
class Post:
    """Represents a social media post."""
    id: str
    author: str
    content: str
    timestamp: datetime
    likes: int
    reposts: int
    comments: int
    liked_by_user: bool = False
    reposted_by_user: bool = False


@dataclass
class Message:
    """Represents a chat message."""
    id: str
    sender: str
    content: str
    timestamp: datetime
    is_read: bool = False


@dataclass
class Conversation:
    """Represents a conversation thread."""
    id: str
    username: str
    last_message: str
    timestamp: datetime
    unread: bool = False
    messages: List[Message] = None


@dataclass
class Notification:
    """Represents a notification."""
    id: str
    type: str  # 'mention', 'like', 'repost', 'follow', 'comment'
    actor: str
    content: str
    timestamp: datetime
    read: bool = False
    related_post: Optional[str] = None


@dataclass
class UserSettings:
    """Represents user settings."""
    username: str
    display_name: str
    bio: str
    email_notifications: bool
    show_online_status: bool
    private_account: bool
    github_connected: bool = False
    gitlab_connected: bool = False
    google_connected: bool = False
    discord_connected: bool = False

