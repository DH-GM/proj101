"""Authentication configuration and constants"""

# OAuth endpoints
COGNITO_AUTH_URL = "https://us-east-2xzzmuowl9.auth.us-east-2.amazoncognito.com/login/continue"
COGNITO_TOKEN_URL = "https://us-east-2xzzmuowl9.auth.us-east-2.amazoncognito.com/oauth2/token"
COGNITO_USERINFO_URL = "https://us-east-2xzzmuowl9.auth.us-east-2.amazoncognito.com/oauth2/userInfo"

# App credentials
COGNITO_CLIENT_ID = "7109b3p9beveapsmr806freqnn"
COGNITO_CLIENT_SECRET = "1t46ik23730a5fbboiimdbh8ffkicnm69c40ifbg9jou401pft02"

# OAuth settings
REDIRECT_URI = "http://localhost:5173/callback"
OAUTH_SCOPES = ["email", "openid", "phone"]

# Local settings
AUTH_SERVER_HOST = "localhost"
AUTH_SERVER_PORT = 5173
AUTH_SERVER_URL = f"http://{AUTH_SERVER_HOST}:{AUTH_SERVER_PORT}"

# Storage settings
KEYRING_SERVICE = "tuitter"
TOKEN_KEY = "oauth_tokens"
USERNAME_KEY = "username"
