from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import os
import random
import json
import requests
from pathlib import Path

# === lightweight data objects used by the UI ===
from dataclasses import dataclass
from data_models import Notification
import os
import requests
from requests import Session
from typing import Iterable
import keyring

from dotenv import load_dotenv

serviceKeyring = "tuiitter"

load_dotenv(override=True)

@dataclass
class User:
    id: int
    handle: str  
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
    id: int
    sender: str
    sender_handle: str  # Denormalized from user table per PostgreSQL schema
    content: str
    timestamp: datetime
    is_read: bool = False


@dataclass
class Conversation:
    id: int
    participant_handles: List[str]
    last_message_preview: str
    last_message_at: datetime
    unread: bool = False


class Comment:
    def __init__(self, author: str, content: str, timestamp: datetime):
        self.author = author
        self.content = content
        self.timestamp = timestamp


@dataclass
class UserSettings:
    user_id: Optional[int] = None
    email_notifications: Optional[bool] = True
    show_online_status: Optional[bool] = True
    private_account: Optional[bool] = False
    github_connected: Optional[bool] = False
    gitlab_connected: Optional[bool] = False
    google_connected: Optional[bool] = False
    discord_connected: Optional[bool] = False
    ascii_pic: Optional[str] = ""
    updated_at: Optional[datetime] = None

class APIInterface:
    def get_current_user(self) -> User: ...
    def set_handle(self, handle: str) -> None: ...
    def get_timeline(self, limit: int = 50) -> List[Post]: ...
    def get_discover_posts(self, limit: int = 50) -> List[Post]: ...
    def get_conversations(self) -> List[Conversation]: ...
    def get_conversation_messages(self, conversation_id: int) -> List[Message]: ...
    def send_message(self, conversation_id: int, content: str) -> Message: ...
    def get_or_create_dm(self, other_user_handle: str) -> Conversation: ...
    def get_notifications(self, unread_only: bool = False) -> List[Notification]: ...
    def mark_notification_read(self, notification_id: int) -> bool: ...
    def get_user_settings(self) -> UserSettings: ...
    def update_user_settings(self, settings: UserSettings) -> bool: ...
    def create_post(self, content: str) -> bool: ...
    def like_post(self, post_id: int) -> bool: ...
    def repost(self, post_id: int) -> bool: ...
    # comments
    def get_comments(self, post_id: int) -> List[Dict[str, Any]]: ...
    def add_comment(self, post_id: int, text: str) -> Dict[str, Any]: ...


class RealAPI(APIInterface):
    """Real API client that talks to an external HTTP backend.

    It expects a base_url like https://api.example.com and optional
    token-based auth via BACKEND_TOKEN env var.
    """
    def __init__(self, base_url: str, token: str | None = None, timeout: float = 5.0, handle: str = "yourname"):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.handle = handle
        self.session: Session = requests.Session()

    # --- helpers ---
    def set_token(self, token: str) -> None:
        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def set_handle(self, handle: str) -> None:
        """Update the handle (username) used in API requests"""
        self.handle = handle

    def _get(self, path: str, params: Dict[str, Any] | None = None) -> Any:
        if params is None:
            params = {}
        params.setdefault("handle", self.handle)
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self.session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json_payload: Dict[str, Any] | None = None, params: Dict[str, Any] | None = None) -> Any:
        if params is None:
            params = {}
        params.setdefault("handle", self.handle)
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = self.session.post(url, params=params, json=json_payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

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

    def get_conversation_messages(self, conversation_id: int) -> List[Message]:
        data = self._get(f"/conversations/{conversation_id}/messages")
        return [self._convert_message(m) for m in data]

    def send_message(self, conversation_id: int, content: str) -> Message:
        # Backend expects sender_handle in the request body
        data = self._post(
            f"/conversations/{conversation_id}/messages",
            json_payload={"content": content, "sender_handle": self.handle},
        )
        return self._convert_message(data)
    
    def get_or_create_dm(self, other_user_handle: str) -> Conversation:
        """Get or create a direct message conversation with another user"""
        data = self._post(
            "/dm",
            json_payload={
                "user_a_handle": self.handle,
                "user_b_handle": other_user_handle
            }
        )
        return Conversation(**data)

    def get_notifications(self, unread_only: bool = False) -> List[Notification]:
        # Backend uses 'unread' parameter, not 'unread_only'
        params = {"unread": "true"} if unread_only else {}
        data = self._get("/notifications", params=params)
        notif_fields = Notification.__dataclass_fields__.keys()
        filtered = [{k: v for k, v in n.items() if k in notif_fields} for n in data]
        return [Notification(**n) for n in filtered]

    def mark_notification_read(self, notification_id: int) -> bool:
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

    def like_post(self, post_id: int) -> bool:
        self._post(f"/posts/{post_id}/like")
        return True

    def repost(self, post_id: int) -> bool:
        self._post(f"/posts/{post_id}/repost")
        return True

    def get_comments(self, post_id: int) -> List[Dict[str, Any]]:
        data = self._get(f"/posts/{post_id}/comments")
        return data

    def add_comment(self, post_id: int, text: str) -> Dict[str, Any]:
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
    
    def _convert_message(self, m: Dict[str, Any]) -> Message:
        """Convert backend message response to Message dataclass"""
        return Message(
            id=int(m.get("id", 0)),
            sender=m.get("sender") or m.get("sender_handle") or self.handle,
            sender_handle=m.get("sender_handle") or m.get("sender") or self.handle,
            content=m.get("content") or "",
            timestamp=m.get("timestamp")
            if isinstance(m.get("timestamp"), datetime)
            else datetime.fromisoformat(m.get("timestamp"))
            if m.get("timestamp")
            else datetime.now(),
            is_read=bool(m.get("is_read") or False),
        )

# Global api selection: prefer real backend when BACKEND_URL is set
_backend_url = os.environ.get("BACKEND_URL")

if _backend_url:
    # Get username from keyring if available, otherwise use default
    _username = keyring.get_password(serviceKeyring, "username") or "yourname"
    api = RealAPI(base_url=_backend_url, handle=_username)

    try:
        token_data = keyring.get_password(serviceKeyring, "oauth_tokens.json")
        if token_data:
            tokens = json.loads(token_data)
            if "access_token" in tokens:
                api.set_token(tokens["access_token"])
    except Exception as e:
        print(f"Warning: Could not load auth token: {e}")
else:
    # Fallback to prevent NameError on import
    # Will fail at runtime with clear error message
    class _StubAPI:
        def __getattr__(self, name):
            raise RuntimeError(
                f"BACKEND_URL environment variable is not set. "
                f"Please set BACKEND_URL to your FastAPI backend URL (e.g., 'http://localhost:8000'). "
                f"Attempted to call: {name}"
            )
    api = _StubAPI()
