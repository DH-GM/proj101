import json
import platform
from pathlib import Path
import logging
import os

_DEBUG_FLAG_FILE = Path.home() / ".tuitter_tokens_debug.log"

SERVICE_NAME = "tuitter"
FALLBACK_TOKEN_FILE = Path.home() / ".tuitter_tokens.json"
REFRESH_PLAIN_FILE = Path.home() / ".tuitter_refresh.json"

# Module logger
logger = logging.getLogger("tuitter.auth_storage")



def save_tokens_full(tokens: dict, username: str | None = None) -> None:
    """Save the full tokens JSON in a platform-appropriate place.

    On non-Windows, prefer keyring under key 'oauth_tokens.json'. On Windows,
    prefer DPAPI-encrypted fallback file. Best-effort and non-fatal.
    """
    try:
        import keyring
    except Exception:
        keyring = None

    # Prepare tokens to save; include username when provided so a full-token
    # write won't lose the username that may have been stored separately.
    tokens_to_save = dict(tokens) if isinstance(tokens, dict) else {'tokens': tokens}
    if username:
        tokens_to_save['username'] = username

    # On Windows prefer DPAPI file (keyring backends can be flaky for large blobs)
    if platform.system() == "Windows":
        try:
            import base64
            try:
                import win32crypt
                protected = win32crypt.CryptProtectData(json.dumps(tokens_to_save).encode('utf-8'), None, None, None, None, 0)
                b64 = base64.b64encode(protected).decode('ascii')
                FALLBACK_TOKEN_FILE.write_text(json.dumps({'encrypted': True, 'data': b64}), encoding='utf-8')
                logger.info("auth_storage: wrote encrypted full tokens to fallback file")
                return
            except Exception:
                # If win32crypt not available, fall through to keyring or plaintext
                logger.debug("auth_storage: win32crypt not available for full token save")
        except Exception:
            logger.exception("auth_storage: unexpected error saving full tokens on Windows")

    # Non-Windows or fallback: try keyring first
    if keyring:
        try:
            keyring.set_password(SERVICE_NAME, 'oauth_tokens.json', json.dumps(tokens_to_save, indent=2))
            logger.debug("auth_storage: wrote full tokens to keyring oauth_tokens.json")
            return
        except Exception:
            logger.exception("auth_storage: failed to write full tokens to keyring")

    # Last-resort: plaintext file (not ideal)
    try:
        FALLBACK_TOKEN_FILE.write_text(json.dumps(tokens_to_save), encoding='utf-8')
        logger.warning("auth_storage: wrote plaintext full tokens to fallback file (insecure)")
    except Exception:
        logger.exception("auth_storage: failed to write full tokens to fallback file")


def save_refresh_token(refresh_token: str, username: str | None = None) -> None:
    """Save just the refresh token and optional username.

    On Windows we store a DPAPI-encrypted JSON file. On other platforms we
    attempt to use keyring for small secrets and fall back to the file.
    """
    try:
        import keyring
    except Exception:
        keyring = None

    if platform.system() == "Windows":
        try:
            import base64
            try:
                import win32crypt
                payload = json.dumps({'refresh_token': refresh_token, 'username': username}).encode('utf-8')
                protected = win32crypt.CryptProtectData(payload, None, None, None, None, 0)
                b64 = base64.b64encode(protected).decode('ascii')
                FALLBACK_TOKEN_FILE.write_text(json.dumps({'encrypted': True, 'data': b64}), encoding='utf-8')
                logger.info("auth_storage: saved DPAPI-encrypted refresh token to fallback file")
                # Also attempt to save refresh_token and username to keyring if available
                # (some environments can't decrypt the DPAPI file on startup; storing
                # the small refresh token in keyring as a secondary copy is low-risk
                # and improves cross-session resilience)
                # Store username in keyring (small data)
                if keyring and username is not None:
                    try:
                        keyring.set_password(SERVICE_NAME, 'username', username)
                    except Exception:
                        logger.debug("auth_storage: failed to write username to keyring (non-fatal)")

                return
            except Exception:
                logger.exception("auth_storage: win32crypt not available or failed, will fallback")
        except Exception:
            logger.exception("auth_storage: unexpected error saving refresh token on Windows")

    # Non-Windows: try keyring
    if keyring:
        try:
            keyring.set_password(SERVICE_NAME, 'refresh_token', refresh_token)
            logger.debug("auth_storage: saved refresh_token to keyring")
            if username:
                try:
                    keyring.set_password(SERVICE_NAME, 'username', username)
                except Exception:
                    logger.debug("auth_storage: failed to write username to keyring (non-fatal)")
            return
        except Exception:
            logger.exception("auth_storage: keyring write failed for refresh_token; falling back to file")

    # Fallback to plaintext file
    try:
        FALLBACK_TOKEN_FILE.write_text(json.dumps({'refresh_token': refresh_token, 'username': username}), encoding='utf-8')
        logger.warning("auth_storage: wrote plaintext refresh token to fallback file (insecure)")
    except Exception:
        logger.exception("auth_storage: failed to write refresh token to fallback file")


def load_tokens() -> dict | None:
    """Load tokens.

    Returns either:
      - {'tokens': <full tokens dict>, 'username': <username>} if full token blob found
      - {'refresh_token': <str>, 'username': <str|None>} if only refresh token found
      - None if nothing found
    """
    try:
        import keyring
    except Exception:
        keyring = None

    # Lightweight debug trace that doesn't depend on the app logger being
    # configured (helps diagnose startup token-load issues across sessions).
    try:
        _DEBUG_FLAG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _DEBUG_FLAG_FILE.open("a", encoding="utf-8") as _dbg:
            _dbg.write(f"load_tokens: called; platform={platform.system()}\n")
    except Exception:
        pass

    # 1) Try keyring full-token blob
    if keyring:
        try:
            token_blob = keyring.get_password(SERVICE_NAME, 'oauth_tokens.json')
            if token_blob:
                parsed = json.loads(token_blob)
                if isinstance(parsed, dict) and parsed.get('access_token'):
                    try:
                        with _DEBUG_FLAG_FILE.open("a", encoding="utf-8") as _dbg:
                            _dbg.write("load_tokens: found full-token blob in keyring\n")
                    except Exception:
                        pass
                    return {'tokens': parsed, 'username': parsed.get('username')}
        except Exception:
            logger.debug("auth_storage: keyring read for full token blob failed (non-fatal)")
            try:
                with _DEBUG_FLAG_FILE.open("a", encoding="utf-8") as _dbg:
                    _dbg.write("load_tokens: keyring full-token read failed\n")
            except Exception:
                pass

    # 2) Try fallback file (may be DPAPI-encrypted or plaintext)
    if FALLBACK_TOKEN_FILE.exists():
        try:
            try:
                with _DEBUG_FLAG_FILE.open("a", encoding="utf-8") as _dbg:
                    _dbg.write(f"load_tokens: found fallback file at {FALLBACK_TOKEN_FILE}\n")
            except Exception:
                pass
            raw = FALLBACK_TOKEN_FILE.read_text(encoding='utf-8') or '{}'
            data = json.loads(raw)

            if isinstance(data, dict) and data.get('encrypted') and isinstance(data.get('data'), str):
                try:
                    import base64
                    import win32crypt
                    import traceback
                    protected = base64.b64decode(data.get('data'))

                    # Try multiple call signatures for CryptUnprotectData to be
                    # resilient against differences in pywin32 versions.
                    unprotected = None
                    last_exc = None
                    for args in ((protected, None, None, None, 0), (protected,)):
                        try:
                            res = win32crypt.CryptUnprotectData(*args)
                            # res may be a tuple where one element is the data
                            if isinstance(res, (tuple, list)):
                                # Prefer the first non-empty bytes or str element
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
                        # Record the last exception details to the lightweight
                        # debug file for offline inspection, then raise the
                        # last exception so the outer logic falls back.
                        try:
                            with _DEBUG_FLAG_FILE.open("a", encoding="utf-8") as _dbg:
                                _dbg.write("load_tokens: DPAPI decrypt attempt failed; last exception:\n")
                                if last_exc is not None:
                                    import traceback as _tb
                                    _dbg.write("".join(_tb.format_exception(type(last_exc), last_exc, last_exc.__traceback__)))
                                else:
                                    _dbg.write("(no exception captured)\n")
                        except Exception:
                            pass
                        # Re-raise the last exception to be handled by outer
                        # except block (which writes a short FAILED marker).
                        if last_exc is not None:
                            raise last_exc
                        else:
                            raise Exception("DPAPI decrypt failed")

                    # win32crypt.CryptUnprotectData may return bytes or str
                    try:
                        if isinstance(unprotected, bytes):
                            decoded = unprotected.decode('utf-8')
                        elif isinstance(unprotected, str):
                            decoded = unprotected
                        else:
                            # Fallback: coerce to str
                            decoded = str(unprotected)
                        inner = json.loads(decoded)
                    except Exception:
                        # If parsing fails, write the problematic value to debug file
                        try:
                            with _DEBUG_FLAG_FILE.open("a", encoding="utf-8") as _dbg:
                                _dbg.write("load_tokens: DPAPI unprotected payload not JSON; repr:\n")
                                _dbg.write(repr(unprotected) + "\n")
                        except Exception:
                            pass
                        raise
                    if isinstance(inner, dict):
                        try:
                            with _DEBUG_FLAG_FILE.open("a", encoding="utf-8") as _dbg:
                                _dbg.write(f"load_tokens: DPAPI decrypt succeeded, inner keys={list(inner.keys())}\n")
                        except Exception:
                            pass
                        # If inner contains full tokens, return that
                        if inner.get('access_token'):
                            return {'tokens': inner, 'username': inner.get('username')}
                        # Otherwise inner is probably a refresh_token payload
                        return {'refresh_token': inner.get('refresh_token'), 'username': inner.get('username')}
                except Exception:
                    logger.exception("auth_storage: failed to decrypt DPAPI fallback file (non-fatal)")
                    try:
                        with _DEBUG_FLAG_FILE.open("a", encoding="utf-8") as _dbg:
                            _dbg.write("load_tokens: DPAPI decrypt FAILED\n")
                    except Exception:
                        pass

            # If file contains full token blob plaintext
            if isinstance(data, dict) and data.get('access_token'):
                return {'tokens': data, 'username': data.get('username')}

            # Fallback plaintext refresh token
            if isinstance(data, dict) and data.get('refresh_token'):
                try:
                    with _DEBUG_FLAG_FILE.open("a", encoding="utf-8") as _dbg:
                        _dbg.write("load_tokens: found plaintext refresh_token in fallback file\n")
                except Exception:
                    pass
                return {'refresh_token': data.get('refresh_token'), 'username': data.get('username')}
        except Exception:
            logger.exception("auth_storage: failed to read fallback token file (non-fatal)")
            try:
                with _DEBUG_FLAG_FILE.open("a", encoding="utf-8") as _dbg:
                    _dbg.write("load_tokens: failed to read fallback file (exception)\n")
            except Exception:
                pass

    # 3) Try keyring refresh_token / username
    if keyring:
        try:
            refresh = keyring.get_password(SERVICE_NAME, 'refresh_token')
            username = keyring.get_password(SERVICE_NAME, 'username')
            if refresh:
                return {'refresh_token': refresh, 'username': username}
        except Exception:
            logger.debug("auth_storage: keyring read for refresh_token failed (non-fatal)")

    # 4) Try plaintext refresh fallback file (last-resort)
    if REFRESH_PLAIN_FILE.exists():
        try:
            raw = REFRESH_PLAIN_FILE.read_text(encoding='utf-8') or '{}'
            data = json.loads(raw)
            if isinstance(data, dict) and data.get('refresh_token'):
                try:
                    with _DEBUG_FLAG_FILE.open("a", encoding="utf-8") as _dbg:
                        _dbg.write("load_tokens: found plaintext refresh fallback file\n")
                except Exception:
                    pass
                return {'refresh_token': data.get('refresh_token'), 'username': data.get('username')}
        except Exception:
            logger.exception("auth_storage: failed to read plaintext refresh fallback file (non-fatal)")

    return None


def clear_tokens() -> None:
    try:
        try:
            import keyring
        except Exception:
            keyring = None

        if keyring:
            try:
                keyring.delete_password(SERVICE_NAME, 'refresh_token')
            except Exception:
                pass
            try:
                keyring.delete_password(SERVICE_NAME, 'username')
            except Exception:
                pass
            try:
                keyring.delete_password(SERVICE_NAME, 'oauth_tokens.json')
            except Exception:
                pass

        if FALLBACK_TOKEN_FILE.exists():
            try:
                FALLBACK_TOKEN_FILE.unlink()
            except Exception:
                pass
    except Exception:
        logger.exception("auth_storage: failed to clear tokens (non-fatal)")
