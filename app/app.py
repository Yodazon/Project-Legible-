# app.py

import os.path
import base64
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def get_gmail_service():
    """Authenticate and return a Gmail API service instance."""
    creds = None
    credentials_path = os.path.join(os.path.dirname(__file__), "credentials.json")

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

@app.route('/senders', methods=['GET'])
def get_senders():
    """Returns a list of senders based on the recent emails."""
    service = get_gmail_service()
    results = service.users().messages().list(userId="me", maxResults=50).execute()
    messages = results.get("messages", [])
    sender_dict = {}
    for msg in messages:
        msg_detail = service.users().messages().get(userId="me", id=msg["id"]).execute()
        headers = msg_detail["payload"]["headers"]
        sender = next((header['value'] for header in headers if header['name'] == 'From'), 'Unknown Sender')
        sender_email = sender.split()[-1].strip('<>')
        if sender_email not in sender_dict:
            sender_dict[sender_email] = []
        sender_dict[sender_email].append(msg_detail)
    return jsonify(list(sender_dict.keys()))

@app.route('/emails', methods=['POST'])
def get_emails():
    """Returns the 5 most recent emails from a selected sender."""
    service = get_gmail_service()
    sender = request.json.get('sender')
    results = service.users().messages().list(userId="me", maxResults=50).execute()
    messages = results.get("messages", [])
    sender_dict = {}
    for msg in messages:
        msg_detail = service.users().messages().get(userId="me", id=msg["id"]).execute()
        headers = msg_detail["payload"]["headers"]
        email_sender = next((header['value'] for header in headers if header['name'] == 'From'), 'Unknown Sender')
        sender_email = email_sender.split()[-1].strip('<>')
        if sender_email not in sender_dict:
            sender_dict[sender_email] = []
        sender_dict[sender_email].append(msg_detail)
    if sender in sender_dict:
        emails = sender_dict[sender][:5]
        email_data = [{"subject": next((header['value'] for header in email['payload']['headers'] if header['name'] == 'Subject'), 'No Subject'),
                       "body": get_message_body(email)} for email in emails]
        return jsonify(email_data)
    else:
        return jsonify([])

def get_message_body(message):
    """Extracts the body from the Gmail message."""
    parts = message['payload'].get('parts')
    if parts:
        for part in parts:
            if part['mimeType'] == 'text/plain':  # For plain text emails
                body = part['body']['data']
                return base64.urlsafe_b64decode(body).decode('utf-8')
            elif part['mimeType'] == 'text/html':  # For HTML emails
                body = part['body']['data']
                return base64.urlsafe_b64decode(body).decode('utf-8')
        print(parts['mimeType'])
    else:
        body = message['payload']['body']['data']
        print("There are no parts")
        return base64.urlsafe_b64decode(body).decode('utf-8')
        

if __name__ == '__main__':
    app.run(debug=True)
