import os
import gspread
import requests
import json
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
from pytz import timezone
from google.oauth2.service_account import Credentials
from io import BytesIO
from bs4 import BeautifulSoup



# === Configuration ===

ROLE_ID = (os.environ['ROLE_ID'])
DISCORD_WEBHOOK = (os.environ['DISCORD_WEBHOOK'])
SHEET_ID = (os.environ['SHEET_ID'])

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



IMGUR_CLIENT_ID = "3dd4c42bea4ea10"  # Replace with your actual Client ID

def download_imgur_image(link):
    try:
        headers = {
            "Authorization": f"Client-ID {IMGUR_CLIENT_ID}"
        }

        # If it's a direct image link
        if any(link.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            response = requests.get(link)
            if response.status_code == 200:
                filename = link.split("/")[-1].split("?")[0]
                return BytesIO(response.content), filename
            else:
                print(f"❌ Failed to fetch image from: {link}")
                return None, None

        # If it's an Imgur album link
        if "imgur.com/a/" in link:
            album_id = link.split("/a/")[-1].split("/")[0].split("?")[0]
            api_url = f"https://api.imgur.com/3/album/{album_id}/images"
            response = requests.get(api_url, headers=headers)
            if response.status_code == 200:
                images = response.json().get("data", [])
                if images:
                    direct_url = images[0]["link"]
                    image_response = requests.get(direct_url)
                    if image_response.status_code == 200:
                        filename = direct_url.split("/")[-1]
                        return BytesIO(image_response.content), filename
                print("❌ No images found in the Imgur album.")
                return None, None
            else:
                print(f"❌ Failed to fetch album info: {response.status_code} {response.text}")
                return None, None

        # If it's a regular Imgur page (e.g. imgur.com/abc123)
        if "imgur.com" in link:
            image_id = link.strip().split("/")[-1].split("?")[0].split("#")[0]
            api_url = f"https://api.imgur.com/3/image/{image_id}"
            response = requests.get(api_url, headers=headers)
            if response.status_code == 200:
                data = response.json()["data"]
                direct_url = data["link"]
                image_response = requests.get(direct_url)
                if image_response.status_code == 200:
                    filename = direct_url.split("/")[-1]
                    return BytesIO(image_response.content), filename
            else:
                print(f"❌ Failed to fetch image info: {response.status_code} {response.text}")
                return None, None

        print("❌ Unsupported image link format.")
        return None, None

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
            ),

            "inline": False
        },
        {
            "name": "**🔗 Links**",
            "value": (
                f"**Event**: {event_link}\n\n" +
                (f"**Map**: {event_data.get('map')}\n\n" if event_data.get('map') else "") +
                (f"**Slot**: {slot_link}\n\n" if slot_link else "")
            ),
            "inline": False
        },
        {
            "name": "**💬 Thank You Message:**\n",
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

