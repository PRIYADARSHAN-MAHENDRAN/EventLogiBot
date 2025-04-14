import os
import gspread
import requests
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from pytz import timezone
from google.oauth2.service_account import Credentials
from io import BytesIO



# === Configuration ===

# ROLE_ID = "1335290367347658762"
# DISCORD_WEBHOOK = 'https://discord.com/api/webhooks/1349764291859054623/WCmkpgMVX_MkVlpNyBnC_2fycbgDnUNdzMTmZhCdTASythWRXm_oa0UuF1U8Y4SBIYWg'
# SHEET_ID = '1xcTUTFmwirTCIAseDtgr0ev7cHJq8FAuGI7wHDa_yMg'

ROLE_ID = "1356018983496843294"  # Replace with your actual Discord role ID
DISCORD_WEBHOOK = 'https://discord.com/api/webhooks/1358492482580779119/o4-NQuKr1zsUb9rUZsB_EnlYNiZwb_N8uXNfxfIRiGsdR8kh4CoKliIlSb8qot-F0HHO'
SHEET_ID = '1jTadn8TtRP4ip5ayN-UClntNmKDTGY70wdPgo7I7lRY'

# === Time Setup ===

tz_ist = timezone('Asia/Kolkata')
today = datetime.now(tz_ist).date()
timestamp_ist = datetime.now(tz_ist).isoformat()
print(f"today: {today}")
month_name = today.strftime("%B %Y")  # E.g., "April 2025"

# === Authenticate with Google Sheets ===

keyfile_dict = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_KEY"])

# Authorize with gspread
creds = Credentials.from_service_account_info(keyfile_dict, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
client = gspread.authorize(creds)


def download_imgur_image(link):
    try:
        # If it's already a direct image link, use it directly
        if "i.imgur.com" in link:
            direct_url = link
        elif "imgur.com" in link:
            # Extract just the image ID from typical Imgur URL
            image_id = link.strip().split("/")[-1].split("?")[0]
            direct_url = f"https://i.imgur.com/{image_id}.png"
        else:
            print("❌ Not an Imgur link.")
            return None, None

        response = requests.get(direct_url)
        if response.status_code == 200:
            return BytesIO(response.content), direct_url.split("/")[-1]
        else:
            print(f"❌ Failed to fetch image from: {direct_url}")
    except Exception as e:
        print(f"❌ Exception in download_imgur_image: {e}")
    return None, None



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

# === DLC Mapping (from TruckersMP DLC IDs) ===

DLC_ID_MAP = {
    304212: "Going East!",
    304213: "Scandinavia",
    304215: "Vive la France!",
    304216: "Italia",
    304217: "Beyond the Baltic Sea",
    304218: "Road to the Black Sea",
    304219: "Iberia",
    304220: "West Balkans",
    461910: "Heavy Cargo Pack",
    558244: "Special Transport",
    258666: "High Power Cargo Pack",
    620610: "Krone Trailer Pack",
    388470: "Cabin Accessories",
    297721: "Wheel Tuning Pack",
    645630: "Schwarzmüller Trailer Pack",
}

def get_dlc_names(dlc_ids):
    """Convert list of DLC IDs to human-readable names"""
    if not dlc_ids:
        return "Base Map"
    return ", ".join(DLC_ID_MAP.get(int(dlc_id), f"Unknown ({dlc_id})") for dlc_id in dlc_ids)

# === Step 1: Get Today’s Event Links from Google Sheet ===

spreadsheet = client.open_by_key(SHEET_ID)
worksheets = spreadsheet.worksheets()

event_links_today = []

for sheet in worksheets:
    print(f"🔍 Checking sheet: {sheet.title}")
    data = sheet.get_all_values()

    for row in data:
        if len(row) >= 12 and row[11].strip().startswith("https://truckersmp.com/events"):
            raw_date = row[1].strip()
            event_date = parse_flexible_date(raw_date)

            if event_date == today:
                event_url = row[11].strip()
                print(f"✅ Found event for today in '{sheet.title}': {event_url}")
                event_links_today.append((event_url, row))

if not event_links_today:
    print("❌ No events found for today.")
    exit(0)

# === Step 2: Get All Public TruckersMP Event IDs ===

# public_events_res = requests.get("https://api.truckersmp.com/v2/events")
# if public_events_res.status_code != 200:
#     print("❌ Failed to fetch public events.")
#     exit(1)

# try:
#     public_json = public_events_res.json()
#     response_data = public_json.get("response", {})
#     public_event_ids = [
#         str(event["id"])
#         for category in response_data.values() if isinstance(category, list)
#         for event in category
#     ]
# except Exception as e:
#     print(f"❌ Failed to parse public event list: {e}")
#     exit(1)

# === Step 3: Process & Post Each Event to Discord ===

for event_link, row in event_links_today:
    event_id = event_link.strip('/').split('/')[-1].split('-')[0]

    # if event_id not in public_event_ids:
    #          print(f"⚠️ Event {event_id} is not public. Skipping.")
    #          continue

    response = requests.get(f"https://api.truckersmp.com/v2/events/{event_id}")
    if response.status_code != 200:
        print(f"❌ Failed to fetch data for event {event_id}")
        continue

    event_data = response.json().get('response', {})

    # === Extract slot info from Google Sheet row ===
    slot_no = row[9].strip() if len(row) > 9 and row[9].strip() else None
    slot_link = row[10].strip() if len(row) > 10 and row[10].strip() else None

    # === Prepare Discord Embed ===
    thumbnail_url = event_data.get("banner")

    embed = {
        "image": {"url": thumbnail_url},
        "title": f"📅 {event_data.get('name', 'TruckersMP Event')}",
        "url": event_link,
        "color": 16776960,
        "fields": [
            {"name": "🛠 VTC", "value": event_data.get('vtc', {}).get("name", "Unknown VTC"), "inline": True},
            {"name": "📅 Date", "value": format_date(event_data.get("start_at", "")), "inline": True},
            {"name": "⏰ Meetup Time","value": f"{event_data.get('meetup_at', '').split(' ')[1][:5]} UTC ({utc_to_ist_ampm(event_data.get('meetup_at', ''))} IST)","inline": True},
            {"name": "🚀 Departure Time","value": f"{event_data.get('start_at', '').split(' ')[1][:5]} UTC ({utc_to_ist_ampm(event_data.get('start_at', ''))} IST)","inline": True},
            {"name": "🖥 Server", "value": event_data.get("server", {}).get("name", "Unknown Server"), "inline": True},
            {"name": "🚏 Departure", "value": event_data.get("departure", {}).get("city", "Unknown"), "inline": True},
            {"name": "🎯 Arrival", "value": event_data.get("arrival", {}).get("city", "Unknown"), "inline": True},
            {"name": "🗺 DLC Req", "value": get_dlc_names(event_data.get("dlcs", [])), "inline": True},
            {"name": "🪧 Slot Number", "value": slot_no or "N/A", "inline": True},
            {
            "name": "🔗 Links",
            "value": (
                f"Event: {event_link}" +
                (f"\nMap: {event_data.get('map')}" if event_data.get('map') else "") +
                (f"\nSlot: {slot_link}" if slot_link else "")
            ),
            "inline": False
        },
        {
            "name": "💬 Thank You Message:",
            "value": f"💛 Thank you, {event_data.get('vtc', {}).get('name', 'your VTC')}. "
                     f"For inviting us to your {event_data.get('name', 'event')}. "
                     f"We had a great time and enjoyed it a lot! - TAMILNADU LOGISTICS 💛",
            "inline": False
        }
    ],
        "footer": {"text": "by TNL | PRIYADARSHAN"},
    "timestamp": timestamp_ist
    }

    # === Send to Discord Webhook ===
    headers = {
        "Content-Type": "application/json"
    }

    payload = {
        "content": f"||<@&{ROLE_ID}>||",  # Hidden role mention
        "embeds": [embed],
    }

    resp = requests.post(DISCORD_WEBHOOK, headers=headers, json=payload)

    if resp.status_code in [200, 204]:
        print(f"✅ Event {event_id} successfully posted to Discord!")
    else:
        print(f"❌ Failed to post event {event_id} to Discord: {resp.status_code}")
        print(resp.text)
    if slot_link:
        print(f"📸 Slot image link: {slot_link}")
        image_file, filename = download_imgur_image(slot_link)
        if image_file:
            image_file.seek(0)
            files = {
                'file': (filename, image_file, 'image/png')
            }
            resp = requests.post(DISCORD_WEBHOOK, files=files)
    
            if resp.status_code in [200, 204]:
                print("✅ Slot image sent as normal image.")
            else:
                print(f"❌ Failed to send slot image: {resp.status_code}")
        else:
            print("❌ Could not fetch slot image.")

