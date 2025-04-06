import os
import gspread
import requests
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from pytz import timezone, utc
from datetime import timedelta
# === Config ===
ROLE_ID = "1356018983496843294"  # Replace with your actual Discord role ID
content = f"<@&{ROLE_ID}>"

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


def parse_flexible_date(date_str):
    from datetime import datetime

    date_formats = [
        "%A, %B %d, %Y %H.%M",  # Saturday, April 05, 2025 22.30
        "%a, %b %d, %Y %H.%M",  # Wed, Apr 2, 2025 22.30
        "%A, %B %d, %Y",        # Saturday, April 05, 2025
        "%a, %b %d, %Y",        # Wed, Apr 2, 2025
        "%d/%m/%Y",             # 26/4/2025
        "%d-%m-%Y"              # fallback to your original format
    ]

    for fmt in date_formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None  # If all formats fail

data = sheet.get_all_values()
todays_event_link = None
for row in data:
    if len(row) >= 13:
        raw_date = row[2].strip()
        print(f"Raw date from sheet: {raw_date}")
        event_date = parse_flexible_date(raw_date)
        print(f"Parsed sheet date: {event_date}")

        if event_date:
            try:
                event_url = row[12].strip()
                if "truckersmp.com/events" not in event_url:
                    continue

                event_id_candidate = event_url.strip('/').split('/')[-1]
                event_api = requests.get(f"https://api.truckersmp.com/v2/events/{event_id_candidate}")
                if event_api.status_code == 200:
                    event_json = event_api.json().get("response", {})
                    utc_time = datetime.strptime(event_json.get("start_at", ""), "%Y-%m-%d %H:%M:%S")
                    ist_time = utc_time + timedelta(hours=5, minutes=30)
                    print(f"IST event start time: {ist_time} | Date: {ist_time.date()} | Today: {today}")

                    if ist_time.date() == today:
                        print("✅ Matching event found for today!")
                        todays_event_link = event_url
                        break
                else:
                    print(f"Failed to fetch event details for ID {event_id_candidate}")
            except Exception as e:
                print(f"Error checking API date match: {e}")


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


def utc_to_ist(utc_str):
    try:
        dt_utc = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
        dt_ist = dt_utc + timedelta(hours=5, minutes=30)
        return dt_ist.strftime("%H:%M")
    except Exception as e:
        print(f"Error converting UTC to IST: {e}")
        return "N/A"

def format_date(utc_str):
    try:
        dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d-%m-%Y")
    except Exception as e:
        print(f"Error formatting date: {e}")
        return "N/A"

# === Prepare Fancy Embed ===
embed = {
    "title": f"📅 {event_data.get('name', 'TruckersMP Event')}",
    "url": todays_event_link,
    "color": 16776960,  # Yellow
    "fields": [
        {"name": "🛠 VTC", "value": event_data.get('vtc', {}).get("name", "Unknown VTC"), "inline": True},
        {"name": "📅 Date", "value": format_date(event_data.get("start_at", "")), "inline": True},
        {"name": "⏰ Meetup (UTC)", "value": event_data.get("meetup_at", "").split(" ")[1][:5], "inline": True},
        {"name": "⏰ Meetup (IST)", "value": utc_to_ist(event_data.get("meetup_at", "")), "inline": True},
        {"name": "🚀 Start (UTC)", "value": event_data.get("start_at", "").split(" ")[1][:5], "inline": True},
        {"name": "🚀 Start (IST)", "value": utc_to_ist(event_data.get("start_at", "")), "inline": True},
        {"name": "🖥 Server", "value": event_data.get("server", {}).get("name", "Unknown Server"), "inline": True},
        {"name": "🚏 Departure", "value": event_data.get("departure", {}).get("city", "Unknown"), "inline": True},
        {"name": "🎯 Arrival", "value": event_data.get("arrival", {}).get("city", "Unknown"), "inline": True},
        {"name": "🗺 DLC", "value": ", ".join(event_data.get("dlcs", [])) if event_data.get("dlcs") else "Base Map", "inline": True}
    ]
}


# === Send to Discord ===
payload = {
    "content": f"<@&{ROLE_ID}>",  # This will mention the role
    "embeds": [embed]
}

resp = requests.post(DISCORD_WEBHOOK, json=payload)

if resp.status_code in [200, 204]:
    print("✅ Event successfully posted to Discord!")
else:
    print(f"❌ Failed to post to Discord: {resp.status_code}")
    print(resp.text)
