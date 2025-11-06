# Tuitter — terminal social, made for people who love the terminal 🚀

Tuitter is a keyboard-first, terminal-native social client built for people
who prefer speed, privacy, and staying in the flow of their terminal
workflows. Whether you're a developer, sysadmin, designer, or just love
efficient tools, Tuitter gives you a lightweight way to follow timelines,
compose posts, and share expressive ASCII art without leaving your shell.

## Quick install

Install from PyPI (recommended):

```bash
pip install tuitter
# or, sandboxed with pipx for an isolated CLI install
pipx install tuitter
```

Run the app:

```bash
tuitter
```

## Why people love Tuitter

- Speed & focus — keyboard-first controls and lightweight rendering make it
  fast to scan timelines and compose replies.
- Minimal context switching — keep your hands on the keyboard and stay inside
  your terminal workflows.
- Privacy-forward — tokens are kept locally and the client communicates with
  the official hosted backend operated by the Tuitter team.
- Fun & expressive — convert images and videos to ASCII art and create
  playful profile pictures with the built-in generator.

## Who should try it

- Terminal-first professionals and power users
- People who prefer small, focused tools over bloated GUIs
- Communities that value privacy

## Key features

- Keyboard-first navigation (1–5 screens, vim controls)
- Timeline, Discover, Messages, Notifications, and Settings screens
- Direct messages and threaded conversations
- ASCII avatar generator and image/video → ASCII conversion

## System requirements

- Python 3.8+ (3.10–3.13 recommended)
- `tkinter` — for native file dialogs on some platforms (Debian/Ubuntu: `sudo apt install python3-tk`)
- `ffmpeg` — required only for video → ASCII conversion; ensure `ffmpeg` is on PATH

## Authentication & reference backend

Tuitter communicates with an HTTP backend using OIDC ID tokens (the reference
deployment uses AWS Cognito). The packaged client works with the official
hosted backend operated by the Tuitter team. Tokens are stored locally using
`keyring` when available or a DPAPI-encrypted fallback on Windows.

Reference backend architecture (brief): the example backend is a FastAPI
application packaged to run on AWS Lambda (an adapter like Mangum is used),
exposed through API Gateway, and backed by an RDS PostgreSQL database for
persistent data.

## Privacy & security

-- Tokens remain on your device and are not sent to third-party services.
-- The hosted backend and data retention policies are managed by the Tuitter
team; if you have questions about data handling, contact us via issues.

## Troubleshooting (common user issues)

- "No module named tkinter": install the OS package that provides tkinter
  (Debian/Ubuntu: `sudo apt install python3-tk`).
- "No ffmpeg" when converting video: install ffmpeg and ensure it's on PATH.
  -- 401 Unauthorized after login: usually a backend configuration mismatch —
  please file an issue so the Tuitter team can investigate; end users do not
  host backends themselves.
- DPAPI decrypt errors on Windows: ensure `pywin32` is installed and you're
  running as the same user who encrypted the tokens.

## Getting help & community

- File issues or feature requests: https://github.com/tuitter/tuitter/issues
- When asking for help, include the app version (`tuitter --version`) and
  your platform (OS and Python version).
  -- Want to contribute? Open an issue or PR and we can help you get started.
