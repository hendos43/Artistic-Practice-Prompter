import os
import streamlit as st
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

st.title("Google Drive Uploader")
st.write("This app allows you to upload files to Google Drive.")
st.write("Please authenticate with Google Drive to continue.")
st.write("Click the link below to authenticate with Google Drive.")
auth_url, _ = flow.authorization_url()
st.write(f"[Click here to authenticate]({auth_url})")
