import streamlit as st
import json
from datetime import datetime
import os
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import tempfile

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
    # Use the google-callback endpoint instead
    flow.redirect_uri = "https://auth-handler-xfgq.onrender.com/google-callback"
    auth_url, _ = flow.authorization_url(prompt='consent')
    st.session_state["flow"] = flow
    return auth_url

# Step 2: Display Google OAuth link and handle copy-paste of authorization response
if "credentials" not in st.session_state:
    st.html(
        f"""
        <div style="text-align: center; padding: 20px; min-height: 100px;">
            <script>
                // Define handler before adding listener
                function handleGoogleAuth(event) {{
                    console.log('Received message:', event.data);
                    if (event.data.type === 'GOOGLE_AUTH' && event.data.code) {{
                        const callbackUrl = 'https://auth-handler-xfgq.onrender.com/google-callback?code=' + event.data.code;
                        console.log('Setting URL:', callbackUrl);
                        
                        // Try multiple ways to find the input
                        const authInputs = document.querySelectorAll('input');
                        for (const input of authInputs) {{
                            if (input.placeholder && input.placeholder.includes('authorization')) {{
                                input.value = callbackUrl;
                                const form = input.closest('form');
                                if (form) form.submit();
                                break;
                            }}
                        }}
                    }}
                }}

                // Remove any existing listeners
                window.removeEventListener('message', handleGoogleAuth);
                // Add the listener
                window.addEventListener('message', handleGoogleAuth);

                function openGoogleAuth() {{
                    console.log('Opening Google Auth...');
                    const authUrl = '{initiate_google_auth()}';
                    console.log('Auth URL:', authUrl);
                    const popup = window.open(authUrl, 'Google Login', 'width=600,height=600');
                    if (!popup) {{
                        alert('Popup was blocked! Please allow popups for this site.');
                    }}
                }}

                // Make sure the function is available globally
                window.openGoogleAuth = openGoogleAuth;
            </script>
            <a href="#" 
               onclick="window.openGoogleAuth(); return false;"
               style="
                display: inline-block;
                background-color: #4285f4;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 24px;
                font-weight: bold;
                font-size: 16px;
                margin: 10px 0;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
                Login with Google
            </a>
        </div>
        """
    )

    authorization_response = st.text_input(
        "Authorization Response:", 
        placeholder="The authorization response will be filled automatically...",
        label_visibility="collapsed"
    )

    if authorization_response:
        try:
            flow = st.session_state["flow"]
            flow.fetch_token(authorization_response=authorization_response)
            st.session_state["credentials"] = flow.credentials.to_json()
            st.success("Successfully authenticated with Google!")
            st.rerun()
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
