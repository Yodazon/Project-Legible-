# app.py

from flask import Flask, request, jsonify
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from dotenv import load_dotenv
import os
import base64

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

def get_email_body(msg):
    """Extract and render email body, including content loaded by JavaScript."""
    for part in msg['payload']['parts']:
        if part['mimeType'] == 'text/html':
            html_content = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            return render_html_with_selenium(html_content)
    return "No HTML content found."

def render_html_with_selenium(html_content):
    """Render HTML content with Selenium to allow JavaScript execution."""
    service = Service(executable_path= os.getenv('CHROMEDRIVER_PATH'))
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    driver = webdriver.Chrome(service=service, options=options)
    
    driver.get("data:text/html;charset=utf-8," + html_content)
    
    driver.implicitly_wait(10)
    
    rendered_html = driver.page_source
    
    driver.quit()
    
    return rendered_html


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
    data = request.get_json()
    sender = data.get('sender')
    
    service = get_gmail_service()
    results = service.users().messages().list(userId="me", q=f"from:{sender}", maxResults=5).execute()
    messages = results.get('messages', [])
    
    emails = []
    for msg in messages:
        msg_detail = service.users().messages().get(userId="me", id=msg['id']).execute()
        subject = next(header['value'] for header in msg_detail['payload']['headers'] if header['name'] == 'Subject')
        body = get_email_body(msg_detail)
        emails.append({'subject': subject, 'body': body})
    
    return jsonify(emails)

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
    else:
        body = message['payload']['body']['data']

        return base64.urlsafe_b64decode(body).decode('utf-8')
        

if __name__ == '__main__':
    app.run(debug=True)
