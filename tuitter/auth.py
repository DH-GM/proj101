"""
Simplified authentication module using system keyring and dynamic port allocation.
Handles OAuth flow securely and manages token storage.
"""
import http.server
import socketserver
import webbrowser
import threading
import requests
import keyring
import json
import sys
import logging
import os
import platform
from pathlib import Path
from urllib.parse import urlencode, parse_qs, urlparse
import socket
from typing import Dict, Optional
import time

# OAuth configuration constants
COGNITO_DOMAIN = "https://us-east-2xzzmuowl9.auth.us-east-2.amazoncognito.com"
COGNITO_AUTH_URL = f"{COGNITO_DOMAIN}/login"
COGNITO_TOKEN_URL = f"{COGNITO_DOMAIN}/oauth2/token"
COGNITO_USERINFO_URL = f"{COGNITO_DOMAIN}/oauth2/userInfo"
CLIENT_ID = "7109b3p9beveapsmr806freqnn"
CLIENT_SECRET = "1t46ik23730a5fbboiimdbh8ffkicnm69c40ifbg9jou401pft02"
REDIRECT_PORT = 5173  # Fixed redirect port as configured in Cognito
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/callback"
SERVICE_NAME = "tuiitter"  # Keyring service name
SCOPES = ["email", "openid", "phone"]
FALLBACK_TOKEN_FILE = Path.home() / ".tuitter_tokens.json"

class AuthError(Exception):
    """Authentication related errors"""
    pass

def _make_handler(auth_event, auth_response):
    """Return a handler class bound to the given event and response dict.

    HTTPServer needs a class; this factory produces one that uses the
    shared auth_event/auth_response objects so the main thread can wait
    and read results.
    """
    class AuthCallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            """Handle OAuth callback"""
            try:
                parsed = urlparse(self.path)
                params = parse_qs(parsed.query)
                code = params.get('code', [None])[0]

                if not code:
                    raise AuthError("No authorization code received")

                auth_response['code'] = code

                # Send success page
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                success_html = """
                    <html><body style='font-family: system-ui; padding: 2em; text-align: center'>
                        <h1 style='color: #4CAF50'>Authentication Successful!</h1>
                        <p>You can close this window and return to the terminal.</p>
                    </body></html>
                """
                self.wfile.write(success_html.encode('utf-8'))
            except Exception as e:
                auth_response['error'] = str(e)
                self.send_response(400)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                error_html = f"""
                    <html><body style='font-family: system-ui; padding: 2em; text-align: center'>
                        <h1 style='color: #F44336'>Authentication Failed</h1>
                        <p>{str(e)}</p>
                        <p>Please close this window and try again.</p>
                    </body></html>
                """
                self.wfile.write(error_html.encode('utf-8'))
            finally:
                # Signal the main thread that the callback was received
                auth_event.set()

        def log_message(self, format, *args):
            # suppress console logging from BaseHTTPRequestHandler
            return

    return AuthCallbackHandler

def authenticate() -> Dict[str, str]:
    """Complete OAuth flow and store tokens in system keyring.
    Returns dict with username and tokens on success.
    Raises AuthError on failure.
    """
    # Create server with fixed port that matches Cognito configuration
    auth_event = threading.Event()
    auth_response: Dict[str, str] = {}

    # Configure logging for debug mode (enable by setting TUITTER_DEBUG=1)
    logger = logging.getLogger("tuitter.auth")
    if not logger.handlers:
        level = logging.DEBUG if os.getenv("TUITTER_DEBUG") else logging.WARNING
        logger.setLevel(level)
        stream = logging.StreamHandler(sys.stderr)
        stream.setLevel(level)
        fmt = logging.Formatter("[%(name)s] %(levelname)s: %(message)s")
        stream.setFormatter(fmt)
        logger.addHandler(stream)

        # Also write to a debug file when debugging is enabled so Textual's
        # stdout/stderr capturing doesn't hide messages. File: ~/.tuitter_debug.log
        if os.getenv("TUITTER_DEBUG"):
            try:
                log_file = Path.home() / ".tuitter_debug.log"
                fh = logging.FileHandler(log_file, encoding="utf-8")
                fh.setLevel(level)
                fh.setFormatter(fmt)
                logger.addHandler(fh)
            except Exception:
                pass

    handler_class = _make_handler(auth_event, auth_response)
    try:
        # Allow immediate reuse of the address so restarting the auth flow
        # (sign-out -> sign-in) does not fail due to sockets in TIME_WAIT.
        socketserver.TCPServer.allow_reuse_address = True
        server = http.server.HTTPServer(('localhost', REDIRECT_PORT), handler_class)
        logger.debug(f"HTTP server listening on http://localhost:{REDIRECT_PORT}")
    except OSError as e:
        if e.errno == 98 or e.errno == 10048:  # Port already in use
            raise AuthError("Auth server port already in use. Please try again in a few moments.")
        raise

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    logger.debug("Auth server thread started (daemon)")

    try:
        # Build authorization URL with properly encoded parameters
        auth_params = {
            'client_id': CLIENT_ID,
            'response_type': 'code',
            'scope': ' '.join(SCOPES),
            'redirect_uri': REDIRECT_URI
        }
        auth_url = f"{COGNITO_AUTH_URL}?{urlencode(auth_params)}"

        # Open browser for auth
        logger.debug(f"Opening browser to: {auth_url}")
        try:
            webbrowser.open(auth_url)
        except Exception:
            # If browser.open fails, still proceed and let user open URL manually
            logger.warning("Failed to open browser automatically; please open the URL shown above.")

        # Wait for callback
        if not auth_event.wait(timeout=300):  # 5 minute timeout
            raise AuthError("Authentication timed out")

        if 'error' in auth_response:
            raise AuthError(auth_response['error'])

        if 'code' not in auth_response:
            raise AuthError("No authorization code received")

        # Exchange code for tokens
        logger.debug("Received callback code: %s", auth_response.get('code'))
        try:
            token_response = requests.post(
                COGNITO_TOKEN_URL,
                data={
                    'grant_type': 'authorization_code',
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET,
                    'code': auth_response['code'],
                    'redirect_uri': REDIRECT_URI
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=15,
            )
        except Exception as e:
            logger.exception("Token exchange request failed")
            raise AuthError(f"Token exchange request failed: {e}")

        logger.debug("Token exchange HTTP %s", token_response.status_code)

        if not token_response.ok:
            raise AuthError(f"Token exchange failed: {token_response.text}")

        tokens = token_response.json()

        # Get user info
        try:
            user_response = requests.get(
                COGNITO_USERINFO_URL,
                headers={'Authorization': f"Bearer {tokens['access_token']}"},
                timeout=10,
            )
        except Exception as e:
            logger.exception("User info request failed")
            raise AuthError(f"User info request failed: {e}")

        if not user_response.ok:
            raise AuthError(f"Failed to get user info: {user_response.text}")

        user_info = user_response.json()
        username = user_info.get('username') or user_info.get('sub') or ''
        logger.debug("Retrieved user info: %s", user_info)

        refresh_token = tokens.get('refresh_token')

        # Windows-specific: Always use DPAPI-encrypted file for refresh tokens to avoid keyring size limits
        if platform.system() == "Windows":
            logger.info("Windows detected: storing refresh token in DPAPI-encrypted file")
            try:
                import base64
                import win32crypt

                payload = json.dumps({
                    'refresh_token': refresh_token,
                    'username': username
                }).encode('utf-8')

                protected = win32crypt.CryptProtectData(payload, None, None, None, None, 0)
                b64 = base64.b64encode(protected).decode('ascii')
                FALLBACK_TOKEN_FILE.write_text(
                    json.dumps({'encrypted': True, 'data': b64}),
                    encoding='utf-8'
                )
                logger.info("Refresh token encrypted with DPAPI and stored in: %s", FALLBACK_TOKEN_FILE)

                # Store username in keyring (small data, shouldn't cause issues)
                try:
                    keyring.set_password(SERVICE_NAME, 'username', username)
                    logger.info("Username stored in keyring")
                except Exception as e:
                    logger.warning("Failed to store username in keyring: %s", e)

            except ImportError:
                logger.error("win32crypt not available - falling back to plaintext file")
                FALLBACK_TOKEN_FILE.write_text(
                    json.dumps({'refresh_token': refresh_token, 'username': username}),
                    encoding='utf-8'
                )
            except Exception as e:
                logger.exception("Failed to encrypt tokens with DPAPI, using plaintext: %s", e)
                FALLBACK_TOKEN_FILE.write_text(
                    json.dumps({'refresh_token': refresh_token, 'username': username}),
                    encoding='utf-8'
                )

        # Non-Windows: Use keyring for refresh token
        else:
            if refresh_token:
                try:
                    keyring.set_password(SERVICE_NAME, 'refresh_token', refresh_token)
                    logger.info("Refresh token stored in system keyring")
                except Exception:
                    logger.exception("Failed to write refresh token to keyring; using fallback file %s", FALLBACK_TOKEN_FILE)
                    FALLBACK_TOKEN_FILE.write_text(
                        json.dumps({'refresh_token': refresh_token, 'username': username}),
                        encoding='utf-8'
                    )

            # Store username in keyring
            try:
                keyring.set_password(SERVICE_NAME, 'username', username)
            except Exception:
                logger.warning("Failed to store username in keyring")

        return {'username': username, 'tokens': tokens}

    finally:
        # Don't call server.shutdown() here (it blocks). The server thread is
        # daemon=True and will exit with the process. Close the listening socket
        # to free the port for subsequent sign-ins.
        try:
            if server:
                logger.debug("Closing auth server socket")
                server.server_close()
        except Exception:
            logger.exception("Failed to close auth server socket cleanly")

def get_stored_credentials() -> Optional[Dict[str, str]]:
    """Retrieve stored credentials from system keyring or DPAPI-encrypted file.
    Returns dict with username and tokens if found, None otherwise.
    """
    refresh_token = None
    username = None

    try:
        # Windows: Always read from DPAPI-encrypted file
        if platform.system() == "Windows":
            if FALLBACK_TOKEN_FILE.exists():
                try:
                    raw = FALLBACK_TOKEN_FILE.read_text(encoding='utf-8') or '{}'
                    data = json.loads(raw)

                    # Try to decrypt DPAPI-protected data
                    if isinstance(data, dict) and data.get('encrypted'):
                        try:
                            import base64
                            import win32crypt

                            protected = base64.b64decode(data.get('data'))
                            unprotected, _ = win32crypt.CryptUnprotectData(protected, None, None, None, 0)
                            inner = json.loads(unprotected.decode('utf-8'))
                            refresh_token = inner.get('refresh_token')
                            username = inner.get('username')
                        except Exception:
                            # Decryption failed, try plaintext fallback
                            pass

                    # Fallback to plaintext if not encrypted
                    if not refresh_token and isinstance(data, dict):
                        refresh_token = data.get('refresh_token')
                        username = data.get('username')

                except Exception:
                    pass

            # Try to get username from keyring as backup
            if not username:
                try:
                    username = keyring.get_password(SERVICE_NAME, 'username')
                except Exception:
                    pass

        # Non-Windows: Use keyring
        else:
            try:
                refresh_token = keyring.get_password(SERVICE_NAME, 'refresh_token')
                username = keyring.get_password(SERVICE_NAME, 'username')
            except Exception:
                pass

            # Fallback to file if keyring fails
            if not refresh_token and FALLBACK_TOKEN_FILE.exists():
                try:
                    raw = FALLBACK_TOKEN_FILE.read_text(encoding='utf-8') or '{}'
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        refresh_token = data.get('refresh_token')
                        username = username or data.get('username')
                except Exception:
                    pass

        # If we have a refresh token, use it to get fresh access tokens
        if refresh_token:
            try:
                tokens = refresh_tokens(refresh_token)
                if tokens:
                    return {'username': username or '', 'tokens': tokens}
            except Exception:
                # If refresh failed, credentials are invalid
                pass

    except Exception:
        pass

    return None


def refresh_tokens(refresh_token: str) -> Dict[str, str]:
    """Use the OAuth2 refresh_token grant to obtain new tokens.

    Returns the token dict on success or raises AuthError on failure.
    """
    logger = logging.getLogger("tuitter.auth")
    try:
        resp = requests.post(
            COGNITO_TOKEN_URL,
            data={
                'grant_type': 'refresh_token',
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
                'refresh_token': refresh_token,
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10,
        )
    except Exception as e:
        logger.exception("Refresh token request failed")
        raise AuthError(f"Refresh token request failed: {e}")

    if not resp.ok:
        logger.debug("Refresh token HTTP %s: %s", resp.status_code, resp.text)
        raise AuthError(f"Failed to refresh tokens: {resp.text}")

    return resp.json()

def clear_credentials():
    """Clear stored credentials from system keyring."""
    try:
        # Remove refresh token, username, and any legacy full-token key
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
        # Remove fallback file if present
        try:
            if FALLBACK_TOKEN_FILE.exists():
                FALLBACK_TOKEN_FILE.unlink()
        except Exception:
            pass
    except:
        pass  # Ignore errors deleting from keyring
