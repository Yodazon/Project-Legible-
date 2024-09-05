import os.path
import base64
from dotenv import load_dotenv
load_dotenv()

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main():
  """Shows basic usage of the Gmail API.
  Lists the user's Gmail labels.
  """
  creds = None
  # The file token.json stores the user's access and refresh tokens, and is
  # created automatically when the authorization flow completes for the first
  # time.
  if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
  # If there are no (valid) credentials available, let the user log in.
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(
          "credentials.json", SCOPES
      )
      creds = flow.run_local_server(port=0)
    # Save the credentials for the next run
    with open("token.json", "w") as token:
      token.write(creds.to_json())

  try:
    # Call the Gmail API
    service = build("gmail", "v1", credentials=creds)
    #Get list of messages
    results = service.users().messages().list(userId="me", maxResults=10).execute()
    messages = results.get("messages",[])

    if not messages:
      print("No messages found.")
      return
    

    sender_dict = {}
    for msg in messages:
      msg_detail = service.users().messages().get(userId = "me", id=msg["id"]).execute()
      headers = msg_detail["payload"]["headers"]
      sender = next((header['value'] for header in headers if header['name'] == 'From'), 'Unknown Sender')
      sender_email = sender.split()[-1].strip('<>')

      if sender_email not in sender_dict:
        sender_dict[sender_email] = []
      sender_dict[sender_email].append(msg_detail)

    print("Senders")
    for sender_email in sender_dict:
      print(sender_email)


    while True:
      selected_sender = input("Which sender's email would you like to read?: ").strip()
      if selected_sender in sender_dict:
        break
      else:
        print("Sender not found")
    
    selected_emails = sender_dict[selected_sender][:5]
    for idx, email in enumerate(selected_emails):
      subject = next((header['value'] for header in email['payload']['headers'] if header['name'] == 'Subject'), 'No Subject')
      print(f"\nEmail {idx + 1} Subject: {subject}")
      msg_body = get_msg_body(email)
      print(f"Email {idx + 1} Body:\n{msg_body}")

  
   

  except HttpError as error:
    # TODO(developer) - Handle errors from gmail API.
    print(f"An error occurred: {error}")

def get_msg_body(message):
  "Extracts the body from the Gmail message."
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




if __name__ == "__main__":
  main()