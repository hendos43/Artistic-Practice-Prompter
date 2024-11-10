import os
from google_auth_oauthlib.flow import Flow

# Initialize OAuth flow using environment variables
client_config = {
    "web": {
        "client_id": os.getenv("GCP_CLIENT_ID"),
        "client_secret": os.getenv("GCP_CLIENT_SECRET"),
        "auth_uri": os.getenv("GCP_AUTH_URI"),
        "token_uri": os.getenv("GCP_TOKEN_URI")
    }
}

flow = Flow.from_client_config(client_config, scopes=['https://www.googleapis.com/auth/drive.file'])
