from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Static, Input, Button
from textual.reactive import reactive
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
    """Interactive post: ♥, ⇄, 💬 with inline comments."""
    def __init__(self, post: _Post, **kwargs):
        super().__init__(**kwargs)
        self.post = post
        self._comments_open = False

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

# ---------- timeline / discover ----------
class TimelineFeed(VerticalScroll):
    def compose(self) -> ComposeResult:
        posts = api.get_timeline()
        unread = len([p for p in posts if (datetime.now() - p.timestamp).seconds < 3600])
        yield Static(f"timeline.home | {unread} new posts | line 1", classes="panel-header")
        for p in posts:
            yield PostItem(p, classes="post-item")


class TimelineScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="timeline", id="sidebar")
        yield TimelineFeed(id="timeline-feed")


# ---------- discover (restore v1 behavior, keep v2 PostItem) ----------
class DiscoverFeed(VerticalScroll):
    query_text = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._all_posts = []

    def on_mount(self) -> None:
        # load once and render
        self._all_posts = api.get_discover_posts()
        self._render_posts()

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
        except Exception:
            # be resilient if first render happens before container exists
            pass

    def compose(self) -> ComposeResult:
        yield Static("discover.trending | line 1", classes="panel-header")
        yield Input(
            placeholder="Search posts, people, tags...",
            classes="message-input",
            id="discover-search",
        )
        yield Container(id="posts-container")

        # Optional: the suggested follow block from v1
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
        s = api.get_user_settings()
        yield Static("settings.profile | line 1", classes="panel-header")
        yield Static("\n→ Profile Picture (ASCII)", classes="settings-section-header")
        yield Static(" Your profile picture is automatically generated from your username.", classes="settings-help")
        yield Static(f" {api.get_current_user().avatar_ascii}", classes="ascii-avatar")
        yield Static(" [:r] Regenerate", classes="settings-action")
        yield Static("\n→ Account Information", classes="settings-section-header")
        yield Static(f" Username:\n @{s.username}", classes="settings-field")
        yield Static(f"\n Display Name:\n {s.display_name}", classes="settings-field")
        yield Static(f"\n Bio:\n {s.bio}", classes="settings-field")


class SettingsScreen(Container):
    def compose(self) -> ComposeResult:
        yield Sidebar(current="settings", id="sidebar")
        yield SettingsPanel(id="settings-panel")

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


if __name__ == "__main__":
    Proj101App().run()