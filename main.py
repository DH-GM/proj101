from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, Input, Button
from textual.reactive import reactive
from datetime import datetime, timedelta
from api_interface import api
import sys
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from PIL import Image
from ascii_video_widget import ASCIIVideoPlayer
import threading
import webbrowser
import json
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import socketserver


from datetime import datetime
from api_interface import api, Post as _Post, Message as _Message

# ---------- utils ----------
def format_time_ago(dt: datetime) -> str:
    now = datetime.now()
    diff = now - dt
    s = diff.total_seconds()
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{int(s // 60)}m ago"
    if s < 86400:
        return f"{int(s // 3600)}h ago"
    return f"{diff.days}d ago"

# ---------- sidebar ----------
class NavigationItem(Static):
    def __init__(self, label: str, screen_name: str, number: int, active: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.label_text = label
        self.target_screen = screen_name
        self.number = number
        self.active = active

    def render(self) -> str:
        prefix = "▾ " if self.active else "▸ "
        return f"{prefix}[{self.number}] {self.label_text}"

    def on_click(self) -> None:
        self.app.navigate(self.target_screen)

    def set_active(self, is_active: bool) -> None:
        self.active = is_active
        self.refresh()


class CommandItem(Static):
    def __init__(self, shortcut: str, description: str, **kwargs):
        super().__init__(**kwargs)
        self.shortcut = shortcut
        self.description = description

    def render(self) -> str:
        return f"{self.shortcut} - {self.description}"


class StatsDisplay(Static):
    def compose(self) -> ComposeResult:
        user = api.get_current_user()
        yield Static(f"Posts {user.posts_count}", classes="stat-item")
        yield Static(f"Following {user.following}", classes="stat-item")
        yield Static(f"Followers {user.followers}", classes="stat-item")


class Sidebar(Container):
    current = reactive("timeline")

    def __init__(self, current: str = "timeline", **kwargs):
        super().__init__(**kwargs)
        self.current = current

    def compose(self) -> ComposeResult:
        nav = Container(classes="navigation-box")
        with nav:
            yield NavigationItem("Timeline", "timeline", 0, self.current == "timeline", classes="nav-item", id="nav-timeline")
            yield NavigationItem("Discover", "discover", 1, self.current == "discover", classes="nav-item", id="nav-discover")
            yield NavigationItem("Notifs", "notifications", 2, self.current == "notifications", classes="nav-item", id="nav-notifications")
            yield NavigationItem("Messages", "messages", 3, self.current == "messages", classes="nav-item", id="nav-messages")
            yield NavigationItem("Settings", "settings", 4, self.current == "settings", classes="nav-item", id="nav-settings")
        yield nav

        stats = Container(classes="stats-box")
        with stats:
            yield StatsDisplay()
        yield stats

        cmds = Container(classes="commands-box")
        with cmds:
            if self.current in ("timeline", "discover"):
                yield CommandItem(":n", "new post", classes="command-item")
                yield CommandItem(":l", "like", classes="command-item")
                yield CommandItem(":rt", "repost", classes="command-item")
            elif self.current == "messages":
                yield CommandItem(":n", "new message", classes="command-item")
                yield CommandItem(":r", "reply", classes="command-item")
            elif self.current == "notifications":
                yield CommandItem(":m", "mark read", classes="command-item")
        yield cmds

    def update_active(self, screen_name: str):
        self.current = screen_name
        for i in ("timeline", "discover", "notifications", "messages", "settings"):
            try:
                item = self.query_one(f"#nav-{i}", NavigationItem)
                item.set_active(i == screen_name)
            except Exception:
                pass

# ---------- timeline post ----------
class PostItem(Container):
    ...
    def __init__(self, post: _Post, **kwargs):
        super().__init__(**kwargs)
        self.post = post
        self._comments_open = False
        self._selected = False  # NEW

    def set_selected(self, is_selected: bool) -> None:  # NEW
        self._selected = is_selected
        if is_selected:
            self.add_class("selected")
        else:
            self.remove_class("selected")

    def _like_label(self) -> str:
        heart = "♥" if self.post.liked_by_user else "♡"
        return f"{heart} {self.post.likes}"

    def _repost_label(self) -> str:
        return f"⇄ {self.post.reposts}"

    def _comment_label(self) -> str:
        return f"💬 {self.post.comments}"

    def compose(self) -> ComposeResult:
        yield Static(f"@{self.post.author} • {format_time_ago(self.post.timestamp)}", classes="post-header")
        yield Static(self.post.content, classes="post-body")
        
        actions = Horizontal(classes="post-actions")
        with actions:
            yield Button(self._like_label(), id=f"like-{self.post.id}", classes="action like-btn")
            yield Button(self._repost_label(), id=f"repost-{self.post.id}", classes="action repost-btn")
            yield Button(self._comment_label(), id=f"comment-{self.post.id}", classes="action comment-btn")
        yield actions
        
        yield Vertical(id=f"comments-{self.post.id}", classes="comments-section hidden")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = (event.button.id or "")
        
        if bid == f"like-{self.post.id}":
            if api.like_post(self.post.id):
                event.button.label = self._like_label()
                # Add visual feedback
                if self.post.liked_by_user:
                    event.button.add_class("liked")
                else:
                    event.button.remove_class("liked")
        
        elif bid == f"repost-{self.post.id}":
            if api.repost(self.post.id):
                event.button.label = self._repost_label()
                if self.post.reposted_by_user:
                    event.button.add_class("reposted")
                else:
                    event.button.remove_class("reposted")
        
        elif bid == f"comment-{self.post.id}":
            self._toggle_comments()

    def _toggle_comments(self) -> None:
        self._comments_open = not self._comments_open
        panel = self.query_one(f"#comments-{self.post.id}", Vertical)
        panel.remove_children()
        
        if not self._comments_open:
            panel.add_class("hidden")
            return
        
        panel.remove_class("hidden")
        comments = api.get_comments(self.post.id)
        
        if comments:
            for c in comments:
                panel.mount(Static(f"@{c.get('user','user')}: {c.get('text','')}", classes="comment-item"))
        else:
            panel.mount(Static("No comments yet — be first!", classes="comment-hint"))
        
        panel.mount(Input(placeholder="Write a comment and press Enter…", id=f"cinput-{self.post.id}", classes="comment-input"))
        
        # Focus the input
        try:
            input_widget = self.query_one(f"#cinput-{self.post.id}", Input)
            input_widget.focus()
        except Exception:
            pass

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if not event.input.id or not event.input.id.startswith(f"cinput-{self.post.id}"):
            return
        
        text = event.value.strip()
        if not text:
            return
        
        api.add_comment(self.post.id, text)
        panel = self.query_one(f"#comments-{self.post.id}", Vertical)
        
        # Add comment above input
        panel.mount(Static(f"@you: {text}", classes="comment-item"), before=event.input)
        
        event.input.value = ""
        self.post.comments += 1
        
        # Update button count
        try:
            b = self.query_one(f"#comment-{self.post.id}", Button)
            b.label = self._comment_label()
        except Exception:
            pass
# ---------- selectable feed (keyboard + selection) ----------
class SelectableFeed(VerticalScroll):
    """A VerticalScroll that tracks a selected PostItem and exposes actions."""
    can_focus = True
    selected = reactive(0)

    def _post_items(self):
        return [w for w in self.query(PostItem)]

    def _update_selection(self) -> None:
        items = self._post_items()
        if not items:
            return
        self.selected = max(0, min(self.selected, len(items) - 1))
        for i, it in enumerate(items):
            it.set_selected(i == self.selected)
        # keep selected item visible
        try:
            self.scroll_to_widget(items[self.selected], animate=False, top=False)
        except Exception:
            pass

    # Movement
    def move_selection(self, delta: int) -> None:
        items = self._post_items()
        if not items:
            return
        self.selected = max(0, min(self.selected + delta, len(items) - 1))
        self._update_selection()

    # Actions mapped to buttons on the selected PostItem
    def like_selected(self) -> None:
        items = self._post_items()
        if not items:
            return
        item = items[self.selected]
        try:
            btn = item.query_one(f"#like-{item.post.id}", Button)
            item.on_button_pressed(Button.Pressed(btn))
        except Exception:
            pass

    def repost_selected(self) -> None:
        items = self._post_items()
        if not items:
            return
        item = items[self.selected]
        try:
            btn = item.query_one(f"#repost-{item.post.id}", Button)
            item.on_button_pressed(Button.Pressed(btn))
        except Exception:
            pass

    def comment_selected(self) -> None:
        items = self._post_items()
        if not items:
            return
        item = items[self.selected]
        try:
            btn = item.query_one(f"#comment-{item.post.id}", Button)
            item.on_button_pressed(Button.Pressed(btn))
        except Exception:
            pass

    def open_selected(self) -> None:
        # Enter = toggle/expand comments (same as comment button)
        self.comment_selected()


# ---------- timeline / discover ----------
class TimelineFeed(SelectableFeed):
    def compose(self) -> ComposeResult:
        posts = api.get_timeline()
        unread_count = len([p for p in posts if (datetime.now() - p.timestamp).seconds < 3600])
        
        yield Static(f"timeline.home | {unread_count} new posts | line 1", classes="panel-header")
        
        # Add ASCII video if frames exist
        if Path("subway_ascii_frames").exists():
            yield Static("@yourname • just now (Tip: press Alt+Enter to go full screen for better video)", classes="post-author")
            yield ASCIIVideoPlayer("subway_ascii_frames", fps=2, classes="ascii-video")
            yield Static("🚇 Subway ride in ASCII! ♥ 0  ⇄ 0  💬 0", classes="post-stats")
        
        for post in posts:
            yield PostItem(post, classes="post-item")
        unread = len([p for p in posts if (datetime.now() - p.timestamp).seconds < 3600])
        yield Static(f"timeline.home | {unread} new posts | line 1", classes="panel-header")
        for p in posts:
            yield PostItem(p, classes="post-item")
    
    def on_mount(self) -> None:
        self._update_selection()
        self.focus()


class TimelineScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="timeline", id="sidebar")
        yield TimelineFeed(id="timeline-feed")


# ---------- discover (restore v1 behavior, keep v2 PostItem) ----------
class DiscoverFeed(SelectableFeed):
    query_text = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._all_posts = []

    def on_mount(self) -> None:
        self._all_posts = api.get_discover_posts()
        self._render_posts()
        self.focus()

    def _filtered_posts(self):
        if not self.query_text:
            return self._all_posts
        q = self.query_text.lower()
        return [p for p in self._all_posts if q in p.author.lower() or q in p.content.lower()]

    def _render_posts(self) -> None:
        try:
            container = self.query_one("#posts-container", Container)
            container.remove_children()
            for post in self._filtered_posts():
                container.mount(PostItem(post, classes="post-item"))
            # reset selection on new render
            self.selected = 0
            self._update_selection()
        except Exception:
            pass

    def compose(self) -> ComposeResult:
        yield Static("discover.trending | line 1", classes="panel-header")
        yield Input(placeholder="Search posts, people, tags...", classes="message-input", id="discover-search")
        
        # Add ASCII video at top of discover if frames exist
        if Path("subway_ascii_frames").exists():
            yield Static("@yourname • just now (Tip: press Alt+Enter for full screen)", classes="post-author")
            yield ASCIIVideoPlayer("subway_ascii_frames", fps=2, classes="ascii-video")
            yield Static("🚇 Subway ride in ASCII! ♥ 0  ⇄ 0  💬 0", classes="post-stats")
        
        yield Container(id="posts-container")

        yield Static("\n→ Suggested Follow", classes="section-header")
        yield Static(
            "  @opensource_dev\n  Building tools for developers | 1.2k followers\n  [f] Follow  [↑↓] Navigate  [Enter] Open  [?] Help",
            classes="suggested-user",
        )

    def watch_query_text(self, _: str) -> None:
        self._render_posts()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "discover-search":
            self.query_text = event.value




class DiscoverScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="discover", id="sidebar")
        yield DiscoverFeed(id="discover-feed")

# ---------- notifications ----------
class NotificationItem(Static):
    def __init__(self, notif, **kwargs):
        super().__init__(**kwargs)
        self.notif = notif

    def render(self) -> str:
        icon = {"mention": "●", "like": "♥", "repost": "⇄", "follow": "◉"}.get(self.notif.type, "●")
        return f"{icon} @{self.notif.actor} • {format_time_ago(self.notif.timestamp)}\n{self.notif.content}"


class NotificationsFeed(VerticalScroll):
    def compose(self) -> ComposeResult:
        notifs = api.get_notifications()
        unread = len([n for n in notifs if not n.read])
        yield Static(f"notifications.all | {unread} unread | line 1", classes="panel-header")
        for n in notifs:
            yield NotificationItem(n, classes="notification-item")


class NotificationsScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="notifications", id="sidebar")
        yield NotificationsFeed(id="notifications-feed")

# ---------- messages ----------
class ConversationItem(Static):
    def __init__(self, conv, **kwargs):
        super().__init__(**kwargs)
        self.conv = conv

    def render(self) -> str:
        unread = " • unread" if self.conv.unread else ""
        return f"@{self.conv.username}\n {self.conv.last_message}\n {format_time_ago(self.conv.timestamp)}{unread}"


class ConversationsList(VerticalScroll):
    def compose(self) -> ComposeResult:
        convs = api.get_conversations()
        unread = len([c for c in convs if c.unread])
        yield Static(f"conversations | {unread} unread", classes="panel-header")
        for c in convs:
            yield ConversationItem(c, classes="conversation-item")


class ChatMessage(Static):
    def __init__(self, message: _Message, **kwargs):
        super().__init__(**kwargs)
        self.message = message
        mine = message.sender == "yourname"
        self.add_class("sent" if mine else "received")

    def render(self) -> str:
        return f"{self.message.content}\n{format_time_ago(self.message.timestamp)}"


class ChatView(VerticalScroll):
    conversation_id = "c1"

    def compose(self) -> ComposeResult:
        yield Static("@alice | conversation", classes="panel-header")
        for m in api.get_conversation_messages(self.conversation_id):
            yield ChatMessage(m, classes="chat-message")
        yield Static("-- INSERT --", classes="mode-indicator")
        yield Input(placeholder="Type message and press Enter…", id="chat-input", classes="message-input")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "chat-input":
            return
        text = event.value.strip()
        if not text:
            return
        msg = api.send_message(self.conversation_id, text)
        self.mount(ChatMessage(msg, classes="chat-message"), before=event.input)
        event.input.value = ""
        self.scroll_end(animate=False)


class MessagesScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="messages", id="sidebar")
        yield ConversationsList(id="conversations")
        yield ChatView(id="chat")

# ---------- settings ----------
class SettingsPanel(VerticalScroll):
    def compose(self) -> ComposeResult:
        settings = api.get_user_settings()
        yield Static("settings.profile | line 1", classes="panel-header")
        yield Static("\n→ Profile Picture (ASCII)", classes="settings-section-header")
        yield Static(" Your profile picture is automatically generated from your username.", classes="settings-help")
        yield Static(f" {api.get_current_user().avatar_ascii}", classes="ascii-avatar")
        yield Static(" [:r] Regenerate", classes="settings-action")
        yield Static("\n→ Account Information", classes="settings-section-header")
        yield Static(f"  Username:\n  @{settings.username}", classes="settings-field")
        yield Static(f"\n  Display Name:\n  {settings.display_name}", classes="settings-field")
        yield Static(f"\n  Bio:\n  {settings.bio}", classes="settings-field")
        
        # OAuth Connections
        yield Static("\n→ OAuth Connections", classes="settings-section-header")
        github_status = "Connected" if settings.github_connected else "[:c] Connect"
        gitlab_status = "Connected" if settings.gitlab_connected else "[:c] Connect"
        google_status = "Connected" if settings.google_connected else "[:c] Connect"
        discord_status = "Connected" if settings.discord_connected else "[:c] Connect"
        
        yield Static(f"  [●] GitHub                                              {github_status}", classes="oauth-item")
        yield Static(f"  [○] GitLab                                              {gitlab_status}", classes="oauth-item")
        yield Static(f"  [○] Google                                              {google_status}", classes="oauth-item")
        yield Static(f"  [○] Discord                                             {discord_status}", classes="oauth-item")
        
        # Preferences
        yield Static("\n→ Preferences", classes="settings-section-header")
        email_check = "☑" if settings.email_notifications else "☐"
        online_check = "☑" if settings.show_online_status else "☐"
        private_check = "☑" if settings.private_account else "☐"
        
        yield Static(f"  {email_check} Email notifications", classes="checkbox-item")
        yield Static(f"  {online_check} Show online status", classes="checkbox-item")
        yield Static(f"  {private_check} Private account", classes="checkbox-item")
        
        yield Static("\n  [:w] Save Changes     [:q] Cancel", classes="settings-actions")
        yield Static("\n:w - save  [:e] Edit field  [Tab] Next field  [Esc] Cancel", classes="help-text")
        
        # Session
        yield Static("\n→ Session", classes="settings-section-header")
        yield Button("Sign Out", id="settings-signout", classes="danger")
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "upload-profile-picture":
            try:
                # Open file dialog
                root = tk.Tk()
                root.withdraw()
                file_path = filedialog.askopenfilename(
                    title="Select an Image",
                    filetypes=[("Image files", "*.png *.jpg *.jpeg")]
                )
                root.destroy()
                
                if not file_path:
                    return
                
                # # Crop image to small square from top-left corner
                # cropped_path = "temp_cropped.png"
                # try:
                #     img = Image.open(file_path)
                #     # Monaco terminal cell aspect ~ 1(w) : 1.25(h)
                #     crop_w = img.width
                #     crop_h = min(int(crop_w / 1.25), img.height)
                #     cropped = img.crop((0, 0, crop_w, crop_h))
                #     cropped.save(cropped_path)
                #     self.app.notify(f"Cropped to {crop_w}x{crop_h}", severity="information")
                # except Exception as e:
                #     self.app.notify(f"Crop failed: {e}", severity="error")
                #     return
                
                # Run asciifer on cropped image
                script_path = Path("asciifer/asciifer.py")
                
                if not script_path.exists():
                    return
                
                output_text = "output.txt"
                output_image = "output.png"
                
                # Use system monospace font (exists on all macOS)
                font_path = "/System/Library/Fonts/Monaco.ttf"
                
                cmd = [
                    sys.executable,
                    str(script_path),
                    "--output-text", output_text,
                    "--output-image", output_image,
                    "--font", font_path,
                    "--font-size", "12",
                    file_path  # Use cropped image instead of original
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    return
                
                # Read the generated ASCII art
                if Path(output_text).exists():
                    with open(output_text, "r") as f:
                        lines = f.read().splitlines()

                    # Keep consistent width (characters per line)
                    max_width = max((len(line) for line in lines), default=0)

                    max_lines = int(max_width / 2)

                    lines = lines[:max_lines]

                    ascii_art = "\n".join(lines)
                    
                    # Update the settings model (persist the change)
                    settings = api.get_user_settings()
                    settings.ascii_pic = ascii_art
                    api.update_user_settings(settings)
                    
                    # Update the display widget
                    try:
                        avatar = self.query_one("#profile-picture-display", Static)
                        avatar.update(ascii_art)
                        self.app.notify("Profile picture updated!", severity="success")
                    except Exception as e:
                        self.app.notify(f"Widget not found: {e}", severity="error")
                else:
                    self.app.notify("Output file not generated", severity="error")
            except Exception as e:
                pass
        elif event.button.id == "settings-signout":
            try:
                Path("oauth_tokens.json").unlink(missing_ok=True)
            except Exception:
                pass
            # Navigate to auth-only screen after the current event cycle
            self.app.call_after_refresh(self.app.show_auth_only)
            try:
                self.app.notify("Signed out.", severity="information")
            except Exception:
                pass
        yield Static(f" Username:\n @{s.username}", classes="settings-field")
        yield Static(f"\n Display Name:\n {s.display_name}", classes="settings-field")
        yield Static(f"\n Bio:\n {s.bio}", classes="settings-field")


class SettingsScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="settings", id="sidebar")
        yield SettingsPanel(id="settings-panel")


# ==================== AUTH SCREEN ====================

COGNITO_AUTH_URL = "https://us-east-2tgj9o2fop.auth.us-east-2.amazoncognito.com/login?client_id=jtcdok2taaq48rj50lerhp51v&response_type=code&scope=email+openid+phone&redirect_uri=http%3A%2F%2Flocalhost%3A5173%2Fcallback"
COGNITO_TOKEN_URL = "https://us-east-2tgj9o2fop.auth.us-east-2.amazoncognito.com/oauth2/token"
COGNITO_CLIENT_ID = "jtcdok2taaq48rj50lerhp51v"
REDIRECT_URI = "http://localhost:5173/callback"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    code: str | None = None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/callback":
            qs = parse_qs(parsed.query)
            OAuthCallbackHandler.code = (qs.get("code", [None])[0])
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"You can close this window and return to the app.")
        else:
            self.send_response(404)
            self.end_headers()


class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True


class AuthScreen(Container):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._poll_timer = None
        self._file_timer = None
    def compose(self) -> ComposeResult:
        # Minimal auth screen: centered sign-in button, no sidebar/header/footer
        with Container(id="auth-center"):
            yield Static("Sign in with Cognito (OAuth2)", id="auth-title", classes="signin")
            yield Button("Sign In", id="oauth-signin", classes="upload-profile-picture")
            yield Static("press q to quit", id="oauth-status", classes="signin")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "oauth-signin":
            # Update status immediately so button releases
            try:
                self.query_one("#oauth-status", Static).update("Status: Opening browser...")
            except Exception:
                pass
            
            # Schedule the server/browser opening for after this event
            self.call_after_refresh(self._start_oauth_flow)
        elif event.button.id == "oauth-signout":
            try:
                Path("oauth_tokens.json").unlink(missing_ok=True)
                self.query_one("#oauth-status", Static).update("Status: Signed out")
            except Exception:
                pass
    
    def _start_oauth_flow(self) -> None:
        """Start the OAuth flow - called after button press event completes."""
        print("Starting OAuth server...")
        
        # Reset code state
        OAuthCallbackHandler.code = None
        
        # Start local HTTP server in a separate thread with select-based timeout
        def run_server():
            try:
                import select
                server = ThreadingHTTPServer(("", 5173), OAuthCallbackHandler)
                server.timeout = 0.1  # Very short timeout
                end_time = datetime.now() + timedelta(seconds=60)
                
                print("Server listening on port 5173...")
                while datetime.now() < end_time and OAuthCallbackHandler.code is None:
                    # Use select to avoid blocking
                    ready, _, _ = select.select([server.socket], [], [], 0.1)
                    if ready:
                        server.handle_request()
                
                print("Server loop ended")
                server.server_close()
            except Exception as e:
                print(f"Server error: {e}")
        
        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()
        
        # Open browser to Cognito hosted UI
        print("Opening browser...")
        webbrowser.open(COGNITO_AUTH_URL)
        
        # Update status
        try:
            self.query_one("#oauth-status", Static).update("Status: Waiting for sign-in...")
        except Exception:
            pass
        
        # Poll for code and tokens file
        self._poll_timer = self.set_interval(0.5, self._check_code)
        self._file_timer = self.set_interval(0.5, self._check_tokens_file)

    def _check_code(self) -> None:
        code = OAuthCallbackHandler.code
        if code:
            # Exchange code for tokens
            try:
                data = {
                    "grant_type": "authorization_code",
                    "client_id": COGNITO_CLIENT_ID,
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                }
                headers = {"Content-Type": "application/x-www-form-urlencoded"}
                resp = requests.post(COGNITO_TOKEN_URL, data=data, headers=headers)
                if resp.ok:
                    tokens = resp.json()
                    # Persist in a simple file for demo
                    Path("oauth_tokens.json").write_text(json.dumps(tokens, indent=2))
                    self.query_one("#oauth-status", Static).update("Status: Signed in (tokens saved to oauth_tokens.json)")
                    # Switch to main app layout
                    try:
                        # stop timers
                        if self._poll_timer:
                            self._poll_timer.pause()
                        if self._file_timer:
                            self._file_timer.pause()
                        self.app.show_main_app()
                    except Exception:
                        pass
                else:
                    self.query_one("#oauth-status", Static).update(f"Status: Token exchange failed {resp.status_code}")
            except Exception as e:
                self.query_one("#oauth-status", Static).update(f"Status: Error {e}")
        # else keep polling via interval

    def _check_tokens_file(self) -> None:
        try:
            p = Path("oauth_tokens.json")
            if p.exists():
                data = json.loads(p.read_text() or "{}")
                # naive check for an access_token
                if isinstance(data, dict) and ("access_token" in data or "id_token" in data):
                    if self._poll_timer:
                        self._poll_timer.pause()
                    if self._file_timer:
                        self._file_timer.pause()
                    self.query_one("#oauth-status", Static).update("Status: Signed in (tokens detected)")
                    self.app.show_main_app()
        except Exception:
            pass


# ==================== MAIN APP ====================

# ---------- app ----------
class Proj101App(App):
    CSS_PATH = "main.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("0", "show_timeline", "Timeline", show=False),
        Binding("1", "show_discover", "Discover", show=False),
        Binding("2", "show_notifications", "Notifications", show=False),
        Binding("3", "show_messages", "Messages", show=False),
        Binding("4", "show_settings", "Settings", show=False),

        Binding("j", "select_down", show=False),
        Binding("k", "select_up", show=False),
        Binding("l", "like_selected", show=False),
        Binding("r", "repost_selected", show=False),
        Binding("c", "comment_selected", show=False),
        Binding("enter", "open_selected", show=False),

        Binding("/", "focus_discover_search", show=False),

        # Selection + actions (timeline/discover)
        Binding("j", "select_down", show=False),
        Binding("k", "select_up", show=False),
        Binding("l", "like_selected", show=False),
        Binding("r", "repost_selected", show=False),
        Binding("c", "comment_selected", show=False),
        Binding("enter", "open_selected", show=False),

        # Quick focus for discover search
        Binding("/", "focus_discover_search", show=False),
    ]

    current = reactive("timeline")

    def navigate(self, name: str) -> None:
        """Simple navigator for sidebar clicks / key bindings."""
        mapping = {
            "timeline": self.action_show_timeline,
            "discover": self.action_show_discover,
            "notifications": self.action_show_notifications,
            "messages": self.action_show_messages,
            "settings": self.action_show_settings,
        }
        action = mapping.get(name)
        if action:
            action()

    def compose(self) -> ComposeResult:
        # If we don't have tokens, show auth-first experience
        if not Path("oauth_tokens.json").exists():
            yield AuthScreen(id="screen-container")
        else:
            yield Static("proj101 [timeline] @yourname", id="app-header")
            yield TimelineScreen(id="screen-container")
            yield Static(":↑↓ Navigate [n] New Post [f] Follow [/] Search [?] Help", id="app-footer")
            yield Input(id="command-input", classes="command-bar")
    
    def switch_screen(self, screen_name: str):
        """Switch to a different screen."""
        if screen_name == self.current_screen_name:
            return
        
        # Screen mapping
        screen_map = {
            "timeline": (TimelineScreen, ":↑↓ Navigate [n] New Post [f] Follow [/] Search [?] Help"),
            "discover": (DiscoverScreen, ":/ - search [f] Follow [↑↓] Navigate [Enter] Open [?] Help"),
            "notifications": (NotificationsScreen, ":[↑] Previous [n] Next [m] Mark Read [Enter] Open [q] Quit"),
            "messages": (MessagesScreen, ":i - insert mode [Ctrl+N] New [↑↓] Navigate [Enter] Open [Esc] Exit"),
            "settings": (SettingsScreen, ":w - save  [:e] Edit field  [Tab] Next field  [Esc] Cancel"),
        }
        
        if screen_name in screen_map:
            # Remove old screen container by querying all and removing
            old_containers = self.query("#screen-container")
            for container in old_containers:
                container.remove()
            
            # Mount new screen
            ScreenClass, footer_text = screen_map[screen_name]
            self.call_after_refresh(self.mount, ScreenClass(id="screen-container"))
            
            # Update header and footer
            self.query_one("#app-header", Static).update(f"proj101 [{screen_name}] @yourname")
            self.query_one("#app-footer", Static).update(footer_text)
            self.current_screen_name = screen_name
            
            # Update sidebar navigation arrows
            try:
                sidebar = self.query_one("#sidebar", Sidebar)
                sidebar.update_active(screen_name)
            except:
                pass

    def show_main_app(self) -> None:
        # Clear current content and mount full app layout after auth
        try:
            for w in list(self.children):
                w.remove()
        except Exception:
            pass
        self.mount(Static("proj101 [timeline] @yourname", id="app-header"))
        self.mount(TimelineScreen(id="screen-container"))
        self.mount(Static(":↑↓ Navigate [n] New Post [f] Follow [/] Search [?] Help", id="app-footer"))
        self.mount(Input(id="command-input", classes="command-bar"))
        self.current_screen_name = "timeline"

    def show_auth_only(self) -> None:
        # Reset UI to auth first screen
        try:
            for w in list(self.children):
                w.remove()
        except Exception:
            pass
        self.mount(AuthScreen(id="screen-container"))
        self.current_screen_name = "auth"
    
    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()
    
    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.theme = "textual-dark" if self.theme == "textual-light" else "textual-light"
    
    def action_insert_mode(self) -> None:
        """Enter insert mode."""
        try:
            input_widget = self.query_one("#message-input", Input)
            input_widget.focus()
        except:
            pass
    
    def action_normal_mode(self) -> None:
        """Return to normal mode."""
        self.screen.focus_next()
    
    def action_show_timeline(self) -> None:
        """Show timeline screen."""
        self.switch_screen("timeline")
    
    def action_show_discover(self) -> None:
        """Show discover screen."""
        self.switch_screen("discover")
    
    def action_show_notifications(self) -> None:
        """Show notifications screen."""
        self.switch_screen("notifications")
    
    def action_show_messages(self) -> None:
        """Show messages screen."""
        self.switch_screen("messages")
    
    def action_show_settings(self) -> None:
        """Show settings screen."""
        self.switch_screen("settings")
    
    def action_show_command_bar(self) -> None:
        """Show vim-style command bar."""
        try:
            command_input = self.query_one("#command-input", Input)
            
            command_input.styles.display = "block"
            command_input.value = ":"
            self.command_mode = True
            command_input.focus()
            # Move cursor to end (after the colon)
            self.call_after_refresh(self._focus_command_input)
        except Exception as e:
            pass
    
    def _focus_command_input(self) -> None:
        """Focus the command input and position cursor after the colon."""
        try:
            command_input = self.query_one("#command-input", Input)
            command_input.focus()
            command_input.cursor_position = len(command_input.value)
        except:
            pass
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Prevent removing the colon prefix in command mode."""
        if event.input.id == "command-input" and self.command_mode:
            # Ensure the input always starts with ':'
            if not event.value.startswith(":"):
                event.input.value = ":" + event.value
                event.input.cursor_position = len(event.input.value)
    
    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle command input submission."""
        if event.input.id == "command-input" and self.command_mode:
            command = event.value.strip()
            
            # Hide command bar
            command_input = self.query_one("#command-input", Input)
            command_input.styles.display = "none"
            event.input.value = ""
            self.command_mode = False
            
            # Parse command - strip the colon prefix
            if command.startswith(":"):
                command = command[1:]
            
            # Navigation commands
            screen_map = {
                "0": "timeline",
                "1": "discover",
                "2": "notifications",
                "3": "messages",
                "4": "settings",
            }
            
            if command in screen_map:
                self.switch_screen(screen_map[command])
            elif command == "q" or command == "quit":
                self.exit()
    
    def on_key(self, event) -> None:
        """Handle escape key in command mode."""
        if event.key == "escape" and self.command_mode:
            try:
                command_input = self.query_one("#command-input", Input)
                command_input.styles.display = "none"
                command_input.value = ""
                self.command_mode = False
                event.prevent_default()
            except:
                pass
        yield Static("proj101 [timeline] @yourname", id="app-header")
        yield TimelineScreen(id="screen-container")
        yield Static(":↑↓ Navigate [Enter] Open [?] Help", id="app-footer")

    def _swap_screen(self, ScreenClass, name: str, footer_text: str):
        try:
            self.query_one("#screen-container").remove()
        except Exception:
            pass
        self.call_after_refresh(self.mount, ScreenClass(id="screen-container"))
        self.query_one("#app-header", Static).update(f"proj101 [{name}] @yourname")
        self.query_one("#app-footer", Static).update(footer_text)
        self.current = name
        try:
            self.query_one("#sidebar", Sidebar).update_active(name)
        except Exception:
            pass
    
    def _active_feed(self):
        """Return the currently active SelectableFeed, if any."""
        try:
            if self.current == "timeline":
                return self.query_one("#timeline-feed", SelectableFeed)
            elif self.current == "discover":
                return self.query_one("#discover-feed", SelectableFeed)
        except Exception:
            return None
        return None

    def action_show_timeline(self):
        self._swap_screen(TimelineScreen, "timeline", ":↑↓ Navigate [n] New Post [?] Help")

    def action_show_discover(self):
        # Fixed: Removed [/] which was causing markup error
        self._swap_screen(DiscoverScreen, "discover", ":↑↓ Navigate (/) Search [?] Help")

    def action_show_notifications(self):
        self._swap_screen(NotificationsScreen, "notifications", ":[↑] Prev [n] Next [m] Mark Read")

    def action_show_messages(self):
        self._swap_screen(MessagesScreen, "messages", ":i Insert [Esc] Normal")

    def action_show_settings(self):
        self._swap_screen(SettingsScreen, "settings", ":w Save [:e] Edit [Esc] Cancel")
    
    def action_select_down(self):
        feed = self._active_feed()
        if feed:
            feed.move_selection(1)

    def action_select_up(self):
        feed = self._active_feed()
        if feed:
            feed.move_selection(-1)

    def action_like_selected(self):
        feed = self._active_feed()
        if feed:
            feed.like_selected()

    def action_repost_selected(self):
        feed = self._active_feed()
        if feed:
            feed.repost_selected()

    def action_comment_selected(self):
        feed = self._active_feed()
        if feed:
            feed.comment_selected()

    def action_open_selected(self):
        feed = self._active_feed()
        if feed:
            feed.open_selected()

    def action_focus_discover_search(self):
        if self.current == "discover":
            try:
                self.query_one("#discover-search", Input).focus()
            except Exception:
                pass
# Focus a sensible default widget after swap
    def _focus_default(self) -> None:
        try:
            if self.current == "timeline":
                self.set_focus(self.query_one("#timeline-feed"))
            elif self.current == "discover":
                self.set_focus(self.query_one("#discover-feed"))
            elif self.current == "notifications":
                self.set_focus(self.query_one("#notifications-feed"))
            elif self.current == "messages":
                # leave focus behavior as-is (you can focus chat input here if you want)
                pass
        except Exception:
            pass

        self.call_after_refresh(self._focus_default)


if __name__ == "__main__":
    Proj101App().run()