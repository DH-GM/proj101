"""Token persistence helpers for tuitter.

This module provides a single canonical writer and reader for the full
token blob. Historically the codebase used a variety of shapes (separate
`refresh_token` entries, a small `username` key, or an entire JSON blob).
We normalize to one shape: the full token dict is stored under the key
`oauth_tokens.json` (in keyring when available) or in a fallback file.

Functions:
  - save_tokens_full(tokens: dict, username: Optional[str]) -> None
  - load_tokens() -> Optional[dict]  # returns {'tokens': {...}, 'username': '...'}
  - clear_tokens() -> None
"""

from __future__ import annotations

import json
import platform
from pathlib import Path
import os
import logging
from typing import Optional

_DEBUG_FLAG_FILE = Path.home() / ".tuitter_tokens_debug.log"
SERVICE_NAME = "tuitter"
FALLBACK_TOKEN_FILE = Path.home() / ".tuitter_tokens.json"

logger = logging.getLogger("tuitter.auth_storage")

# Ensure auth_storage logger writes to the same debug file used elsewhere,
# but only when TUITTER_DEBUG is enabled.
if os.getenv("TUITTER_DEBUG"):
    if not any(isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == str(_DEBUG_FLAG_FILE) for h in logger.handlers):
        try:
            fh = logging.FileHandler(str(_DEBUG_FLAG_FILE), encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
            logger.addHandler(fh)
        except Exception:
            # never fail core logic for logging issues
            pass
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.WARNING)


def _write_debug(msg: str) -> None:
    try:
        # Only write debug traces to the on-disk debug file when debugging is enabled.
        if not os.getenv("TUITTER_DEBUG"):
            return
        _DEBUG_FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _DEBUG_FLAG_FILE.open("a", encoding="utf-8") as _dbg:
            _dbg.write(msg + "\n")
    except Exception:
        # Debug logging must never fail core logic
        pass


def save_tokens_full(tokens: dict, username: Optional[str] = None) -> None:
    """Persist the full token blob in a platform-appropriate store.

    This is the canonical writer used throughout the app. It will try, in
    order: (1) platform DPAPI-encrypted fallback file on Windows (if
    win32crypt is available), (2) keyring under key 'oauth_tokens.json',
    (3) plaintext fallback file as a last resort.

    Writing the separate small 'username' key into keyring is performed as
    a best-effort compatibility step so UI code that still reads
    keyring.get_password(SERVICE_NAME, 'username') continues to work.
    """
    try:
        import keyring
    except Exception:
        keyring = None

    tokens_to_save = dict(tokens) if isinstance(tokens, dict) else {"tokens": tokens}
    if username:
        tokens_to_save.setdefault("username", username)

    # Prefer encrypted fallback file on Windows when win32crypt is available
    if platform.system() == "Windows":
        try:
            import base64
            try:
                import win32crypt  # type: ignore

                protected = win32crypt.CryptProtectData(
                    json.dumps(tokens_to_save).encode("utf-8"), None, None, None, None, 0
                )
                b64 = base64.b64encode(protected).decode("ascii")
                payload = json.dumps({"encrypted": True, "data": b64})
                # Atomic write: write to temp file then replace
                try:
                    import tempfile
                    tmp = None
                    FALLBACK_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(FALLBACK_TOKEN_FILE.parent)) as fh:
                        tmp = fh.name
                        fh.write(payload)
                    # Use os.replace for atomic rename across platforms
                    import os
                    os.replace(tmp, str(FALLBACK_TOKEN_FILE))
                    logger.info("auth_storage: wrote encrypted full tokens to fallback file (atomic)")
                except Exception:
                    logger.exception("auth_storage: failed atomic write for DPAPI fallback; trying direct write")
                    FALLBACK_TOKEN_FILE.write_text(payload, encoding="utf-8")
                # best-effort username into keyring
                if keyring and username:
                    try:
                        keyring.set_password(SERVICE_NAME, "username", username)
                    except Exception:
                        logger.debug("auth_storage: failed to write username to keyring (non-fatal)")
                return
            except Exception:
                logger.debug("auth_storage: win32crypt not available or failed; falling back to keyring/plaintext")
        except Exception:
            logger.exception("auth_storage: unexpected error while attempting DPAPI save")

    # Try keyring for the full token blob
    if keyring:
        try:
            keyring.set_password(SERVICE_NAME, "oauth_tokens.json", json.dumps(tokens_to_save, indent=2))
            logger.debug("auth_storage: wrote full tokens to keyring oauth_tokens.json")
            if username:
                try:
                    keyring.set_password(SERVICE_NAME, "username", username)
                except Exception:
                    logger.debug("auth_storage: failed to write username to keyring (non-fatal)")
            return
        except Exception:
            logger.exception("auth_storage: failed to write full tokens to keyring; will try file fallback")

    # Last resort: plaintext fallback file (insecure)
    try:
        FALLBACK_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(tokens_to_save)
        try:
            import tempfile, os
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(FALLBACK_TOKEN_FILE.parent)) as fh:
                tmp = fh.name
                fh.write(payload)
            os.replace(tmp, str(FALLBACK_TOKEN_FILE))
            logger.warning("auth_storage: wrote plaintext full tokens to fallback file (insecure, atomic)")
        except Exception:
            # Best-effort fallback to direct write if atomic rename fails
            FALLBACK_TOKEN_FILE.write_text(payload, encoding="utf-8")
            logger.warning("auth_storage: wrote plaintext full tokens to fallback file (insecure)")

        if keyring and username:
            try:
                keyring.set_password(SERVICE_NAME, "username", username)
            except Exception:
                logger.debug("auth_storage: failed to write username to keyring (non-fatal)")
    except Exception:
        logger.exception("auth_storage: failed to write full tokens to fallback file")


def load_tokens() -> Optional[dict]:
    """Load the canonical full-token blob and return a normalized dict.

    Returns either None or {'tokens': <dict>, 'username': <str or None>}.
    The function will try keyring first and then the fallback file (which may
    be DPAPI-encrypted on Windows).
    """
    try:
        import keyring
    except Exception:
        keyring = None

    _write_debug(f"load_tokens: called; platform={platform.system()}")

    # 1) keyring blob
    if keyring:
        try:
            token_blob = keyring.get_password(SERVICE_NAME, "oauth_tokens.json")
            if token_blob:
                parsed = json.loads(token_blob)
                if isinstance(parsed, dict) and parsed.get("access_token"):
                    username = parsed.get("username")
                    # If username is missing in the blob, try the small username key
                    if not username:
                        try:
                            username = keyring.get_password(SERVICE_NAME, "username")
                        except Exception:
                            username = None
                    _write_debug("load_tokens: found full-token blob in keyring")
                    return {"tokens": parsed, "username": username}
        except Exception:
            logger.debug("auth_storage: keyring read for full token blob failed (non-fatal)")
            _write_debug("load_tokens: keyring full-token read failed")

    # 2) fallback file
    if FALLBACK_TOKEN_FILE.exists():
        _write_debug(f"load_tokens: found fallback file at {FALLBACK_TOKEN_FILE}")
        try:
            raw = FALLBACK_TOKEN_FILE.read_text(encoding="utf-8") or "{}"
            data = json.loads(raw)
        except Exception:
            return None

        # Encrypted DPAPI payload
        if isinstance(data, dict) and data.get("encrypted") and isinstance(data.get("data"), str):
            try:
                import base64
                try:
                    import win32crypt  # type: ignore
                    protected = base64.b64decode(data.get("data"))
                    # try multiple signatures for CryptUnprotectData
                    unprotected = None
                    last_exc = None
                    for args in ((protected, None, None, None, 0), (protected,)):
                        try:
                            res = win32crypt.CryptUnprotectData(*args)
                            if isinstance(res, (tuple, list)):
                                chosen = None
                                for part in res:
                                    if isinstance(part, (bytes, str)) and part:
                                        chosen = part
                                        break
                                unprotected = chosen if chosen is not None else res[0]
                            else:
                                unprotected = res
                            break
                        except Exception as e:
                            last_exc = e

                    if unprotected is None:
                        if last_exc is not None:
                            raise last_exc
                        raise Exception("DPAPI decrypt failed")

                    if isinstance(unprotected, bytes):
                        decoded = unprotected.decode("utf-8")
                    elif isinstance(unprotected, str):
                        decoded = unprotected
                    else:
                        decoded = str(unprotected)

                    inner = json.loads(decoded)
                    if isinstance(inner, dict) and inner.get("access_token"):
                        return {"tokens": inner, "username": inner.get("username")}
                except Exception:
                    logger.exception("auth_storage: failed to decrypt DPAPI fallback file (non-fatal)")
                    _write_debug("load_tokens: DPAPI decrypt FAILED")
            except Exception:
                # If base64/win32crypt import fails, fall through to plaintext handling
                logger.debug("auth_storage: DPAPI decrypt path not available")

        # Plaintext full-token JSON
        if isinstance(data, dict) and data.get("access_token"):
            return {"tokens": data, "username": data.get("username")}

    return None


def clear_tokens() -> None:
    """Remove stored tokens and username from all backends (best-effort)."""
    try:
        import keyring
    except Exception:
        keyring = None

    if keyring:
        try:
            keyring.delete_password(SERVICE_NAME, "oauth_tokens.json")
        except Exception:
            pass
        try:
            keyring.delete_password(SERVICE_NAME, "username")
        except Exception:
            pass

    try:
        if FALLBACK_TOKEN_FILE.exists():
            FALLBACK_TOKEN_FILE.unlink()
    except Exception:
        pass

