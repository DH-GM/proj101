
import logging
import os
if os.getenv("DEV") == "TRUE":
    logging.basicConfig(filename='tuitter_debug.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
    logging.debug('very top of main.py')
else:
    logging.basicConfig(level=logging.CRITICAL)  # Effectively disables debug/info logging

from textual.app import App
from textual.containers import Container, Horizontal, Vertical, VerticalScroll, ScrollableContainer
from textual.screen import Screen
try:
    from textual.app import ComposeResult
except ImportError:
    ComposeResult = object
from textual.binding import Binding
from textual.widgets import Static, Input, Button, TextArea
from textual.reactive import reactive
from textual.screen import ModalScreen
from datetime import datetime
from api_interface import api
import sys
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from PIL import Image
from ascii_video_widget import ASCIIVideoPlayer

class CommentScreen(Screen):
    def __init__(self, post, **kwargs):
        super().__init__(**kwargs)
        self.post = post
        self.comments = []
        self.input_box = None

    def compose(self):
        # Post at the top
        yield Static("─ Post ─", classes="comment-thread-header", markup=False)
        yield PostItem(self.post)
        # Comments
        self.comments = api.get_comments(self.post.id)
        logging.debug(f"[compose] Comments fetched: {self.comments}")
        # Input for new comment (now above the comments)
        self.input_box = Input(placeholder="Type your comment and press Enter… (Esc to go back)", id="comment-input")
        yield self.input_box
        yield Static("─ Comments ─", classes="comment-thread-header", markup=False)
        for c in self.comments:
            author = c.get("user", "unknown")
            content = c.get("text", "")
            timestamp = c.get("timestamp") or c.get("created_at") or datetime.now().isoformat()
            try:
                c_time = format_time_ago(datetime.fromisoformat(timestamp))
            except Exception:
                c_time = "just now"
            yield Static(f"  @{author} • {c_time}\n  {content}\n", classes="comment-thread-item", markup=False)
            yield Static("")  # Add a blank line between comments

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "comment-input":
            return
        text = event.value.strip()
        if not text:
            return
        api.add_comment(self.post.id, text)
        # Fetch updated comments and refresh the screen
        self.comments = api.get_comments(self.post.id)
        self.refresh()
        # Clear and unfocus the input
        if hasattr(self, 'input_box') and self.input_box:
            self.input_box.value = ""
            self.input_box.blur()
        # Show a notification/toast (if supported by the app)
        if hasattr(self.app, 'notify'):
            self.app.notify("Comment posted!", timeout=2)

    def on_key(self, event) -> None:
        if event.key == "escape":
            try:
                self.app.pop_screen()
            except Exception:
                pass

from textual.app import App
from textual.containers import Container
try:
    from textual.app import ComposeResult
except ImportError:
    ComposeResult = object
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll, ScrollableContainer
from textual.widgets import Static, Input, Button, TextArea
from textual.reactive import reactive
from textual.screen import ModalScreen
from datetime import datetime
from api_interface import api
import sys
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from PIL import Image
from ascii_video_widget import ASCIIVideoPlayer



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


# ───────── Items ─────────

class NavigationItem(Static):
    def __init__(self, label: str, screen_name: str, number: int, active: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.label_text = label
        self.screen_name = screen_name
        self.number = number
        self.active = active
        if active:
            self.add_class("active")

    def render(self) -> str:
        if self.active:
            return f"[bold #4a9eff]{self.number}:[/] {self.label_text}"
        else:
            return f"{self.number}: {self.label_text}"

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


class ProfileDisplay(Static):
    """Display user profile."""

    def compose(self) -> ComposeResult:
        user = api.get_current_user()
        yield Static(f"@{user.username} • {user.display_name}", classes="profile-username")
        yield Static(f"P:{user.posts_count} F:{user.following} F:{user.followers}", classes="profile-stat")


class ConversationItem(Static):
    def __init__(self, conversation, **kwargs):
        super().__init__(**kwargs)
        self.conversation = conversation

    def render(self) -> str:
        unread_marker = "• " if self.conversation.unread else "  "
        time_ago = format_time_ago(self.conversation.timestamp)
        unread_text = "• unread" if self.conversation.unread else ""
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
        self.has_video = hasattr(post, 'video_path') and post.video_path

    def compose(self):
        """Compose compact post (no inline comments)."""
        time_ago = format_time_ago(self.post.timestamp)
        like_symbol = "♥" if self.post.liked_by_user else "♡"
        repost_symbol = "⇄" if self.post.reposted_by_user else "⇄"

        # Repost banner if this is a reposted post by you (either client-injected or backend-marked)
        if getattr(self, "reposted_by_you", False) or getattr(self.post, "reposted_by_user", False):
            yield Static("🔁 Reposted by you", classes="repost-banner", markup=False)

        # Post header and content
        yield Static(
            f"@{self.post.author} • {time_ago}\n{self.post.content}",
            classes="post-text",
            markup=False
        )

        # Video player if post has video
        if self.has_video and Path(self.post.video_path).exists():
            yield ASCIIVideoPlayer(
                frames_dir=self.post.video_path,
                fps=getattr(self.post, 'video_fps', 2),
                classes="post-video"
            )

        # Post stats - non-interactive
        yield Static(
            f"{like_symbol} {self.post.likes}  {repost_symbol} {self.post.reposts}  💬 {self.post.comments}",
            classes="post-stats",
            markup=False
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
class NotificationItem(Static):
    def __init__(self, notification, **kwargs):
        super().__init__(**kwargs)
        self.notification = notification
        if not notification.read:
            self.add_class("unread")

    def render(self) -> str:
        t = format_time_ago(self.notification.timestamp)
        icon = {"mention": "●", "like": "♥", "repost": "⇄", "follow": "◉", "comment": "💬"}.get(self.notification.type, "●")
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

    def __init__(self, username: str, display_name: str, bio: str, followers: int, following: int, ascii_pic: str, **kwargs):
        super().__init__(**kwargs)
        self.username = username
        self.display_name = display_name
        self.bio = bio
        self.followers = followers
        self.following = following
        self.ascii_pic = ascii_pic

    def compose(self):
        card_container = Container(classes="user-card-container")

        with card_container:
            pic_container = Container(classes="user-card-pic")
            with pic_container:
                yield Static(self.ascii_pic, classes="user-card-avatar")
            yield pic_container

            info_container = Container(classes="user-card-info")
            with info_container:
                yield Static(self.display_name, classes="user-card-name")
                yield Static(f"@{self.username}", classes="user-card-username")
                yield Static(self.bio, classes="user-card-bio")

                stats_container = Container(classes="user-card-stats")
                with stats_container:
                    yield Static(f"{self.followers} Followers", classes="user-card-stat")
                    yield Static(f"{self.following} Following", classes="user-card-stat")
                yield stats_container

                buttons_container = Container(classes="user-card-buttons")
                with buttons_container:
                    yield Button("Follow", id=f"follow-{self.username}", classes="user-card-button")
                    yield Button("Message", id=f"message-{self.username}", classes="user-card-button")
                    yield Button("View Profile", id=f"view-{self.username}", classes="user-card-button")
                yield buttons_container
            yield info_container

        yield card_container


# ───────── Sidebar ─────────

class Sidebar(VerticalScroll):
    current_screen = reactive("timeline")

    def __init__(self, current: str = "timeline", **kwargs):
        super().__init__(**kwargs)
        self.current_screen = current

    def compose(self):
        nav_container = Container(classes="navigation-box")
        nav_container.border_title = "Navigation [N]"
        with nav_container:
            yield NavigationItem("Timeline", "timeline", 1, self.current_screen == "timeline", classes="nav-item", id="nav-timeline")
            yield NavigationItem("Discover", "discover", 2, self.current_screen == "discover", classes="nav-item", id="nav-discover")
            yield NavigationItem("Notifs", "notifications", 3, self.current_screen == "notifications", classes="nav-item", id="nav-notifications")
            yield NavigationItem("Messages", "messages", 4, self.current_screen == "messages", classes="nav-item", id="nav-messages")
            yield NavigationItem("Settings", "settings", 5, self.current_screen == "settings", classes="nav-item", id="nav-settings")
        yield nav_container

        profile_container = Container(classes="profile-box")
        profile_container.border_title = "Profile [:P]"
        with profile_container:
            yield ProfileDisplay()
        yield profile_container

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
            yield CommandItem(":s", "search", classes="command-item")
            yield CommandItem("0", "main", classes="command-item")
        yield commands_container

    def update_active(self, screen_name: str):
        self.current_screen = screen_name
        for nav_id in ["nav-timeline", "nav-discover", "nav-notifications", "nav-messages", "nav-settings"]:
            try:
                nav_item = self.query_one(f"#{nav_id}", NavigationItem)
                nav_item.set_active(nav_item.screen_name == screen_name)
            except Exception:
                pass


# ───────── Modal Dialogs ─────────

class NewPostDialog(ModalScreen):
    """Modal dialog for creating a new post."""

    CSS = """
    NewPostDialog {
        align: center middle;
    }

    #dialog-container {
        width: 80;
        height: auto;
        background: #1a1a1a;
        border: round cyan;
        padding: 2;
    }

    #dialog-title {
        color: cyan;
        text-style: bold;
        text-align: center;
        margin-bottom: 1;
    }

    #post-textarea {
        width: 100%;
        height: 10;
        margin-bottom: 1;
    }

    #action-buttons {
        width: 100%;
        height: auto;
        align: center middle;
        layout: horizontal;
        margin: 1 0;
    }

    #media-buttons {
        width: 100%;
        height: auto;
        align: center middle;
        layout: horizontal;
        margin: 1 0;
    }

    #action-buttons Button, #media-buttons Button {
        width: 1fr;
        margin: 0 1;
        min-width: 20;
        height: 3;
        padding: 1 2;
        border: none;
        background: #2a2a2a;
    }

    #action-buttons Button:hover, #media-buttons Button:hover {
        background: #3a3a3a;
        border: none;
    }

    #action-buttons, #media-buttons {
        margin: 1;
        padding: 0 2;
    }

    Button#attach-photo, Button#attach-video {
        background: #2a2a2a;
    }

    Button#attach-photo:hover, Button#attach-video:hover {
        background: #3a3a3a;
    }

    Button#post-button {
        background: #4a9eff;
        border: none;
    }

    Button#post-button:hover {
        background: #5aaeff;
        border: none;
    }

    Button#cancel-button {
        border: none;
    }

    Button#cancel-button:hover {
        background: #3a3a3a;
        border: none;
    }

    .attachments-list {
        margin: 1 0;
        color: #888888;
    }
    """

    def compose(self):
        with Container(id="dialog-container"):
            yield Static("New Post", id="dialog-title")
            yield TextArea(id="post-textarea")
            # area to show selected attachments
            yield Static("", id="attachments-list", classes="attachments-list")

            with Container(id="action-buttons"):
                yield Button("Post", variant="primary", id="post-button")
                yield Button("Cancel", variant="default", id="cancel-button")

            with Container(id="media-buttons"):
                yield Button("📷 Photo", id="attach-photo")
                yield Button("📹 Video", id="attach-video")

    def on_mount(self) -> None:
        """Focus the textarea when dialog opens."""
        self.query_one("#post-textarea", TextArea).focus()
        # initialize attachments container on the instance
        self._attachments = []  # list of (type, path) tuples, type in ('photo','video')

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = getattr(event.button, "id", None)

        if btn_id == "attach-photo":
            # open file dialog to select image
            try:
                root = tk.Tk()
                root.withdraw()
                file_path = filedialog.askopenfilename(
                    title="Select an image",
                    filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")]
                )
                root.destroy()
                if file_path:
                    # optionally validate image via PIL
                    try:
                        Image.open(file_path).verify()
                    except Exception:
                        # still allow selecting, but notify user
                        self.app.notify("Selected file may not be a valid image", severity="warning")
                    self._attachments.append(("photo", file_path))
                    self._update_attachments_display()
            except Exception:
                pass

        elif btn_id == "attach-video":
            # open file dialog to select video file
            try:
                root = tk.Tk()
                root.withdraw()
                file_path = filedialog.askopenfilename(
                    title="Select a video",
                    filetypes=[("Video files", "*.mp4 *.mov *.avi *.mkv *.webm")]
                )
                root.destroy()
                if file_path:
                    self._attachments.append(("video", file_path))
                    self._update_attachments_display()
            except Exception:
                pass

        elif btn_id == "post-button":
            textarea = self.query_one("#post-textarea", TextArea)
            content = textarea.text.strip()

            if not content and not self._attachments:
                self.app.notify("Post cannot be empty", severity="warning")
                return

            # prepare attachments payload (paths) for API
            attachments_payload = [
                {"type": t, "path": p} for (t, p) in self._attachments
            ]

            # attempt to call API with attachments, fall back if signature differs
            try:
                # prefer create_post(content, attachments=...)
                new_post = api.create_post(content, attachments=attachments_payload)
            except TypeError:
                try:
                    # fallback: create_post(content, files)
                    new_post = api.create_post(content, attachments_payload)
                except Exception:
                    # last resort: call without attachments
                    new_post = api.create_post(content)

            try:
                self.app.notify("Post created successfully!", severity="success")
            except Exception:
                pass
            self.dismiss(True)

        elif btn_id == "cancel-button":
            self.dismiss(False)

    def _update_attachments_display(self) -> None:
        try:
            widget = self.query_one("#attachments-list", Static)
            if not self._attachments:
                widget.update("")
                return
            lines = [f"Attachments:" ]
            for i, (t, p) in enumerate(self._attachments, start=1):
                short = Path(p).name
                lines.append(f"  {i}. [{t}] {short}")
            widget.update("\n".join(lines))
        except Exception:
            pass


# ───────── Screens ─────────

class TimelineFeed(VerticalScroll):
    def key_enter(self) -> None:
        self.open_comment_screen()
    cursor_position = reactive(0)

    reposted_posts = reactive([])  # List of (post, timestamp) tuples

    def compose(self):
        posts = api.get_timeline()
        reposted_sorted = sorted(self.reposted_posts, key=lambda x: x[1], reverse=True)
        all_posts = [p for p, _ in reposted_sorted] + posts
        unread_count = len([p for p in all_posts if (datetime.now() - p.timestamp).seconds < 3600])
        self.border_title = "Main Timeline [0]"
        yield Static(f"timeline.home | {unread_count} new posts | line 1", classes="panel-header", markup=False)
        for i, post in enumerate(all_posts):
            is_repost = i < len(reposted_sorted)
            post_item = PostItem(post, reposted_by_you=is_repost, classes="post-item", id=f"post-{i}")
            if i == self.cursor_position:
                post_item.add_class("vim-cursor")
            yield post_item

    def open_comment_screen(self):
        logging.debug("open_comment_screen called in TimelineFeed")
        posts = api.get_timeline()
        reposted_sorted = sorted(self.reposted_posts, key=lambda x: x[1], reverse=True)
        all_posts = [p for p, _ in reposted_sorted] + posts
        logging.debug(f"cursor_position={self.cursor_position}, total_posts={len(all_posts)}")
        if 0 <= self.cursor_position < len(all_posts):
            post = all_posts[self.cursor_position]
            logging.debug(f"Opening comment screen for post id={getattr(post, 'id', None)} author={getattr(post, 'author', None)}")
            self.app.push_screen(CommentScreen(post))
        else:
            logging.debug("Invalid cursor position in open_comment_screen")
            print("[DEBUG] Invalid cursor position for comment screen")

    def on_key(self, event) -> None:
        if event.key == "c":
            self.open_comment_screen()
            event.prevent_default()
        elif event.key == "enter":
            self.open_comment_screen()
            event.prevent_default()
        # ...existing code...
        # ...existing code...

    def on_mount(self) -> None:
        self.watch(self, "cursor_position", self._update_cursor)

    def _update_cursor(self) -> None:
        """Update the cursor position"""
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
        except Exception:
            pass

    def on_focus(self) -> None:
        """When the feed gets focus"""
        self.cursor_position = 0
        self._update_cursor()

    def on_blur(self) -> None:
        """When feed loses focus"""
        pass

    def key_j(self) -> None:
        """Move down with j key"""
        items = list(self.query(".post-item"))
        if self.cursor_position < len(items) - 1:
            self.cursor_position += 1

    def key_k(self) -> None:
        """Move up with k key"""
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def key_g(self) -> None:
        """Go to top with gg"""
        # g is handled in on_key for double-press
        pass

    def key_G(self) -> None:
        """Go to bottom with G"""
        items = list(self.query(".post-item"))
        self.cursor_position = len(items) - 1

    def key_ctrl_d(self) -> None:
        """Half page down"""
        items = list(self.query(".post-item"))
        self.cursor_position = min(self.cursor_position + 5, len(items) - 1)

    def key_ctrl_u(self) -> None:
        """Half page up"""
        self.cursor_position = max(self.cursor_position - 5, 0)

    def key_w(self) -> None:
        """Word forward - move down by 3"""
        items = list(self.query(".post-item"))
        self.cursor_position = min(self.cursor_position + 3, len(items) - 1)

    def key_b(self) -> None:
        """Word backward - move up by 3"""
        self.cursor_position = max(self.cursor_position - 3, 0)

    def on_key(self, event) -> None:
        """Handle g+g key combination for top"""
        if event.key == "g" and event.is_repeat:
            self.cursor_position = 0
            event.prevent_default()


class TimelineScreen(Container):
    def compose(self):
        yield Sidebar(current="timeline", id="sidebar")
        yield TimelineFeed(id="timeline-feed")


class DiscoverFeed(Container):
    query_text = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._all_posts = []
        self.border_title = "Discover [0]"
        self._dummy_users = {
            "john doe": {
                "username": "johndoe",
                "display_name": "John Doe",
                "bio": "Software engineer and coffee enthusiast ☕ | Building cool stuff",
                "followers": 1543,
                "following": 892,
                "ascii_pic": "  [●▓▓●]\n  |≈ ◡ ≈|\n  |▓███▓|"
            },
            "jane smith": {
                "username": "janesmith",
                "display_name": "Jane Smith",
                "bio": "Designer | Creative thinker | Love minimalism 🎨",
                "followers": 2341,
                "following": 456,
                "ascii_pic": "  [◉▓▓◉]\n  |^ ▽ ^|\n  |▓███▓|"
            },
            "alice wonder": {
                "username": "alicewonder",
                "display_name": "Alice Wonder",
                "bio": "Explorer of digital worlds | Tech blogger | Cat lover 🐱",
                "followers": 987,
                "following": 234,
                "ascii_pic": "  [●▓▓●]\n  |◡ ω ◡|\n  |▓███▓|"
            }
        }

    def on_mount(self) -> None:
        self._all_posts = api.get_discover_posts()

    def _filtered_posts(self):
        if not self.query_text:
            return self._all_posts
        q = self.query_text.lower()
        return [p for p in self._all_posts if q in p.author.lower() or q in p.content.lower()]

    def _search_users(self):
        if not self.query_text:
            return []
        q = self.query_text.lower()
        matching_users = []
        for name, data in self._dummy_users.items():
            if q in name or q in data["username"].lower() or q in data["display_name"].lower():
                matching_users.append(data)
        return matching_users

    def compose(self):
        yield Input(placeholder="Search posts, people, tags...", classes="message-input", id="discover-search")
        yield VerticalScroll(id="search-results-container")
        yield Static("\n→ Suggested Follow", classes="section-header")
        yield Static(
            "  @opensource_dev\n  Building tools for developers | 1.2k followers\n  [f] Follow  [↑↓] Navigate  [Enter] Open  [?] Help",
            classes="suggested-user",
            markup=False,
        )

    def watch_query_text(self, _: str) -> None:
        try:
            container = self.query_one("#search-results-container", VerticalScroll)
            container.remove_children()

            matching_users = self._search_users()

            if matching_users:
                container.mount(Static("\n→ People", classes="section-header"))
                for user_data in matching_users:
                    card = UserProfileCard(
                        username=user_data["username"],
                        display_name=user_data["display_name"],
                        bio=user_data["bio"],
                        followers=user_data["followers"],
                        following=user_data["following"],
                        ascii_pic=user_data["ascii_pic"],
                        classes="user-profile-card"
                    )
                    container.mount(card)

            filtered_posts = self._filtered_posts()
            if filtered_posts:
                if matching_users:
                    container.mount(Static("\n→ Posts", classes="section-header"))
                for post in filtered_posts:
                    container.mount(PostItem(post, classes="post-item"))
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "discover-search":
            self.query_text = event.value


class DiscoverScreen(Container):
    def compose(self):
        yield Sidebar(current="discover", id="sidebar")
        yield DiscoverFeed(id="discover-feed")


class NotificationsFeed(VerticalScroll):
    def compose(self):
        notifications = api.get_notifications()
        unread_count = len([n for n in notifications if not n.read])
        self.border_title = "Notifications [0]"
        yield Static(f"notifications.all | {unread_count} unread | line 1", classes="panel-header")
        for notif in notifications:
            yield NotificationItem(notif, classes="notification-item")
        yield Static("\n[↑] Previous [n] Next [m] Mark Read [Enter] Open [q] Quit", classes="help-text", markup=False)


class NotificationsScreen(Container):
    def compose(self):
        yield Sidebar(current="notifications", id="sidebar")
        yield NotificationsFeed(id="notifications-feed")


class ConversationsList(VerticalScroll):
    cursor_position = reactive(0)

    def compose(self):
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
        items = list(self.query(".conversation-item"))
        if self.cursor_position < len(items) - 1:
            self.cursor_position += 1

    def key_k(self) -> None:
        """Move up with k key"""
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def key_g(self) -> None:
        """Go to top with gg"""
        # g is handled in on_key for double-press
        pass

    def key_G(self) -> None:
        """Go to bottom with G"""
        items = list(self.query(".conversation-item"))
        self.cursor_position = len(items) - 1

    def key_ctrl_d(self) -> None:
        """Half page down"""
        items = list(self.query(".conversation-item"))
        self.cursor_position = min(self.cursor_position + 5, len(items) - 1)

    def key_ctrl_u(self) -> None:
        """Half page up"""
        self.cursor_position = max(self.cursor_position - 5, 0)

    def key_w(self) -> None:
        """Word forward - move down by 3"""
        items = list(self.query(".conversation-item"))
        self.cursor_position = min(self.cursor_position + 3, len(items) - 1)

    def key_b(self) -> None:
        """Word backward - move up by 3"""
        self.cursor_position = max(self.cursor_position - 3, 0)

    def on_key(self, event) -> None:
        """Handle g+g key combination for top"""
        if event.key == "g" and event.is_repeat:
            self.cursor_position = 0
            event.prevent_default()


class ChatView(VerticalScroll):
    conversation_id = "c1"
    cursor_position = reactive(0)

    def compose(self):
        self.border_title = "Chat [0]"
        messages = api.get_conversation_messages(self.conversation_id)
        yield Static("@alice | conversation", classes="panel-header")
        for msg in messages:
            yield ChatMessage(msg, classes="chat-message")
        yield Static("-- INSERT --", classes="mode-indicator")
        yield Input(placeholder="Type message and press Enter… (Esc to cancel)",
                    classes="message-input", id="message-input")

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
        messages = self.query(".chat-message")
        if self.cursor_position < len(messages) - 1:
            self.cursor_position += 1

    def key_k(self) -> None:
        """Vim-style up navigation"""
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def key_g(self) -> None:
        """Vim-style go to top"""
        self.cursor_position = 0

    def key_G(self) -> None:
        """Vim-style go to bottom"""
        messages = self.query(".chat-message")
        self.cursor_position = max(0, len(messages) - 1)


class MessagesScreen(Container):
    def compose(self):
        yield Sidebar(current="messages", id="sidebar")
        yield ConversationsList(id="conversations")
        yield ChatView(id="chat")

    def on_mount(self) -> None:
        """Add border to conversations list"""
        conversations = self.query_one("#conversations", ConversationsList)
        conversations.border_title = "Messages [6]"
        conversations.border = "round #4a9eff"


class SettingsPanel(VerticalScroll):
    cursor_position = reactive(0)

    def compose(self):
        self.border_title = "Settings [0]"
        settings = api.get_user_settings()
        yield Static("settings.profile | line 1", classes="panel-header")
        yield Static("\n→ Profile Picture (ASCII)", classes="settings-section-header")
        yield Static("Make ASCII Profile Picture from image file")
        yield Button("Upload file", id="upload-profile-picture", classes="upload-profile-picture")
        yield Static(f"{settings.ascii_pic}", id="profile-picture-display", classes="ascii-avatar")

        yield Static("\n→ Account Information", classes="settings-section-header")
        yield Static(f"  Username:\n  @{settings.username}", classes="settings-field")
        yield Static(f"\n  Display Name:\n  {settings.display_name}", classes="settings-field")
        yield Static(f"\n  Bio:\n  {settings.bio}", classes="settings-field")
        yield Static("\n→ OAuth Connections", classes="settings-section-header")
        github_status = "Connected" if settings.github_connected else "[:c] Connect"
        gitlab_status = "Connected" if settings.gitlab_connected else "[:c] Connect"
        google_status = "Connected" if settings.google_connected else "[:c] Connect"
        discord_status = "Connected" if settings.discord_connected else "[:c] Connect"
        yield Static(f"  [●] GitHub                                              {github_status}", classes="oauth-item")
        yield Static(f"  [○] GitLab                                              {gitlab_status}", classes="oauth-item")
        yield Static(f"  [○] Google                                              {google_status}", classes="oauth-item")
        yield Static(f"  [○] Discord                                             {discord_status}", classes="oauth-item")
        yield Static("\n→ Preferences", classes="settings-section-header")
        email_check = "☑" if settings.email_notifications else "☐"
        online_check = "☑" if settings.show_online_status else "☐"
        private_check = "☑" if settings.private_account else "☐"
        yield Static(f"  {email_check} Email notifications", classes="checkbox-item")
        yield Static(f"  {online_check} Show online status", classes="checkbox-item")
        yield Static(f"  {private_check} Private account", classes="checkbox-item")
        yield Static("\n  [:w] Save Changes     [:q] Cancel", classes="settings-actions")
        yield Static("\n:w - save  [:e] Edit field  [Tab] Next field  [Esc] Cancel", classes="help-text", markup=False)

    def watch_cursor_position(self, old_position: int, new_position: int) -> None:
        """Update the cursor when position changes"""
        # We'll consider settings items that can be selected for cursor movement:
        selectable_classes = [".upload-profile-picture", ".oauth-item", ".checkbox-item"]

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
        selectable_classes = [".upload-profile-picture", ".oauth-item", ".checkbox-item"]
        items = []
        for cls in selectable_classes:
            items.extend(list(self.query(cls)))

        if self.cursor_position < len(items) - 1:
            self.cursor_position += 1

    def key_k(self) -> None:
        """Vim-style up navigation"""
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def key_g(self) -> None:
        """Vim-style go to top"""
        self.cursor_position = 0

    def key_G(self) -> None:
        """Vim-style go to bottom"""
        selectable_classes = [".upload-profile-picture", ".oauth-item", ".checkbox-item"]
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
                    filetypes=[("Image files", "*.png *.jpg *.jpeg")]
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
                    "--output-text", output_text,
                    "--output-image", output_image,
                    "--font", font_path,
                    "--font-size", "24",
                    file_path
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
        self.border_title = "Profile [0]"
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
                yield Static(f"{user.following}\nFollowing", classes="profile-stat-item")
                yield Static(f"{user.followers}\nFollowers", classes="profile-stat-item")
            yield stats_row

            bio_container = Container(classes="profile-bio-container")
            bio_container.border_title = "Bio"
            with bio_container:
                yield Static(f"{settings.bio}", classes="profile-bio-display")
            yield bio_container

        yield profile_container
        yield Static("\n[:e] Edit Profile  [Esc] Back", classes="help-text", markup=False)

    def watch_cursor_position(self, old_position: int, new_position: int) -> None:
        """Update the cursor when position changes"""
        # For profile panel, we'll treat the profile-stat-item elements as navigable
        items = list(self.query(".profile-stat-item"))

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
        items = list(self.query(".profile-stat-item"))
        if self.cursor_position < len(items) - 1:
            self.cursor_position += 1

    def key_k(self) -> None:
        """Vim-style up navigation"""
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def key_h(self) -> None:
        """Vim-style left navigation"""
        items = list(self.query(".profile-stat-item"))
        if self.cursor_position > 0:
            self.cursor_position -= 1

    def key_l(self) -> None:
        """Vim-style right navigation"""
        items = list(self.query(".profile-stat-item"))
        if self.cursor_position < len(items) - 1:
            self.cursor_position += 1

    def key_g(self) -> None:
        """Vim-style go to top"""
        self.cursor_position = 0

    def key_G(self) -> None:
        """Vim-style go to bottom"""
        items = list(self.query(".profile-stat-item"))
        self.cursor_position = max(0, len(items) - 1)


class ProfileScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="profile", id="sidebar")
        yield ProfilePanel(id="profile-panel")


class Proj101App(App):
    CSS_PATH = "main.tcss"

    BINDINGS = [
        # Basic app controls
        Binding("q", "quit", "Quit", show=False),
        Binding("i", "insert_mode", "Insert", show=True),
        Binding("escape", "normal_mode", "Normal", show=False),
        Binding("d", "toggle_dark", "Dark", show=True),

        # Screen navigation
        Binding("0", "focus_main_content", "Main Content", show=False),
        Binding("1", "show_timeline", "Timeline", show=False),
        Binding("2", "show_discover", "Discover", show=False),
        Binding("3", "show_notifications", "Notifications", show=False),
        Binding("4", "show_messages", "Messages", show=False),
        Binding("5", "show_settings", "Settings", show=False),
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
        Binding("g g", "vim_top", "Top", show=False),
        Binding("G", "vim_bottom", "Bottom", show=False),
        Binding("ctrl+d", "vim_half_page_down", "Half Page Down", show=False),
        Binding("ctrl+u", "vim_half_page_up", "Half Page Up", show=False),
        Binding("ctrl+f", "vim_page_down", "Page Down", show=False),
        Binding("ctrl+b", "vim_page_up", "Page Up", show=False),
        Binding("/", "vim_search", "Search", show=False),
        Binding("n", "vim_next_search", "Next Search", show=False),
        Binding("N", "vim_prev_search", "Previous Search", show=False),
        Binding("$", "vim_line_end", "End of Line", show=False),
        Binding("^", "vim_line_start", "Start of Line", show=False),
    ]

    current_screen_name = reactive("timeline")
    command_mode = reactive(False)

    def compose(self) -> ComposeResult:
        yield Static("proj101 [timeline] @yourname", id="app-header", markup=False)
        yield TimelineScreen(id="screen-container")
        yield Static(":↑↓ Navigate [0] Main [1-5] Sidebar [n] New Post [f] Follow [/] Search [?] Help", id="app-footer", markup=False)
        yield Input(id="command-input", classes="command-bar")

    def switch_screen(self, screen_name: str):
        if screen_name == self.current_screen_name:
            return
        screen_map = {
            "timeline": (TimelineScreen, ":[0] Main [1-5] Sidebar [↑↓] Navigate [n] New Post [f] Follow [/] Search [?] Help"),
            "discover": (DiscoverScreen, ":[0] Main [1-5] Sidebar [/] Search [f] Follow [↑↓] Navigate [Enter] Open [?] Help"),
            "notifications": (NotificationsScreen, ":[0] Main [1-5] Sidebar [↑] Previous [n] Next [m] Mark Read [Enter] Open [q] Quit"),
            "messages": (MessagesScreen, ":[0] Chat [6] Messages [1-5] Sidebar [i] Insert [j/k] Navigate [Enter] Open [Esc] Exit"),
            "profile": (ProfileScreen, ":[0] Main [1-5] Sidebar [:e] Edit Profile [Esc] Back"),
            "settings": (SettingsScreen, ":[0] Main [1-5] Sidebar [w] Save [:e] Edit field [Tab] Next field [Esc] Cancel"),
        }
        if screen_name in screen_map:
            for container in self.query("#screen-container"):
                container.remove()
            ScreenClass, footer_text = screen_map[screen_name]
            self.call_after_refresh(self.mount, ScreenClass(id="screen-container"))
            self.query_one("#app-header", Static).update(f"proj101 [{screen_name}] @yourname")
            self.query_one("#app-footer", Static).update(footer_text)
            self.current_screen_name = screen_name
            try:
                sidebar = self.query_one("#sidebar", Sidebar)
                sidebar.update_active(screen_name)
            except Exception:
                pass

    def action_quit(self) -> None:
        self.exit()

    def action_toggle_dark(self) -> None:
        self.theme = "textual-dark" if self.theme == "textual-light" else "textual-light"

    def action_insert_mode(self) -> None:
        try:
            self.query_one("#message-input", Input).focus()
        except Exception:
            pass

    def action_normal_mode(self) -> None:
        self.screen.focus_next()

    def action_show_timeline(self) -> None:
        self.switch_screen("timeline")
        self.action_focus_main_content()

    def action_show_discover(self) -> None:
        self.switch_screen("discover")
        self.action_focus_main_content()

    def action_show_notifications(self) -> None:
        self.switch_screen("notifications")
        self.action_focus_main_content()

    def action_show_messages(self) -> None:
        self.switch_screen("messages")
        self.action_focus_main_content()

    def action_show_settings(self) -> None:
        self.switch_screen("settings")
        self.action_focus_main_content()

    def action_focus_navigation(self) -> None:
        try:
            sidebar = self.query_one("#sidebar", Sidebar)
            nav_item = sidebar.query_one(".nav-item", NavigationItem)
            nav_item.focus()
        except:
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

            if target_id:
                panel = self.query_one(target_id)
                panel.border_title = f"{panel.border_title.split('[')[0]}[0]"
                panel.add_class("vim-mode-active")
                panel.focus()

        except Exception:
            pass

    def action_focus_messages(self) -> None:
        """Focus the messages list when pressing 6"""
        try:
            if self.current_screen_name == "messages":
                conversations = self.query_one("#conversations", ConversationsList)
                conversations.border_title = "Messages [6]"
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
        # The key will be handled by the focused widget's key_G method if it exists
        pass

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

    def action_vim_search(self) -> None:
        """Start a search (/ key)"""
        try:
            command_input = self.query_one("#command-input", Input)
            command_input.styles.display = "block"
            command_input.value = "/"
            self.command_mode = True
            command_input.focus()
            self.call_after_refresh(self._focus_command_input)
        except Exception:
            pass

    def action_vim_next_search(self) -> None:
        """Find next search match (n key)"""
        # Will be implemented in the content panels
        pass

    def action_vim_prev_search(self) -> None:
        """Find previous search match (N key)"""
        # Will be implemented in the content panels
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
            command_input = self.query_one("#command-input", Input)
            command_input.styles.display = "block"
            command_input.value = ":"
            self.command_mode = True
            command_input.focus()
            self.call_after_refresh(self._focus_command_input)
        except Exception:
            pass

    def _focus_command_input(self) -> None:
        try:
            command_input = self.query_one("#command-input", Input)
            command_input.focus()
            command_input.cursor_position = len(command_input.value)
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "command-input" and self.command_mode:
            if not event.value.startswith(":"):
                event.input.value = ":" + event.value
                event.input.cursor_position = len(event.input.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "command-input" and self.command_mode:
            command = event.value.strip()
            command_input = self.query_one("#command-input", Input)
            command_input.styles.display = "none"
            event.input.value = ""
            self.command_mode = False
            if command.startswith(":"):
                command = command[1:]
            screen_map = {"1": "timeline", "2": "discover", "3": "notifications", "4": "messages", "5": "settings"}
            if command in screen_map:
                self.switch_screen(screen_map[command])
            elif command in ("q", "quit"):
                self.exit()
            elif command == "P" or command.upper() == "P":
                self.switch_screen("profile")
            elif command == "n":
                self.action_new_post()
            elif command == "l":
                # Like the currently focused post in timeline
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
                                # Refresh timeline
                                self.switch_screen("timeline")
                    except Exception:
                        pass
            elif command == "c":
                logging.debug(":c command received in Proj101App.on_input_submitted")
                # Open comment screen for the currently focused post in timeline
                if self.current_screen_name == "timeline":
                    try:
                        timeline_feed = self.query_one("#timeline-feed")
                        items = list(timeline_feed.query(".post-item"))
                        idx = getattr(timeline_feed, "cursor_position", 0)
                        logging.debug(f"timeline_feed.cursor_position={idx}, items={len(items)}")
                        if 0 <= idx < len(items):
                            post_item = items[idx]
                            post = getattr(post_item, "post", None)
                            logging.debug(f"Opening comment screen for post id={getattr(post, 'id', None)} author={getattr(post, 'author', None)}")
                            if post:
                                self.push_screen(CommentScreen(post))
                        else:
                            logging.debug("Invalid cursor position for :c command")
                    except Exception as e:
                        logging.exception("Exception in :c command:")
            elif command == "rt":
                # Repost the currently focused post in timeline
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
                                timeline_feed.reposted_posts = [(repost_copy, repost_copy.timestamp)] + [p for p in getattr(timeline_feed, 'reposted_posts', [])]
                                # Refresh timeline
                                self.switch_screen("timeline")
                    except Exception:
                        pass

    def action_new_post(self) -> None:
        """Show the new post dialog."""
        def check_refresh(result):
            if result:
                if self.current_screen_name == "timeline":
                    self.switch_screen("timeline")

        self.push_screen(NewPostDialog(), check_refresh)

    def on_key(self, event) -> None:
        if event.key == "escape" and self.command_mode:
            try:
                command_input = self.query_one("#command-input", Input)
                command_input.styles.display = "none"
                command_input.value = ""
                self.command_mode = False
                event.prevent_default()
            except Exception:
                pass


if __name__ == "__main__":
    logging.debug('inside __main__ guard, about to run app')
    try:
        Proj101App().run()
    except Exception as e:
        import traceback
        logging.exception('Exception occurred while running Proj101App:')
