#!/usr/bin/env python3
"""
Standalone OAuth callback server
Auto-started by main app or run manually:
    python3 oauth_server.py
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import requests
from pathlib import Path
import sys
import signal
import subprocess
import os
import keyring

serviceKeyring = "tuiitter"

def get_token(username: str) -> str:
    return keyring.get_password(serviceKeyring, username)

def set_token(username: str, token: str) -> None:
    return keyring.set_password(serviceKeyring, username, token)

def delete_token(username: str) -> None:
    return keyring.delete_password(serviceKeyring, username)

def get_user_name(username: str) -> str:
    return keyring.get_password(serviceKeyring, username)

def set_user_name(username: str, user_name: str) -> None:
    return keyring.set_password(serviceKeyring, username, user_name)

def delete_user_name(username: str) -> None:
    return keyring.delete_password(serviceKeyring, username)

COGNITO_TOKEN_URL = "https://us-east-2xzzmuowl9.auth.us-east-2.amazoncognito.com/oauth2/token"
COGNITO_USERNAME_URL = "https://us-east-2xzzmuowl9.auth.us-east-2.amazoncognito.com/oauth2/userInfo"
COGNITO_CLIENT_SECRET = "1t46ik23730a5fbboiimdbh8ffkicnm69c40ifbg9jou401pft02"
COGNITO_CLIENT_ID = "7109b3p9beveapsmr806freqnn"
REDIRECT_URI = "http://localhost:5173/callback"

# Store main app PID to restart it
MAIN_APP_PID_FILE = ".main_app_pid"


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet mode - only print important messages
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/callback":
            qs = parse_qs(parsed.query)
            code = qs.get("code", [None])[0]
            
            if code:
                print(f"✅ Code received", file=sys.stderr, flush=True)
                
                # Exchange code for tokens
                try:
                    data = {
                        "grant_type": "authorization_code",
                        "client_id": COGNITO_CLIENT_ID,
                        "client_secret": COGNITO_CLIENT_SECRET,
                        "code": code,
                        "redirect_uri": REDIRECT_URI,
                    }
                    headers = {"Content-Type": "application/x-www-form-urlencoded"}
                    resp = requests.post(COGNITO_TOKEN_URL, data=data, headers=headers)
                    
                    if resp.ok:
                        tokens = resp.json()
                        # Path("oauth_tokens.json").write_text(json.dumps(tokens, indent=2) + "\n")

                        set_token("oauth_tokens.json", json.dumps(tokens, indent=2) + "\n")
                        print("✅ Tokens saved", file=sys.stderr, flush=True)
                        
                        # Signal wrapper script to restart main.py
                        try:
                            pid_file = Path(MAIN_APP_PID_FILE)
                            if pid_file.exists():
                                pid = int(pid_file.read_text().strip())
                                print(f"🔄 Sending restart signal to main app (PID: {pid})...", file=sys.stderr, flush=True)
                                
                                # Create restart signal
                                Path(".restart_signal").touch()
                                
                                # Kill main app - wrapper script will restart it
                                os.kill(pid, signal.SIGTERM)
                        except Exception as e:
                            print(f"⚠️  Couldn't signal restart: {e}", file=sys.stderr, flush=True)
                        
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html")
                        self.end_headers()
                        self.wfile.write(b"""
                        <html><body style='font-family:monospace;padding:40px;text-align:center;'>
                        <h1 style='color:green;'>Success!</h1>
                        <p>You can close this window and return to the app.</p>
                        </body></html>
                        """)
                    else:
                        print(f"❌ Token exchange failed: {resp.status_code}", file=sys.stderr, flush=True)
                        print(f"{resp.json()}", file=sys.stderr, flush=True)
                        self.send_response(500)
                        self.send_header("Content-Type", "text/plain")
                        self.end_headers()
                        self.wfile.write(f"Token exchange failed: {resp.status_code}".encode())

                    try:
                        resp = requests.get(COGNITO_USERNAME_URL, headers={"Authorization": f"Bearer {tokens['access_token']}"})
                        print(f"{resp.json()}", file=sys.stderr, flush=True)
                        user_name = resp.json()["username"]
                        # Path("oauth_tokens.json").open("a").write(json.dumps({"user_name": user_name}, indent=2) + "\n")
                        print(f"✅ User name: {user_name}", file=sys.stderr, flush=True)
                        print(f"{json.dumps(resp.json(), indent=2)}", file=sys.stderr, flush=True)
                        set_user_name("username", user_name)
                        print(f"✅ Tokens verified: {resp}", file=sys.stderr, flush=True)
                    except Exception as e:
                        print(f"❌ Tokens verification failed: {e}", file=sys.stderr, flush=True)
                        self.send_response(500)
                        self.send_header("Content-Type", "text/plain")
                        self.end_headers()
                except Exception as e:
                    print(f"❌ Error: {e}", file=sys.stderr, flush=True)
                    self.send_response(500)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write(f"Error: {e}".encode())
            else:
                self.send_response(400)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(b"No code parameter")
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    try:
        server = HTTPServer(("", 5173), OAuthCallbackHandler)
        print("🚀 OAuth server ready on http://localhost:5173", file=sys.stderr, flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped", file=sys.stderr, flush=True)
        server.server_close()
    except Exception as e:
        print(f"❌ Server error: {e}", file=sys.stderr, flush=True)
        sys.exit(1)

