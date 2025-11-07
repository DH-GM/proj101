"""
Simple OAuth callback server that handles the authentication flow
and stores tokens securely using the system keyring.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser
import requests
import keyring
import json
import sys
from urllib.parse import urlencode, urlparse, parse_qs
from typing import Optional, Dict, Any
import signal
import threading
from .auth_config import *

class AuthServer:
    def __init__(self):
        self.server: Optional[HTTPServer] = None
        self.auth_complete = threading.Event()
        self.auth_result: Dict[str, Any] = {}

    def start(self) -> None:
        """Start the auth server and open the browser for login"""
        # Setup server
        self.server = HTTPServer((AUTH_SERVER_HOST, AUTH_SERVER_PORT), self._make_handler())
        server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        server_thread.start()

        # Build auth URL
        params = {
            "client_id": COGNITO_CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(OAUTH_SCOPES)
        }
        auth_url = f"{COGNITO_AUTH_URL}?{urlencode(params)}"

        # Open browser
        webbrowser.open(auth_url)

        # Wait for auth to complete or timeout
        self.auth_complete.wait(timeout=300)  # 5 minute timeout
        self.stop()

        if not self.auth_result.get("success"):
            raise RuntimeError(self.auth_result.get("error", "Authentication failed"))

    def stop(self) -> None:
        """Stop the auth server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def _make_handler(self):
        """Create a request handler class with access to auth server state"""
        outer = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                """Suppress default logging"""
                pass

            def do_GET(self):
                """Handle OAuth callback"""
                try:
                    # Parse the callback URL
                    parsed = urlparse(self.path)
                    if parsed.path != "/callback":
                        self._error_response("Invalid callback path")
                        return

                    params = parse_qs(parsed.query)
                    code = params.get("code", [None])[0]
                    if not code:
                        self._error_response("No authorization code received")
                        return

                    # Exchange code for tokens
                    token_response = requests.post(
                        COGNITO_TOKEN_URL,
                        data={
                            "grant_type": "authorization_code",
                            "client_id": COGNITO_CLIENT_ID,
                            "client_secret": COGNITO_CLIENT_SECRET,
                            "code": code,
                            "redirect_uri": REDIRECT_URI
                        },
                        headers={"Content-Type": "application/x-www-form-urlencoded"}
                    )

                    if not token_response.ok:
                        self._error_response(f"Token exchange failed: {token_response.text}")
                        return

                    tokens = token_response.json()

                    # Get user info
                    user_response = requests.get(
                        COGNITO_USERINFO_URL,
                        headers={"Authorization": f"Bearer {tokens['access_token']}"}
                    )

                    if not user_response.ok:
                        self._error_response(f"Failed to get user info: {user_response.text}")
                        return

                    user_info = user_response.json()

                    # Store tokens and username
                    keyring.set_password(KEYRING_SERVICE, TOKEN_KEY, json.dumps(tokens))
                    keyring.set_password(KEYRING_SERVICE, USERNAME_KEY, user_info["username"])

                    # Signal success
                    outer.auth_result = {
                        "success": True,
                        "username": user_info["username"]
                    }

                    # Send success response
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(b"""
                        <html><body style='font-family: system-ui; padding: 40px; text-align: center;'>
                            <h1 style='color: #4CAF50;'>✅ Login Successful!</h1>
                            <p>You can close this window and return to the application.</p>
                        </body></html>
                    """)

                except Exception as e:
                    self._error_response(f"Authentication error: {str(e)}")
                finally:
                    outer.auth_complete.set()

            def _error_response(self, message: str):
                """Send an error response and store the error"""
                outer.auth_result = {
                    "success": False,
                    "error": message
                }
                self.send_response(400)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(f"""
                    <html><body style='font-family: system-ui; padding: 40px; text-align: center;'>
                        <h1 style='color: #F44336;'>❌ Authentication Failed</h1>
                        <p>{message}</p>
                        <p>You can close this window and try again.</p>
                    </body></html>
                """.encode())

        return CallbackHandler

def start_auth() -> Dict[str, Any]:
    """Start the authentication flow and return the result"""
    server = AuthServer()
    try:
        server.start()
        return server.auth_result
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        server.stop()

if __name__ == "__main__":
    # Can be run standalone for testing
    try:
        result = start_auth()
        print(json.dumps(result, indent=2))
    except KeyboardInterrupt:
        print("\nAuth server stopped")
