import os
import gspread
import requests
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from pytz import timezone, utc

# === Config ===
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name('truckersmp-events-ef7e395df282.json', scope)
client = gspread.authorize(credentials)

SHEET_ID = '1jTadn8TtRP4ip5ayN-UClntNmKDTGY70wdPgo7I7lRY'
DISCORD_WEBHOOK = 'https://discord.com/api/webhooks/1358492482580779119/o4-NQuKr1zsUb9rUZsB_EnlYNiZwb_N8uXNfxfIRiGsdR8kh4CoKliIlSb8qot-F0HHO'

# === Time Setup ===
tz_ist = timezone('Asia/Kolkata')
today = datetime.now(tz_ist).date()
month_name = today.strftime("%B %Y")  # e.g., "April 2025"

# === Load Sheet ===
try:
    sheet = client.open_by_key(SHEET_ID).worksheet(month_name)
except gspread.exceptions.WorksheetNotFound:
    print(f"Worksheet '{month_name}' not found.")
    exit(0)

# === Find Today's Event ===
data = sheet.get_all_values()
todays_event_link = None
for row in data:
    if len(row) >= 13:
        try:
            event_date = datetime.strptime(row[2], "%d-%m-%Y").date()
            if event_date == today:
                todays_event_link = row[12]
                break
        except Exception:
            continue

if not todays_event_link:
    print("No event found for today.")
    exit(0)

# === Extract Event ID ===
event_id = todays_event_link.strip('/').split('/')[-1]
print(f"Event ID: {event_id}")

# === Check Event Public ===
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
    exit(1)

if event_id not in public_event_ids:
    print(f"TruckersMP Event with ID {event_id} not found in public list. It may be private or unapproved.")
    exit(0)

# === Fetch Full Event Details ===
response = requests.get(f"https://api.truckersmp.com/v2/events/{event_id}")
if response.status_code == 404:
    print(f"TruckersMP Event with ID {event_id} not found. It may have been deleted.")
    exit(0)
elif response.status_code != 200:
    print(f"Failed to fetch event data from TruckersMP API. Status code: {response.status_code}")
    exit(1)

event_data = response.json().get('response', {})

# === UTC to IST Converter ===
def utc_to_ist(iso_time_str):
    try:
        dt_utc = datetime.strptime(iso_time_str, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        # fallback if missing timezone
        dt_utc = datetime.strptime(iso_time_str, "%Y-%m-%dT%H:%M:%S")
        dt_utc = utc.localize(dt_utc)
    dt_ist = dt_utc.astimezone(tz_ist)
    return dt_ist.strftime("%H:%M")

def format_date(iso_time_str):
    try:
        dt = datetime.strptime(iso_time_str, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        dt = datetime.strptime(iso_time_str, "%Y-%m-%dT%H:%M:%S")
        dt = utc.localize(dt)
    return dt.strftime("%d-%m-%Y")

# === Prepare Fancy Embed ===
embed = {
    "title": f"📅 {event_data.get('name', 'TruckersMP Event')}",
    "url": todays_event_link,
    "color": 16776960,  # Yellow
    "fields": [
        {"name": "🛠 VTC", "value": event_data.get("vtc", {}).get("name", "Unknown VTC"), "inline": True},
        {"name": "📅 Date", "value": format_date(event_data.get("start_at", "")), "inline": True},
        {"name": "⏰ Meetup (UTC)", "value": event_data.get("meetup_at", "").split("T")[1][:5], "inline": True},
        {"name": "⏰ Meetup (IST)", "value": utc_to_ist(event_data.get("meetup_at", "")), "inline": True},
        {"name": "🚀 Start (UTC)", "value": event_data.get("start_at", "").split("T")[1][:5], "inline": True},
        {"name": "🚀 Start (IST)", "value": utc_to_ist(event_data.get("start_at", "")), "inline": True},
        {"name": "🖥 Server", "value": event_data.get("server", "Unknown"), "inline": True},
        {"name": "🚏 Departure", "value": event_data.get("departure", "Unknown"), "inline": True},
        {"name": "🎯 Arrival", "value": event_data.get("arrival", "Unknown"), "inline": True},
        {"name": "🗺 DLC", "value": ", ".join(event_data.get("dlcs", [])) if event_data.get("dlcs") else "Base Map", "inline": True},
    ]
}

# === Send to Discord ===
resp = requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]})
if resp.status_code in [200, 204]:
    print("✅ Event successfully posted to Discord!")
else:
    print(f"❌ Failed to post to Discord: {resp.status_code}")
    print(resp.text)
