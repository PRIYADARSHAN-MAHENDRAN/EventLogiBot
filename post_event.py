import os
import gspread
import requests
import json

from datetime import datetime
from google.oauth2.service_account import Credentials
from pytz import timezone

# Load credentials and config
credentials = ServiceAccountCredentials.from_json_keyfile_name('truckersmp-events-ef7e395df282.json', scope)

SHEET_ID = os.environ['SHEET_ID']
DISCORD_WEBHOOK = os.environ['DISCORD_WEBHOOK']

# Parse the service account key
import json
creds_dict = json.loads(credentials_info)
creds = Credentials.from_service_account_info(creds_dict, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
client = gspread.authorize(creds)

# Get current month name and today's date in IST
tz = timezone('Asia/Kolkata')
today = datetime.now(tz).date()
month_name = today.strftime("%B %Y")  # Example: 'April 2025'

try:
    sheet = client.open_by_key(SHEET_ID).worksheet(month_name)
except gspread.exceptions.WorksheetNotFound:
    print(f"Worksheet '{month_name}' not found.")
    exit(0)

# Get all records
data = sheet.get_all_values()

# Find today's event based on column C (date) and get link from column M
todays_event_link = None
for row in data:
    if len(row) >= 13:
        try:
            event_date = datetime.strptime(row[2], "%d-%m-%Y").date()
            if event_date == today:
                todays_event_link = row[12]  # Column M is index 12
                break
        except Exception:
            continue

if not todays_event_link:
    print("No event found for today.")
    exit(0)

# Extract event ID from link
event_id = todays_event_link.strip('/').split('/')[-1]

# Get event details from TruckersMP API
response = requests.get(f"https://api.truckersmp.com/v2/event/{event_id}")
if response.status_code != 200:
    print("Failed to fetch event data from TruckersMP API")
    exit(1)

event_data = response.json().get('response', {})

# Prepare message for Discord
embed = {
    "title": event_data.get("name", "TruckersMP Event"),
    "url": todays_event_link,
    "fields": [
        {"name": "Game", "value": event_data.get("game", "N/A"), "inline": True},
        {"name": "Server", "value": event_data.get("server", "N/A"), "inline": True},
        {"name": "Start Time (UTC)", "value": event_data.get("start_at", "N/A"), "inline": False},
        {"name": "Departure", "value": event_data.get("departure", "N/A"), "inline": True},
        {"name": "Arrival", "value": event_data.get("arrival", "N/A"), "inline": True},
        {"name": "Meetup Location", "value": event_data.get("meetup", "N/A"), "inline": False},
    ]
}

# Post to Discord
requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]})
print("Posted to Discord!")
