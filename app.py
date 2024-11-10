import streamlit as st
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import tempfile
from streamlit_oauth import OAuth

# OAuth setup
client_id = st.secrets["GCP_CLIENT_ID"]
client_secret = st.secrets["GCP_CLIENT_SECRET"]
redirect_uri = "https://artistic-practice-prompter.streamlit.app/"

# Initialize OAuth for Google
oauth = OAuth(client_id, client_secret, redirect_uri)
oauth.authorize("https://www.googleapis.com/auth/drive.file")  # Request Google Drive permissions

# Function to load prompts from JSON file
def load_prompts():
    with open('prompts.json', 'r') as file:
        data = json.load(file)
    return data["questions"]

# Function to get daily prompt based on the day of the year
def get_daily_prompt(questions):
    day_of_year = datetime.now().timetuple().tm_yday
    prompt_index = (day_of_year - 1) % len(questions)
    return questions[prompt_index]["question"]

# Initialize Streamlit app
st.title("Daily Prompt Response")
st.write("Authenticate with Google to respond to today’s prompt and save it to your Google Drive.")

# Step 1: Authenticate and obtain Google credentials
credentials = oauth.get_credentials()

if credentials:
    # Store credentials in session for reuse
    st.session_state["credentials"] = credentials.to_json()

    # Load prompts and display daily prompt
    questions = load_prompts()
    prompt = get_daily_prompt(questions)
    st.write("## Today's Prompt")
    st.write(prompt)

    # Text area for user response and file uploader
    response = st.text_area("Your Response")
    uploaded_files = st.file_uploader("Upload additional files (images, videos, etc.)", accept_multiple_files=True)

    # Function to create folders if they don’t exist in Google Drive
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

    # Save response and files to Google Drive
    def save_response_to_drive(prompt_text, response_text, uploaded_files):
        creds = Credentials.from_authorized_user_info(json.loads(st.session_state["credentials"]))
        drive_service = build("drive", "v3", credentials=creds)
        main_folder = "Artistic Practice Prompter"
        date_folder = datetime.now().strftime("%Y-%m-%d")

        # Create folder structure
        main_folder_id = create_folder_if_not_exists(drive_service, main_folder)
        date_folder_id = create_folder_if_not_exists(drive_service, date_folder, main_folder_id)

        # Save response text as a file in Drive
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
else:
    # Display login button if not authenticated
    st.write("Click below to log in with Google:")
    if st.button("Login with Google"):
        oauth.redirect_authorize()
