# calendar_service.py
import os
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def get_calendar_service():
    """ Authenticates the workspace and builds the Google Calendar API service instance """
    creds = None
    # token.json stores your active user login tokens automatically after the first authorization pass
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

def generate_google_meet_link(date_str, time_str, summary, description, client_email, duration_minutes=90):
    """
    Creates a formal Google Calendar Event and auto-injects a native Google Meet space.
    Expects date_str format: "DD/MM/YYYY" and time_str format: "10:00 AM"
    Accepts dynamic session duration in minutes (defaults to 90 if not provided).
    """
    try:
        service = get_calendar_service()
        
        # 1. Parse your front-end date/time values into an ISO timestamp
        time_clean = time_str.strip()
        parsed_time = datetime.datetime.strptime(f"{date_str} {time_clean}", "%d/%m/%Y %I:%M %p")
        
        start_time = parsed_time.isoformat()
        
        # FIX: Replaced the hardcoded 90 minutes with the dynamic parameter
        end_time = (parsed_time + datetime.timedelta(minutes=duration_minutes)).isoformat() 
        
        # 2. Build the event payload architecture demanding a Google Meet asset
        event_body = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time, 'timeZone': 'Africa/Lagos'}, # Change to your preferred zone
            'end': {'dateTime': end_time, 'timeZone': 'Africa/Lagos'},
            'attendees': [{'email': client_email}],
            'conferenceData': {
                'createRequest': {
                    'requestId': f"req-{int(parsed_time.timestamp())}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                }
            }
        }
        
        # 3. Dispatch creation request directly to Google servers
        event = service.events().insert(
            calendarId='primary',
            body=event_body,
            conferenceDataVersion=1,
            sendUpdates='all' # Automatically emails a native calendar invitation card
        ).execute()
        
        # 4. Extract the cleanly generated dynamic Google Meet link string
        meet_link = event.get('conferenceData', {}).get('entryPoints', [{}])[0].get('uri')
        return meet_link if meet_link else "https://meet.google.com"
        
    except Exception as e:
        print(f"Google Calendar Error: {str(e)}")
        return "https://meet.google.com" # Fallback link if API fails