"""
API Interface Layer for social.vim
This module provides an abstraction layer between the UI and the backend.
Replace the FakeAPI class with a real API client to connect to your backend.
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import os
import random
import json
import requests
from pathlib import Path

# === lightweight data objects used by the UI ===
from dataclasses import dataclass
import os
import requests
from requests import Session
from typing import Iterable


@dataclass
class User:
    username: str
    display_name: str
    bio: str
    followers: int
    following: int
    posts_count: int
    ascii_pic: str = ""


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


class Comment:
    def __init__(self, author: str, content: str, timestamp: datetime):
        self.author = author
        self.content = content
        self.timestamp = timestamp


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
    ascii_pic: str = ""


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
    def create_post(self, content: str) -> bool: ...
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
            ascii_pic="  [●▓▓●]\n  |≈ ◡ ≈|\n  |▓███▓|",
        )
        self._init_fake_data()

    def _init_fake_data(self):
        now = datetime.now()

        self.timeline_posts: List[Post] = [
            Post(
                "1",
                "yourname",
                "Just shipped a new feature! The TUI is looking amazing 🚀",
                now - timedelta(minutes=5),
                12,
                3,
                2,
                liked_by_user=True,
            ),
            Post(
                "2",
                "alice",
                "Working on a new CLI tool for developers. Any testers?",
                now - timedelta(minutes=15),
                45,
                12,
                1,
            ),
            Post(
                "3",
                "bob",
                "Refactoring is like cleaning your room. You know where everything is in the mess, but it's still better to organize it.",
                now - timedelta(hours=1),
                234,
                67,
                0,
            ),
        ]

        self.discover_posts: List[Post] = [
            Post(
                "10",
                "techwriter",
                "Just discovered this amazing TUI framework! #vim #tui #opensource",
                now - timedelta(hours=2),
                234,
                45,
                18,
            ),
            Post(
                "11",
                "cliexpert",
                "Hot take: TUIs are making a comeback! 💻",
                now - timedelta(hours=4),
                189,
                52,
                34,
            ),
            Post(
                "12",
                "vimfan",
                "Finally got my vim config working with this social network.",
                now - timedelta(hours=5),
                156,
                28,
                12,
            ),
        ]

        self.conversations: List[Conversation] = [
            Conversation(
                "c1",
                "alice",
                "Thanks! Let me know if you need...",
                now - timedelta(minutes=2),
                True,
            ),
            Conversation(
                "c2", "charlie", "That sounds perfect!", now - timedelta(hours=1), True
            ),
            Conversation(
                "c3",
                "bob",
                "Working on a new CLI tool...",
                now - timedelta(hours=3),
                False,
            ),
        ]

        self.messages: Dict[str, List[Message]] = {
            "c1": [
                Message(
                    "m1",
                    "alice",
                    "Hey! Did you see the new feature I pushed?",
                    now - timedelta(minutes=15),
                    True,
                ),
                Message(
                    "m2",
                    "yourname",
                    "Yes! It looks amazing! 🎉",
                    now - timedelta(minutes=13),
                    True,
                ),
                Message(
                    "m3",
                    "yourname",
                    "The TUI design is so clean. How did you implement the navigation system?",
                    now - timedelta(minutes=12),
                    True,
                ),
                Message(
                    "m4",
                    "alice",
                    "State machine for navigation. Want me to share code?",
                    now - timedelta(minutes=8),
                    True,
                ),
                Message(
                    "m5",
                    "yourname",
                    "That would be great! Happy to test too.",
                    now - timedelta(seconds=30),
                    True,
                ),
            ]
        }

        self.notifications: List[Notification] = [
            Notification(
                "n1",
                "mention",
                "charlie",
                "@yourname what do you think?",
                now - timedelta(minutes=5),
                False,
                "11",
            ),
            Notification(
                "n2",
                "like",
                "alice",
                "liked your post",
                now - timedelta(minutes=15),
                False,
                "1",
            ),
        ]

        self.settings = UserSettings(
            username="yourname",
            display_name="Your Name",
            bio=self.current_user.bio,
            email_notifications=True,
            show_online_status=True,
            private_account=False,
            github_connected=True,
            ascii_pic="  [●▓▓●]\n  |≈ ◡ ≈|\n  |▓███▓|",
        )

        # simple in-memory comments: post_id -> list of dicts
        self.comments: Dict[str, List[Dict[str, Any]]] = {
            "1": [
                {"user": "alice", "text": "Looks awesome!"},
                {"user": "bob", "text": "🔥"},
            ],
            "2": [{"user": "charlie", "text": "Count me in"}],
        }

    # --- User / settings ---
    def get_current_user(self) -> User:
        return self.current_user

    def get_user_settings(self) -> UserSettings:
        return self.settings

    def update_user_settings(self, settings: UserSettings) -> bool:
        self.settings = settings
        # Update current_user ascii_pic as well
        self.current_user.ascii_pic = settings.ascii_pic
        return True

    # --- Timeline / Discover ---
    def get_timeline(self, limit: int = 50) -> List[Post]:
        """Get the user's timeline/feed."""
        return self.timeline_posts[:limit]

    def get_discover_posts(self, limit: int = 50) -> List[Post]:
        """Get discover/explore posts."""
        return self.discover_posts[:limit]

    def get_post_comments(self, post_id: str, limit: int = 5):
        """Get top comments for a post."""
        # Return fake comments for now
        return [
            Comment("alice", "Great post!", datetime.now() - timedelta(hours=2)),
            Comment(
                "bob", "I totally agree with this", datetime.now() - timedelta(hours=5)
            ),
            Comment(
                "charlie", "Thanks for sharing!", datetime.now() - timedelta(days=1)
            ),
        ][:limit]

    def add_comment(self, post_id: str, content: str):
        """Add a new comment to a post."""
        return Comment("yourname", content, datetime.now())

    def get_conversations(self) -> List[Conversation]:
        """Get all conversations for the current user."""
        return self.conversations

    def get_conversation_messages(self, conversation_id: str) -> List[Message]:
        """Get all messages in a specific conversation."""
        return self.messages.get(conversation_id, [])

    def send_message(self, conversation_id: str, content: str) -> Message:
        """Send a message in a conversation."""
        now = datetime.now()
        new_msg = Message(
            id=f"m{random.randint(1000, 9999)}",
            sender="yourname",
            content=content,
            timestamp=now,
            is_read=True,
        )
        if conversation_id not in self.messages:
            self.messages[conversation_id] = []
        self.messages[conversation_id].append(new_msg)

        # Update conversation last message
        for conv in self.conversations:
            if conv.id == conversation_id:
                conv.last_message = (
                    content[:30] + "..." if len(content) > 30 else content
                )
                conv.timestamp = now
                break

        return new_msg

    def get_notifications(self, unread_only: bool = False) -> List[Notification]:
        """Get notifications for the current user."""
        if unread_only:
            return [n for n in self.notifications if not n.read]
        return self.notifications

    def mark_notification_read(self, notification_id: str) -> bool:
        """Mark a notification as read."""
        for notif in self.notifications:
            if notif.id == notification_id:
                notif.read = True
                return True
        return False

    def create_post(self, content: str, image_path=None, video_path=None) -> bool:
        """Create a new post with optional media."""
        now = datetime.now()
        new_post = Post(
            id=str(random.randint(100, 9999)),
            author="yourname",
            content=content,
            timestamp=now,
            likes=0,
            reposts=0,
            comments=0,
            liked_by_user=False,
            reposted_by_user=False,
        )
        self.timeline_posts.insert(0, new_post)
        self.current_user.posts_count += 1
        return True

    def like_post(self, post_id: str) -> bool:
        """Like/unlike a post."""
        for post in self.timeline_posts + self.discover_posts:
            if post.id == post_id:
                if post.liked_by_user:
                    post.likes -= 1
                    post.liked_by_user = False
                else:
                    post.likes += 1
                    post.liked_by_user = True
                return True
        return False

    def repost(self, post_id: str) -> bool:
        """Repost/unrepost a post."""
        for post in self.timeline_posts + self.discover_posts:
            if post.id == post_id:
                if post.reposted_by_user:
                    post.reposts -= 1
                    post.reposted_by_user = False
                else:
                    post.reposts += 1
                    post.reposted_by_user = True
                return True
        return False

    def add_comment(self, post_id: str, text: str) -> Dict[str, Any]:
        """Add a comment to a post."""
        if post_id not in self.comments:
            self.comments[post_id] = []

        comment = {"user": "yourname", "text": text}
        self.comments[post_id].append(comment)

        # Update comment count on post
        for post in self.timeline_posts + self.discover_posts:
            if post.id == post_id:
                post.comments += 1
                break

        return comment

    def get_comments(self, post_id: str) -> List[Dict[str, Any]]:
        """Get comments for a post."""
        return self.comments.get(post_id, [])


# === Real API Backend (with OAuth) ===
class RealAPI(APIInterface):
    def __init__(self, base_url: str = "https://your-api.com/api"):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
        self._load_tokens()

    def _load_tokens(self):
        """Load tokens from oauth_tokens.json if it exists."""
        token_file = Path("oauth_tokens.json")
        if token_file.exists():
            try:
                with open(token_file, "r") as f:
                    data = json.load(f)
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token")
            except Exception as e:
                print(f"Error loading tokens: {e}")

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authorization."""
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> requests.Response:
        """Make a GET request."""
        url = f"{self.base_url}{endpoint}"
        return requests.get(url, headers=self._get_headers(), params=params)

    def _post(self, endpoint: str, json: Optional[Dict] = None) -> requests.Response:
        """Make a POST request."""
        url = f"{self.base_url}{endpoint}"
        return requests.post(url, headers=self._get_headers(), json=json)

    def _put(self, endpoint: str, json: Optional[Dict] = None) -> requests.Response:
        """Make a PUT request."""
        url = f"{self.base_url}{endpoint}"
        return requests.put(url, headers=self._get_headers(), json=json)

    def get_current_user(self) -> User:
        """Get current user info."""
        resp = self._get("/user")
        data = resp.json()
        return User(**data)

    def get_timeline(self, limit: int = 50) -> List[Post]:
        """Get the user's timeline/feed."""
        resp = self._get(f"/timeline?limit={limit}")
        return [Post(**p) for p in resp.json()]

    def get_discover_posts(self, limit: int = 50) -> List[Post]:
        """Get discover/explore posts."""
        resp = self._get(f"/discover?limit={limit}")
        return [Post(**p) for p in resp.json()]

    def get_conversations(self) -> List[Conversation]:
        """Get all conversations for the current user."""
        resp = self._get("/conversations")
        return [Conversation(**c) for c in resp.json()]

    def get_conversation_messages(self, conversation_id: str) -> List[Message]:
        """Get all messages in a specific conversation."""
        resp = self._get(f"/conversations/{conversation_id}/messages")
        return [Message(**m) for m in resp.json()]

    def send_message(self, conversation_id: str, content: str) -> Message:
        """Send a message in a conversation."""
        data = {"content": content}
        resp = self._post(f"/conversations/{conversation_id}/messages", json=data)
        return Message(**resp.json())

    def get_notifications(self, unread_only: bool = False) -> List[Notification]:
        """Get notifications for the current user."""
        params = {"unread_only": unread_only} if unread_only else {}
        resp = self._get("/notifications", params=params)
        return [Notification(**n) for n in resp.json()]

    def mark_notification_read(self, notification_id: str) -> bool:
        """Mark a notification as read."""
        try:
            self._put(f"/notifications/{notification_id}/read")
            return True
        except Exception:
            return False

    def get_user_settings(self) -> UserSettings:
        """Get user settings."""
        resp = self._get("/user/settings")
        return UserSettings(**resp.json())

    def update_user_settings(self, settings: UserSettings) -> bool:
        """Update user settings."""
        try:
            data = settings.__dict__
            self._put("/user/settings", json=data)
            return True
        except Exception:
            return False

    def create_post(self, content: str, image_path=None, video_path=None) -> bool:
        """Create a new post with optional media."""
        url = f"{self.base_url}/posts"
        files = {}
        data = {"content": content}

        try:
            if image_path:
                files["image"] = open(image_path, "rb")
            if video_path:
                files["video"] = open(video_path, "rb")

            headers = {"Authorization": f"Bearer {self.access_token}"}
            resp = requests.post(url, headers=headers, data=data, files=files or None)

            return resp.status_code in [200, 201]
        except Exception as e:
            print(f"Error creating post: {e}")
            return False
        finally:
            for f in files.values():
                f.close()

    def like_post(self, post_id: str) -> bool:
        """Like a post."""
        try:
            self._post(f"/posts/{post_id}/like")
            return True
        except Exception:
            return False

    def repost(self, post_id: str) -> bool:
        """Repost/share a post."""
        try:
            self._post(f"/posts/{post_id}/repost")
            return True
        except Exception:
            return False

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
class RealAPI(APIInterface):
    """Real API client that talks to an external HTTP backend.

    It expects a base_url like https://api.example.com and optional
    token-based auth via BACKEND_TOKEN env var.
    """

    def __init__(self, base_url: str, token: str | None = None, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.session: Session = requests.Session()
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    # --- helpers ---
    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json_payload: Dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self.session.post(url, json=json_payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    # --- implementations (minimal, may need expansion) ---
    def get_current_user(self) -> User:
        data = self._get("/me")
        return User(**data)

    def get_timeline(self, limit: int = 50) -> List[Post]:
        data = self._get("/timeline", params={"limit": limit})
        return [Post(**self._convert_post(p)) for p in data]

    def get_discover_posts(self, limit: int = 50) -> List[Post]:
        data = self._get("/discover", params={"limit": limit})
        return [Post(**self._convert_post(p)) for p in data]

    def get_conversations(self) -> List[Conversation]:
        data = self._get("/conversations")
        return [Conversation(**c) for c in data]

    def get_conversation_messages(self, conversation_id: str) -> List[Message]:
        data = self._get(f"/conversations/{conversation_id}/messages")
        return [Message(**m) for m in data]

    def send_message(self, conversation_id: str, content: str) -> Message:
        data = self._post(
            f"/conversations/{conversation_id}/messages",
            json_payload={"content": content},
        )
        return Message(**data)

    def get_notifications(self, unread_only: bool = False) -> List[Notification]:
        params = (
            {"unread_only": str(bool(unread_only)).lower()} if unread_only else None
        )
        data = self._get("/notifications", params=params)
        return [Notification(**n) for n in data]

    def mark_notification_read(self, notification_id: str) -> bool:
        self._post(f"/notifications/{notification_id}/read")
        return True

    def get_user_settings(self) -> UserSettings:
        data = self._get("/settings")
        return UserSettings(**data)

    def update_user_settings(self, settings: UserSettings) -> bool:
        self._post("/settings", json_payload=settings.__dict__)
        return True

    def create_post(self, content: str) -> Post:
        data = self._post("/posts", json_payload={"content": content})
        return Post(**self._convert_post(data))

    def like_post(self, post_id: str) -> bool:
        self._post(f"/posts/{post_id}/like")
        return True

    def repost(self, post_id: str) -> bool:
        self._post(f"/posts/{post_id}/repost")
        return True

    def get_comments(self, post_id: str) -> List[Dict[str, Any]]:
        data = self._get(f"/posts/{post_id}/comments")
        return data

    def add_comment(self, post_id: str, text: str) -> Dict[str, Any]:
        data = self._post(f"/posts/{post_id}/comments", json_payload={"text": text})
        return data

    # --- conversion helpers ---
    def _convert_post(self, p: Dict[str, Any]) -> Dict[str, Any]:
        # Ensure fields match Post dataclass naming
        out = dict(
            id=str(p.get("id")),
            author=p.get("author") or p.get("username") or p.get("user"),
            content=p.get("content") or p.get("text") or "",
            timestamp=p.get("timestamp")
            if isinstance(p.get("timestamp"), datetime)
            else datetime.fromisoformat(p.get("timestamp"))
            if p.get("timestamp")
            else datetime.now(),
            likes=int(p.get("likes") or 0),
            reposts=int(p.get("reposts") or 0),
            comments=int(p.get("comments") or 0),
            liked_by_user=bool(p.get("liked_by_user") or p.get("liked") or False),
            reposted_by_user=bool(
                p.get("reposted_by_user") or p.get("reposted") or False
            ),
        )
        return out


# Global api selection: prefer real backend when BACKEND_URL is set
_backend_url = os.environ.get("BACKEND_URL")
_backend_token = os.environ.get("BACKEND_TOKEN")

if _backend_url:
    try:
        api = RealAPI(_backend_url, token=_backend_token)
    except Exception:
        # Fallback to fake API if real client construction fails
        api = FakeAPI()
else:
    api = FakeAPI()
