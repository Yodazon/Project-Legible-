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
    

    print("Emails:")
    email_dict = {}

    for idx,msg in enumerate(messages):
      #Get messgae details
      msg_detail = service.users().messages().get(userId = "me", id=msg["id"]).execute()
      email_dict[idx] = msg_detail['id']

      #Display subject/snippet to user
      headers = msg_detail["payload"]["headers"]
      subject = next(header['value'] for header in headers if header['name'] == 'Subject')
      print(f"{idx}: {subject}")

    #Ask users to pick emails by index
    selected_indices = input("Enter the email indices (comma-separated) you want to read: ").split(',')
    selected_indices = [int(index.strip()) for index in selected_indices]
    
    for index in selected_indices:
      msg_id = email_dict[index]
      msg_detail = service.users().messages().get(userId="me", id=msg_id).execute()
      msg_body = get_msg_body(msg_detail)
      print(f"\nEmail {index} Body:\n{msg_body}")

  except HttpError as error:
    # TODO(developer) - Handle errors from gmail API.
    print(f"An error occurred: {error}")

def get_msg_body(message):
  "Extract Body from Email"
  parts = message['payload'].get('parts')
  if parts:
    body = parts[0]['body']['data']
    return base64.urlsafe_b64decode(body).decode('utf-8')




if __name__ == "__main__":
  main()