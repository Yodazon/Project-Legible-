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
import datetime

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

import re
import base64

def get_email_body(msg):
    """Extract and render email body, including content loaded by JavaScript."""
    if 'parts' in msg['payload']:
        for part in msg['payload']['parts']:
            if part['mimeType'] == 'text/html':
                if 'data' in part['body']:
                    html_content = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    rendered_content = render_html_with_selenium(html_content)
                    return process_links(rendered_content)
                elif 'parts' in part:  # Nested parts
                    return get_email_body({'payload': part})
            elif part['mimeType'] == 'text/plain':
                if 'data' in part['body']:
                    return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
    else:
        if msg['payload']['mimeType'] == 'text/html':
            if 'data' in msg['payload']['body']:
                html_content = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode('utf-8')
                rendered_content = render_html_with_selenium(html_content)
                return process_links(rendered_content)
        elif msg['payload']['mimeType'] == 'text/plain':
            if 'data' in msg['payload']['body']:
                return base64.urlsafe_b64decode(msg['payload']['body']['data']).decode('utf-8')
    
    return "No content found."


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


def process_links(html_content):
    """Replace hyperlinks with 'click here' text."""
    return re.sub(r'<a[^>]+href="([^"]+)"[^>]*>.*?</a>', r'<a href="\1">click here</a>', html_content)


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
    senders = data.get('senders', [])
    
    service = get_gmail_service()
    all_emails = []

    for sender in senders:
        results = service.users().messages().list(userId="me", q=f"from:{sender}", maxResults=5).execute()
        messages = results.get('messages', [])
        
        for msg in messages:
            msg_detail = service.users().messages().get(userId="me", id=msg['id']).execute()
            subject = next(header['value'] for header in msg_detail['payload']['headers'] if header['name'] == 'Subject')


            # Retrieve the date from the correct header
            date_str = next(header['value'] for header in msg_detail['payload']['headers'] if header['name'] == 'Date')

            # Clean up the date string by removing '(UTC)' if it exists
            date_str = date_str.replace(' (UTC)', '')

            body = get_email_body(msg_detail)
            date = datetime.datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z')
            all_emails.append({'subject': subject, 'body': body, 'date': date})
    
    # Sort emails by date
    sorted_emails = sorted(all_emails, key=lambda x: x['date'], reverse=True)
    
    # Remove date before returning
    for email in sorted_emails:
        email.pop('date')

    return jsonify(sorted_emails)


if __name__ == '__main__':
    app.run(debug=True)