import os
import gspread
import requests
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from pytz import timezone

# Load credentials and config
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('truckersmp-events-ef7e395df282.json', scope)
client = gspread.authorize(credentials)

SHEET_ID = '1jTadn8TtRP4ip5ayN-UClntNmKDTGY70wdPgo7I7lRY'
DISCORD_WEBHOOK = 'https://discord.com/api/webhooks/1358492482580779119/o4-NQuKr1zsUb9rUZsB_EnlYNiZwb_N8uXNfxfIRiGsdR8kh4CoKliIlSb8qot-F0HHO'

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
print(f"Event ID: {event_id}")

# Validate event ID exists in public event list
public_events_res = requests.get("https://api.truckersmp.com/v2/events")
if public_events_res.status_code != 200:
    print("Failed to fetch public events.")
    exit(1)

try:
    public_json = public_events_res.json()
    response_data = public_json.get("response", {})
    public_event_ids = []

    for category in response_data.values():
        if isinstance(category, list):
            for event in category:
                public_event_ids.append(str(event["id"]))

except Exception as e:
    print(f"Failed to parse public event list: {e}")
    print(public_events_res.text)
    exit(1)

if event_id not in public_event_ids:
    print(f"TruckersMP Event with ID {event_id} not found in public list. It may be private or unapproved.")
    exit(0)

# Fetch full event details
response = requests.get(f"https://api.truckersmp.com/v2/events/{event_id}")

if response.status_code == 404:
    print(f"TruckersMP Event with ID {event_id} not found. It may have been deleted.")
    exit(0)
elif response.status_code != 200:
    print(f"Failed to fetch event data from TruckersMP API. Status code: {response.status_code}")
    print(response.text)
    exit(1)

event_data = response.json().get('response', {})

# Safely access nested fields
server = event_data.get("server", {}).get("name", "N/A")
departure = event_data.get("departure", {}).get("city", "N/A")
arrival = event_data.get("arrival", {}).get("city", "N/A")
meetup_location = event_data.get("departure", {}).get("location", "N/A")

# Prepare message for Discord
# Create a new embed dictionary using your desired structure
from dateutil import parser
from pytz import timezone, utc

def safe_time_part(iso_str):
    if iso_str and "T" in iso_str:
        return iso_str.split("T")[1][:5]
    return "Unknown"

def safe_date_part(iso_str):
    if iso_str and "T" in iso_str:
        return iso_str.split("T")[0]
    return "Unknown"

def utc_to_ist(iso_time):
    if iso_time and "T" in iso_time:
        dt_utc = parser.isoparse(iso_time).replace(tzinfo=utc)
        dt_ist = dt_utc.astimezone(timezone('Asia/Kolkata'))
        return dt_ist.strftime("%H:%M")
    return "Unknown"

embed = {
    "title": f"📅 {event_data.get('name', 'TruckersMP Event')}",
    "url": todays_event_link,
    "color": 0xFFFF00,  # Yellow
    "fields": [
        {"name": "🛠 VTC", "value": event_data.get("vtc", {}).get("name", "Unknown VTC"), "inline": True},
        {"name": "📅 Date", "value": safe_date_part(event_data.get("start_at", "")), "inline": True},
        {"name": "⏰ Meetup (UTC)", "value": safe_time_part(event_data.get("meetup_at", "")), "inline": True},
        {"name": "⏰ Meetup (IST)", "value": utc_to_ist(event_data.get("meetup_at", "")), "inline": True},
        {"name": "🚀 Start (UTC)", "value": safe_time_part(event_data.get("start_at", "")), "inline": True},
        {"name": "🚀 Start (IST)", "value": utc_to_ist(event_data.get("start_at", "")), "inline": True},
        {"name": "🖥 Server", "value": event_data.get("server", {}).get("name", "Unknown"), "inline": True},
        {"name": "🚏 Departure", "value": event_data.get("departure", {}).get("city", "Unknown"), "inline": True},
        {"name": "🎯 Arrival", "value": event_data.get("arrival", {}).get("city", "Unknown"), "inline": True},
        {"name": "🗺 DLC", "value": ", ".join(event_data.get("dlcs", [])) or "Base Map", "inline": True}
    ]
}

payload = {
    "content": f"🚛 **Today's TruckersMP Event!**",
    "embeds": [embed]
}

res = requests.post(DISCORD_WEBHOOK, json=payload)
print(f"Posted to Discord! Status: {res.status_code}")

