import streamlit as st
from streamlit_oauth import OAuth2Component
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from datetime import datetime
import tempfile
import json

# Set up OAuth2Component using Streamlit Secrets Manager
AUTHORIZE_URL = st.secrets["AUTHORIZE_URL"]
TOKEN_URL = st.secrets["TOKEN_URL"]
REFRESH_TOKEN_URL = st.secrets["REFRESH_TOKEN_URL"]
REVOKE_TOKEN_URL = st.secrets["REVOKE_TOKEN_URL"]
CLIENT_ID = st.secrets["CLIENT_ID"]
CLIENT_SECRET = st.secrets["CLIENT_SECRET"]
REDIRECT_URI = st.secrets["REDIRECT_URI"]
SCOPE = st.secrets["SCOPE"]

# Initialize OAuth2 component
oauth2 = OAuth2Component(CLIENT_ID, CLIENT_SECRET, AUTHORIZE_URL, TOKEN_URL, REFRESH_TOKEN_URL, REVOKE_TOKEN_URL)

# Function to get daily prompt (example data for demonstration)
def get_daily_prompt():
    return "What inspired you today?"

# Initialize Streamlit app
st.title("Daily Prompt Response")
st.write("Authenticate with Google to respond to today’s prompt and save it to your Google Drive.")

# Check if token exists in session state
if 'token' not in st.session_state:
    # Show authorize button and check for result without rerun
    result = oauth2.authorize_button("Authorize with Google", REDIRECT_URI, SCOPE)
    if result and 'token' in result:
        # Save the token in session state if authorization is successful
        st.session_state['token'] = result['token']
        st.info("Authorization successful. Please reload the page if needed to proceed.")
else:
    # Retrieve the token from session state
    token = st.session_state['token']
    prompt = get_daily_prompt()
    st.write("## Today's Prompt")
    st.write(prompt)

    response = st.text_area("Your Response")
    uploaded_files = st.file_uploader("Upload additional files (images, videos, etc.)", accept_multiple_files=True)

    # Function to create folders in Google Drive if they don’t exist
    def create_folder_if_not_exists(drive_service, folder_name, parent_id=None):
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'"
        if parent_id:
            query += f" and '{parent_id}' in parents"
        results = drive_service.files().list(q=query, spaces='drive', fields="files(id, name)").execute()
        files = results.get('files', [])
        if files:
            return files[0]['id']
        else:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id] if parent_id else []
            }
            folder = drive_service.files().create(body=file_metadata, fields='id').execute()
            return folder['id']

    # Function to save response and uploaded files to Google Drive
    def save_response_to_drive(prompt_text, response_text, uploaded_files):
        creds = Credentials(token=token['access_token'])
        drive_service = build("drive", "v3", credentials=creds)
        main_folder = "Artistic Practice Prompter"
        date_folder = datetime.now().strftime("%Y-%m-%d")

        main_folder_id = create_folder_if_not_exists(drive_service, main_folder)
        date_folder_id = create_folder_if_not_exists(drive_service, date_folder, main_folder_id)

        # Save the response text as a file in Google Drive
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
            temp_file.write(f"Prompt: {prompt_text}\nResponse: {response_text}".encode())
            temp_file.flush()
            file_metadata = {
                'name': 'response.txt',
                'parents': [date_folder_id],
                'mimeType': 'text/plain'
            }
            media = MediaFileUpload(temp_file.name, mimetype='text/plain')
            drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()

        # Save each uploaded file to the date folder
        for uploaded_file in uploaded_files:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded_file.name}") as temp_file:
                temp_file.write(uploaded_file.read())
                temp_file.flush()
                file_metadata = {
                    'name': uploaded_file.name,
                    'parents': [date_folder_id]
                }
                media = MediaFileUpload(temp_file.name, mimetype=uploaded_file.type)
                drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            
        st.success("Response and files saved to your Google Drive!")

    # Button to save the response and uploaded files to Google Drive
    if st.button("Save Response and Files to Google Drive"):
        save_response_to_drive(prompt, response, uploaded_files)

    # Optionally, allow users to refresh the token
    if st.button("Refresh Token"):
        refreshed_token = oauth2.refresh_token(token)
        st.session_state['token'] = refreshed_token
