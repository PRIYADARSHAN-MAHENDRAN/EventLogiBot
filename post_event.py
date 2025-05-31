import os
import gspread
import requests
import json
import time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from pytz import timezone
from google.oauth2.service_account import Credentials
from io import BytesIO
from bs4 import BeautifulSoup
from calendar import month_name as calendar_month_name



# === Configuration ===

ROLE_ID = (os.environ['ROLE_ID'])
DISCORD_WEBHOOK = (os.environ['DISCORD_WEBHOOK'])
SHEET_ID = (os.environ['SHEET_ID'])

# === Time Setup ===

tz_ist = timezone('Asia/Kolkata')
today = datetime.now(tz_ist).date()
timestamp_ist = datetime.now(tz_ist).isoformat()
print(f"today: {today}"+f"IST time: {timestamp}")
month_name = today.strftime("%b").upper() + "-" + str(today.year)  # E.g., "April 2025"

# === Authenticate with Google Sheets ===

keyfile_dict = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_KEY"])

# Authorize with gspread
creds = Credentials.from_service_account_info(keyfile_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
client = gspread.authorize(creds)

# === Date Parsing Helper ===

def parse_flexible_date(date_str):
    """Try multiple date formats to extract date from sheet"""
    date_formats = [
        "%A, %B %d, %Y %H.%M",  # Saturday, April 05, 2025 22.30
        "%a, %b %d, %Y %H.%M",  # Wed, Apr 2, 2025 22.30
        "%A, %B %d, %Y",        # Saturday, April 05, 2025
        "%a, %b %d, %Y",        # Wed, Apr 2, 2025
        "%d/%m/%Y",             # 26/4/2025
        "%d-%m-%Y"              # 26-04-2025
    ]
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue
    return None

# === Time Conversion Helpers ===

def utc_to_ist_ampm(utc_str):
    try:
        dt_utc = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
        dt_ist = dt_utc + timedelta(hours=5, minutes=30)
        return dt_ist.strftime("%I:%M %p")  # 12-hour format with AM/PM
    except Exception as e:
        print(f"Error converting UTC to IST: {e}")
        return "N/A"

def format_date(utc_str):
    """Format date as DD-MM-YYYY"""
    try:
        dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d-%m-%Y")
    except Exception as e:
        print(f"Error formatting date: {e}")
        return "N/A"


# === Step 1: Get Today’s Event Links from Google Sheet ===

spreadsheet = client.open_by_key(SHEET_ID)
# Try to open only the current month sheet
try:
    sheet = spreadsheet.worksheet(month_name)
    print(f"✅ Sheet '{month_name}' has found.")
except gspread.exceptions.WorksheetNotFound:
    print(f"❌ Sheet '{month_name}' has not found.")
    exit(0)

event_links_today = []
data = sheet.get_all_values()

for row in data:
    if len(row) >= 12 and row[11].strip().startswith("https://truckersmp.com/events"):
        raw_date = row[1].strip()
        event_date = parse_flexible_date(raw_date)

        if event_date == today:
            event_url = row[11].strip()
            print(f"✅ Found event for today in '{month_name}': {event_url}")
            event_links_today.append((event_url, row))

if not event_links_today:
    print("❌ No events found for today.")
    exit(0)


for event_link, row in event_links_today:
    event_id = event_link.strip('/').split('/')[-1].split('-')[0]


    response = requests.get(f"https://api.truckersmp.com/v2/events/{event_id}")
    if response.status_code != 200:
        print(f"❌ Failed to fetch data for event {event_id}")
        continue

    event_data = response.json().get('response', {})

    # === Extract slot info from Google Sheet row ===
    slot_no = row[9].strip() if len(row) > 9 and row[9].strip() else None
    slot_link = row[10].strip() if len(row) > 10 and row[10].strip() else None
    dlcs = event_data.get("dlcs", {})
    if dlcs:
        dlc_id, dlc_name = next(iter(dlcs.items()))
        dlc_display = f"{dlc_name}"
    else:
        dlc_display = "Base Map"

    # === Prepare Discord Embed ===
    thumbnail_url = event_data.get("banner")

    embed = {
    "image": {"url": thumbnail_url},
    "title": f"📅 {event_data.get('name', 'TruckersMP Event')}",
    "url": event_link,
    "color": 16776960,
    "fields": [
        {
            "name": "",
            "value": (
                    f"**🛠 VTC** : {event_data.get('vtc', {}).get('name', 'Unknown VTC')}\n\n"
                    f"**📅 Date** : {format_date(event_data.get('start_at', ''))}\n\n"
                    f"**⏰ Meetup Time** : {event_data.get('meetup_at', '').split(' ')[1][:5]} UTC "
                    f"({utc_to_ist_ampm(event_data.get('meetup_at', ''))} IST)\n\n"
                    f"**🚀 Departure Time** : {event_data.get('start_at', '').split(' ')[1][:5]} UTC "
                    f"({utc_to_ist_ampm(event_data.get('start_at', ''))} IST)\n\n"
                    f"**🖥 Server** : {event_data.get('server', {}).get('name', 'Unknown Server')}\n\n"
                    f"**🚏 Departure** : {event_data.get('departure', {}).get('city', 'Unknown')} "
                    f"({event_data.get('departure', {}).get('location', 'Unknown')})\n\n"
                    f"**🎯 Arrival** : {event_data.get('arrive', {}).get('city', 'Unknown')} "
                    f"({event_data.get('arrive', {}).get('location', 'Unknown')})\n\n"
                    f"**🗺 DLC Req** : {dlc_display}\n\n"
                    f"**🪧 Slot Number** : {slot_no or 'N/A'}\n\n"
                    f"**Event**: {event_link}\n\n"
                    + (f"**Map**: {event_data.get('map')}\n\n" if event_data.get('map') else "")
                    + (f"**Slot**: {slot_link}\n\n" if slot_link else "")
                    + "**💬 Thank You Message:**\n\n"
                    + f"💛 Thank you, {event_data.get('vtc', {}).get('name', 'your VTC')}. "
                      f"For inviting us to your {event_data.get('name', 'event')}. "
                      f"We had a great time and enjoyed it a lot! - TAMILNADU LOGISTICS 💛"
                ),
            "inline": False
        },
    ],
    "footer": {"text": "by TNL | PRIYADARSHAN"},
    "timestamp": timestamp_ist

}

    # === Send event embed ===
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "content": f"||<@&{ROLE_ID}>||",
        "embeds": [embed],
    }
    resp = requests.post(DISCORD_WEBHOOK, headers=headers, json=payload)
    
    if resp.status_code in [200, 204]:
        print(f"✅ Event {event_id} successfully posted to Discord!")
    else:
        print(f"❌ Failed to post event {event_id} to Discord: {resp.status_code}")
        print(resp.text)

    time.sleep(1)
    # === Send Route Map as plain message ===
    map_url = event_data.get("map")
    if map_url:
        map_payload = {
            "content": f"🗺️ **Route Map for {event_data.get('name', 'Event')}**\n{map_url}"
        }
        reps=requests.post(DISCORD_WEBHOOK, headers=headers, json=map_payload)
        if resp.status_code in [200, 204]:
            print("✅ Map image sent with caption.")
        else:
            print(f"❌ Failed to send map image: {resp.status_code}")
    else:
        print("❌ Could not fetch map image.")

    time.sleep(1)
    
    if slot_link:
        slot_payload = {
            "content": f"📸 **Slot Image for {event_data.get('name', 'Event')}**\n{slot_link}"
        }
        resp=requests.post(DISCORD_WEBHOOK, headers=headers, json=slot_payload)
        if resp.status_code in [200, 204]:
            print("✅ Slot image sent with caption.")
        else:
            print(f"❌ Failed to send slot image: {resp.status_code}")
    else:
        print("❌ Could not fetch slot image.")

    time.sleep(1)
