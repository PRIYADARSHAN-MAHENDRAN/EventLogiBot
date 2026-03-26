import os
import gspread
import requests
import json
import time
import traceback
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from pytz import timezone
from google.oauth2.service_account import Credentials
from io import BytesIO
from bs4 import BeautifulSoup
from calendar import month_name as calendar_month_name

# --- Global list to collect errors ---
error_log = []

def send_error_report():
    print(error_log)
    if not error_log:
        print("✅ No errors to report.")
        return

    try:
        mentions = os.environ.get("ERROR_ROLE", "")
        content = f"||{mentions}||\n❌ **Error Summary:**\n```" + "\n".join(error_log) + "```"

        payload = {
            "content": content,  # mentions must be in content, not embeds
            "allowed_mentions": {
                "parse": ["roles", "users"]
            }
        }

        res = requests.post(ERROR_WEBHOOK, json=payload)
        res.raise_for_status()
        print(f"✅ Error report sent to Discord ({len(error_log)} errors)")
    except Exception as e:
        print(f"❌ Failed to send error report: {e}")


def send_error(e, context=""):
    """Collect individual errors without spamming Discord."""
    msg = f"{context}: {e}"
    error_log.append(msg)

# === Configuration ===

ROLE_ID = (os.environ['ROLE_ID'])
ROLE_ID1 = (os.environ['ROLE_ID1'])
DISCORD_WEBHOOK = (os.environ['DISCORD_WEBHOOK'])
SHEET_ID = (os.environ['SHEET_ID'])
ERROR_WEBHOOK = os.environ['ERROR_WEBHOOK']


# === Time Setup ===

tz_ist = timezone('Asia/Kolkata')
today = datetime.now(tz_ist).date()
timestamp_ist = datetime.now(tz_ist).isoformat()
print(f"Today: {today}\n"+f"IST time: {timestamp_ist}")
month_name = today.strftime("%b").upper() +" " + str(today.year)  # E.g., "April 2025"

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
    try:
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
        raise ValueError(f"No valid date format found for '{date_str}'")
    except Exception as e:
        send_error(e, f"parse_flexible_date failed for date: {date_str}")
        return None

# === Time Conversion Helpers ===

def utc_to_ist_ampm(utc_str):
    try:
        dt_utc = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
        dt_ist = dt_utc + timedelta(hours=5, minutes=30)
        return dt_ist.strftime("%I:%M %p")  # 12-hour format with AM/PM
    except Exception as e:
        print(f"Error converting UTC to IST: {e}")
        send_error(e, "Error converting UTC to IST")
        return "N/A"

def format_date(utc_str):
    """Format date as DD-MM-YYYY"""
    try:
        dt = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d-%m-%Y")
    except Exception as e:
        print(f"Error formatting date: {e}")
        send_error(e, "Error formatting date")
        return "N/A"

def utc_to_ist_datetime(utc_str):
    dt_utc = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S")
    dt_ist = dt_utc + timedelta(hours=5, minutes=30)
    return dt_ist

def is_event_today(sheet_date, meetup_utc):
    try:
        dt_ist = utc_to_ist_datetime(meetup_utc)
        event_date = dt_ist.date()
        event_time = dt_ist.time()

        # Case 1: Same day
        if event_date == sheet_date:
            return True

        # Case 2: Next day but early morning (before 2 AM)
        if event_date == sheet_date + timedelta(days=1) and event_time.hour < 2:
            return True

        return False

    except Exception as e:
        send_error(e, "Date validation failed")
        return False
# === Step 1: Get Today’s Event Links from Google Sheet ===

def open_sheet_with_retry(client, sheet_id, retries=5):
    for i in range(retries):
        try:
            print(f"Opening sheet (Attempt {i+1})...")
            return client.open_by_key(sheet_id)
        except Exception as e:
            print(f"❌ Attempt {i+1} failed: {e}")
            time.sleep(5)
    raise Exception("❌ Failed to open Google Sheet after multiple attempts")

spreadsheet = open_sheet_with_retry(client, SHEET_ID)

# Try to open only the current month sheet
try:
    sheet = spreadsheet.worksheet(month_name)
    print(f"✅ Sheet '{month_name}' has found.")
except gspread.exceptions.WorksheetNotFound:
    print(f"❌ Sheet '{month_name}' has not found.")
    send_error("❌ Sheet has not found so kindly check month name in sheet", "Event Checker")
    send_error_report()
    exit(0)

event_links_today = []
data = sheet.get_all_values()

for row in data:
    if row[11].strip().startswith("https://truckersmp.com/events"):
        raw_date = row[1].strip()
        event_date = parse_flexible_date(raw_date)

        if event_date == today:
            event_url = row[11].strip()
            print(f"✅ Found event for today in '{month_name}': {event_url}")
            event_links_today.append((event_url, row))

if not event_links_today:
    print("❌ No events found for today.")
    send_error("❌ No events found for today.", "Event Checker")
    send_error_report()
    exit(0)


for event_link, row in event_links_today:
    event_id = event_link.strip('/').split('/')[-1].split('-')[0]


    response = requests.get(f"https://api.truckersmp.com/v2/events/{event_id}")
    if response.status_code != 200:
        print(f"❌ Failed to fetch data for event {event_id}")
        send_error("❌ Failed to fetch data for event", "Event Checker")

        continue

    event_data = response.json().get('response', {})

    meetup_utc = event_data.get('meetup_at')

    if is_event_today(today, meetup_utc):
        print("✅ Event matches today's IST logic")
    else:
        print(f"❌Date mismatch (Sheet: {today}, API: {utc_to_ist_datetime(meetup_utc).date()})")
        send_error(f"❌ Date mismatch (Sheet: {today}, Truckersmp: {utc_to_ist_datetime(meetup_utc).date()})", "Validation")
        continue
    
    # === Extract slot info from Google Sheet row ===
    slot_no = row[9].strip() if len(row) > 9 and row[9].strip() else None
    slot_link = row[10].strip() if len(row) > 10 and row[10].strip() else None
    dlcs = event_data.get("dlcs", {})
    if dlcs:
        dlc_id, dlc_name = next(iter(dlcs.items()))
        dlc_display = f"{dlc_name}"
    else:
        dlc_display = "Base Map"

    # === Pick Thank You Name ===
    thank_you_name = event_data.get('vtc', {}).get('name')
    if not thank_you_name or thank_you_name.strip() == "":
        thank_you_name = event_data.get('user', {}).get('username', 'your VTC')

    
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
                    + f"💛 Thank you, {thank_you_name}. "
                      f"For inviting us to your {event_data.get('name', 'event')}. "
                      f"We had a great time and enjoyed it a lot! - TAMILNADU LOGISTICS 💛"
                ),
            "inline": False
        },
    ],
    "footer": {"text": "by TNL | EVENT MANAGEMENT"},
    "timestamp": timestamp_ist

}

    # === Send event embed ===
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "content": f"||<@&{ROLE_ID}><@&{ROLE_ID1}>||",
        "embeds": [embed],
    }
    resp = requests.post(DISCORD_WEBHOOK, headers=headers, json=payload)
    
    if resp.status_code in [200, 204]:
        print(f"✅ Event {event_id} successfully posted to Discord!")
    else:
        print(f"❌ Failed to post event {event_id} to Discord: {resp.status_code}")
        print(resp.text)
        send_error("❌ Failed to post event to Discord", "Event Checker")


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
            send_error("Failed to send map image", "Event Checker")

    else:
        print("❌ Could not fetch map image.")
        send_error("Could not fetch map image", "Event Checker")


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
            send_error("Failed to send slot image", "Event Checker")

    else:
        print("❌ Could not fetch slot image.")
        send_error("Could not fetch slot image", "Event Checker")


    time.sleep(1)
send_error_report()
