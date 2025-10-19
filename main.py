from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input, Label, Button, Checkbox
from textual.reactive import reactive
from datetime import datetime, timedelta
from api_interface import api
import sys
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
from PIL import Image


def format_time_ago(dt: datetime) -> str:
    """Format datetime as 'time ago' string."""
    now = datetime.now()
    diff = now - dt
    
    if diff.seconds < 60:
        return "just now"
    elif diff.seconds < 3600:
        mins = diff.seconds // 60
        return f"{mins}m ago"
    elif diff.seconds < 86400:
        hours = diff.seconds // 3600
        return f"{hours}h ago"
    else:
        days = diff.days
        return f"{days}d ago"


class NavigationItem(Static):
    """A navigation menu item."""
    
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
        """Handle click event."""
        self.app.switch_screen(self.screen_name)
    
    def set_active(self, is_active: bool) -> None:
        """Update the active state of this navigation item."""
        self.active = is_active
        if is_active:
            self.add_class("active")
        else:
            self.remove_class("active")
        self.refresh()


class CommandItem(Static):
    """A command menu item."""
    
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
    """A conversation list item."""
    
    def __init__(self, conversation, **kwargs):
        super().__init__(**kwargs)
        self.conversation = conversation
    
    def render(self) -> str:
        unread_marker = "• " if self.conversation.unread else "  "
        time_ago = format_time_ago(self.conversation.timestamp)
        unread_text = "• unread" if self.conversation.unread else ""
        return f"{unread_marker}@{self.conversation.username}\n  {self.conversation.last_message}\n  {time_ago} {unread_text}"


class ChatMessage(Static):
    """A chat message bubble."""
    
    def __init__(self, message, current_user: str = "yourname", **kwargs):
        super().__init__(**kwargs)
        self.message = message
        self.is_sent = message.sender == current_user
        self.add_class("sent" if self.is_sent else "received")
    
    def render(self) -> str:
        time_str = format_time_ago(self.message.timestamp)
        return f"{self.message.content}\n{time_str}"


class PostItem(Static):
    """A post/tweet item."""
    
    def __init__(self, post, **kwargs):
        super().__init__(**kwargs)
        self.post = post
    
    def render(self) -> str:
        time_ago = format_time_ago(self.post.timestamp)
        like_symbol = "♥" if self.post.liked_by_user else "♡"
        repost_symbol = "⇄" if self.post.reposted_by_user else "⇄"
        return f"@{self.post.author} • {time_ago}\n\n{self.post.content}\n\n{like_symbol} {self.post.likes}  {repost_symbol} {self.post.reposts}  💬 {self.post.comments}"


class NotificationItem(Static):
    """A notification item."""
    
    def __init__(self, notification, **kwargs):
        super().__init__(**kwargs)
        self.notification = notification
        if not notification.read:
            self.add_class("unread")
    
    def render(self) -> str:
        time_ago = format_time_ago(self.notification.timestamp)
        icon_map = {
            "mention": "●",
            "like": "♥",
            "repost": "⇄",
            "follow": "◉",
            "comment": "💬"
        }
        icon = icon_map.get(self.notification.type, "●")
        
        if self.notification.type == "mention":
            content = f'@{self.notification.actor} mentioned you • {time_ago}\n{self.notification.content}'
        elif self.notification.type == "like":
            content = f'{icon} @{self.notification.actor} liked your post • {time_ago}\n{self.notification.content}'
        elif self.notification.type == "repost":
            content = f'{icon} @{self.notification.actor} reposted • {time_ago}\n{self.notification.content}'
        elif self.notification.type == "follow":
            content = f'{icon} @{self.notification.actor} started following you • {time_ago}'
        else:
            content = f'{icon} @{self.notification.actor} • {time_ago}\n{self.notification.content}'
        
        return content


class Sidebar(Container):
    """Left sidebar with navigation."""
    
    current_screen = reactive("timeline")
    
    def __init__(self, current: str = "timeline", **kwargs):
        super().__init__(**kwargs)
        self.current_screen = current
    
    def compose(self) -> ComposeResult:
        # Navigation Section Box
        nav_container = Container(classes="navigation-box")
        nav_container.border_title = "Navigation [N]"
        with nav_container:
            yield NavigationItem("Timeline", "timeline", 0, self.current_screen == "timeline", classes="nav-item", id="nav-timeline")
            yield NavigationItem("Discover", "discover", 1, self.current_screen == "discover", classes="nav-item", id="nav-discover")
            yield NavigationItem("Notifs", "notifications", 2, self.current_screen == "notifications", classes="nav-item", id="nav-notifications")
            yield NavigationItem("Messages", "messages", 3, self.current_screen == "messages", classes="nav-item", id="nav-messages")
            yield NavigationItem("Settings", "settings", 4, self.current_screen == "settings", classes="nav-item", id="nav-settings")
        yield nav_container
        
        # Profile Section Box
        profile_container = Container(classes="profile-box")
        profile_container.border_title = "Profile [:P]"
        with profile_container:
            yield ProfileDisplay()
        yield profile_container
        
        # Commands Section Box
        commands_container = Container(classes="commands-box")
        commands_container.border_title = "Commands"
        with commands_container:
            # Screen-specific commands
            if self.current_screen == "messages":
                yield CommandItem(":n", "new message", classes="command-item")
                yield CommandItem(":r", "reply", classes="command-item")
            elif self.current_screen == "timeline" or self.current_screen == "discover":
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
        """Update which navigation item is active."""
        self.current_screen = screen_name
        # Update all navigation items
        nav_ids = ["nav-timeline", "nav-discover", "nav-notifications", "nav-messages", "nav-settings"]
        for nav_id in nav_ids:
            try:
                nav_item = self.query_one(f"#{nav_id}", NavigationItem)
                nav_item.set_active(nav_item.screen_name == screen_name)
            except:
                pass


# ==================== TIMELINE SCREEN ====================

class TimelineFeed(VerticalScroll):
    """Timeline feed with posts from following."""
    
    def compose(self) -> ComposeResult:
        user = api.get_current_user()
        posts = api.get_timeline()
        unread_count = len([p for p in posts if (datetime.now() - p.timestamp).seconds < 3600])
        
        yield Static(f"timeline.home | {unread_count} new posts | line 1", classes="panel-header")
        
        for post in posts:
            yield PostItem(post, classes="post-item")


class TimelineScreen(Container):
    """Timeline screen layout."""
    
    def compose(self) -> ComposeResult:
        yield Sidebar(current="timeline", id="sidebar")
        yield TimelineFeed(id="timeline-feed")


# ==================== DISCOVER SCREEN ====================

class DiscoverFeed(VerticalScroll):
    """Discover feed with trending posts and interactive search."""

    query_text = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._all_posts = []

    def on_mount(self) -> None:
        """Load posts once mounted."""
        self._all_posts = api.get_discover_posts()

    def _filtered_posts(self):
        if not self.query_text:
            return self._all_posts
        q = self.query_text.lower()
        return [
            p for p in self._all_posts
            if q in p.author.lower() or q in p.content.lower()
        ]

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search posts, people, tags...", classes="message-input", id="discover-search")
        yield Container(id="posts-container")
        yield Static("\n→ Suggested Follow", classes="section-header")
        yield Static(
            "  @opensource_dev\n  Building tools for developers | 1.2k followers\n  [f] Follow  [↑↓] Navigate  [Enter] Open  [?] Help",
            classes="suggested-user",
        )

    def watch_query_text(self, query: str) -> None:
        """Update posts when query changes."""
        try:
            container = self.query_one("#posts-container", Container)
            container.remove_children()
            for post in self._filtered_posts():
                container.mount(PostItem(post, classes="post-item"))
        except:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "discover-search":
            self.query_text = event.value


class DiscoverScreen(Container):
    """Discover screen layout."""
    
    def compose(self) -> ComposeResult:
        yield Sidebar(current="discover", id="sidebar")
        yield DiscoverFeed(id="discover-feed")


# ==================== NOTIFICATIONS SCREEN ====================

class NotificationsFeed(VerticalScroll):
    """Notifications feed."""
    
    def compose(self) -> ComposeResult:
        notifications = api.get_notifications()
        unread_count = len([n for n in notifications if not n.read])
        
        yield Static(f"notifications.all | {unread_count} unread | line 1", classes="panel-header")
        
        for notif in notifications:
            yield NotificationItem(notif, classes="notification-item")
        
        yield Static("\n[↑] Previous [n] Next [m] Mark Read [Enter] Open [q] Quit", classes="help-text")


class NotificationsScreen(Container):
    """Notifications screen layout."""
    
    def compose(self) -> ComposeResult:
        yield Sidebar(current="notifications", id="sidebar")
        yield NotificationsFeed(id="notifications-feed")


# ==================== MESSAGES SCREEN ====================

class ConversationsList(VerticalScroll):
    """Middle panel with conversations list."""
    
    def compose(self) -> ComposeResult:
        conversations = api.get_conversations()
        unread_count = len([c for c in conversations if c.unread])
        
        yield Static(f"conversations | {unread_count} unread", classes="panel-header")
        
        for conv in conversations:
            yield ConversationItem(conv, classes="conversation-item")


class ChatView(VerticalScroll):
    """Right panel with chat messages."""
    
    def compose(self) -> ComposeResult:
        # Hardcoded to alice conversation for now
        messages = api.get_conversation_messages("c1")
        
        yield Static("@alice | conversation | line 12", classes="panel-header")
        
        for msg in messages:
            yield ChatMessage(msg, classes="chat-message")
        
        yield Static("-- INSERT --", classes="mode-indicator")
        yield Input(placeholder="Type message... (Esc to cancel)", classes="message-input", id="message-input")



class MessagesScreen(Container):
    """Main messages screen layout."""
    
    def compose(self) -> ComposeResult:
        yield Sidebar(current="messages", id="sidebar")
        yield ConversationsList(id="conversations")
        yield ChatView(id="chat")


# ==================== SETTINGS SCREEN ====================

class SettingsPanel(VerticalScroll):
    """Settings panel with profile and preferences."""
    
    def compose(self) -> ComposeResult:
        settings = api.get_user_settings()
        
        yield Static("settings.profile | line 1", classes="panel-header")
        
        # Profile Picture
        yield Static("\n→ Profile Picture (ASCII)", classes="settings-section-header")
        yield Static("Make ASCII Profile Picture from image file")
        yield Button("Upload file", id="upload-profile-picture", classes="upload-profile-picture")
        # yield Static("      Your profile picture is automatically generated from your username.", classes="settings-help")
        # yield Static(f"    [@#$&●*]\n    |+ YY =|\n    |$%&++=|", classes="ascii-avatar")
        # yield Static("      [:r] Regenerate", classes="settings-action")
        yield Static(f"{settings.ascii_pic}", id="profile-picture-display", classes="ascii-avatar")
        
        # Account Information
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
                    "--font-size", "24",
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


class SettingsScreen(Container):
    """Settings screen layout."""
    
    def compose(self) -> ComposeResult:
        yield Sidebar(current="settings", id="sidebar")
        yield SettingsPanel(id="settings-panel")


# ==================== PROFILE SCREEN ====================

class ProfilePanel(VerticalScroll):
    """Profile panel with large display."""
    
    def compose(self) -> ComposeResult:
        user = api.get_current_user()
        settings = api.get_user_settings()
        
        yield Static("profile | @yourname | line 1", classes="panel-header")
        
        # Centered profile container
        profile_container = Container(classes="profile-center-container")
        
        with profile_container:
            # Profile Picture
            yield Static(
                "    [@#$&●*]\n    |+ YY =|\n    |$%&++=|", 
                classes="profile-avatar-large"
            )
            
            # Display Name
            yield Static(f"{settings.display_name}", classes="profile-name-large")
            
            # Username
            yield Static(f"@{settings.username}", classes="profile-username-display")
            
            # Stats Row
            stats_row = Container(classes="profile-stats-row")
            with stats_row:
                yield Static(f"{user.posts_count}\nPosts", classes="profile-stat-item")
                yield Static(f"{user.following}\nFollowing", classes="profile-stat-item")
                yield Static(f"{user.followers}\nFollowers", classes="profile-stat-item")
            yield stats_row
            
            # Bio Section
            bio_container = Container(classes="profile-bio-container")
            bio_container.border_title = "Bio"
            with bio_container:
                yield Static(f"{settings.bio}", classes="profile-bio-display")
            yield bio_container
        
        yield profile_container
        
        yield Static("\n[:e] Edit Profile  [Esc] Back", classes="help-text")


class ProfileScreen(Container):
    """Profile screen layout."""
    
    def compose(self) -> ComposeResult:
        yield Sidebar(current="profile", id="sidebar")
        yield ProfilePanel(id="profile-panel")


# ==================== MAIN APP ====================

class Proj101App(App):
    """A vim-style social network TUI application."""
    
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
        """Switch to a different screen."""
        if screen_name == self.current_screen_name:
            return
        
        # Screen mapping
        screen_map = {
            "timeline": (TimelineScreen, ":↑↓ Navigate [n] New Post [f] Follow [/] Search [?] Help"),
            "discover": (DiscoverScreen, ":/ - search [f] Follow [↑↓] Navigate [Enter] Open [?] Help"),
            "notifications": (NotificationsScreen, ":[↑] Previous [n] Next [m] Mark Read [Enter] Open [q] Quit"),
            "messages": (MessagesScreen, ":i - insert mode [Ctrl+N] New [↑↓] Navigate [Enter] Open [Esc] Exit"),
            "profile": (ProfileScreen, ":[:e] Edit Profile [Esc] Back"),
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
    
    def action_focus_navigation(self) -> None:
        """Focus on navigation section."""
        try:
            sidebar = self.query_one("#sidebar", Sidebar)
            nav_item = sidebar.query_one(".nav-item", NavigationItem)
            nav_item.focus()
        except:
            pass
    
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
            elif command == "P" or command.upper() == "P":
                self.switch_screen("profile")
    
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

if __name__ == "__main__":
    app = Proj101App()
    app.run()