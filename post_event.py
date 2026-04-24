# =========================
# 📦 Imports
# =========================

import os
import gspread
import requests
import json
import time
import re
from datetime import datetime, timedelta
from pytz import timezone
from google.oauth2.service_account import Credentials


# =========================
# ⚙️ Global Variables
# =========================

error_log = []


# =========================
# 🚨 Error Handling
# =========================

def send_error(e, context=""):
    msg = f"{context}: {e}"
    error_log.append(msg)
    
def send_error_report():
    if not error_log:
        print("✅ No errors to report.")
        return
    try:
        mentions = os.environ.get("ERROR_ROLE", "")
        content = f"||{mentions}||\n❌ **Error Summary ({len(error_log)} errors):**\n\n"
        for err in error_log:
            content += f"• {err}\n"
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


# =========================
# ⏱️ Time Setup
# =========================

tz_ist = timezone('Asia/Kolkata')
today = datetime.now(tz_ist).date()
timestamp_ist = datetime.now(tz_ist).isoformat()
print(f"Today: {today}\n"+f"IST time: {timestamp_ist}")
month_name = today.strftime("%b").upper() +" " + str(today.year)  # E.g., "April 2025"


# =========================
# 🔐 Configuration
# =========================

ROLE_ID = (os.environ['ROLE_ID'])
ROLE_ID1 = (os.environ['ROLE_ID1'])
DISCORD_WEBHOOK = (os.environ['DISCORD_WEBHOOK'])
SHEET_ID = (os.environ['SHEET_ID'])
ERROR_WEBHOOK = os.environ['ERROR_WEBHOOK']


# =========================
# 📊 Google Sheets Setup
# =========================

keyfile_dict = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_KEY"])
creds = Credentials.from_service_account_info(keyfile_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"])
client = gspread.authorize(creds)


# =========================
# 🕒 Time Helpers
# =========================

def is_event_today_ist(meetup_utc):
    try:
        dt_ist = utc_to_ist_datetime(meetup_utc)
        return dt_ist.date() == today
    except Exception as e:
        send_error(e, "IST date check failed")
        return False

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


# =========================
# 🌐 API Helper
# =========================

def fetch_event(event_id, retries=3):
    for _ in range(retries):
        try:
            res = requests.get(f"https://api.truckersmp.com/v2/events/{event_id}")
            if res.status_code == 200:
                return res.json().get("response", {})
        except Exception as e:
            send_error(e, "API fetch error")
        time.sleep(2)
    return None

def open_sheet(client, sheet_id, retries=5):
    for i in range(retries):
        try:
            print(f"Opening sheet (Attempt {i+1})...")
            return client.open_by_key(sheet_id)
        except Exception as e:
            print(f"❌ Attempt {i+1} failed: {e}")
            time.sleep(5)
    raise Exception("❌ Failed to open Google Sheet after multiple attempts")


# =========================
# 📄 Load Sheet
# =========================

spreadsheet = open_sheet(client, SHEET_ID)

# Try to open only the current month sheet
try:
    sheet = spreadsheet.worksheet(month_name)
    print(f"✅ Sheet '{month_name}' has found.")
except gspread.exceptions.WorksheetNotFound:
    print(f"❌ Sheet '{month_name}' has not found.")
    send_error("❌ Sheet has not found so kindly check month name in sheet", "Event Checker")
    send_error_report()
    exit(0)

data = sheet.get_all_values()
data = [row for row in data if any(cell.strip() for cell in row)]
print(f"Total rows fetched: {len(data)}")

# =========================
# 🔁 Main Loop
# =========================

for idx, row in enumerate(data, start=1):
    print(f"[Row {idx}] RAW LINK: {row[11]}")
    if len(row) <= 11:
        print(f"[Row {idx}] ❌ Skipped: Not enough columns")
        continue
    
    event_link = row[11].strip()
    
    if not event_link.startswith("https://truckersmp.com/events"):
        print(f"[Row {idx}] ❌ Skipped: Invalid event link -> {event_link}")
        continue
    
    # Extract event ID
    match = re.search(r"events/(\d+)", event_link)
    if not match:
        print(f"[Row {idx}] ❌ Skipped: Event ID not found in link -> {event_link}")
        continue
    
    event_id = match.group(1)
    print(f"[Row {idx}] 🔍 Processing Event ID: {event_id}")
    
    # Fetch API
    event_data = fetch_event(event_id)
    
    if not event_data:
        print(f"[Row {idx}] ❌ API Failed: https://truckersmp.com/events/{event_id}")
        send_error(f"Failed to fetch event details: https://truckersmp.com/events/{event_id}", "API")
        continue
    
    print(f"[Row {idx}] ✅ API Success: {event_data.get('name', 'Unknown Event')}")
    
    meetup_utc = event_data.get("meetup_at")
    
    if not meetup_utc:
        print(f"[Row {idx}] ❌ Skipped: 'meetup_at' missing in API")
        continue
    
    print(f"[Row {idx}] 🕒 Meetup UTC: {meetup_utc}")
    
    # Convert to IST for debug
    try:
        ist_time = utc_to_ist_datetime(meetup_utc)
        print(f"[Row {idx}] 🇮🇳 IST Time: {ist_time}")
    except Exception as e:
        print(f"[Row {idx}] ❌ Error converting time: {e}")
    
    # ✅ Check date using API only
    if not is_event_today_ist(meetup_utc):
        print(f"[Row {idx}] ⏭ Skipped: Not today's event")
        continue
    
    print(f"[Row {idx}] 🎯 MATCH: Event is today!")

    # === Extract slot info from sheet ===
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
        send_error(f"❌ Failed to post event to Discord for {event_data.get('name', 'TruckersMP Event')}", "Event Checker")


    time.sleep(1)
    # === Send Route Map as plain message ===
    map_url = event_data.get("map")
    if map_url:
        map_payload = {
            "content": f"🗺️ **Route Map for {event_data.get('name', 'Event')}**\n{map_url}"
        }
        reps=requests.post(DISCORD_WEBHOOK, headers=headers, json=map_payload)
        if reps.status_code in [200, 204]:
            print("✅ Map image sent with caption.")
        else:
            print(f"❌ Failed to send map image for {event_data.get('name', 'TruckersMP Event')}: {resp.status_code}")
            send_error(f"Failed to send map image for {event_data.get('name', 'TruckersMP Event')}", "Event Checker")

    else:
        print(f"❌ Could not fetch map image for {event_data.get('name', 'TruckersMP Event')}")
        send_error(f"Could not fetch map image for {event_data.get('name', 'TruckersMP Event')}", "Event Checker")


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
            send_error(f"Failed to send slot image for {event_data.get('name', 'TruckersMP Event')}", "Event Checker")

    else:
        print(f"❌ Could not fetch slot image for {event_data.get('name', 'TruckersMP Event')}.")
        send_error(f"Could not fetch slot image for {event_data.get('name', 'TruckersMP Event')}", "Event Checker")


    time.sleep(1)
    print("Next event check")
send_error_report()
