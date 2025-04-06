import gspread
from datetime import datetime
import requests
import os
import json
from google.oauth2.service_account import Credentials

# === CONFIG ===
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SHEET_ID = os.environ["SHEET_ID"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
TRUCKERSMP_API_BASE = "https://api.truckersmp.com/v2/event/"
creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS"])

# === AUTH GOOGLE SHEETS ===

creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

client = gspread.authorize(creds)

# === GET TODAY'S DATE ===
today_str = datetime.utcnow().strftime("%Y-%m-%d")

# === READ ALL MONTH TABS ===
sheet = client.open_by_key(SHEET_ID)
worksheets = sheet.worksheets()

event_found = False

for ws in worksheets:
    data = ws.get_all_records()
    for row in data:
        date = str(row.get("Date", "")).strip()
        link = str(row.get("Event Link", "")).strip()

        if not date or not link:
            continue

        try:
            event_date = datetime.strptime(date, "%Y-%m-%d").strftime("%Y-%m-%d")
            if event_date == today_str:
                # === GET EVENT ID FROM URL ===
                event_id = link.rstrip("/").split("/")[-1]
                response = requests.get(f"{TRUCKERSMP_API_BASE}{event_id}")
                if response.status_code == 200:
                    event = response.json().get("response", {})

                    embed = {
                        "title": event.get("name"),
                        "description": f"**Time (UTC):** {event.get('start_at')}\n"
                                       f"**Game:** {event.get('game')}\n"
                                       f"**Server:** {event.get('server', {}).get('name')}\n"
                                       f"**Departure:** {event.get('departure')}\n"
                                       f"**Arrival:** {event.get('arrival')}\n"
                                       f"**Meetup Location:** {event.get('meetup')}\n"
                                       f"**Start Location:** {event.get('start')}\n"
                                       f"**VTC:** [{event.get('vtc', {}).get('name')}]({event.get('vtc', {}).get('url')})\n"
                                       f"**Link:** [View Event]({link})",
                        "color": 5814783
                    }

                    requests.post(DISCORD_WEBHOOK, json={"embeds": [embed]})
                    print("✅ Posted to Discord.")
                    event_found = True
                    break
        except Exception as e:
            print(f"Error processing row: {e}")
    if event_found:
        break

if not event_found:
    print("❌ No event found for today.")
