import streamlit as st
import json
from datetime import datetime
import os
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import tempfile
import secrets

# Configuration for OAuth scopes
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Load the prompts from JSON file
with open('prompts.json', 'r') as file:
    data = json.load(file)
    questions = data["questions"]

# Function to get the daily prompt based on the day of the year
def get_daily_prompt():
    day_of_year = datetime.now().timetuple().tm_yday
    prompt_index = (day_of_year - 1) % len(questions)  # -1 to make it 0-indexed
    return questions[prompt_index]["question"]

# Initialize Streamlit app
st.title("Daily Prompt Response")
st.write("Authenticate with Google to respond to today’s prompt and save it to your Google Drive.")

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
    flow.redirect_uri = "https://auth-handler-xfgq.onrender.com/google-callback"
    
    # Only generate new state if it doesn't exist
    if "oauth_state" not in st.session_state:
        state = secrets.token_urlsafe(16)
        st.session_state["oauth_state"] = state
    else:
        state = st.session_state["oauth_state"]
    
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent',
        state=state
    )
    st.session_state["flow"] = flow
    return auth_url

if "credentials" not in st.session_state:
    auth_url = initiate_google_auth()
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.link_button(
            "Login with Google",
            auth_url,
            type="primary",
            use_container_width=True
        )

    st.info("After clicking the button above and logging in, you'll be redirected to a page with a URL. Copy that URL and paste it below.")
    
    authorization_response = st.text_input(
        "Paste the authorization URL here:",
        placeholder="https://auth-handler-xfgq.onrender.com/google-callback?code=...&state=...",
        label_visibility="visible"
    )

    if authorization_response:
        try:
            flow = st.session_state["flow"]
            
            # Extract state from response URL
            from urllib.parse import urlparse, parse_qs
            parsed_url = urlparse(authorization_response)
            response_state = parse_qs(parsed_url.query).get('state', [None])[0]
            
            # Debug output
            st.write("Debug info:")
            st.write(f"Expected state: {st.session_state.get('oauth_state')}")
            st.write(f"Received state: {response_state}")
            
            # Verify state matches
            if not response_state or response_state != st.session_state.get("oauth_state"):
                raise ValueError("State parameter doesn't match")
                
            flow.fetch_token(authorization_response=authorization_response)
            st.session_state["credentials"] = flow.credentials.to_json()
            st.success("Successfully authenticated with Google!")
            st.rerun()
        except Exception as e:
            st.error(f"Authentication failed: {str(e)}")

# Step 3: Display daily prompt and save response if authenticated
if "credentials" in st.session_state:
    # Display the daily prompt
    prompt = get_daily_prompt()
    st.write("## Today's Prompt")
    st.write(prompt)

    # User response area and file uploader
    response = st.text_area("Your Response")
    uploaded_files = st.file_uploader("Upload additional files (images, videos, etc.)", accept_multiple_files=True)

    # Function to create folders if they don’t exist
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

    # Save response to Google Drive with folder structure
    def save_response_to_drive(prompt_text, response_text, uploaded_files):
        # Parse credentials from JSON string stored in session state
        creds_info = json.loads(st.session_state["credentials"])
        creds = Credentials.from_authorized_user_info(creds_info)
        drive_service = build("drive", "v3", credentials=creds)

        # Folder names
        main_folder = "Artistic Practice Prompter"
        date_folder = datetime.now().strftime("%Y-%m-%d")

        # Create folder structure
        main_folder_id = create_folder_if_not_exists(drive_service, main_folder)
        date_folder_id = create_folder_if_not_exists(drive_service, date_folder, main_folder_id)

        # Save response text as a file
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
