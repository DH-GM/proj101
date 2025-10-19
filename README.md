# Tuitter 🚀

**Twitter + LazyGit = Tuitter**

A vim-style social network TUI (Terminal User Interface) that brings social media to your terminal with powerful keyboard shortcuts and beautiful design.

![Tuitter Demo](https://img.shields.io/badge/TUI-Textual-blue) ![Python](https://img.shields.io/badge/Python-3.12+-green) ![License](https://img.shields.io/badge/license-MIT-purple)

## ✨ Features

- 🎮 **Vim-style Navigation** - Navigate with keyboard shortcuts (1-5 for screens, i for insert, Esc for normal)
- 📱 **Multiple Screens** - Timeline, Discover, Messages, Notifications, Settings
- 🔍 **Live Search** - Real-time filtering in Discover feed
- 💬 **Direct Messaging** - Multi-conversation chat system
- 🎨 **ASCII Art Profiles** - Generate profile pictures from images
- 🔔 **Rich Notifications** - Likes, reposts, mentions, follows
- 🌐 **Web Deployable** - Run in terminal OR serve as web app
- ⚡ **Backend Ready** - Clean API layer for AWS Lambda integration

## 🎯 Quick Start

### Clone with submodules

```bash
git clone --recurse-submodules https://github.com/DH-GM/proj101.git
cd proj101
```

### Install and run

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
python3 main.py
```

### Or run on web

```bash
textual-web --config serve.toml
```

Open browser at `http://localhost:8000`

## 📸 Screenshots

**Messages Screen**
```
┌─ proj101 [messages] @yourname ─────────────────────────┐
│ ~ NAVIGATION ~     │ conversations | 2 unread         │
│ ▸ Timeline         │                                  │
│ ▸ Discover         │ • @alice                         │
│ ▸ Notifications    │   Thanks! Let me know...         │
│ ▸ Messages         │   2m ago • unread                │
│ ▸ Settings         │                                  │
│                    │ @charlie                         │
│ ~ STATS ~          │   That sounds perfect!           │
│ Posts 142          │   1h ago • unread                │
│ Following 328      │                                  │
│ Followers 891      │                                  │
│                    │                                  │
│ ~ COMMANDS ~       │   [Messages displayed here]      │
│ :n - new message   │                                  │
│ :r - reply         └──────────────────────────────────┘
```

## 🎮 Keybindings

| Key | Action |
|-----|--------|
| `1` | Timeline |
| `2` | Discover |
| `3` | Notifications |
| `4` | Messages |
| `5` | Settings |
| `i` | Insert mode |
| `Esc` | Normal mode |
| `d` | Toggle dark/light mode |
| `q` | Quit |

## 🏗️ Architecture

### Frontend (TUI)
- **Textual Framework** - Modern Python TUI framework
- **Reactive UI** - Live updates without page reloads
- **Custom Widgets** - Reusable components for posts, messages, notifications

### Backend (AWS Serverless)
- **AWS Lambda** - Serverless compute
- **API Gateway** - RESTful HTTP endpoints
- **S3** - Media and profile picture storage
- **DynamoDB** - NoSQL database (planned)
- **JWT Authentication** - Secure token-based auth

### Data Flow

```
TUI App → API Interface → API Gateway → Lambda → DynamoDB/S3
                ↑                                      ↓
            Mock Data                            Real Data
```

## 📁 Project Structure

```
proj101/
├── main.py                 # Main TUI application
├── main.tcss              # Textual CSS styling
├── data_models.py         # Data structures
├── api_interface.py       # API abstraction layer
├── serve.toml            # Textual Web config
├── requirements.txt      # Python dependencies
├── asciifer/            # Image to ASCII converter (submodule)
├── backend/             # Backend code (planned)
│   ├── auth.py         # JWT and OAuth2
│   └── lambda/         # Lambda functions
├── INSTALL.md          # Detailed installation guide
└── PROJECT_DESCRIPTION.md  # Full project details
```

## 🔌 Connecting Your Backend

The app is designed with a clean API abstraction layer. To connect to a real backend:

**1. Replace the FakeAPI with your implementation:**

```python
# In api_interface.py
from backend.real_api import RealAPI

# Change from:
api = FakeAPI()

# To:
api = RealAPI(base_url="https://your-api.com", token="...")
```

**2. Implement the APIInterface:**

```python
class RealAPI(APIInterface):
    def get_timeline(self, limit: int = 50) -> List[Post]:
        response = requests.get(f"{self.base_url}/timeline?limit={limit}")
        return [Post(**p) for p in response.json()]
    
    # Implement other methods...
```

See [PROJECT_DESCRIPTION.md](PROJECT_DESCRIPTION.md) for full backend integration guide.

## 🎨 Features in Detail

### Timeline
- View posts from users you follow
- Like, repost, comment interactions
- Real-time updates

### Discover
- Trending posts with hashtags
- **Live search** - Filter by content, author, or tags
- Suggested users to follow

### Messages
- Direct messaging with multiple conversations
- Unread message indicators
- Real-time chat bubbles (sent/received)

### Notifications
- Likes, reposts, mentions, follows
- Unread indicators
- Navigate and mark as read

### Settings
- **ASCII Profile Pictures** - Upload images and convert to ASCII art
- Account information management
- OAuth connections (GitHub, GitLab, Google, Discord)
- Privacy preferences

## 🛠️ Development

### Running locally

```bash
source venv/bin/activate
python3 main.py
```

### Adding new screens

1. Create a `FeedClass` extending `VerticalScroll`
2. Create a `ScreenClass` extending `Container`
3. Add to `screen_map` in `switch_screen()`
4. Add keybinding to `BINDINGS`

### Styling

Edit `main.tcss` to customize colors, spacing, and layout.

## 📦 Dependencies

- **textual** - TUI framework
- **textual-web** - Web server for TUI apps
- **requests** - HTTP client
- **Pillow** - Image processing
- **asciifer** - ASCII art generation (submodule)

## 🚀 Deployment

### Web Deployment

```bash
textual-web --config serve.toml
```

### AWS Lambda Deployment (Coming Soon)

```bash
serverless deploy
```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

MIT License - See [LICENSE](LICENSE) for details

## 🙏 Credits

- **Textual** - [textualize.io](https://textual.textualize.io/)
- **asciifer** - [github.com/Refffy/asciifer](https://github.com/Refffy/asciifer)

## 📧 Support

- 📖 [Full Documentation](PROJECT_DESCRIPTION.md)
- 🔧 [Installation Guide](INSTALL.md)
- 🐛 [Report Issues](https://github.com/DH-GM/proj101/issues)

---

**Built with ❤️ for terminal enthusiasts**

*Inspired by Twitter's simplicity and LazyGit's efficiency*

