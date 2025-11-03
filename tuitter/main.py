from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import (
    Container,
    Horizontal,
    Vertical,
    VerticalScroll,
    ScrollableContainer,
)
from textual.widgets import Static, Input, Button, TextArea, Label, RichLog
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.message import Message
from datetime import datetime
from .api_interface import api
import sys
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from PIL import Image
from .ascii_video_widget import ASCIIVideoPlayer
import json
from typing import List, Dict
from rich.text import Text
import logging
import time


# Custom message for draft updates
class DraftsUpdated(Message):
    """Posted when drafts are updated."""

    pass


# Drafts file path
DRAFTS_FILE = Path.home() / ".proj101_drafts.json"


def load_drafts() -> List[Dict]:
    """Load drafts from local storage."""
    if not DRAFTS_FILE.exists():
        return []
    try:
        with open(DRAFTS_FILE, "r") as f:
            drafts = json.load(f)
            # Convert timestamp strings back to datetime objects
            for draft in drafts:
                draft["timestamp"] = datetime.fromisoformat(draft["timestamp"])
            return drafts
    except Exception:
        return []


def save_drafts(drafts: List[Dict]) -> None:
    """Save drafts to local storage."""
    try:
        # Convert datetime objects to ISO format strings
        drafts_to_save = []
        for draft in drafts:
            draft_copy = draft.copy()
            draft_copy["timestamp"] = draft["timestamp"].isoformat()
            drafts_to_save.append(draft_copy)

        with open(DRAFTS_FILE, "w") as f:
            json.dump(drafts_to_save, f, indent=2)
    except Exception as e:
        print(f"Error saving drafts: {e}")


def add_draft(content: str, attachments: List = None) -> None:
    """Add a new draft and maintain max 2 drafts."""
    drafts = load_drafts()

    # Create new draft
    new_draft = {
        "content": content,
        "attachments": attachments or [],
        "timestamp": datetime.now(),
    }

    # Add new draft
    drafts.append(new_draft)

    # Sort by timestamp (oldest first)
    drafts.sort(key=lambda x: x["timestamp"])

    # Keep only the 2 most recent drafts
    if len(drafts) > 2:
        drafts = drafts[-2:]

    save_drafts(drafts)


def delete_draft(index: int) -> None:
    """Delete a specific draft by index."""
    drafts = load_drafts()
    if 0 <= index < len(drafts):
        drafts.pop(index)
        save_drafts(drafts)


def format_time_ago(dt: datetime) -> str:
    """Format datetime as 'time ago' string."""
    now = datetime.now()
    diff = now - dt
    if diff.days > 0:
        return f"{diff.days}d ago"
    if diff.seconds < 60:
        return "just now"
    if diff.seconds < 3600:
        return f"{diff.seconds // 60}m ago"
    return f"{diff.seconds // 3600}h ago"


# ───────── Comment Screen ─────────
class CommentFeed(VerticalScroll):
    """Comment feed modeled after DiscoverFeed"""

    cursor_position = reactive(0)  # 0 = post, 1 = input, 2+ = comments
    scroll_y = reactive(0)  # Track scroll position

    def __init__(self, post, **kwargs):
        super().__init__(**kwargs)
        self.post = post
        self.comments = []

    def compose(self):
        # Post at the top
        yield Static("─ Post ─", classes="comment-thread-header", markup=False)
        yield PostItem(self.post)

        yield Static("─ Comments ─", classes="comment-thread-header", markup=False)

        # Input for new comment
        yield Input(
            placeholder="[i] to comment... Press Enter to submit",
            id="comment-input",
        )

        # Comments
        self.comments = api.get_comments(self.post.id)
        logging.debug(f"[compose] Comments fetched: {self.comments}")

        for i, c in enumerate(self.comments):
            author = c.get("user", "unknown")
            content = c.get("text", "")
            timestamp = (
                c.get("timestamp") or c.get("created_at") or datetime.now().isoformat()
            )
            try:
                c_time = format_time_ago(datetime.fromisoformat(timestamp))
            except Exception:
                c_time = "just now"
            comment = Static(
                f"  @{author} • {c_time}\n  {content}\n",
                classes="comment-thread-item comment-item",
                id=f"comment-{i}",
                markup=False,
            )
            comment.styles.background = "#282A36"  # Force dark background
            yield comment

    def on_mount(self) -> None:
        """Watch cursor position for updates"""
        self.watch(self, "cursor_position", self._update_cursor)
        self.watch(self, "scroll_y", self._check_scroll_load)

    def _check_scroll_load(self) -> None:
        """Check if we need to load more comments based on scroll position"""
        # Not needed for comments but keeping pattern consistent
        pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle comment submission"""
        if event.input.id != "comment-input":
            return
        text = event.value.strip()
        if not text:
            return

        api.add_comment(self.post.id, text)

        # Clear input
        event.input.value = ""
        event.input.blur()

        # Refresh comments
        self._refresh_comments()

        # Show notification
        if hasattr(self.app, "notify"):
            self.app.notify("Comment posted!", timeout=2)

    def _refresh_comments(self) -> None:
        """Refresh the comment list"""
        try:
            # Remove existing comment items
            for item in self.query(".comment-item"):
                item.remove()

            # Fetch updated comments
            self.comments = api.get_comments(self.post.id)

            # Add new comments
            for i, c in enumerate(self.comments):
                author = c.get("user", "unknown")
                content = c.get("text", "")
                timestamp = (
                    c.get("timestamp")
                    or c.get("created_at")
                    or datetime.now().isoformat()
                )
                try:
                    c_time = format_time_ago(datetime.fromisoformat(timestamp))
                except Exception:
                    c_time = "just now"
                comment_widget = Static(
                    f"  @{author} • {c_time}\n  {content}\n",
                    classes="comment-thread-item comment-item",
                    id=f"comment-{i}",
                    markup=False,
                )
                comment_widget.styles.background = "#282A36"  # Force dark background
                self.mount(comment_widget)

            # Reset cursor position
            self.cursor_position = 0
        except Exception:
            pass

    def key_i(self) -> None:
        """Focus comment input with i key"""
        if self.app.command_mode:
            return
        # Set cursor to position 1 (input) and focus it
        self.cursor_position = 1
        try:
            comment_input = self.query_one("#comment-input", Input)
            comment_input.focus()
        except Exception:
            pass

    def key_q(self) -> None:
        """Exit comment screen with q key"""
        if self.app.command_mode:
            return
        try:
            self.app.pop_screen()
        except Exception:
            pass

    def _get_navigable_items(self) -> list:
        """Get all navigable items (post + input + comments)"""
        try:
            post_item = self.query_one(PostItem)
            comment_input = self.query_one("#comment-input", Input)
            comment_items = list(self.query(".comment-item"))
            return [post_item, comment_input] + comment_items
        except Exception:
            return []

    def _update_cursor(self) -> None:
        """Update the cursor position - includes post + input + comments"""
        try:
            items = self._get_navigable_items()
            post_item = self.query_one(PostItem)
            comment_items = list(self.query(".comment-item"))
            comment_input = self.query_one("#comment-input", Input)

            # Remove cursor from all items
            post_item.remove_class("vim-cursor")
            comment_input.remove_class("vim-cursor")
            for item in comment_items:
                item.remove_class("vim-cursor")
                item.styles.background = (
                    "#282A36"  # Reset to dark background, not empty
                )

            if 0 <= self.cursor_position < len(items):
                item = items[self.cursor_position]
                if isinstance(item, PostItem):
                    # Add cursor to post
                    item.add_class("vim-cursor")
                    self.focus()
                elif isinstance(item, Input):
                    # Don't focus the input, just add visual indicator
                    item.add_class("vim-cursor")
                    # Make sure screen has focus so vim keys work
                    self.focus()
                else:
                    # Add cursor class to comment (no background change, just text style)
                    item.add_class("vim-cursor")
                self.scroll_to_widget(item, top=True)
        except Exception:
            pass

    def on_focus(self) -> None:
        """When the screen gets focus"""
        self.cursor_position = 0
        self._update_cursor()

    def on_blur(self) -> None:
        """When screen loses focus"""
        pass

    def on_scroll(self, event) -> None:
        """Update scroll position reactive when scrolling"""
        self.scroll_y = self.scroll_offset.y

    def key_j(self) -> None:
        """Move down with j key"""
        if self.app.command_mode:
            return
        items = self._get_navigable_items()
        if self.cursor_position < len(items) - 1:
            self.cursor_position += 1

    def key_k(self) -> None:
        """Move up with k key"""
        if self.app.command_mode:
            return
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def key_g(self) -> None:
        """Go to top with gg"""
        if self.app.command_mode:
            return
        pass  # Handled in on_key for double-press

    def key_G(self) -> None:
        """Go to bottom with G"""
        if self.app.command_mode:
            return
        items = self._get_navigable_items()
        self.cursor_position = len(items) - 1

    def key_ctrl_d(self) -> None:
        """Half page down"""
        if self.app.command_mode:
            return
        items = self._get_navigable_items()
        self.cursor_position = min(self.cursor_position + 5, len(items) - 1)

    def key_ctrl_u(self) -> None:
        """Half page up"""
        if self.app.command_mode:
            return
        self.cursor_position = max(self.cursor_position - 5, 0)

    def key_w(self) -> None:
        """Word forward - move down by 3"""
        if self.app.command_mode:
            return
        items = self._get_navigable_items()
        self.cursor_position = min(self.cursor_position + 3, len(items) - 1)

    def key_b(self) -> None:
        """Word backward - move up by 3"""
        if self.app.command_mode:
            return
        self.cursor_position = max(self.cursor_position - 3, 0)

    def key_d(self) -> None:
        """Prevent 'd' from triggering drafts when in comment screen"""
        if self.app.command_mode:
            return
        # Just prevent propagation - 'd' has no function in comment screen
        pass

    def on_key(self, event) -> None:
        """Handle g+g key combination for top and escape from input"""
        # Don't process keys if app is in command mode
        if self.app.command_mode:
            return

        if event.key == "escape":
            # If comment input has focus, unfocus it and return focus to screen
            try:
                comment_input = self.query_one("#comment-input", Input)
                if comment_input.has_focus:
                    comment_input.blur()
                    self.focus()
                    self.cursor_position = 0
                    event.prevent_default()
                    event.stop()
                    return
            except Exception:
                pass

        if event.key == "g":
            now = time.time()
            if hasattr(self, "last_g_time") and now - self.last_g_time < 0.5:
                self.cursor_position = 0
                event.prevent_default()
                delattr(self, "last_g_time")
            else:
                self.last_g_time = now

        # Prevent 'd' from propagating to app level (show drafts)
        if event.key == "d":
            event.prevent_default()
            event.stop()


class CommentScreen(Screen):
    """Screen wrapper for CommentFeed"""

    def __init__(self, post, **kwargs):
        super().__init__(**kwargs)
        self.post = post

    def compose(self) -> ComposeResult:
        yield CommentFeed(self.post, id="comment-feed")
        yield Static(
            "[i] Input [q] Back [j/k] Navigate", id="comment-footer", markup=False
        )


# ───────── Items ─────────


class NavigationItem(Static):
    def __init__(
        self, label: str, screen_name: str, number: int, active: bool = False, **kwargs
    ):
        # Ensure markup is enabled
        kwargs.setdefault("markup", True)
        super().__init__(**kwargs)
        self.label_text = label
        self.screen_name = screen_name
        self.number = number
        self.active = active
        if active:
            self.add_class("active")

    def render(self) -> str:
        if self.active:
            return f"[bold white]{self.number}: {self.label_text}[/]"
        else:
            return f"[#888888]{self.number}: {self.label_text}[/]"

    def on_click(self) -> None:
        self.app.switch_screen(self.screen_name)

    def set_active(self, is_active: bool) -> None:
        self.active = is_active
        (self.add_class if is_active else self.remove_class)("active")
        self.refresh()


class CommandItem(Static):
    def __init__(self, shortcut: str, description: str, **kwargs):
        super().__init__(**kwargs)
        self.shortcut = shortcut
        self.description = description

    def render(self) -> str:
        return f"{self.shortcut} - {self.description}"


class DraftItem(Static):
    """Display a saved draft in sidebar."""

    def __init__(self, draft: Dict, index: int, **kwargs):
        super().__init__(**kwargs)
        self.draft = draft
        self.draft_index = index
        self.border = "round"
        self.border_title = f"Draft {index + 1}"

    def render(self) -> str:
        """Render the draft item as text."""
        content = (
            self.draft["content"][:40] + "..."
            if len(self.draft["content"]) > 40
            else self.draft["content"]
        )
        time_ago = format_time_ago(self.draft["timestamp"])
        attachments_count = len(self.draft.get("attachments", []))
        attach_text = f" 📎{attachments_count}" if attachments_count > 0 else ""

        return f"{time_ago}\n{content}{attach_text}"

    def on_click(self) -> None:
        """Handle click on draft item - for now just open it."""
        self.app.action_open_draft(self.draft_index)


class ProfileDisplay(Static):
    """Display user profile."""

    def compose(self) -> ComposeResult:
        user = api.get_current_user()
        yield Static(
            f"@{user.username} • {user.display_name}", classes="profile-username"
        )


class ConversationItem(Static):
    def __init__(self, conversation, **kwargs):
        super().__init__(**kwargs)
        self.conversation = conversation

    def render(self) -> str:
        unread_marker = "🔵 " if self.conversation.unread else "  "
        time_ago = format_time_ago(self.conversation.timestamp)
        unread_text = "🔵 unread" if self.conversation.unread else ""
        return f"{unread_marker}@{self.conversation.username}\n  {self.conversation.last_message}\n  {time_ago} {unread_text}"


class ChatMessage(Static):
    def __init__(self, message, current_user: str = "yourname", **kwargs):
        super().__init__(**kwargs)
        self.message = message
        is_sent = message.sender == current_user
        self.add_class("sent" if is_sent else "received")

    def render(self) -> str:
        return f"{self.message.content}\n{format_time_ago(self.message.timestamp)}"


class PostItem(Static):
    """Simple non-interactive post display."""

    def __init__(self, post, reposted_by_you=False, **kwargs):
        super().__init__(**kwargs)
        self.post = post
        self.reposted_by_you = reposted_by_you
        self.has_video = hasattr(post, "video_path") and post.video_path

    def compose(self) -> ComposeResult:
        """Compose compact post."""
        time_ago = format_time_ago(self.post.timestamp)
        like_symbol = "❤️" if self.post.liked_by_user else "🤍"
        repost_symbol = "🔁" if self.post.reposted_by_user else "🔁"

        # Repost banner if this is a reposted post by you (either client-injected or backend-marked)
        if getattr(self, "reposted_by_you", False) or getattr(
            self.post, "reposted_by_user", False
        ):
            yield Static("🔁 Reposted by you", classes="repost-banner", markup=False)

        # Post header and content
        yield Static(
            f"@{self.post.author} • {time_ago}\n{self.post.content}",
            classes="post-text",
            markup=False,
        )

        # Video player if post has video
        if self.has_video and Path(self.post.video_path).exists():
            yield ASCIIVideoPlayer(
                frames_dir=self.post.video_path,
                fps=getattr(self.post, "video_fps", 2),
                classes="post-video",
            )

        # Post stats - non-interactive
        yield Static(
            f"{like_symbol} {self.post.likes}  {repost_symbol} {self.post.reposts}  💬 {self.post.comments}",
            classes="post-stats",
            markup=False,
        )

    def watch_has_class(self, has_class: bool) -> None:
        """Watch for class changes to handle cursor"""
        if has_class and "vim-cursor" in self.classes:
            # We have cursor focus
            self.border = "ascii"
            self.styles.background = "darkblue"
        else:
            # We don't have cursor focus
            self.border = ""
            self.styles.background = ""

    def on_click(self) -> None:
        """Handle click to open comment screen"""
        try:
            self.app.push_screen(CommentScreen(self.post))
        except Exception:
            pass


class NotificationItem(Static):
    def __init__(self, notification, **kwargs):
        super().__init__(**kwargs)
        self.notification = notification
        if not notification.read:
            self.add_class("unread")

    def render(self) -> str:
        t = format_time_ago(self.notification.timestamp)
        icon = {
            "mention": "📢",
            "like": "❤️",
            "repost": "🔁",
            "follow": "👥",
            "comment": "💬",
        }.get(self.notification.type, "🔵")
        n = self.notification
        if n.type == "mention":
            return f"@{n.actor} mentioned you • {t}\n{n.content}"
        if n.type == "like":
            return f"{icon} @{n.actor} liked your post • {t}\n{n.content}"
        if n.type == "repost":
            return f"{icon} @{n.actor} reposted • {t}\n{n.content}"
        if n.type == "follow":
            return f"{icon} @{n.actor} started following you • {t}"
        return f"{icon} @{n.actor} • {t}\n{n.content}"


class UserProfileCard(Static):
    """A user profile card for search results."""

    def __init__(
        self,
        username: str,
        display_name: str,
        bio: str,
        followers: int,
        following: int,
        ascii_pic: str,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.username = username
        self.display_name = display_name
        self.bio = bio
        self.followers = followers
        self.following = following
        self.ascii_pic = ascii_pic

    def compose(self) -> ComposeResult:
        card_container = Container(classes="user-card-container")

        with card_container:
            pic_container = Container(classes="user-card-pic")
            with pic_container:
                yield Static(self.ascii_pic, classes="user-card-avatar")
            yield pic_container

            info_container = Container(classes="user-card-info")
            with info_container:
                yield Static(self.display_name, classes="user-card-name")
                # Make username clickable as a button-like widget
                yield Button(
                    f"@{self.username}",
                    id=f"username-{self.username}",
                    classes="user-card-username-btn",
                )

                yield Static(self.bio, classes="user-card-bio")

                stats_container = Container(classes="user-card-stats")
                with stats_container:
                    yield Static(
                        f"{self.followers} Followers", classes="user-card-stat"
                    )
                    yield Static(
                        f"{self.following} Following", classes="user-card-stat"
                    )
                yield stats_container

                buttons_container = Container(classes="user-card-buttons")
                with buttons_container:
                    yield Button(
                        "Follow",
                        id=f"follow-{self.username}",
                        classes="user-card-button",
                    )
                    yield Button(
                        "Message",
                        id=f"message-{self.username}",
                        classes="user-card-button",
                    )
                    yield Button(
                        "View Profile",
                        id=f"view-{self.username}",
                        classes="user-card-button",
                    )
                yield buttons_container
            yield info_container

        yield card_container

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        btn_id = event.button.id

        if btn_id == f"view-{self.username}" or btn_id == f"username-{self.username}":
            self.app.action_view_user_profile(self.username)
        elif btn_id == f"follow-{self.username}":
            try:
                self.app.notify(f"✓ Following @{self.username}!", severity="success")
            except:
                pass
        elif btn_id == f"message-{self.username}":
            # Open messages screen with this user
            self.app.action_open_dm(self.username)


# ───────── Top Navbar ─────────


class TopNav(Horizontal):
    """Horizontal top navigation bar."""

    current = reactive("timeline")

    def __init__(self, current: str = "timeline", **kwargs):
        super().__init__(**kwargs)
        self.current = current

    def compose(self) -> ComposeResult:
        yield Label("[1] Timeline", classes="nav-item", id="nav-timeline")
        yield Label("[2] Discover", classes="nav-item", id="nav-discover")
        yield Label("[3] Notifs", classes="nav-item", id="nav-notifications")
        yield Label("[4] Messages", classes="nav-item", id="nav-messages")
        yield Label("[5] Settings", classes="nav-item", id="nav-settings")

    def on_mount(self) -> None:
        """Set initial active state when mounted."""
        self.update_active(self.current)

    def on_click(self, event) -> None:
        """Handle clicks on nav items."""
        # Map nav item IDs to screen names
        id_to_screen = {
            "nav-timeline": "timeline",
            "nav-discover": "discover",
            "nav-notifications": "notifications",
            "nav-messages": "messages",
            "nav-settings": "settings",
        }

        # Check which widget was clicked by examining all nav items
        for nav_id, screen_name in id_to_screen.items():
            try:
                nav_item = self.query_one(f"#{nav_id}", Label)
                # Check if the click coordinates are within this nav item's region
                if nav_item.region.contains(event.screen_x, event.screen_y):
                    self.app.switch_screen(screen_name)
                    break
            except Exception:
                pass

    def update_active(self, screen_name: str):
        """Update which nav item is marked as active."""
        self.current = screen_name

        # Map screen names to nav item IDs
        nav_map = {
            "timeline": "nav-timeline",
            "discover": "nav-discover",
            "notifications": "nav-notifications",
            "messages": "nav-messages",
            "settings": "nav-settings",
        }

        # Remove active class from all items
        for nav_id in nav_map.values():
            try:
                item = self.query_one(f"#{nav_id}", Label)
                item.remove_class("active")
            except Exception:
                pass

        # Add active class to current screen's nav item
        if screen_name in nav_map:
            try:
                item = self.query_one(f"#{nav_map[screen_name]}", Label)
                item.add_class("active")
            except Exception:
                pass


# ───────── Sidebar ─────────


class Sidebar(VerticalScroll):
    current_screen = reactive("timeline")

    def __init__(self, current: str = "timeline", show_nav: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.current_screen = current
        self.show_nav = show_nav

    def compose(self) -> ComposeResult:
        # Navigation box (optional, default hidden since we have top navbar)
        if self.show_nav:
            nav_container = Container(classes="navigation-box")
            nav_container.border_title = "Navigation [N]"
            with nav_container:
                yield NavigationItem(
                    "Timeline",
                    "timeline",
                    1,
                    self.current_screen == "timeline",
                    classes="nav-item",
                )
                yield NavigationItem(
                    "Discover",
                    "discover",
                    2,
                    self.current_screen == "discover",
                    classes="nav-item",
                )
                yield NavigationItem(
                    "Notifs",
                    "notifications",
                    3,
                    self.current_screen == "notifications",
                    classes="nav-item",
                )
                yield NavigationItem(
                    "Messages",
                    "messages",
                    4,
                    self.current_screen == "messages",
                    classes="nav-item",
                )
                yield NavigationItem(
                    "Settings",
                    "settings",
                    5,
                    self.current_screen == "settings",
                    classes="nav-item",
                )
            yield nav_container

        profile_container = Container(classes="profile-box")
        profile_container.border_title = "\\[p] Profile"
        with profile_container:
            yield ProfileDisplay()
        yield profile_container

        # Drafts section
        drafts_container = Container(classes="drafts-box")
        drafts_container.border_title = "\\[d] Drafts"
        with drafts_container:
            drafts = load_drafts()
            if drafts:
                # Show most recent first
                for i, draft in enumerate(reversed(drafts)):
                    yield DraftItem(draft, len(drafts) - 1 - i, classes="draft-item")
            else:
                yield Static(
                    "No drafts\n\nPress :n to create", classes="no-drafts-text"
                )
        yield drafts_container

        commands_container = Container(classes="commands-box")
        commands_container.border_title = "Commands"
        with commands_container:
            # Show only screen-specific commands to save space
            if self.current_screen == "messages":
                yield CommandItem(":n", "new msg", classes="command-item")
                yield CommandItem(":r", "reply", classes="command-item")
            elif self.current_screen in ("timeline", "discover"):
                yield CommandItem(":n", "new post", classes="command-item")
                yield CommandItem(":l", "like", classes="command-item")
                yield CommandItem(":rt", "repost", classes="command-item")
                yield CommandItem(":c", "comment", classes="command-item")
            elif self.current_screen == "notifications":
                yield CommandItem(":m", "mark read", classes="command-item")
                yield CommandItem(":ma", "mark all", classes="command-item")
            elif self.current_screen == "profile":
                yield CommandItem(":e", "edit", classes="command-item")
                yield CommandItem(":f", "follow", classes="command-item")
            elif self.current_screen == "settings":
                yield CommandItem(":w", "save", classes="command-item")
                yield CommandItem(":e", "edit", classes="command-item")

            # Common commands (limited to save space)
            yield CommandItem("p", "profile", classes="command-item")
            yield CommandItem("d", "drafts", classes="command-item")
            yield CommandItem("0", "main", classes="command-item")
        yield commands_container

    def update_active(self, screen_name: str):
        self.current_screen = screen_name
        for nav_item in self.query(".nav-item"):
            try:
                nav_item.set_active(nav_item.screen_name == screen_name)
            except Exception:
                pass

    def refresh_drafts(self):
        """Refresh the drafts display."""
        try:
            # Find drafts container by class
            drafts_container = self.query_one(".drafts-box", Container)
            # Remove all draft items
            for item in drafts_container.query(".draft-item, .no-drafts-text"):
                item.remove()

            # Add updated drafts
            drafts = load_drafts()
            if drafts:
                # Show most recent first
                for i, draft in enumerate(reversed(drafts)):
                    drafts_container.mount(
                        DraftItem(draft, len(drafts) - 1 - i, classes="draft-item")
                    )
            else:
                drafts_container.mount(
                    Static("No drafts\n\nPress :n to create", classes="no-drafts-text")
                )
        except Exception as e:
            print(f"Error refreshing drafts: {e}")

    def on_drafts_updated(self, message: DraftsUpdated) -> None:
        """Handle drafts updated message."""
        self.refresh_drafts()


# ───────── Modal Dialogs ─────────


class NewPostDialog(ModalScreen):
    """Modal dialog for creating a new post."""

    cursor_position = reactive(0)  # 0 = textarea, 1-5 = buttons

    def __init__(self, draft_content: str = "", draft_attachments: List = None):
        super().__init__()
        self.draft_content = draft_content
        self.draft_attachments = draft_attachments or []
        self.in_insert_mode = True  # Start in insert mode (textarea focused)

    def compose(self) -> ComposeResult:
        with Container(id="dialog-container"):
            yield Static("✨ Create New Post", id="dialog-title")
            yield TextArea(id="post-textarea")
            # Key hints for vim navigation
            yield Static(
                "\\[i] edit | \\[esc] navigate", id="vim-hints", classes="vim-hints"
            )
            # Status/attachments display area
            yield Static("", id="attachments-list", classes="attachments-list")
            yield Static("", id="status-message", classes="status-message")

            # Media attachment buttons
            with Container(id="media-buttons"):
                yield Button("📁 Files", id="attach-files")
                yield Button("🖼️ Photo", id="attach-photo")

            # Action buttons
            with Container(id="action-buttons"):
                yield Button("📤 Post", variant="primary", id="post-button")
                yield Button("💾 Save", id="draft-button")
                yield Button("❌ Cancel", id="cancel-button")

    def on_mount(self) -> None:
        """Focus the textarea when dialog opens."""
        textarea = self.query_one("#post-textarea", TextArea)

        # Load draft content if provided
        if self.draft_content:
            textarea.text = self.draft_content

        # Initialize attachments list
        self._attachments = (
            self.draft_attachments.copy() if self.draft_attachments else []
        )

        # Update attachments display
        self._update_attachments_display()

        textarea.focus()
        self.in_insert_mode = True
        self.cursor_position = 0

    def _get_navigable_buttons(self) -> list:
        """Get list of all navigable buttons in order."""
        buttons = []
        try:
            # Media buttons
            buttons.append(self.query_one("#attach-files", Button))
            buttons.append(self.query_one("#attach-photo", Button))
            # Action buttons
            buttons.append(self.query_one("#post-button", Button))
            buttons.append(self.query_one("#draft-button", Button))
            buttons.append(self.query_one("#cancel-button", Button))
        except:
            pass
        return buttons

    def _update_cursor(self) -> None:
        """Update visual cursor position."""
        buttons = self._get_navigable_buttons()

        # Remove vim-cursor from all buttons
        for btn in buttons:
            btn.remove_class("vim-cursor")

        textarea = self.query_one("#post-textarea", TextArea)

        if self.in_insert_mode:
            # In insert mode, textarea has focus
            textarea.focus()
        else:
            # In navigation mode, highlight current button
            if 1 <= self.cursor_position <= len(buttons):
                buttons[self.cursor_position - 1].add_class("vim-cursor")

    def watch_cursor_position(self, old: int, new: int) -> None:
        """React to cursor position changes."""
        self._update_cursor()

    def key_escape(self) -> None:
        """Exit insert mode and enter navigation mode."""
        if self.app.command_mode:
            return
        if self.in_insert_mode:
            self.in_insert_mode = False
            self.cursor_position = 1  # Start at first button
            self._update_cursor()

    def key_i(self) -> None:
        """Enter insert mode (focus textarea)."""
        if self.app.command_mode:
            return
        if not self.in_insert_mode:
            self.in_insert_mode = True
            self.cursor_position = 0
            self._update_cursor()

    def key_j(self) -> None:
        """Move cursor down (to next row)."""
        if self.app.command_mode:
            return
        if not self.in_insert_mode:
            buttons = self._get_navigable_buttons()
            if not buttons:
                return

            # Current position: 1-2 (media buttons) -> 3-5 (action buttons)
            if self.cursor_position in [1, 2]:  # Media buttons row
                # Move to corresponding action button (Files->Post, Photo->Save)
                if self.cursor_position == 1:
                    self.cursor_position = 3  # Files -> Post
                else:  # position == 2
                    self.cursor_position = 4  # Photo -> Save
            elif self.cursor_position in [3, 4, 5]:  # Already in action buttons row
                # Stay in same row, or wrap if desired
                pass

    def key_k(self) -> None:
        """Move cursor up (to previous row)."""
        if self.app.command_mode:
            return
        if not self.in_insert_mode:
            # Current position: 3-5 (action buttons) -> 1-2 (media buttons)
            if self.cursor_position in [3, 4, 5]:  # Action buttons row
                # Move to corresponding media button (Post->Files, Save->Photo, Cancel->Photo)
                if self.cursor_position == 3:
                    self.cursor_position = 1  # Post -> Files
                elif self.cursor_position == 4:
                    self.cursor_position = 2  # Save -> Photo
                else:  # position == 5 (Cancel)
                    self.cursor_position = 2  # Cancel -> Photo
            elif self.cursor_position in [1, 2]:  # Already in media buttons row
                # Stay in same row, or wrap if desired
                pass

    def key_h(self) -> None:
        """Move cursor left (within same row)."""
        if self.app.command_mode:
            return
        if not self.in_insert_mode:
            # Move left within the same row
            if self.cursor_position in [1, 2]:  # Media buttons row
                self.cursor_position = max(self.cursor_position - 1, 1)
            elif self.cursor_position in [3, 4, 5]:  # Action buttons row
                self.cursor_position = max(self.cursor_position - 1, 3)

    def key_l(self) -> None:
        """Move cursor right (within same row)."""
        if self.app.command_mode:
            return
        if not self.in_insert_mode:
            buttons = self._get_navigable_buttons()
            if not buttons:
                return

            # Move right within the same row
            if self.cursor_position in [1, 2]:  # Media buttons row
                self.cursor_position = min(self.cursor_position + 1, 2)
            elif self.cursor_position in [3, 4, 5]:  # Action buttons row
                self.cursor_position = min(self.cursor_position + 1, 5)

    def on_key(self, event) -> None:
        """Handle key events to prevent double-triggering."""
        if self.app.command_mode:
            return
        # In navigation mode, prevent Enter from bubbling to buttons
        if not self.in_insert_mode and event.key == "enter":
            event.prevent_default()
            event.stop()
            # Handle the button activation
            if self.cursor_position >= 1:
                buttons = self._get_navigable_buttons()
                if 1 <= self.cursor_position <= len(buttons):
                    button = buttons[self.cursor_position - 1]
                    self.on_button_pressed(Button.Pressed(button))

    def key_enter(self) -> None:
        """Activate the current button."""
        # This is now handled in on_key to prevent double-triggering
        pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = getattr(event.button, "id", None)

        if btn_id == "attach-files":
            self._show_status("📁 Opening file browser...")
            # Implement camera capture here
            # For now, we'll just open a file dialog as placeholder
            try:
                root = tk.Tk()
                root.withdraw()
                file_path = filedialog.askopenfilename(
                    title="Select a file",
                    filetypes=[
                        ("All files", "*.*"),
                        ("Images", "*.png *.jpg *.jpeg *.gif *.bmp"),
                        ("Documents", "*.pdf *.doc *.docx *.txt"),
                    ],
                )
                root.destroy()
                if file_path:
                    self._attachments.append(("file", file_path))
                    self._update_attachments_display()
                    self._show_status("✓ File added!")
            except Exception as e:
                self._show_status(f"⚠ Error: {str(e)}", error=True)

        elif btn_id == "attach-photo":
            self._show_status("🖼️ Opening photo selector...")
            try:
                root = tk.Tk()
                root.withdraw()
                file_path = filedialog.askopenfilename(
                    title="Select an image",
                    filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")],
                )
                root.destroy()
                if file_path:
                    try:
                        Image.open(file_path).verify()
                        self._attachments.append(("photo", file_path))
                        self._update_attachments_display()
                        self._show_status("✓ Photo added!")
                    except Exception:
                        self._show_status("⚠ Invalid image file", error=True)
            except Exception as e:
                self._show_status(f"⚠ Error: {str(e)}", error=True)

        elif btn_id == "post-button":
            self._handle_post()

        elif btn_id == "draft-button":
            self._handle_save_draft()

        elif btn_id == "cancel-button":
            self.dismiss(False)

    def _handle_post(self) -> None:
        """Handle posting the content."""
        textarea = self.query_one("#post-textarea", TextArea)
        content = textarea.text.strip()

        if not content and not self._attachments:
            self._show_status("⚠ Post cannot be empty!", error=True)
            return

        self._show_status("📤 Publishing post...")

        # Prepare attachments payload
        attachments_payload = [{"type": t, "path": p} for (t, p) in self._attachments]

        # Call API to create post
        try:
            new_post = api.create_post(content, attachments=attachments_payload)
            self._show_status("✓ Post published successfully!")
            try:
                self.app.notify("📤 Post published!", severity="success")
            except:
                pass
            self.dismiss(True)
        except TypeError:
            try:
                new_post = api.create_post(content, attachments_payload)
                self._show_status("✓ Post published successfully!")
                try:
                    self.app.notify("📤 Post published!", severity="success")
                except:
                    pass
                self.dismiss(True)
            except Exception as e:
                # Fallback without attachments
                try:
                    new_post = api.create_post(content)
                    self._show_status("✓ Post published (without attachments)")
                    try:
                        self.app.notify("📤 Post published!", severity="warning")
                    except:
                        pass
                    self.dismiss(True)
                except Exception as e:
                    self._show_status(f"⚠ Error: {str(e)}", error=True)

    def _handle_save_draft(self) -> None:
        """Handle saving the post as a draft."""
        textarea = self.query_one("#post-textarea", TextArea)
        content = textarea.text.strip()

        if not content and not self._attachments:
            self._show_status("⚠ Draft cannot be empty!", error=True)
            return

        self._show_status("💾 Saving draft...")

        # Save draft using the add_draft function
        try:
            add_draft(content, self._attachments)
            self._show_status("✓ Draft saved!")
            try:
                self.app.notify("💾 Draft saved successfully!", severity="success")
                # Post a custom message to refresh drafts everywhere
                self.app.post_message(DraftsUpdated())
            except:
                pass
            self.dismiss(False)
        except Exception as e:
            self._show_status(f"⚠ Error: {str(e)}", error=True)

    def _update_attachments_display(self) -> None:
        """Update the attachments display area."""
        try:
            widget = self.query_one("#attachments-list", Static)
            if not self._attachments:
                widget.update("")
                return
            lines = ["📎 Attachments:"]
            for i, (t, p) in enumerate(self._attachments, start=1):
                short = Path(p).name
                icon = {"file": "📁", "photo": "🖼️"}.get(t, "📎")
                lines.append(f"  {i}. {icon} {short}")
            widget.update("\n".join(lines))
        except Exception:
            pass

    def _show_status(self, message: str, error: bool = False) -> None:
        """Show a status message."""
        try:
            widget = self.query_one("#status-message", Static)
            if error:
                widget.styles.color = "#ff4444"
            else:
                widget.styles.color = "#4a9eff"
            widget.update(message)
            # Clear status after 3 seconds
            self.set_timer(3, lambda: widget.update(""))
        except Exception:
            pass


class DeleteDraftDialog(ModalScreen):
    """Modal dialog for confirming draft deletion."""
    cursor_position = reactive(0)  # 0 = Yes, 1 = Cancel

    def __init__(self, draft_index: int):
        super().__init__()
        self.draft_index = draft_index

    def on_mount(self) -> None:
        """Initialize selection"""
        self.cursor_position = 0  # Default to Yes

    def compose(self) -> ComposeResult:
        with Container(id="dialog-container"):
            yield Static("🗑️ Delete Draft?", id="dialog-title")
            yield Static(
                "Are you sure you want to delete this draft?", classes="dialog-message"
            )

            with Container(id="action-buttons"):
                confirm_btn = Button("✓ Yes, Delete", id="confirm-delete")
                cancel_btn = Button("❌ Cancel", id="cancel-delete")
                if self.cursor_position == 0:
                    confirm_btn.add_class("selected")
                else:
                    cancel_btn.add_class("selected")
                yield confirm_btn
                yield cancel_btn

    def key_h(self) -> None:
        """Select Yes (left)"""
        self.cursor_position = 0

    def key_l(self) -> None:
        """Select Cancel (right)"""
        self.cursor_position = 1

    def key_enter(self) -> None:
        """Execute the selected action"""
        if self.cursor_position == 0:
            delete_draft(self.draft_index)
            try:
                self.app.notify("🗑️ Draft deleted!", severity="success")
                # Post message to refresh drafts everywhere
                self.app.post_message(DraftsUpdated())
            except:
                pass
            self.dismiss(True)
        else:
            self.dismiss(False)

    def watch_cursor_position(self, old_position: int, new_position: int) -> None:
        """Update button styles based on cursor position"""
        try:
            confirm_btn = self.query_one("#confirm-delete", Button)
            cancel_btn = self.query_one("#cancel-delete", Button)

            if new_position == 0:
                confirm_btn.add_class("selected")
                cancel_btn.remove_class("selected")
            else:
                cancel_btn.add_class("selected")
                confirm_btn.remove_class("selected")
        except:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = getattr(event.button, "id", None)

        if btn_id == "confirm-delete":
            delete_draft(self.draft_index)
            try:
                self.app.notify("🗑️ Draft deleted!", severity="success")
                # Post message to refresh drafts everywhere
                self.app.post_message(DraftsUpdated())
            except:
                pass
            self.dismiss(True)
        elif btn_id == "cancel-delete":
            self.dismiss(False)


# ───────── Screens ─────────


class TimelineFeed(VerticalScroll):
    cursor_position = reactive(0)
    reposted_posts = reactive([])  # List of (post, timestamp) tuples
    scroll_y = reactive(0)  # Track scroll position
    _all_posts = []  # Cache all posts locally
    _displayed_count = 20  # Number of posts currently displayed
    _batch_size = 20  # Number of posts to load at a time
    _loading_more = False  # Flag to prevent multiple simultaneous loads

    def key_enter(self) -> None:
        """Open comment screen for focused post"""
        if self.app.command_mode:
            return
        self.open_comment_screen()

    def open_comment_screen(self):
        """Open the comment screen for the currently focused post"""
        logging.debug("open_comment_screen called in TimelineFeed")
        items = list(self.query(".post-item"))
        logging.debug(
            f"cursor_position={self.cursor_position}, total_items={len(items)}"
        )
        if 0 <= self.cursor_position < len(items):
            post_item = items[self.cursor_position]
            post = getattr(post_item, "post", None)
            logging.debug(
                f"Opening comment screen for post id={getattr(post, 'id', None)} author={getattr(post, 'author', None)}"
            )
            if post:
                self.app.push_screen(CommentScreen(post))
        else:
            logging.debug("Invalid cursor position in open_comment_screen")

    def compose(self) -> ComposeResult:
        # Fetch all posts once and cache them
        posts = api.get_timeline()
        reposted_sorted = sorted(self.reposted_posts, key=lambda x: x[1], reverse=True)
        self._all_posts = [p for p, _ in reposted_sorted] + posts

        unread_count = len(
            [
                p
                for p in self._all_posts
                if (datetime.now() - p.timestamp).seconds < 3600
            ]
        )
        self.border_title = "Main Timeline"
        yield Static(
            f"timeline.home | {unread_count} new posts | line 1",
            classes="panel-header",
            markup=False,
        )

        # Initially display only the first batch
        repost_count = len(reposted_sorted)
        for i, post in enumerate(self._all_posts[: self._displayed_count]):
            is_repost = i < repost_count
            post_item = PostItem(
                post, reposted_by_you=is_repost, classes="post-item", id=f"post-{i}"
            )
            if i == 0:
                post_item.add_class("vim-cursor")
            yield post_item

    def on_mount(self) -> None:
        self.watch(self, "cursor_position", self._update_cursor)
        self.watch(self, "scroll_y", self._check_scroll_load)

    def _check_scroll_load(self) -> None:
        """Check if we need to load more posts based on scroll position"""
        try:
            # Get the virtual size (total content height) and viewport size
            virtual_size = self.virtual_size.height
            container_size = self.container_size.height

            # If we're within 100 pixels of the bottom, load more
            if (
                virtual_size > 0
                and self.scroll_y + container_size >= virtual_size - 100
            ):
                self._load_more_posts()
        except Exception:
            pass

    def _load_more_posts(self) -> None:
        """Load the next batch of posts from cache"""
        if self._loading_more or self._displayed_count >= len(self._all_posts):
            return

        self._loading_more = True
        try:
            # Calculate how many new posts to add
            old_count = self._displayed_count
            self._displayed_count = min(
                self._displayed_count + self._batch_size, len(self._all_posts)
            )

            # Mount the new posts
            repost_count = len(
                [
                    p
                    for p, _ in sorted(
                        self.reposted_posts, key=lambda x: x[1], reverse=True
                    )
                ]
            )
            for i in range(old_count, self._displayed_count):
                post = self._all_posts[i]
                is_repost = i < repost_count
                post_item = PostItem(
                    post, reposted_by_you=is_repost, classes="post-item", id=f"post-{i}"
                )
                self.mount(post_item)
        finally:
            self._loading_more = False

    def _update_cursor(self) -> None:
        """Update the cursor position and check if we need to load more"""
        try:
            # Find all post items
            items = list(self.query(".post-item"))

            # Remove cursor from all items
            for i, item in enumerate(items):
                item.remove_class("vim-cursor")

            # Add cursor to focused item
            if 0 <= self.cursor_position < len(items):
                item = items[self.cursor_position]
                item.add_class("vim-cursor")
                # Ensure the cursor is visible
                self.scroll_to_widget(item, top=True)

                # Load more posts if we're near the end (within 5 posts)
                if self.cursor_position >= len(items) - 5:
                    self._load_more_posts()
        except Exception:
            pass

    def on_focus(self) -> None:
        """When the feed gets focus"""
        self.cursor_position = 0
        self._update_cursor()

    def on_blur(self) -> None:
        """When feed loses focus"""
        pass

    def on_scroll(self, event) -> None:
        """Update scroll position reactive when scrolling"""
        self.scroll_y = self.scroll_offset.y

    def key_j(self) -> None:
        """Move down with j key"""
        if self.app.command_mode:
            return
        items = list(self.query(".post-item"))
        if self.cursor_position < len(items) - 1:
            self.cursor_position += 1

    def key_k(self) -> None:
        """Move up with k key"""
        if self.app.command_mode:
            return
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def key_g(self) -> None:
        """Go to top with gg"""
        pass  # g is handled in on_key for double-press

    def key_G(self) -> None:
        """Go to bottom with G"""
        if self.app.command_mode:
            return
        items = list(self.query(".post-item"))
        self.cursor_position = len(items) - 1

    def key_ctrl_d(self) -> None:
        """Half page down"""
        if self.app.command_mode:
            return
        items = list(self.query(".post-item"))
        self.cursor_position = min(self.cursor_position + 5, len(items) - 1)

    def key_ctrl_u(self) -> None:
        """Half page up"""
        if self.app.command_mode:
            return
        self.cursor_position = max(self.cursor_position - 5, 0)

    def key_w(self) -> None:
        """Word forward - move down by 3"""
        if self.app.command_mode:
            return
        items = list(self.query(".post-item"))
        self.cursor_position = min(self.cursor_position + 3, len(items) - 1)

    def key_b(self) -> None:
        """Word backward - move up by 3"""
        if self.app.command_mode:
            return
        self.cursor_position = max(self.cursor_position - 3, 0)

    def on_key(self, event) -> None:
        """Handle g+g key combination for top and prevent escape from unfocusing"""
        # Don't process keys if app is in command mode
        if self.app.command_mode:
            return

        if event.key == "escape":
            # Prevent escape from unfocusing the feed
            event.prevent_default()
            event.stop()
            return
        if event.key == "g":
            now = time.time()
            if hasattr(self, "last_g_time") and now - self.last_g_time < 0.5:
                self.cursor_position = 0
                event.prevent_default()
                delattr(self, "last_g_time")
            else:
                self.last_g_time = now


class TimelineScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="timeline", id="sidebar")
        yield TimelineFeed(id="timeline-feed")


class DiscoverFeed(VerticalScroll):
    cursor_position = reactive(0)
    query_text = reactive("")
    scroll_y = reactive(0)  # Track scroll position
    _search_timer = None  # Timer for debouncing search
    _all_posts = []  # Cache all posts locally
    _filtered_posts = []  # Currently filtered posts
    _displayed_count = 20  # Number of posts currently displayed
    _batch_size = 20  # Number of posts to load at a time
    _loading_more = False  # Flag to prevent multiple simultaneous loads

    def key_enter(self) -> None:
        """Open comment screen when pressing enter on a post"""
        if self.app.command_mode:
            return
        self.open_comment_screen()

    def open_comment_screen(self) -> None:
        """Open the comment screen for the currently focused post"""
        try:
            items = list(self.query(".post-item"))
            # Adjust cursor position to account for search input at position 0
            post_idx = self.cursor_position - 1
            if 0 <= post_idx < len(items):
                post_item = items[post_idx]
                post = getattr(post_item, "post", None)
                if post:
                    self.app.push_screen(CommentScreen(post))
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        self.border_title = "Discover"

        # Search input at the top
        yield Input(
            placeholder="[/] Search posts, people, tags...",
            classes="discover-search-input",
            id="discover-search",
        )

        # Fetch all posts once and cache them
        self._all_posts = api.get_discover_posts()
        self._filtered_posts = self._all_posts.copy()
        self._displayed_count = min(self._batch_size, len(self._filtered_posts))

        yield Static(
            "discover.trending | explore posts | line 1",
            classes="panel-header",
            markup=False,
        )

        # Initially display only the first batch
        for i, post in enumerate(self._filtered_posts[: self._displayed_count]):
            post_item = PostItem(post, classes="post-item", id=f"discover-post-{i}")
            # Don't add cursor here, will be handled by _update_cursor
            yield post_item

    def on_mount(self) -> None:
        self.watch(self, "cursor_position", self._update_cursor)
        self.watch(self, "scroll_y", self._check_scroll_load)

    def _check_scroll_load(self) -> None:
        """Check if we need to load more posts based on scroll position"""
        try:
            # Get the virtual size (total content height) and viewport size
            virtual_size = self.virtual_size.height
            container_size = self.container_size.height

            # If we're within 100 pixels of the bottom, load more
            if (
                virtual_size > 0
                and self.scroll_y + container_size >= virtual_size - 100
            ):
                self._load_more_posts()
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes with debouncing"""
        if event.input.id == "discover-search":
            self.query_text = event.value

            # Cancel any existing timer
            if self._search_timer is not None:
                self._search_timer.stop()

            # Set a new timer to filter after 300ms of no typing
            self._search_timer = self.set_timer(0.3, self._filter_posts)

    def _filter_posts(self) -> None:
        """Filter posts based on search query from local cache"""
        try:
            # Filter from cached posts
            if self.query_text:
                q = self.query_text.lower()
                self._filtered_posts = [
                    p
                    for p in self._all_posts
                    if q in p.author.lower() or q in p.content.lower()
                ]
            else:
                self._filtered_posts = self._all_posts.copy()

            # Reset displayed count
            self._displayed_count = min(self._batch_size, len(self._filtered_posts))

            # Remove existing post items
            for item in self.query(".post-item"):
                item.remove()

            # Add filtered posts (only first batch)
            for i, post in enumerate(self._filtered_posts[: self._displayed_count]):
                post_item = PostItem(post, classes="post-item", id=f"discover-post-{i}")
                self.mount(post_item)

            # Reset cursor to search input (position 0)
            self.cursor_position = 0
        except Exception:
            pass

    def _load_more_posts(self) -> None:
        """Load the next batch of posts from filtered cache"""
        if self._loading_more or self._displayed_count >= len(self._filtered_posts):
            return

        self._loading_more = True
        try:
            # Calculate how many new posts to add
            old_count = self._displayed_count
            self._displayed_count = min(
                self._displayed_count + self._batch_size, len(self._filtered_posts)
            )

            # Mount the new posts
            for i in range(old_count, self._displayed_count):
                post = self._filtered_posts[i]
                post_item = PostItem(post, classes="post-item", id=f"discover-post-{i}")
                self.mount(post_item)
        finally:
            self._loading_more = False

    def key_slash(self) -> None:
        """Focus search input with / key"""
        if self.app.command_mode:
            return
        # Set cursor to position 0 and focus the input
        self.cursor_position = 0
        try:
            search_input = self.query_one("#discover-search", Input)
            search_input.focus()
        except Exception:
            pass

    def _get_navigable_items(self) -> list:
        """Get all navigable items (search input + posts)"""
        try:
            search_input = self.query_one("#discover-search", Input)
            post_items = list(self.query(".post-item"))
            return [search_input] + post_items
        except Exception:
            return []

    def _update_cursor(self) -> None:
        """Update the cursor position - includes search input + posts"""
        try:
            items = self._get_navigable_items()
            post_items = list(self.query(".post-item"))
            search_input = self.query_one("#discover-search", Input)

            # Remove cursor from all post items and search input
            for item in post_items:
                item.remove_class("vim-cursor")
            search_input.remove_class("vim-cursor")

            if 0 <= self.cursor_position < len(items):
                item = items[self.cursor_position]
                if isinstance(item, Input):
                    # Don't focus the input, just add visual indicator
                    item.add_class("vim-cursor")
                    # Make sure feed has focus so vim keys work
                    self.focus()
                else:
                    # Add cursor class to post
                    item.add_class("vim-cursor")
                self.scroll_to_widget(item, top=True)

                # Load more posts if we're near the end (within 5 posts)
                # Subtract 1 because position 0 is the search input
                if self.cursor_position > 0 and self.cursor_position >= len(items) - 5:
                    self._load_more_posts()
        except Exception:
            pass

    def on_focus(self) -> None:
        """When the feed gets focus"""
        self.cursor_position = 0
        self._update_cursor()

    def on_blur(self) -> None:
        """When feed loses focus"""
        pass

    def on_scroll(self, event) -> None:
        """Update scroll position reactive when scrolling"""
        self.scroll_y = self.scroll_offset.y

    def key_j(self) -> None:
        """Move down with j key"""
        if self.app.command_mode:
            return
        items = self._get_navigable_items()
        if self.cursor_position < len(items) - 1:
            self.cursor_position += 1

    def key_k(self) -> None:
        """Move up with k key"""
        if self.app.command_mode:
            return
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def key_g(self) -> None:
        """Go to top with gg"""
        if self.app.command_mode:
            return
        pass  # Handled in on_key for double-press

    def key_G(self) -> None:
        """Go to bottom with G"""
        if self.app.command_mode:
            return
        items = self._get_navigable_items()
        self.cursor_position = len(items) - 1

    def key_ctrl_d(self) -> None:
        """Half page down"""
        if self.app.command_mode:
            return
        items = self._get_navigable_items()
        self.cursor_position = min(self.cursor_position + 5, len(items) - 1)

    def key_ctrl_u(self) -> None:
        """Half page up"""
        if self.app.command_mode:
            return
        self.cursor_position = max(self.cursor_position - 5, 0)

    def key_w(self) -> None:
        """Word forward - move down by 3"""
        if self.app.command_mode:
            return
        items = self._get_navigable_items()
        self.cursor_position = min(self.cursor_position + 3, len(items) - 1)

    def key_b(self) -> None:
        """Word backward - move up by 3"""
        if self.app.command_mode:
            return
        self.cursor_position = max(self.cursor_position - 3, 0)

    def key_i(self) -> None:
        """Focus search input with i key (insert mode) when cursor is on it"""
        if self.app.command_mode:
            return
        if self.cursor_position == 0:
            try:
                search_input = self.query_one("#discover-search", Input)
                search_input.focus()
            except Exception:
                pass

    def on_key(self, event) -> None:
        """Handle g+g key combination for top and escape from search"""
        # Don't process keys if app is in command mode
        if self.app.command_mode:
            return

        if event.key == "escape":
            # If search input has focus, move cursor to first post and return focus to feed
            try:
                search_input = self.query_one("#discover-search", Input)
                if search_input.has_focus:
                    # Move cursor to first post (position 1)
                    self.cursor_position = 1
                    # Remove focus from input and give it back to feed
                    self.focus()
                    event.prevent_default()
                    event.stop()
                    return
            except Exception:
                pass

        # If cursor is on search input (position 0) and user types a letter/number/space
        # Focus the search input to start typing
        if self.cursor_position == 0:
            # Check if it's a typeable character (letter, number, space, punctuation except vim keys)
            if len(event.key) == 1 and event.key not in [
                "j",
                "k",
                "g",
                "G",
                "w",
                "b",
                "h",
                "l",
                "0",
                "1",
                "2",
                "3",
                "4",
                "5",
                "6",
                "p",
                "d",
                "i",
                "q",
                ":",
                "/",
            ]:
                try:
                    search_input = self.query_one("#discover-search", Input)
                    search_input.focus()
                    # Let the event propagate to the input
                    return
                except Exception:
                    pass

        if event.key == "g":
            now = time.time()
            if hasattr(self, "last_g_time") and now - self.last_g_time < 0.5:
                self.cursor_position = 0
                event.prevent_default()
                delattr(self, "last_g_time")
            else:
                self.last_g_time = now


class DiscoverScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="discover", id="sidebar")
        yield DiscoverFeed(id="discover-feed")


class NotificationsFeed(VerticalScroll):
    cursor_position = reactive(0)

    def compose(self) -> ComposeResult:
        notifications = api.get_notifications()
        unread_count = len([n for n in notifications if not n.read])
        self.border_title = "Notifications"
        yield Static(
            f"notifications.all | {unread_count} unread | line 1",
            classes="panel-header",
        )
        for i, notif in enumerate(notifications):
            item = NotificationItem(notif, classes="notification-item", id=f"notif-{i}")
            if i == 0:
                item.add_class("vim-cursor")
            yield item
        yield Static(
            "\n[j/k] Navigate [Enter] Open [:q] Quit",
            classes="help-text",
            markup=False,
        )

    def on_mount(self) -> None:
        """Watch for cursor position changes"""
        self.watch(self, "cursor_position", self._update_cursor)

    def _update_cursor(self) -> None:
        """Update the cursor position"""
        try:
            items = list(self.query(".notification-item"))
            for item in items:
                item.remove_class("vim-cursor")

            if 0 <= self.cursor_position < len(items):
                item = items[self.cursor_position]
                item.add_class("vim-cursor")
                self.scroll_to_widget(item)
        except Exception:
            pass

    def key_j(self) -> None:
        """Move down with j key"""
        if self.app.command_mode:
            return
        items = list(self.query(".notification-item"))
        if self.cursor_position < len(items) - 1:
            self.cursor_position += 1

    def key_k(self) -> None:
        """Move up with k key"""
        if self.app.command_mode:
            return
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def key_g(self) -> None:
        """Go to top with gg"""
        if self.app.command_mode:
            return
        pass  # Handled in on_key for double-press

    def key_G(self) -> None:
        """Go to bottom with G"""
        if self.app.command_mode:
            return
        items = list(self.query(".notification-item"))
        self.cursor_position = len(items) - 1

    def key_ctrl_d(self) -> None:
        """Half page down"""
        if self.app.command_mode:
            return
        items = list(self.query(".notification-item"))
        self.cursor_position = min(self.cursor_position + 5, len(items) - 1)

    def key_ctrl_u(self) -> None:
        """Half page up"""
        if self.app.command_mode:
            return
        self.cursor_position = max(self.cursor_position - 5, 0)

    def key_w(self) -> None:
        """Word forward - move down by 3"""
        if self.app.command_mode:
            return
        items = list(self.query(".notification-item"))
        self.cursor_position = min(self.cursor_position + 3, len(items) - 1)

    def key_b(self) -> None:
        """Word backward - move up by 3"""
        if self.app.command_mode:
            return
        self.cursor_position = max(self.cursor_position - 3, 0)

    def on_key(self, event) -> None:
        """Handle g+g key combination for top and prevent escape from unfocusing"""
        # Don't process keys if app is in command mode
        if self.app.command_mode:
            return

        if event.key == "escape":
            # Prevent escape from unfocusing the feed
            event.prevent_default()
            event.stop()
            return
        if event.key == "g":
            now = time.time()
            if hasattr(self, "last_g_time") and now - self.last_g_time < 0.5:
                self.cursor_position = 0
                event.prevent_default()
                delattr(self, "last_g_time")
            else:
                self.last_g_time = now


class NotificationsScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="notifications", id="sidebar")
        yield NotificationsFeed(id="notifications-feed")


class ConversationsList(VerticalScroll):
    cursor_position = reactive(0)
    can_focus = True

    def compose(self) -> ComposeResult:
        conversations = api.get_conversations()
        unread_count = len([c for c in conversations if c.unread])
        yield Static(f"conversations | {unread_count} unread", classes="panel-header")
        for i, conv in enumerate(conversations):
            item = ConversationItem(conv, classes="conversation-item", id=f"conv-{i}")
            if i == 0:
                item.add_class("vim-cursor")
            yield item

    def on_mount(self) -> None:
        """Watch for cursor position changes"""
        self.watch(self, "cursor_position", self._update_cursor)

    def _update_cursor(self) -> None:
        """Update the cursor position"""
        try:
            # Find all conversation items
            items = list(self.query(".conversation-item"))

            # Remove cursor from all items
            for item in items:
                item.remove_class("vim-cursor")

            # Add cursor to focused item
            if 0 <= self.cursor_position < len(items):
                item = items[self.cursor_position]
                item.add_class("vim-cursor")
                # Ensure the cursor is visible
                self.scroll_to_widget(item, top=True)
        except Exception:
            pass

    def on_focus(self) -> None:
        """When the list gets focus"""
        self.cursor_position = 0
        self._update_cursor()

    def on_blur(self) -> None:
        """When list loses focus"""
        pass

    def key_j(self) -> None:
        """Move down with j key"""
        if self.app.command_mode:
            return
        items = list(self.query(".conversation-item"))
        if self.cursor_position < len(items) - 1:
            self.cursor_position += 1

    def key_k(self) -> None:
        """Move up with k key"""
        if self.app.command_mode:
            return
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def key_g(self) -> None:
        """Go to top with gg"""
        if self.app.command_mode:
            return
        # g is handled in on_key for double-press
        pass

    def key_G(self) -> None:
        """Go to bottom with G"""
        if self.app.command_mode:
            return
        items = list(self.query(".conversation-item"))
        self.cursor_position = len(items) - 1

    def key_ctrl_d(self) -> None:
        """Half page down"""
        if self.app.command_mode:
            return
        items = list(self.query(".conversation-item"))
        self.cursor_position = min(self.cursor_position + 5, len(items) - 1)

    def key_ctrl_u(self) -> None:
        """Half page up"""
        if self.app.command_mode:
            return
        self.cursor_position = max(self.cursor_position - 5, 0)

    def key_w(self) -> None:
        """Word forward - move down by 3"""
        if self.app.command_mode:
            return
        items = list(self.query(".conversation-item"))
        self.cursor_position = min(self.cursor_position + 3, len(items) - 1)

    def key_b(self) -> None:
        """Word backward - move up by 3"""
        if self.app.command_mode:
            return
        self.cursor_position = max(self.cursor_position - 3, 0)

    def on_key(self, event) -> None:
        """Handle g+g key combination for top and prevent escape from unfocusing"""
        if self.app.command_mode:
            return
        if event.key == "escape":
            # Prevent escape from unfocusing the conversation list
            event.prevent_default()
            event.stop()
            return
        if event.key == "g":
            now = time.time()
            if hasattr(self, "last_g_time") and now - self.last_g_time < 0.5:
                self.cursor_position = 0
                event.prevent_default()
                delattr(self, "last_g_time")
            else:
                self.last_g_time = now


class ChatView(VerticalScroll):
    conversation_id = reactive("c1")
    conversation_username = reactive("alice")
    cursor_position = reactive(0)

    def __init__(self, conversation_id: str = "c1", username: str = "alice", **kwargs):
        super().__init__(**kwargs)
        self.conversation_id = conversation_id
        self.conversation_username = username

    def compose(self) -> ComposeResult:
        self.border_title = "[0] Chat"
        messages = api.get_conversation_messages(self.conversation_id)
        yield Static(
            f"@{self.conversation_username} | conversation", classes="panel-header"
        )
        for msg in messages:
            yield ChatMessage(msg, classes="chat-message")
        yield Static("-- INSERT --", classes="mode-indicator")
        yield Input(
            placeholder="Type message and press Enter… (Esc to cancel)",
            classes="message-input",
            id="message-input",
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "message-input":
            return
        text = event.value.strip()
        if not text:
            return

        new_msg = api.send_message(self.conversation_id, text)
        self.mount(ChatMessage(new_msg, classes="chat-message"), before=event.input)
        event.input.value = ""
        event.input.focus()
        self.scroll_end(animate=False)

    def watch_cursor_position(self, old_position: int, new_position: int) -> None:
        """Update the cursor when position changes"""
        # Remove cursor from old position
        messages = self.query(".chat-message")
        if old_position < len(messages):
            old_msg = messages[old_position]
            if "vim-cursor" in old_msg.classes:
                old_msg.remove_class("vim-cursor")

        # Add cursor to new position
        if new_position < len(messages):
            new_msg = messages[new_position]
            new_msg.add_class("vim-cursor")

            self.scroll_to_widget(new_msg)

    def key_j(self) -> None:
        """Vim-style down navigation"""
        if self.app.command_mode:
            return
        messages = self.query(".chat-message")
        if self.cursor_position < len(messages) - 1:
            self.cursor_position += 1

    def key_k(self) -> None:
        """Vim-style up navigation"""
        if self.app.command_mode:
            return
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def key_g(self) -> None:
        """Vim-style go to top"""
        if self.app.command_mode:
            return
        self.cursor_position = 0

    def key_G(self) -> None:
        """Vim-style go to bottom"""
        if self.app.command_mode:
            return
        messages = self.query(".chat-message")
        self.cursor_position = max(0, len(messages) - 1)


class MessagesScreen(Container):
    def __init__(self, username: str = None, **kwargs):
        super().__init__(**kwargs)
        self.dm_username = username

    def compose(self) -> ComposeResult:
        yield Sidebar(current="messages", id="sidebar")
        yield ConversationsList(id="conversations")

        # If a specific username is provided, open chat with them
        if self.dm_username:
            # Create a new conversation ID for this user
            conv_id = f"dm-{self.dm_username}"
            yield ChatView(
                conversation_id=conv_id, username=self.dm_username, id="chat"
            )
        else:
            yield ChatView(id="chat")

    def on_mount(self) -> None:
        """Add border to conversations list and update chat if DM"""
        conversations = self.query_one("#conversations", ConversationsList)
        conversations.border_title = "[6] Messages"

        # If opening a DM, update the chat header
        if self.dm_username:
            try:
                chat = self.query_one("#chat", ChatView)
                # Update the header to show we're chatting with this user
                header = chat.query_one(".panel-header", Static)
                header.update(f"@{self.dm_username} | new conversation")

                # Focus the message input
                self.call_after_refresh(self._focus_message_input)
            except:
                pass

    def _focus_message_input(self):
        """Focus the message input for new DM"""
        try:
            msg_input = self.query_one("#message-input", Input)
            msg_input.focus()
        except:
            pass


class SettingsPanel(VerticalScroll):
    cursor_position = reactive(0)

    def compose(self) -> ComposeResult:
        self.border_title = "Settings"
        settings = api.get_user_settings()
        yield Static("settings.profile | line 1", classes="panel-header")
        yield Static("\n→ Profile Picture (ASCII)", classes="settings-section-header")
        yield Static("Make ASCII Profile Picture from image file")
        yield Button(
            "Upload file", id="upload-profile-picture", classes="upload-profile-picture"
        )
        yield Static(
            f"{settings.ascii_pic}",
            id="profile-picture-display",
            classes="ascii-avatar",
        )

        yield Static("\n→ Account Information", classes="settings-section-header")
        yield Static(f"  Username:\n  @{settings.username}", classes="settings-field")
        yield Static(
            f"\n  Display Name:\n  {settings.display_name}", classes="settings-field"
        )
        yield Static(f"\n  Bio:\n  {settings.bio}", classes="settings-field")
        yield Static("\n→ OAuth Connections", classes="settings-section-header")
        github_status = "Connected" if settings.github_connected else "[:c] Connect"
        gitlab_status = "Connected" if settings.gitlab_connected else "[:c] Connect"
        google_status = "Connected" if settings.google_connected else "[:c] Connect"
        discord_status = "Connected" if settings.discord_connected else "[:c] Connect"
        yield Static(
            f"  [🟢] GitHub                                              {github_status}",
            classes="oauth-item",
        )
        yield Static(
            f"  [⚪] GitLab                                              {gitlab_status}",
            classes="oauth-item",
        )
        yield Static(
            f"  [⚪] Google                                              {google_status}",
            classes="oauth-item",
        )
        yield Static(
            f"  [⚪] Discord                                             {discord_status}",
            classes="oauth-item",
        )
        yield Static("\n→ Preferences", classes="settings-section-header")
        email_check = "✅" if settings.email_notifications else "⬜"
        online_check = "✅" if settings.show_online_status else "⬜"
        private_check = "✅" if settings.private_account else "⬜"
        yield Static(f"  {email_check} Email notifications", classes="checkbox-item")
        yield Static(f"  {online_check} Show online status", classes="checkbox-item")
        yield Static(f"  {private_check} Private account", classes="checkbox-item")
        yield Static(
            "\n  [:w] Save Changes     [:q] Cancel", classes="settings-actions"
        )
        yield Static(
            "\n:w - save  [:e] Edit field  [Tab] Next field  [Esc] Cancel",
            classes="help-text",
            markup=False,
        )

    def watch_cursor_position(self, old_position: int, new_position: int) -> None:
        """Update the cursor when position changes"""
        # We'll consider settings items that can be selected for cursor movement:
        selectable_classes = [
            ".upload-profile-picture",
            ".oauth-item",
            ".checkbox-item",
        ]

        items = []
        for cls in selectable_classes:
            items.extend(list(self.query(cls)))

        # Remove cursor from old position
        if old_position < len(items):
            old_item = items[old_position]
            if "vim-cursor" in old_item.classes:
                old_item.remove_class("vim-cursor")

        # Add cursor to new position
        if new_position < len(items):
            new_item = items[new_position]
            new_item.add_class("vim-cursor")
            self.scroll_to_widget(new_item)

    def key_j(self) -> None:
        """Vim-style down navigation"""
        if self.app.command_mode:
            return
        selectable_classes = [
            ".upload-profile-picture",
            ".oauth-item",
            ".checkbox-item",
        ]
        items = []
        for cls in selectable_classes:
            items.extend(list(self.query(cls)))

        if self.cursor_position < len(items) - 1:
            self.cursor_position += 1

    def key_k(self) -> None:
        """Vim-style up navigation"""
        if self.app.command_mode:
            return
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def key_g(self) -> None:
        """Vim-style go to top"""
        if self.app.command_mode:
            return
        self.cursor_position = 0

    def key_G(self) -> None:
        """Vim-style go to bottom"""
        if self.app.command_mode:
            return
        selectable_classes = [
            ".upload-profile-picture",
            ".oauth-item",
            ".checkbox-item",
        ]
        items = []
        for cls in selectable_classes:
            items.extend(list(self.query(cls)))
        self.cursor_position = max(0, len(items) - 1)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "upload-profile-picture":
            try:
                root = tk.Tk()
                root.withdraw()
                file_path = filedialog.askopenfilename(
                    title="Select an Image",
                    filetypes=[("Image files", "*.png *.jpg *.jpeg")],
                )
                root.destroy()

                if not file_path:
                    return

                script_path = Path("asciifer/asciifer.py")

                if not script_path.exists():
                    return

                output_text = "output.txt"
                output_image = "output.png"
                font_path = "/System/Library/Fonts/Monaco.ttf"

                cmd = [
                    sys.executable,
                    str(script_path),
                    "--output-text",
                    output_text,
                    "--output-image",
                    output_image,
                    "--font",
                    font_path,
                    "--font-size",
                    "24",
                    file_path,
                ]

                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    return

                if Path(output_text).exists():
                    with open(output_text, "r") as f:
                        lines = f.read().splitlines()

                    max_width = max((len(line) for line in lines), default=0)
                    max_lines = int(max_width / 2)
                    lines = lines[:max_lines]
                    ascii_art = "\n".join(lines)

                    settings = api.get_user_settings()
                    settings.ascii_pic = ascii_art
                    api.update_user_settings(settings)

                    try:
                        avatar = self.query_one("#profile-picture-display", Static)
                        avatar.update(ascii_art)
                        self.app.notify("Profile picture updated!", severity="success")
                    except Exception as e:
                        self.app.notify(f"Widget not found: {e}", severity="error")
                else:
                    self.app.notify("Output file not generated", severity="error")
            except Exception:
                pass


class SettingsScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="settings", id="sidebar")
        yield SettingsPanel(id="settings-panel")


class ProfilePanel(VerticalScroll):
    cursor_position = reactive(0)

    def compose(self) -> ComposeResult:
        self.border_title = "Profile"
        user = api.get_current_user()
        settings = api.get_user_settings()

        yield Static("profile | @yourname | line 1", classes="panel-header")

        profile_container = Container(classes="profile-center-container")

        with profile_container:
            yield Static(settings.ascii_pic, classes="profile-avatar-large")
            yield Static(f"{settings.display_name}", classes="profile-name-large")
            yield Static(f"@{settings.username}", classes="profile-username-display")

            stats_row = Container(classes="profile-stats-row")
            with stats_row:
                yield Static(f"{user.posts_count}\nPosts", classes="profile-stat-item")
                yield Static(
                    f"{user.following}\nFollowing", classes="profile-stat-item"
                )
                yield Static(
                    f"{user.followers}\nFollowers", classes="profile-stat-item"
                )
            yield stats_row

            bio_container = Container(classes="profile-bio-container")
            bio_container.border_title = "Bio"
            with bio_container:
                yield Static(f"{settings.bio}", classes="profile-bio-display")
            yield bio_container

        yield profile_container
        yield Static(
            "\n[j/k] Navigate  [:e] Edit Profile  [Esc] Back",
            classes="help-text",
            markup=False,
        )

    def key_j(self) -> None:
        """Scroll down with j key"""
        if self.app.command_mode:
            return
        self.scroll_down()

    def key_k(self) -> None:
        """Scroll up with k key"""
        if self.app.command_mode:
            return
        self.scroll_up()

    def key_g(self) -> None:
        """Go to top with gg"""
        if self.app.command_mode:
            return
        pass  # Handled in on_key for double-press

    def key_G(self) -> None:
        """Go to bottom with G"""
        if self.app.command_mode:
            return
        self.scroll_end(animate=False)

    def key_ctrl_d(self) -> None:
        """Half page down"""
        self.scroll_page_down()

    def key_ctrl_u(self) -> None:
        """Half page up"""
        self.scroll_page_up()

    def on_key(self, event) -> None:
        """Handle g+g key combination for top and escape from input"""
        if event.key == "escape":
            # If message input has focus, unfocus it and return focus to chat
            try:
                msg_input = self.query_one("#message-input", Input)
                if msg_input.has_focus:
                    self.focus()
                    event.prevent_default()
                    event.stop()
                    return
            except Exception:
                pass
            # Otherwise prevent escape from unfocusing the chat view
            event.prevent_default()
            event.stop()
            return
        if event.key == "g":
            now = time.time()
            if hasattr(self, "last_g_time") and now - self.last_g_time < 0.5:
                self.scroll_home(animate=False)
                event.prevent_default()
                delattr(self, "last_g_time")
            else:
                self.last_g_time = now


class ProfileScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="profile", id="sidebar")
        yield ProfilePanel(id="profile-panel")


class UserProfileViewPanel(VerticalScroll):
    """Panel for viewing another user's profile."""

    is_following = reactive(False)

    def __init__(self, username: str, **kwargs):
        super().__init__(**kwargs)
        self.username = username

    def compose(self) -> ComposeResult:
        self.border_title = f"@{self.username}"

        # Get user data from the dummy users or generate fake data
        user_data = self._get_user_data()

        yield Static(f"profile | @{self.username} | line 1", classes="panel-header")

        profile_container = Container(classes="profile-center-container")

        with profile_container:
            yield Static(user_data["ascii_pic"], classes="profile-avatar-large")
            yield Static(f"{user_data['display_name']}", classes="profile-name-large")
            yield Static(f"@{self.username}", classes="profile-username-display")

            stats_row = Container(classes="profile-stats-row")
            with stats_row:
                yield Static(
                    f"{user_data['posts_count']}\nPosts", classes="profile-stat-item"
                )
                yield Static(
                    f"{user_data['following']}\nFollowing", classes="profile-stat-item"
                )
                yield Static(
                    f"{user_data['followers']}\nFollowers", classes="profile-stat-item"
                )
            yield stats_row

            bio_container = Container(classes="profile-bio-container")
            bio_container.border_title = "Bio"
            with bio_container:
                yield Static(f"{user_data['bio']}", classes="profile-bio-display")
            yield bio_container

            # Action buttons
            buttons_container = Container(classes="profile-action-buttons")
            with buttons_container:
                follow_btn = Button(
                    "👥 Follow", id="follow-user-btn", classes="profile-action-btn"
                )
                yield follow_btn
                yield Button(
                    "💬 Message", id="message-user-btn", classes="profile-action-btn"
                )
            yield buttons_container

        yield profile_container

        # Recent posts section
        yield Static("\n→ Recent Posts", classes="section-header")
        posts = self._get_user_posts()
        for post in posts:
            yield PostItem(post, classes="post-item")

        yield Static(
            "\n[Esc] Back  [:f] Follow  [:m] Message", classes="help-text", markup=False
        )

    def _get_user_data(self) -> Dict:
        """Get or generate user data."""
        # Check if this is one of our dummy users
        try:
            discover_feed = self.app.query_one("#discover-feed", DiscoverFeed)

            for name, data in discover_feed._dummy_users.items():
                if data["username"] == self.username:
                    return {
                        "display_name": data["display_name"],
                        "bio": data["bio"],
                        "followers": data["followers"],
                        "following": data["following"],
                        "ascii_pic": data["ascii_pic"],
                        "posts_count": 42,  # Fake post count
                    }
        except:
            pass

        # Generate fake data for other users
        return {
            "display_name": self.username.replace("_", " ").title(),
            "bio": f"Hi! I'm {self.username}. Welcome to my profile! 👋",
            "followers": 156,
            "following": 89,
            "ascii_pic": "  [👀]\n  |◠ ◡ ◠|\n  |▓███▓|",
            "posts_count": 28,
        }

    def _get_user_posts(self) -> List:
        """Get fake posts from this user."""
        from api_interface import Post

        # Generate 3 fake posts
        posts = []
        for i in range(3):
            post = Post(
                id=f"fake-{self.username}-{i}",
                author=self.username,
                content=f"This is a sample post from @{self.username}! Post #{i + 1}",
                timestamp=datetime.now(),
                likes=10 + i * 5,
                reposts=2 + i,
                comments=3 + i,
                liked_by_user=False,
                reposted_by_user=False,
            )
            posts.append(post)

        return posts

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        btn_id = event.button.id

        if btn_id == "follow-user-btn":
            # Toggle follow state
            self.is_following = not self.is_following

            # Update button text and styling
            try:
                follow_btn = self.query_one("#follow-user-btn", Button)
                if self.is_following:
                    follow_btn.label = "✓ Following"
                    follow_btn.add_class("following")
                    # Increment following count in user profile
                    current_user = api.get_current_user()
                    current_user.following += 1
                    self.app.notify(
                        f"✓ Following @{self.username}!", severity="success"
                    )
                else:
                    follow_btn.label = "👥 Follow"
                    follow_btn.remove_class("following")
                    # Decrement following count in user profile
                    current_user = api.get_current_user()
                    current_user.following -= 1
                    self.app.notify(f"Unfollowed @{self.username}", severity="info")
            except:
                pass
        elif btn_id == "message-user-btn":
            # Open DM with this user
            self.app.action_open_dm(self.username)


class UserProfileViewScreen(Container):
    """Screen for viewing another user's profile."""

    def __init__(self, username: str, **kwargs):
        super().__init__(**kwargs)
        self.username = username

    def compose(self) -> ComposeResult:
        yield Sidebar(current="discover", id="sidebar")
        yield UserProfileViewPanel(username=self.username, id="user-profile-panel")


class DraftsPanel(VerticalScroll):
    """Main panel for viewing all drafts."""

    cursor_position = reactive(0)
    selected_action = reactive("open")  # "open" or "delete"

    def compose(self) -> ComposeResult:
        self.border_title = "Drafts"
        drafts = load_drafts()

        yield Static(
            f"drafts.all | {len(drafts)} saved | line 1", classes="panel-header"
        )

        if not drafts:
            yield Static(
                "\n📝 No drafts saved yet\n\nPress :n to create a new post",
                classes="no-drafts-message",
            )
        else:
            # Show most recent first
            for i, draft in enumerate(reversed(drafts)):
                actual_index = len(drafts) - 1 - i
                box = self._create_draft_box(draft, actual_index)
                if i == 0:
                    box.add_class("vim-cursor")
                yield box

        yield Static(
            "\n[j/k] Navigate [h/l] Select Action [Enter] Execute [:o#/:x#] Direct [Esc] Back",
            classes="help-text",
            markup=False,
        )

    def on_mount(self) -> None:
        """Watch for cursor position changes"""
        self.watch(self, "cursor_position", self._update_cursor)
        self.watch(self, "selected_action", self._update_action_highlight)

    def _update_cursor(self) -> None:
        """Update the cursor position"""
        try:
            items = list(self.query(".draft-box"))
            for item in items:
                item.remove_class("vim-cursor")

            if 0 <= self.cursor_position < len(items):
                item = items[self.cursor_position]
                item.add_class("vim-cursor")
                self.scroll_to_widget(item)
                # Update action highlight for new position
                self._update_action_highlight()
        except Exception:
            pass

    def _update_action_highlight(self) -> None:
        """Update which action button is highlighted"""
        try:
            # Get all action buttons
            open_buttons = list(self.query(".draft-action-btn"))
            delete_buttons = list(self.query(".draft-action-btn-delete"))

            # Remove highlight from all buttons
            for btn in open_buttons + delete_buttons:
                btn.remove_class("action-selected")

            # Add highlight to selected button in current draft
            if 0 <= self.cursor_position < len(open_buttons):
                if self.selected_action == "open":
                    open_buttons[self.cursor_position].add_class("action-selected")
                else:
                    delete_buttons[self.cursor_position].add_class("action-selected")
        except Exception:
            pass

    def key_j(self) -> None:
        """Move down with j key"""
        if self.app.command_mode:
            return
        items = list(self.query(".draft-box"))
        if self.cursor_position < len(items) - 1:
            self.cursor_position += 1
            self.selected_action = "open"  # Reset to open when moving

    def key_k(self) -> None:
        """Move up with k key"""
        if self.app.command_mode:
            return
        if self.cursor_position > 0:
            self.cursor_position -= 1
            self.selected_action = "open"  # Reset to open when moving

    def key_g(self) -> None:
        """Go to top with gg"""
        if self.app.command_mode:
            return
        pass  # Handled in on_key for double-press

    def key_G(self) -> None:
        """Go to bottom with G"""
        if self.app.command_mode:
            return
        items = list(self.query(".draft-box"))
        self.cursor_position = len(items) - 1

    def key_ctrl_d(self) -> None:
        """Half page down"""
        if self.app.command_mode:
            return
        items = list(self.query(".draft-box"))
        self.cursor_position = min(self.cursor_position + 5, len(items) - 1)

    def key_ctrl_u(self) -> None:
        """Half page up"""
        if self.app.command_mode:
            return
        self.cursor_position = max(self.cursor_position - 5, 0)

    def key_w(self) -> None:
        """Word forward - move down by 3"""
        if self.app.command_mode:
            return
        items = list(self.query(".draft-box"))
        self.cursor_position = min(self.cursor_position + 3, len(items) - 1)

    def key_b(self) -> None:
        """Word backward - move up by 3"""
        if self.app.command_mode:
            return
        self.cursor_position = max(self.cursor_position - 3, 0)

    def key_h(self) -> None:
        """Select 'open' action with h key"""
        if self.app.command_mode:
            return
        self.selected_action = "open"

    def key_l(self) -> None:
        """Select 'delete' action with l key"""
        if self.app.command_mode:
            return
        self.selected_action = "delete"



    def on_key(self, event) -> None:
        """Handle g+g key combination for top, enter for actions, and escape for command mode"""
        if event.key == "escape":
            # If in command mode, let the app handle it (don't stop propagation)
            if self.app.command_mode:
                # Don't prevent or stop - let it bubble up to app's on_key
                return
            # Otherwise prevent escape from unfocusing the drafts panel
            event.prevent_default()
            event.stop()
            return
        if event.key == "enter":
            if self.app.command_mode:
                return
            event.prevent_default()
            event.stop()
            try:
                drafts = load_drafts()
                if 0 <= self.cursor_position < len(drafts):
                    actual_index = len(drafts) - 1 - self.cursor_position
                    if self.selected_action == "open":
                        self.app.action_open_draft(actual_index)
                    else:
                        self.app.push_screen(DeleteDraftDialog(actual_index))
            except Exception:
                pass
            return
        if event.key == "g":
            now = time.time()
            if hasattr(self, "last_g_time") and now - self.last_g_time < 0.5:
                self.cursor_position = 0
                event.prevent_default()
                delattr(self, 'last_g_time')
            else:
                self.last_g_time = now

    def _create_draft_box(self, draft: Dict, index: int) -> Container:
        """Create a nice box for displaying a draft."""
        box = Container(classes="draft-box")
        box.border = "round"
        box.border_title = f"💾 Draft {index + 1}"

        # Header with timestamp
        time_ago = format_time_ago(draft["timestamp"])
        box.mount(Static(f"⏰ Saved {time_ago}", classes="draft-timestamp"))

        # Content preview
        content = draft["content"]
        preview = content if len(content) <= 200 else content[:200] + "..."
        box.mount(Static(preview, classes="draft-content-preview"))

        # Attachments info
        attachments = draft.get("attachments", [])
        if attachments:
            attach_text = f"📎 {len(attachments)} attachment(s)"
            box.mount(Static(attach_text, classes="draft-attachments-info"))

        # Action buttons
        actions_container = Container(classes="draft-actions")
        actions_container.mount(
            Button(f"✏️ Open", id=f"open-draft-{index}", classes="draft-action-btn")
        )
        actions_container.mount(
            Button(
                f"🗑️ Delete",
                id=f"delete-draft-{index}",
                classes="draft-action-btn-delete",
            )
        )
        box.mount(actions_container)

        return box

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle draft action buttons."""
        btn_id = event.button.id

        if btn_id and btn_id.startswith("open-draft-"):
            index = int(btn_id.split("-")[-1])
            self.app.action_open_draft(index)
        elif btn_id and btn_id.startswith("delete-draft-"):
            index = int(btn_id.split("-")[-1])
            self.app.push_screen(DeleteDraftDialog(index))

    def on_drafts_updated(self, message: DraftsUpdated) -> None:
        """Handle drafts updated message - refresh the panel."""
        # Remove all children and re-compose
        self.remove_children()
        drafts = load_drafts()

        self.mount(
            Static(f"drafts.all | {len(drafts)} saved | line 1", classes="panel-header")
        )

        if not drafts:
            self.mount(
                Static(
                    "\n📝 No drafts saved yet\n\nPress :n to create a new post",
                    classes="no-drafts-message",
                )
            )
        else:
            # Show most recent first
            for i, draft in enumerate(reversed(drafts)):
                actual_index = len(drafts) - 1 - i
                box = self._create_draft_box(draft, actual_index)
                if i == 0:
                    box.add_class("vim-cursor")
                self.mount(box)

        self.mount(
            Static(
                "\n[j/k] Navigate [h/l] Select Action [Enter] Execute [:o#/:x#] Direct [Esc] Back",
                classes="help-text",
                markup=False,
            )
        )

        # Reset cursor position
        self.cursor_position = 0


class DraftsScreen(Container):
    """Screen for viewing and managing all drafts."""

    def compose(self) -> ComposeResult:
        yield Sidebar(current="drafts", id="sidebar")
        yield DraftsPanel(id="drafts-panel")


class Proj101App(App):
    CSS_PATH = "main.tcss"

    # Disable dark mode toggle - we use our own colors
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        # Basic app controls
        Binding("q", "quit", "Quit", show=False),
        Binding("i", "insert_mode", "Insert", show=True),
        Binding("escape", "normal_mode", "Normal", show=False),
        # Screen navigation
        Binding("0", "focus_main_content", "Main Content", show=False),
        Binding("1", "show_timeline", "Timeline", show=False),
        Binding("2", "show_discover", "Discover", show=False),
        Binding("3", "show_notifications", "Notifications", show=False),
        Binding("4", "show_messages", "Messages", show=False),
        Binding("5", "show_settings", "Settings", show=False),
        Binding("p", "show_profile", "Profile", show=False),
        Binding("d", "show_drafts", "Drafts", show=False),
        Binding("6", "focus_messages", "Messages List", show=False),
        Binding("shift+n", "focus_navigation", "Nav Focus", show=False),
        Binding("colon", "show_command_bar", "Command", show=False),
        # Vim-style navigation bindings
        Binding("j", "vim_down", "Down", show=False),
        Binding("k", "vim_up", "Up", show=False),
        Binding("h", "vim_left", "Left", show=False),
        Binding("l", "vim_right", "Right", show=False),
        Binding("w", "vim_word_forward", "Word Forward", show=False),
        Binding("b", "vim_word_backward", "Word Backward", show=False),
        Binding("G", "vim_bottom", "Bottom", show=False),
        Binding("ctrl+d", "vim_half_page_down", "Half Page Down", show=False),
        Binding("ctrl+u", "vim_half_page_up", "Half Page Up", show=False),
        Binding("ctrl+f", "vim_page_down", "Page Down", show=False),
        Binding("ctrl+b", "vim_page_up", "Page Up", show=False),
        Binding("$", "vim_line_end", "End of Line", show=False),
        Binding("^", "vim_line_start", "Start of Line", show=False),
    ]

    current_screen_name = reactive("timeline")
    command_mode = reactive(False)
    command_text = reactive("")
    _switching = False  # Flag to prevent concurrent screen switches

    def watch_command_text(self, new_text: str) -> None:
        """Update command bar whenever command_text changes"""
        try:
            command_bar = self.query_one("#command-bar", Static)
            command_bar.update(new_text)
        except:
            pass

    def compose(self) -> ComposeResult:
        yield Static("tuitter [timeline] @yourname", id="app-header", markup=False)
        yield TopNav(id="top-navbar", current="timeline")
        yield TimelineScreen(id="screen-container")
        yield Static(
            "[1-5] Screens [p] Profile [d] Drafts [j/k] Navigate [:n] New Post [:q] Quit",
            id="app-footer",
            markup=False,
        )
        yield Static("", id="command-bar")

    def on_mount(self) -> None:
        """Focus the main timeline feed on app startup"""
        self.call_after_refresh(self._focus_initial_content)

    def _focus_initial_content(self) -> None:
        """Helper to focus the timeline feed after initial render"""
        try:
            timeline_feed = self.query_one("#timeline-feed", TimelineFeed)
            timeline_feed.add_class("vim-mode-active")
            timeline_feed.focus()
            # Ensure the first post has the cursor
            timeline_feed.cursor_position = 0
        except Exception:
            pass

    def switch_screen(self, screen_name: str, **kwargs):
        # Prevent concurrent screen switches
        if self._switching:
            return
        if screen_name == self.current_screen_name and not kwargs:
            return
        screen_map = {
            "timeline": (
                TimelineScreen,
                "[1-5] Screens [p] Profile [d] Drafts [j/k] Navigate [:n] New Post [:q] Quit",
            ),
            "discover": (
                DiscoverScreen,
                "[1-5] Screens [p] Profile [d] Drafts [j/k] Navigate [/] Search [:n] New Post [:q] Quit",
            ),
            "notifications": (
                NotificationsScreen,
                "[1-5] Screens [p] Profile [d] Drafts [j/k] Navigate [:q] Quit",
            ),
            "messages": (
                MessagesScreen,
                "[0] Chat [6] Messages [1-5] Screens [p] Profile [d] Drafts [j/k] Navigate [:n] New Message [:q] Quit",
            ),
            "profile": (
                ProfileScreen,
                "[1-5] Screens [d] Drafts [j/k] Navigate [:q] Quit",
            ),
            "settings": (
                SettingsScreen,
                "[1-5] Screens [p] Profile [d] Drafts [j/k] Navigate [:q] Quit",
            ),
            "drafts": (
                DraftsScreen,
                "[1-5] Screens [p] Profile [j/k] Navigate [h/l] Select [Enter] Execute [:q] Quit",
            ),
            "user_profile": (
                UserProfileViewScreen,
                "[1-5] Screens [p] Profile [d] Drafts [:m] Message [:q] Quit",
            ),
        }
        if screen_name in screen_map:
            self._switching = True  # Set flag to prevent concurrent switches

            for container in self.query("#screen-container"):
                container.remove()
            ScreenClass, footer_text = screen_map[screen_name]
            self.call_after_refresh(
                self.mount, ScreenClass(id="screen-container", **kwargs)
            )

            # Update header based on screen
            if screen_name == "user_profile" and "username" in kwargs:
                self.query_one("#app-header", Static).update(
                    f"tuitter [@{kwargs['username']}] @yourname"
                )
            elif screen_name == "messages" and "username" in kwargs:
                self.query_one("#app-header", Static).update(
                    f"tuitter [dm:@{kwargs['username']}] @yourname"
                )
            else:
                self.query_one("#app-header", Static).update(
                    f"tuitter [{screen_name}] @yourname"
                )

            self.query_one("#app-footer", Static).update(footer_text)
            self.current_screen_name = screen_name

            # Update top navbar
            try:
                self.query_one("#top-navbar", TopNav).update_active(screen_name)
            except Exception:
                pass

            # Update sidebar (if it exists)
            try:
                sidebar = self.query_one("#sidebar", Sidebar)
                # For user profile view, highlight discover in sidebar
                if screen_name == "user_profile":
                    sidebar.update_active("discover")
                elif screen_name == "messages":
                    sidebar.update_active("messages")
                else:
                    sidebar.update_active(screen_name)
            except Exception:
                pass

            # Focus the main content area after screen switch
            self.call_after_refresh(self._focus_main_content_for_screen, screen_name)

            # Reset the switching flag after a brief delay
            self.set_timer(0.1, lambda: setattr(self, "_switching", False))

    def _focus_main_content_for_screen(self, screen_name: str) -> None:
        """Focus the main content feed/panel for the current screen"""
        try:
            # Map screen names to their main content widget IDs
            content_map = {
                "timeline": "#timeline-feed",
                "discover": "#discover-feed",
                "notifications": "#notifications-feed",
                "messages": "#chat",
                "profile": "#profile-panel",
                "settings": "#settings-panel",
                "drafts": "#drafts-panel",
                "user_profile": "#user-profile-panel",
            }

            if screen_name in content_map:
                widget_id = content_map[screen_name]
                widget = self.query_one(widget_id)
                widget.focus()

                # Reset cursor position to 0 for feeds with cursor navigation
                if hasattr(widget, "cursor_position"):
                    widget.cursor_position = 0
        except Exception:
            pass

    def action_quit(self) -> None:
        self.exit()

    def action_insert_mode(self) -> None:
        try:
            self.query_one("#message-input", Input).focus()
        except Exception:
            pass

    def action_normal_mode(self) -> None:
        self.screen.focus_next()

    def action_show_timeline(self) -> None:
        self.switch_screen("timeline")

    def action_show_discover(self) -> None:
        self.switch_screen("discover")

    def action_show_notifications(self) -> None:
        self.switch_screen("notifications")

    def action_show_messages(self) -> None:
        self.switch_screen("messages")

    def action_show_settings(self) -> None:
        self.switch_screen("settings")

    def action_show_profile(self) -> None:
        """Show the user's own profile screen."""
        self.switch_screen("profile")

    def action_show_drafts(self) -> None:
        """Show the drafts screen."""
        self.switch_screen("drafts")

    def action_view_user_profile(self, username: str) -> None:
        """View another user's profile."""
        self.switch_screen("user_profile", username=username)

    def action_open_dm(self, username: str) -> None:
        """Open a DM with a specific user."""
        try:
            self.notify(f"💬 Opening chat with @{username}...", severity="info")
        except:
            pass

        # Switch to messages screen with this specific user
        self.switch_screen("messages", username=username)

        # Focus will be set in MessagesScreen.on_mount()

    def action_focus_navigation(self) -> None:
        try:
            topnav = self.query_one("#top-navbar", TopNav)
            first = topnav.query_one(".nav-item", NavigationItem)
            first.focus()
        except Exception:
            pass

    def action_focus_main_content(self) -> None:
        """Focus the main content area when pressing 0"""
        try:
            target_id = None
            if self.current_screen_name == "timeline":
                target_id = "#timeline-feed"
            elif self.current_screen_name == "discover":
                target_id = "#discover-feed"
            elif self.current_screen_name == "notifications":
                target_id = "#notifications-feed"
            elif self.current_screen_name == "messages":
                target_id = "#chat"
            elif self.current_screen_name == "settings":
                target_id = "#settings-panel"
            elif self.current_screen_name == "profile":
                target_id = "#profile-panel"
            elif self.current_screen_name == "drafts":
                target_id = "#drafts-panel"
            elif self.current_screen_name == "user_profile":
                target_id = "#user-profile-panel"

            if target_id:
                panel = self.query_one(target_id)
                panel.add_class("vim-mode-active")
                panel.focus()

        except Exception:
            pass

    def action_focus_messages(self) -> None:
        """Focus the messages list when pressing 6"""
        try:
            if self.current_screen_name == "messages":
                conversations = self.query_one("#conversations", ConversationsList)
                conversations.border_title = "[6] Messages"
                conversations.add_class("vim-mode-active")
                conversations.focus()
                # Reset cursor position to ensure it's visible
                conversations.cursor_position = 0
                conversations._update_cursor()
        except Exception:
            pass

    # Vim-style navigation actions - these forward to focused widget
    def action_vim_down(self) -> None:
        """Move down (j key)"""
        # The key will be handled by the focused widget's key_j method if it exists
        pass

    def action_vim_up(self) -> None:
        """Move up (k key)"""
        # The key will be handled by the focused widget's key_k method if it exists
        pass

    def action_vim_left(self) -> None:
        """Move left (h key)"""
        # The key will be handled by the focused widget's key_h method if it exists
        pass

    def action_vim_right(self) -> None:
        """Move right (l key)"""
        # The key will be handled by the focused widget's key_l method if it exists
        pass

    def action_vim_word_forward(self) -> None:
        """Move forward one word (w key)"""
        # The key will be handled by the focused widget's key_w method if it exists
        pass

    def action_vim_word_backward(self) -> None:
        """Move backward one word (b key)"""
        # The key will be handled by the focused widget's key_b method if it exists
        pass

    def action_vim_top(self) -> None:
        """Move to the top (gg key)"""
        # This is handled by the on_key method for the double-g press
        pass

    def action_vim_bottom(self) -> None:
        """Move to the bottom (G key)"""
        focused = self.focused
        if focused and hasattr(focused, "key_G"):
            focused.key_G()

    def action_vim_half_page_down(self) -> None:
        """Move half page down (Ctrl+d)"""
        # The key will be handled by the focused widget's key_ctrl_d method if it exists
        pass

    def action_vim_half_page_up(self) -> None:
        """Move half page up (Ctrl+u)"""
        # The key will be handled by the focused widget's key_ctrl_u method if it exists
        pass

    def action_vim_page_down(self) -> None:
        """Move one page down (Ctrl+f)"""
        # The key will be handled by the focused widget's key_ctrl_f method if it exists
        pass

    def action_vim_page_up(self) -> None:
        """Move one page up (Ctrl+b)"""
        # The key will be handled by the focused widget's key_ctrl_b method if it exists
        pass

    def action_vim_line_start(self) -> None:
        """Go to start of line (^ key)"""
        # Will be implemented in the content panels
        pass

    def action_vim_line_end(self) -> None:
        """Go to end of line ($ key)"""
        # Will be implemented in the content panels
        pass

    def action_show_command_bar(self) -> None:
        try:
            command_bar = self.query_one("#command-bar", Static)
            command_bar.styles.display = "block"
            self.command_text = ":"
            self.command_mode = True
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        # Don't interfere with command input typing
        pass

    def action_new_post(self) -> None:
        """Show the new post dialog."""

        def check_refresh(result):
            if result:
                if self.current_screen_name == "timeline":
                    self.switch_screen("timeline")

        self.push_screen(NewPostDialog(), check_refresh)

    def action_open_draft(self, draft_index: int) -> None:
        """Open a draft in the new post dialog."""
        try:
            drafts = load_drafts()
            if 0 <= draft_index < len(drafts):
                draft = drafts[draft_index]

                def check_refresh(result):
                    if result:
                        # Post was published, delete the draft
                        delete_draft(draft_index)
                        try:
                            # Post message to refresh drafts everywhere
                            self.post_message(DraftsUpdated())
                        except:
                            pass
                        if self.current_screen_name == "timeline":
                            self.switch_screen("timeline")
                        elif self.current_screen_name == "drafts":
                            self.switch_screen("drafts")
                    else:
                        # Dialog was closed without posting, refresh drafts in case it was saved
                        try:
                            # Post message to refresh drafts everywhere
                            self.post_message(DraftsUpdated())
                        except:
                            pass
                        # Refresh drafts screen if we're on it
                        if self.current_screen_name == "drafts":
                            self.switch_screen("drafts")

                self.push_screen(
                    NewPostDialog(
                        draft_content=draft["content"],
                        draft_attachments=draft.get("attachments", []),
                    ),
                    check_refresh,
                )
            else:
                self.notify("Draft not found", severity="error")
        except Exception as e:
            self.notify(f"Error opening draft: {str(e)}", severity="error")

    def on_key(self, event) -> None:
        if self.command_mode:
            # CRITICAL: Stop event propagation IMMEDIATELY when in command mode
            event.prevent_default()
            event.stop()

            if event.key == "escape":
                try:
                    command_bar = self.query_one("#command-bar", Static)
                    command_bar.styles.display = "none"
                except:
                    pass
                self.command_text = ""
                self.command_mode = False
            elif event.key == "enter":
                command = self.command_text.strip()
                try:
                    command_bar = self.query_one("#command-bar", Static)
                    command_bar.styles.display = "none"
                except:
                    pass
                self.command_mode = False

                # Process command
                if command.startswith(":"):
                    command = command[1:]
                elif command.startswith("/"):
                    command = command[1:]

                screen_map = {
                    "1": "timeline",
                    "2": "discover",
                    "3": "notifications",
                    "4": "messages",
                    "5": "settings",
                }
                if command in screen_map:
                    self.switch_screen(screen_map[command])
                elif command in ("q", "quit"):
                    self.exit()
                elif command.upper() == "P":
                    self.switch_screen("profile")
                elif command == "n":
                    # Handle :n differently based on screen
                    if self.current_screen_name in ["timeline", "discover"]:
                        self.action_new_post()
                    elif self.current_screen_name == "messages":
                        # Focus message input in messages screen
                        try:
                            msg_input = self.query_one("#message-input", Input)
                            msg_input.focus()
                        except:
                            pass
                    # Don't do anything for other screens (like drafts)
                elif command.upper() == "D":
                    self.action_show_drafts()
                elif command == "l":
                    # Like the currently focused post in timeline or discover
                    if self.current_screen_name == "timeline":
                        try:
                            timeline_feed = self.query_one("#timeline-feed")
                            items = list(timeline_feed.query(".post-item"))
                            idx = getattr(timeline_feed, "cursor_position", 0)
                            if 0 <= idx < len(items):
                                post_item = items[idx]
                                post = getattr(post_item, "post", None)
                                if post:
                                    api.like_post(post.id)
                                    self.notify("Post liked!", severity="success")
                                    # Refresh timeline
                                    self.switch_screen("timeline")
                        except Exception:
                            pass
                    elif self.current_screen_name == "discover":
                        try:
                            discover_feed = self.query_one("#discover-feed")
                            items = list(discover_feed.query(".post-item"))
                            idx = getattr(discover_feed, "cursor_position", 0)
                            if 0 <= idx < len(items):
                                post_item = items[idx]
                                post = getattr(post_item, "post", None)
                                if post:
                                    api.like_post(post.id)
                                    self.notify("Post liked!", severity="success")
                                    # Refresh discover
                                    self.switch_screen("discover")
                        except Exception:
                            pass
                elif command == "c":
                    logging.debug(":c command received in Proj101App.on_key")
                    # Open comment screen for the currently focused post in timeline or discover
                    if self.current_screen_name == "timeline":
                        try:
                            timeline_feed = self.query_one("#timeline-feed")
                            items = list(timeline_feed.query(".post-item"))
                            idx = getattr(timeline_feed, "cursor_position", 0)
                            logging.debug(
                                f"timeline_feed.cursor_position={idx}, items={len(items)}"
                            )
                            if 0 <= idx < len(items):
                                post_item = items[idx]
                                post = getattr(post_item, "post", None)
                                logging.debug(
                                    f"Opening comment screen for post id={getattr(post, 'id', None)} author={getattr(post, 'author', None)}"
                                )
                                if post:
                                    self.push_screen(CommentScreen(post))
                            else:
                                logging.debug("Invalid cursor position for :c command")
                        except Exception as e:
                            logging.exception("Exception in :c command:")
                    elif self.current_screen_name == "discover":
                        try:
                            discover_feed = self.query_one("#discover-feed")
                            items = list(discover_feed.query(".post-item"))
                            idx = getattr(discover_feed, "cursor_position", 0)
                            logging.debug(
                                f"discover_feed.cursor_position={idx}, items={len(items)}"
                            )
                            if 0 <= idx < len(items):
                                post_item = items[idx]
                                post = getattr(post_item, "post", None)
                                logging.debug(
                                    f"Opening comment screen for post id={getattr(post, 'id', None)} author={getattr(post, 'author', None)}"
                                )
                                if post:
                                    self.push_screen(CommentScreen(post))
                            else:
                                logging.debug("Invalid cursor position for :c command")
                        except Exception as e:
                            logging.exception("Exception in :c command:")
                elif command == "rt":
                    # Repost the currently focused post in timeline or discover
                    if self.current_screen_name == "timeline":
                        try:
                            timeline_feed = self.query_one("#timeline-feed")
                            items = list(timeline_feed.query(".post-item"))
                            idx = getattr(timeline_feed, "cursor_position", 0)
                            if 0 <= idx < len(items):
                                post_item = items[idx]
                                post = getattr(post_item, "post", None)
                                if post:
                                    api.repost(post.id)
                                    # Insert a reposted copy at the top of the timeline
                                    from copy import deepcopy

                                    repost_copy = deepcopy(post)
                                    repost_copy.timestamp = datetime.now()
                                    # Add to reposted_posts in TimelineFeed
                                    timeline_feed.reposted_posts = [
                                        (repost_copy, repost_copy.timestamp)
                                    ] + [
                                        p
                                        for p in getattr(
                                            timeline_feed, "reposted_posts", []
                                        )
                                    ]
                                    self.notify("Post reposted!", severity="success")
                                    # Refresh timeline
                                    self.switch_screen("timeline")
                        except Exception:
                            pass
                    elif self.current_screen_name == "discover":
                        try:
                            discover_feed = self.query_one("#discover-feed")
                            items = list(discover_feed.query(".post-item"))
                            idx = getattr(discover_feed, "cursor_position", 0)
                            if 0 <= idx < len(items):
                                post_item = items[idx]
                                post = getattr(post_item, "post", None)
                                if post:
                                    api.repost(post.id)
                                    # Refresh discover
                                    self.switch_screen("discover")
                        except Exception:
                            pass
                elif command.startswith("o") and len(command) > 1:
                    try:
                        draft_number = int(command[1:])  # User enters 1-indexed
                        draft_index = draft_number - 1  # Convert to 0-indexed for array
                        self.action_open_draft(draft_index)
                    except:
                        pass
                elif command.startswith("x") and len(command) > 1:
                    try:
                        draft_number = int(command[1:])  # User enters 1-indexed
                        draft_index = draft_number - 1  # Convert to 0-indexed for array
                        self.push_screen(DeleteDraftDialog(draft_index))
                    except:
                        pass

                self.command_text = ""
            elif event.key == "backspace":
                if len(self.command_text) > 1:
                    self.command_text = self.command_text[:-1]
            elif len(event.key) == 1 and event.key.isprintable():
                self.command_text += event.key
            # All other keys are already stopped at the top of command_mode block
            return


def main():
    logging.debug("inside __main__ guard, about to run app")
    try:
        Proj101App().run()
    except Exception as e:
        import traceback

        logging.exception("Exception occurred while running Proj101App:")


if __name__ == "__main__":
    main()
