"""
API Interface Layer for social.vim
This module provides an abstraction layer between the UI and the backend.
Replace the FakeAPI class with a real API client to connect to your backend.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import random

# === lightweight data objects used by the UI ===
from dataclasses import dataclass


@dataclass
class User:
    username: str
    display_name: str
    bio: str
    followers: int
    following: int
    posts_count: int
    avatar_ascii: str = ""


@dataclass
class Post:
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
    id: str
    sender: str
    content: str
    timestamp: datetime
    is_read: bool = False


@dataclass
class Conversation:
    id: str
    username: str
    last_message: str
    timestamp: datetime
    unread: bool = False


@dataclass
class Notification:
    id: str
    type: str  # 'mention', 'like', 'repost', 'follow', 'comment'
    actor: str
    content: str
    timestamp: datetime
    read: bool = False
    related_post: Optional[str] = None


@dataclass
class UserSettings:
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


# === API interface ===
class APIInterface:
    def get_current_user(self) -> User: ...
    def get_timeline(self, limit: int = 50) -> List[Post]: ...
    def get_discover_posts(self, limit: int = 50) -> List[Post]: ...
    def get_conversations(self) -> List[Conversation]: ...
    def get_conversation_messages(self, conversation_id: str) -> List[Message]: ...
    def send_message(self, conversation_id: str, content: str) -> Message: ...
    def get_notifications(self, unread_only: bool = False) -> List[Notification]: ...
    def mark_notification_read(self, notification_id: str) -> bool: ...
    def get_user_settings(self) -> UserSettings: ...
    def update_user_settings(self, settings: UserSettings) -> bool: ...
    def create_post(self, content: str) -> Post: ...
    def like_post(self, post_id: str) -> bool: ...
    def repost(self, post_id: str) -> bool: ...
    # comments
    def get_comments(self, post_id: str) -> List[Dict[str, Any]]: ...
    def add_comment(self, post_id: str, text: str) -> Dict[str, Any]: ...


# === Fake dev backend ===
class FakeAPI(APIInterface):
    def __init__(self):
        self.current_user = User(
            username="yourname",
            display_name="Your Name",
            bio="Building cool stuff with TUIs | vim enthusiast | developer",
            followers=891,
            following=328,
            posts_count=142,
            avatar_ascii="[@#$&●*]",
        )
        self._init_fake_data()

    def _init_fake_data(self):
        now = datetime.now()

        self.timeline_posts: List[Post] = [
            Post("1", "yourname", "Just shipped a new feature! The TUI is looking amazing 🚀",
                 now - timedelta(minutes=5), 12, 3, 2, liked_by_user=True),
            Post("2", "alice", "Working on a new CLI tool for developers. Any testers?",
                 now - timedelta(minutes=15), 45, 12, 1),
            Post("3", "bob", "Refactoring is like cleaning your room. You know where everything is in the mess, but it's still better to organize it.",
                 now - timedelta(hours=1), 234, 67, 0),
        ]

        self.discover_posts: List[Post] = [
            Post("10", "techwriter", "Just discovered this amazing TUI framework! #vim #tui #opensource",
                 now - timedelta(hours=2), 234, 45, 18),
            Post("11", "cliexpert", "Hot take: TUIs are making a comeback! 💻",
                 now - timedelta(hours=4), 189, 52, 34),
            Post("12", "vimfan", "Finally got my vim config working with this social network.",
                 now - timedelta(hours=5), 156, 28, 12),
        ]

        self.conversations: List[Conversation] = [
            Conversation("c1", "alice", "Thanks! Let me know if you need...", now - timedelta(minutes=2), True),
            Conversation("c2", "charlie", "That sounds perfect!", now - timedelta(hours=1), True),
            Conversation("c3", "bob", "Working on a new CLI tool...", now - timedelta(hours=3), False),
        ]

        self.messages: Dict[str, List[Message]] = {
            "c1": [
                Message("m1", "alice", "Hey! Did you see the new feature I pushed?", now - timedelta(minutes=15), True),
                Message("m2", "yourname", "Yes! It looks amazing! 🎉", now - timedelta(minutes=13), True),
                Message("m3", "yourname", "The TUI design is so clean. How did you implement the navigation system?", now - timedelta(minutes=12), True),
                Message("m4", "alice", "State machine for navigation. Want me to share code?", now - timedelta(minutes=8), True),
                Message("m5", "yourname", "That would be great! Happy to test too.", now - timedelta(seconds=30), True),
            ]
        }

        self.notifications: List[Notification] = [
            Notification("n1", "mention", "charlie", '@yourname what do you think?', now - timedelta(minutes=5), False, "11"),
            Notification("n2", "like", "alice", "liked your post", now - timedelta(minutes=15), False, "1"),
        ]

        self.settings = UserSettings(
            username="yourname",
            display_name="Your Name",
            bio=self.current_user.bio,
            email_notifications=True,
            show_online_status=True,
            private_account=False,
            github_connected=True,
        )

        # simple in-memory comments: post_id -> list of dicts
        self.comments: Dict[str, List[Dict[str, Any]]] = {
            "1": [{"user": "alice", "text": "Looks awesome!"}, {"user": "bob", "text": "🔥"}],
            "2": [{"user": "charlie", "text": "Count me in"}],
        }

    # --- User / settings ---
    def get_current_user(self) -> User: return self.current_user
    def get_user_settings(self) -> UserSettings: return self.settings
    def update_user_settings(self, settings: UserSettings) -> bool:
        self.settings = settings
        return True

    # --- Timeline / Discover ---
    def get_timeline(self, limit: int = 50) -> List[Post]:
        return self.timeline_posts[:limit]

    def get_discover_posts(self, limit: int = 50) -> List[Post]:
        return self.discover_posts[:limit]

    def create_post(self, content: str) -> Post:
        p = Post(
            id=f"p{random.randint(1000, 9999)}",
            author="yourname",
            content=content,
            timestamp=datetime.now(),
            likes=0,
            reposts=0,
            comments=0,
            liked_by_user=False,
            reposted_by_user=False,
        )
        self.timeline_posts.insert(0, p)
        return p

    def like_post(self, post_id: str) -> bool:
        for p in self.timeline_posts + self.discover_posts:
            if p.id == post_id:
                if p.liked_by_user:
                    p.liked_by_user = False
                    p.likes = max(0, p.likes - 1)
                else:
                    p.liked_by_user = True
                    p.likes += 1
                return True
        return False

    def repost(self, post_id: str) -> bool:
        for p in self.timeline_posts + self.discover_posts:
            if p.id == post_id:
                if p.reposted_by_user:
                    p.reposted_by_user = False
                    p.reposts = max(0, p.reposts - 1)
                else:
                    p.reposted_by_user = True
                    p.reposts += 1
                return True
        return False

    # --- Conversations / Messages ---
    def get_conversations(self) -> List[Conversation]:
        return self.conversations

    def get_conversation_messages(self, conversation_id: str) -> List[Message]:
        return self.messages.get(conversation_id, [])

    def send_message(self, conversation_id: str, content: str) -> Message:
        msg = Message(
            id=f"m{random.randint(1000, 9999)}",
            sender="yourname",
            content=content,
            timestamp=datetime.now(),
            is_read=True,
        )
        self.messages.setdefault(conversation_id, []).append(msg)
        # update preview in conversations list
        for c in self.conversations:
            if c.id == conversation_id:
                c.last_message = content
                c.timestamp = datetime.now()
                break
        return msg

    # --- Notifications ---
    def get_notifications(self, unread_only: bool = False) -> List[Notification]:
        return [n for n in self.notifications if not n.read] if unread_only else self.notifications

    def mark_notification_read(self, notification_id: str) -> bool:
        for n in self.notifications:
            if n.id == notification_id:
                n.read = True
                return True
        return False

    # --- Comments ---
    def get_comments(self, post_id: str) -> List[Dict[str, Any]]:
        return list(self.comments.get(post_id, []))

    def add_comment(self, post_id: str, text: str) -> Dict[str, Any]:
        entry = {"user": "yourname", "text": text}
        self.comments.setdefault(post_id, []).append(entry)
        # reflect count on post objects
        for p in self.timeline_posts + self.discover_posts:
            if p.id == post_id:
                p.comments += 1
                break
        return entry


# Global API instance
api = FakeAPI()
