from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll, ScrollableContainer
from textual.widgets import Header, Footer, Static, Input, Label, Button, Checkbox
from textual.reactive import reactive
from datetime import datetime, timedelta
from api_interface import api


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
    
    def __init__(self, label: str, screen_name: str, active: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.label_text = label
        self.screen_name = screen_name
        self.active = active
        if active:
            self.add_class("active")
    
    def render(self) -> str:
        prefix = "▾ " if self.active else "▸ "
        return f"{prefix}{self.label_text}"
    
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


class StatsDisplay(Static):
    """Display user stats."""
    
    def compose(self) -> ComposeResult:
        user = api.get_current_user()
        yield Static(f"Posts {user.posts_count}", classes="stat-item")
        yield Static(f"Following {user.following}", classes="stat-item")
        yield Static(f"Followers {user.followers}", classes="stat-item")


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
        yield Static("~ NAVIGATION ~", classes="section-header")
        yield NavigationItem("Timeline", "timeline", self.current_screen == "timeline", classes="nav-item", id="nav-timeline")
        yield NavigationItem("Discover", "discover", self.current_screen == "discover", classes="nav-item", id="nav-discover")
        yield NavigationItem("Notifications", "notifications", self.current_screen == "notifications", classes="nav-item", id="nav-notifications")
        yield NavigationItem("Messages", "messages", self.current_screen == "messages", classes="nav-item", id="nav-messages")
        yield NavigationItem("Settings", "settings", self.current_screen == "settings", classes="nav-item", id="nav-settings")
        
        yield Static("\n~ STATS ~", classes="section-header")
        yield StatsDisplay()
        
        yield Static("\n~ COMMANDS ~", classes="section-header")
        
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
        elif self.current_screen == "settings":
            yield CommandItem(":w", "save", classes="command-item")
            yield CommandItem(":q", "quit", classes="command-item")
            yield CommandItem(":e", "edit", classes="command-item")
        
        yield CommandItem(":d", "delete", classes="command-item")
        yield CommandItem(":s", "search", classes="command-item")
    
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
        yield Static("      Your profile picture is automatically generated from your username.", classes="settings-help")
        yield Static(f"    [@#$&●*]\n    |+ YY =|\n    |$%&++=|", classes="ascii-avatar")
        yield Static("      [:r] Regenerate", classes="settings-action")
        
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


class SettingsScreen(Container):
    """Settings screen layout."""
    
    def compose(self) -> ComposeResult:
        yield Sidebar(current="settings", id="sidebar")
        yield SettingsPanel(id="settings-panel")


# ==================== MAIN APP ====================

class Proj101App(App):
    """A vim-style social network TUI application."""
    
    CSS_PATH = "main.tcss"
    
    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("i", "insert_mode", "Insert", show=True),
        Binding("escape", "normal_mode", "Normal", show=False),
        Binding("d", "toggle_dark", "Dark", show=True),
        Binding("1", "show_timeline", "Timeline", show=False),
        Binding("2", "show_discover", "Discover", show=False),
        Binding("3", "show_notifications", "Notifications", show=False),
        Binding("4", "show_messages", "Messages", show=False),
        Binding("5", "show_settings", "Settings", show=False),
    ]
    
    current_screen_name = reactive("timeline")
    
    def compose(self) -> ComposeResult:
        yield Static("proj101 [timeline] @yourname", id="app-header")
        yield TimelineScreen(id="screen-container")
        yield Static(":↑↓ Navigate [n] New Post [f] Follow [/] Search [?] Help", id="app-footer")
    
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


if __name__ == "__main__":
    app = Proj101App()
    app.run()