import streamlit as st
import json
from datetime import datetime
import os
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

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
    flow.redirect_uri = "https://artistic-practice-prompter.streamlit.app/"  # Replace with your actual Streamlit app URL
    auth_url, _ = flow.authorization_url(prompt='consent')
    st.session_state["flow"] = flow  # Store Flow object in session
    return auth_url

# Step 2: Display Google OAuth link and handle copy-paste of authorization response
if "credentials" not in st.session_state:
    if "auth_url" not in st.session_state:
        st.session_state["auth_url"] = initiate_google_auth()

    # Display the OAuth URL and prompt the user to copy the URL after authenticating
    st.write("Click the link below to authenticate with Google:")
    st.write(f"[Authenticate with Google]({st.session_state['auth_url']})")
    st.write("After authenticating, copy the URL from the address bar of the new tab and paste it below.")

    # Input for the user to paste the redirected URL
    authorization_response = st.text_input("Paste the full authorization response URL here:")

    if st.button("Submit Authorization URL"):
        try:
            # Fetch the Flow object from session state and complete the token exchange
            flow = st.session_state["flow"]
            flow.fetch_token(authorization_response=authorization_response)
            st.session_state["credentials"] = flow.credentials.to_json()
            st.success("Successfully authenticated with Google!")
        except Exception as e:
            st.error(f"Authentication failed: {e}")

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
        file_metadata = {
            'name': 'response.txt',
            'parents': [date_folder_id],
            'mimeType': 'text/plain'
        }
        with open("response.txt", "w") as file:
            file.write(f"Prompt: {prompt_text}\nResponse: {response_text}")
        media = MediaFileUpload("response.txt", mimetype='text/plain')
        drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        os.remove("response.txt")

        # Save each uploaded file to the date folder
        for uploaded_file in uploaded_files:
            file_metadata = {
                'name': uploaded_file.name,
                'parents': [date_folder_id]
            }
            media = MediaFileUpload(uploaded_file.name, mimetype=uploaded_file.type)
            drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        
        st.success("Response and files saved to your Google Drive!")

    # Button to save the response and uploaded files to Google Drive
    if st.button("Save Response and Files to Google Drive"):
        save_response_to_drive(prompt, response, uploaded_files)
