from textual.app import App, ComposeResult
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
        prefix = "▾ " if self.active else "▸ "
        return f"{prefix}[{self.number}] {self.label_text}"

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
        yield Static(f"@{user.username}", classes="profile-username")
        yield Static(f"{user.display_name}", classes="profile-name")
        yield Static(f"\nPosts {user.posts_count}", classes="profile-stat")
        yield Static(f"Following {user.following}", classes="profile-stat")
        yield Static(f"Followers {user.followers}", classes="profile-stat")


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
    
    def __init__(self, post, **kwargs):
        super().__init__(**kwargs)
        self.post = post
        self.has_video = hasattr(post, 'video_path') and post.video_path

    def compose(self) -> ComposeResult:
        """Compose compact post."""
        time_ago = format_time_ago(self.post.timestamp)
        like_symbol = "♥" if self.post.liked_by_user else "♡"
        repost_symbol = "⇄" if self.post.reposted_by_user else "⇄"
        
        # Post header and content
        yield Static(
            f"@{self.post.author} • {time_ago}\n{self.post.content}",
            classes="post-text"
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
            classes="post-stats"
        )


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

class Sidebar(Container):
    current_screen = reactive("timeline")

    def __init__(self, current: str = "timeline", **kwargs):
        super().__init__(**kwargs)
        self.current_screen = current

    def compose(self) -> ComposeResult:
        nav_container = Container(classes="navigation-box")
        nav_container.border_title = "Navigation [N]"
        with nav_container:
            yield NavigationItem("Timeline", "timeline", 0, self.current_screen == "timeline", classes="nav-item", id="nav-timeline")
            yield NavigationItem("Discover", "discover", 1, self.current_screen == "discover", classes="nav-item", id="nav-discover")
            yield NavigationItem("Notifs", "notifications", 2, self.current_screen == "notifications", classes="nav-item", id="nav-notifications")
            yield NavigationItem("Messages", "messages", 3, self.current_screen == "messages", classes="nav-item", id="nav-messages")
            yield NavigationItem("Settings", "settings", 4, self.current_screen == "settings", classes="nav-item", id="nav-settings")
        yield nav_container
        
        profile_container = Container(classes="profile-box")
        profile_container.border_title = "Profile [:P]"
        with profile_container:
            yield ProfileDisplay()
        yield profile_container
        
        commands_container = Container(classes="commands-box")
        commands_container.border_title = "Commands"
        with commands_container:
            if self.current_screen == "messages":
                yield CommandItem(":n", "new message", classes="command-item")
                yield CommandItem(":r", "reply", classes="command-item")
            elif self.current_screen in ("timeline", "discover"):
                yield CommandItem(":n", "new post", classes="command-item")
                yield CommandItem(":r", "reply", classes="command-item")
                yield CommandItem(":l", "like", classes="command-item")
                yield CommandItem(":rt", "repost", classes="command-item")
            elif self.current_screen == "notifications":
                yield CommandItem(":m", "mark read", classes="command-item")
                yield CommandItem(":ma", "mark all", classes="command-item")
                yield CommandItem(":f", "filter", classes="command-item")
            elif self.current_screen == "profile":
                yield CommandItem(":e", "edit profile", classes="command-item")
                yield CommandItem(":f", "follow/unfollow", classes="command-item")
            elif self.current_screen == "settings":
                yield CommandItem(":w", "save", classes="command-item")
                yield CommandItem(":q", "quit", classes="command-item")
                yield CommandItem(":e", "edit", classes="command-item")

            yield CommandItem(":d", "delete", classes="command-item")
            yield CommandItem(":s", "search", classes="command-item")
            yield CommandItem("N", "nav focus", classes="command-item")
            yield CommandItem(":P", "profile", classes="command-item")
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
    
    def compose(self) -> ComposeResult:
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
    def compose(self) -> ComposeResult:
        posts = api.get_timeline()
        unread_count = len([p for p in posts if (datetime.now() - p.timestamp).seconds < 3600])
        yield Static(f"timeline.home | {unread_count} new posts | line 1", classes="panel-header")
        for post in posts:
            yield PostItem(post, classes="post-item")


class TimelineScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="timeline", id="sidebar")
        yield TimelineFeed(id="timeline-feed")


class DiscoverFeed(Container):
    query_text = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._all_posts = []
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

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search posts, people, tags...", classes="message-input", id="discover-search")
        yield VerticalScroll(id="search-results-container")
        yield Static("\n→ Suggested Follow", classes="section-header")
        yield Static(
            "  @opensource_dev\n  Building tools for developers | 1.2k followers\n  [f] Follow  [↑↓] Navigate  [Enter] Open  [?] Help",
            classes="suggested-user",
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
    def compose(self) -> ComposeResult:
        yield Sidebar(current="discover", id="sidebar")
        yield DiscoverFeed(id="discover-feed")


class NotificationsFeed(VerticalScroll):
    def compose(self) -> ComposeResult:
        notifications = api.get_notifications()
        unread_count = len([n for n in notifications if not n.read])
        yield Static(f"notifications.all | {unread_count} unread | line 1", classes="panel-header")
        for notif in notifications:
            yield NotificationItem(notif, classes="notification-item")
        yield Static("\n[↑] Previous [n] Next [m] Mark Read [Enter] Open [q] Quit", classes="help-text")


class NotificationsScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="notifications", id="sidebar")
        yield NotificationsFeed(id="notifications-feed")


class ConversationsList(VerticalScroll):
    def compose(self) -> ComposeResult:
        conversations = api.get_conversations()
        unread_count = len([c for c in conversations if c.unread])
        yield Static(f"conversations | {unread_count} unread", classes="panel-header")
        for conv in conversations:
            yield ConversationItem(conv, classes="conversation-item")


class ChatView(VerticalScroll):
    conversation_id = "c1"

    def compose(self) -> ComposeResult:
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


class MessagesScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="messages", id="sidebar")
        yield ConversationsList(id="conversations")
        yield ChatView(id="chat")


class SettingsPanel(VerticalScroll):
    def compose(self) -> ComposeResult:
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
        yield Static("\n:w - save  [:e] Edit field  [Tab] Next field  [Esc] Cancel", classes="help-text")
    
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
    def compose(self) -> ComposeResult:
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
        yield Static("\n[:e] Edit Profile  [Esc] Back", classes="help-text")


class ProfileScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="profile", id="sidebar")
        yield ProfilePanel(id="profile-panel")


class Proj101App(App):
    CSS_PATH = "main.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("i", "insert_mode", "Insert", show=True),
        Binding("escape", "normal_mode", "Normal", show=False),
        Binding("d", "toggle_dark", "Dark", show=True),
        Binding("0", "show_timeline", "Timeline", show=False),
        Binding("1", "show_discover", "Discover", show=False),
        Binding("2", "show_notifications", "Notifications", show=False),
        Binding("3", "show_messages", "Messages", show=False),
        Binding("4", "show_settings", "Settings", show=False),
        Binding("shift+n", "focus_navigation", "Nav Focus", show=False),
        Binding("colon", "show_command_bar", "Command", show=False),
    ]

    current_screen_name = reactive("timeline")
    command_mode = reactive(False)

    def compose(self) -> ComposeResult:
        yield Static("proj101 [timeline] @yourname", id="app-header")
        yield TimelineScreen(id="screen-container")
        yield Static(":↑↓ Navigate [n] New Post [f] Follow [/] Search [?] Help", id="app-footer")
        yield Input(id="command-input", classes="command-bar")

    def switch_screen(self, screen_name: str):
        if screen_name == self.current_screen_name:
            return
        screen_map = {
            "timeline": (TimelineScreen, ":↑↓ Navigate [n] New Post [f] Follow [/] Search [?] Help"),
            "discover": (DiscoverScreen, ":/ - search [f] Follow [↑↓] Navigate [Enter] Open [?] Help"),
            "notifications": (NotificationsScreen, ":[↑] Previous [n] Next [m] Mark Read [Enter] Open [q] Quit"),
            "messages": (MessagesScreen, ":i - insert mode [Ctrl+N] New [↑↓] Navigate [Enter] Open [Esc] Exit"),
            "profile": (ProfileScreen, ":[:e] Edit Profile [Esc] Back"),
            "settings": (SettingsScreen, ":w - save  [:e] Edit field  [Tab] Next field  [Esc] Cancel"),
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
    
    def action_show_discover(self) -> None: 
        self.switch_screen("discover")
    
    def action_show_notifications(self) -> None: 
        self.switch_screen("notifications")
    
    def action_show_messages(self) -> None: 
        self.switch_screen("messages")
    
    def action_show_settings(self) -> None: 
        self.switch_screen("settings")

    def action_focus_navigation(self) -> None:
        try:
            sidebar = self.query_one("#sidebar", Sidebar)
            nav_item = sidebar.query_one(".nav-item", NavigationItem)
            nav_item.focus()
        except:
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
            screen_map = {"0": "timeline", "1": "discover", "2": "notifications", "3": "messages", "4": "settings"}
            if command in screen_map:
                self.switch_screen(screen_map[command])
            elif command in ("q", "quit"):
                self.exit()
            elif command == "P" or command.upper() == "P":
                self.switch_screen("profile")
            elif command == "n":
                self.action_new_post()
    
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
    Proj101App().run()