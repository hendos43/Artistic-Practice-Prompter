import streamlit as st
import os
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from datetime import datetime

# Configuration for OAuth scopes
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Initialize Streamlit app
st.title("Daily Prompt Response")
st.write("Authenticate with Google to respond to today’s prompt and save it to your Google Drive.")

# Step 1: Google OAuth Flow
def initiate_google_auth():
    client_config = {
        "web": {
            "client_id": os.getenv("GCP_CLIENT_ID"),
            "client_secret": os.getenv("GCP_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = "https://artistic-practice-prompter.streamlit.app/"  
    auth_url, _ = flow.authorization_url(prompt='consent')
    return auth_url, flow

# Step 2: Display Google OAuth link
if "credentials" not in st.session_state:
    auth_url, flow = initiate_google_auth()
    st.write(f"[Click here to authenticate with Google]({auth_url})")

    # Retrieve authorization response URL
    authorization_response = st.text_input("Paste the authorization response URL here:")
    if st.button("Submit Authorization URL"):
        try:
            flow.fetch_token(authorization_response=authorization_response)
            st.session_state["credentials"] = flow.credentials.to_json()
            st.success("Successfully authenticated with Google!")
        except Exception as e:
            st.error(f"Authentication failed: {e}")

# Step 3: Display daily prompt and save response if authenticated
if "credentials" in st.session_state:
    st.write("## Today's Prompt")
    prompt = "What would you create if you forgot all your fears?"  # Example prompt
    st.write(prompt)

    response = st.text_area("Your Response")

    # Step 4: Save response to Google Drive
    def save_response_to_drive(prompt_text, response_text):
        creds = flow.credentials.from_authorized_user_info(st.session_state["credentials"])
        drive_service = build("drive", "v3", credentials=creds)

        # Create a file and upload it to Google Drive
        file_metadata = {
            'name': f"{datetime.now().strftime('%Y-%m-%d')}_response.txt",
            'mimeType': 'text/plain'
        }
        with open("response.txt", "w") as file:
            file.write(f"Prompt: {prompt_text}\nResponse: {response_text}")
        media = MediaFileUpload("response.txt", mimetype='text/plain')
        drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        os.remove("response.txt")
        st.success("Response saved to your Google Drive!")

    if st.button("Save Response to Google Drive"):
        save_response_to_drive(prompt, response)
