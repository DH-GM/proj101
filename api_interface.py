"""
API Interface Layer for social.vim
This module provides an abstraction layer between the UI and the backend.
Replace the FakeAPI class with a real API client to connect to your backend.
"""
from typing import List, Optional
from datetime import datetime, timedelta
import random
from data_models import (
    User, Post, Message, Conversation, Notification, UserSettings
)


class APIInterface:
    """Base interface for API operations."""
    
    def get_current_user(self) -> User:
        raise NotImplementedError
    
    def get_timeline(self, limit: int = 50) -> List[Post]:
        raise NotImplementedError
    
    def get_discover_posts(self, limit: int = 50) -> List[Post]:
        raise NotImplementedError
    
    def get_conversations(self) -> List[Conversation]:
        raise NotImplementedError
    
    def get_conversation_messages(self, conversation_id: str) -> List[Message]:
        raise NotImplementedError
    
    def send_message(self, conversation_id: str, content: str) -> Message:
        raise NotImplementedError
    
    def get_notifications(self, unread_only: bool = False) -> List[Notification]:
        raise NotImplementedError
    
    def mark_notification_read(self, notification_id: str) -> bool:
        raise NotImplementedError
    
    def get_user_settings(self) -> UserSettings:
        raise NotImplementedError
    
    def update_user_settings(self, settings: UserSettings) -> bool:
        raise NotImplementedError
    
    def create_post(self, content: str) -> Post:
        raise NotImplementedError
    
    def like_post(self, post_id: str) -> bool:
        raise NotImplementedError
    
    def repost(self, post_id: str) -> bool:
        raise NotImplementedError


class FakeAPI(APIInterface):
    """
    Fake API implementation with mock data for development.
    Replace this with a real API client that makes HTTP requests to your backend.
    """
    
    def __init__(self):
        self.current_user = User(
            username="yourname",
            display_name="Your Name",
            bio="Building cool stuff with TUIs | vim enthusiast | developer",
            followers=891,
            following=328,
            posts_count=142,
            avatar_ascii="[@#$&●*]"
        )
        self._init_fake_data()
    
    def _init_fake_data(self):
        """Initialize fake data for development."""
        now = datetime.now()
        
        # Fake timeline posts
        self.timeline_posts = [
            Post("1", "yourname", "Just shipped a new feature! The TUI is looking amazing 🚀", 
                 now - timedelta(minutes=5), 12, 3, 5, liked_by_user=True),
            Post("2", "alice", "Working on a new CLI tool for developers. Any testers?", 
                 now - timedelta(minutes=15), 45, 12, 28),
            Post("3", "bob", "Refactoring is like cleaning your room. You know where everything is in the mess, but it's still better to organize it.", 
                 now - timedelta(hours=1), 234, 67, 45),
        ]
        
        # Fake discover posts
        self.discover_posts = [
            Post("10", "techwriter", "Just discovered this amazing TUI framework! The vim-style navigation is incredible. #vim #tui #opensource", 
                 now - timedelta(hours=2), 234, 45, 18),
            Post("11", "cliexpert", "Hot take: TUIs are making a comeback and I'm here for it! Terminal > GUI any day 💻 #cli #terminal", 
                 now - timedelta(hours=4), 189, 52, 34),
            Post("12", "vimfan", "Finally got my custom vim config working with this social network. The hjkl navigation feels so natural! #vim", 
                 now - timedelta(hours=5), 156, 28, 12),
        ]
        
        # Fake conversations
        self.conversations = [
            Conversation("c1", "alice", "Thanks! Let me know if you need...", 
                        now - timedelta(minutes=2), True),
            Conversation("c2", "charlie", "That sounds perfect!", 
                        now - timedelta(hours=1), True),
            Conversation("c3", "bob", "Working on a new CLI tool...", 
                        now - timedelta(hours=3), False),
            Conversation("c4", "dana", "See you tomorrow!", 
                        now - timedelta(days=1), False),
        ]
        
        # Fake messages for alice conversation
        self.messages = {
            "c1": [
                Message("m1", "alice", "Hey! Did you see the new feature I pushed?", 
                       now - timedelta(minutes=15), True),
                Message("m2", "yourname", "Yes! It looks amazing! 🎉", 
                       now - timedelta(minutes=13), True),
                Message("m3", "yourname", "The TUI design is so clean. How did you implement the navigation system?", 
                       now - timedelta(minutes=12), True),
                Message("m4", "alice", "Thanks! I used a state machine for the navigation. Want me to share the code?", 
                       now - timedelta(minutes=8), True),
                Message("m5", "yourname", "That would be great! Thanks! Let me know if you need any help with testing.", 
                       now - timedelta(seconds=30), True),
            ]
        }
        
        # Fake notifications
        self.notifications = [
            Notification("n1", "mention", "charlie", 'In: "Hot take about TUIs..." "@yourname what do you think about this?"', 
                        now - timedelta(minutes=5), False, "post_123"),
            Notification("n2", "like", "alice", '"Just shipped a new feature! The TUI is looking amazing 🚀"', 
                        now - timedelta(minutes=15), False, "1"),
            Notification("n3", "like", "bob", '"Just shipped a new feature! The TUI is looking amazing 🚀"', 
                        now - timedelta(minutes=32), False, "1"),
            Notification("n4", "repost", "dana", 'Your post: "Refactoring is like cleaning your room..."', 
                        now - timedelta(hours=1), False, "3"),
            Notification("n5", "follow", "eve", "", now - timedelta(hours=2), False),
            Notification("n6", "like", "frank", '"Working on a new CLI tool for developers..."', 
                        now - timedelta(hours=3), False, "2"),
        ]
        
        # User settings
        self.settings = UserSettings(
            username="yourname",
            display_name="Your Name",
            bio="Building cool stuff with TUIs | vim enthusiast | developer",
            email_notifications=True,
            show_online_status=True,
            private_account=False,
            ascii_pic="",
            github_connected=True,
            gitlab_connected=False,
            google_connected=False,
            discord_connected=False
        )
    
    def get_current_user(self) -> User:
        return self.current_user
    
    def get_timeline(self, limit: int = 50) -> List[Post]:
        return self.timeline_posts[:limit]
    
    def get_discover_posts(self, limit: int = 50) -> List[Post]:
        return self.discover_posts[:limit]
    
    def get_conversations(self) -> List[Conversation]:
        return self.conversations
    
    def get_conversation_messages(self, conversation_id: str) -> List[Message]:
        return self.messages.get(conversation_id, [])
    
    def send_message(self, conversation_id: str, content: str) -> Message:
        new_message = Message(
            id=f"m{random.randint(1000, 9999)}",
            sender="yourname",
            content=content,
            timestamp=datetime.now(),
            is_read=True
        )
        if conversation_id not in self.messages:
            self.messages[conversation_id] = []
        self.messages[conversation_id].append(new_message)
        return new_message
    
    def get_notifications(self, unread_only: bool = False) -> List[Notification]:
        if unread_only:
            return [n for n in self.notifications if not n.read]
        return self.notifications
    
    def mark_notification_read(self, notification_id: str) -> bool:
        for notif in self.notifications:
            if notif.id == notification_id:
                notif.read = True
                return True
        return False
    
    def get_user_settings(self) -> UserSettings:
        return self.settings
    
    def update_user_settings(self, settings: UserSettings) -> bool:
        self.settings = settings
        return True
    
    def create_post(self, content: str) -> Post:
        new_post = Post(
            id=f"p{random.randint(1000, 9999)}",
            author="yourname",
            content=content,
            timestamp=datetime.now(),
            likes=0,
            reposts=0,
            comments=0,
            liked_by_user=False,
            reposted_by_user=False
        )
        self.timeline_posts.insert(0, new_post)
        return new_post
    
    def like_post(self, post_id: str) -> bool:
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


# Global API instance - replace FakeAPI() with your real API client
api = FakeAPI()

