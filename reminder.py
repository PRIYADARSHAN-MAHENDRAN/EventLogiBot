import os
import json
import gspread
import requests
import pytz
from datetime import datetime, timedelta
from dateutil import parser
from oauth2client.service_account import ServiceAccountCredentials

print("⏰ Starting Event Reminder Script...")

# Setup timezone
utc = pytz.utc
ist = pytz.timezone("Asia/Kolkata")
now_ist = ist.localize(datetime.strptime("2025-06-01 18:30:00", "%Y-%m-%d %H:%M:%S"))
print(f"Current time (IST): {now_ist}")

ROLE_ID = os.environ['ROLE_ID']

# Authenticate
try:
    creds_dict = json.loads(os.environ["GOOGLE_SERVICE_ACCOUNT_KEY"])
    print("✅ Loaded GOOGLE_SERVICE_ACCOUNT_KEY")
except KeyError:
    print("❌ GOOGLE_SERVICE_ACCOUNT_KEY not found in environment variables.")
    exit(1)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

try:
    sheet = client.open_by_key(os.environ['GOOGLE_SHEET_ID'])
    print(f"✅ Connected to Google Sheet ID: {os.environ['GOOGLE_SHEET_ID']}")
except Exception as e:
    print(f"❌ Failed to open Google Sheet: {e}")
    exit(1)

month_year = now_ist.strftime("%b-%Y").upper()
print(f"🔍 Looking for sheet: {month_year}")

try:
    worksheet = sheet.worksheet(month_year)
    print(f"✅ Found worksheet: {month_year}")
except:
    print(f"❌ Worksheet {month_year} not found")
    exit(1)

rows = worksheet.get_all_records()
today_str = now_ist.strftime('%Y-%m-%d')
print(f"📅 Filtering events for today: {today_str}")

def format_date(dt_str):
    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%A, %d %B %Y")

def utc_to_ist_ampm(utc_str):
    utc_dt = utc.localize(datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S"))
    return utc_dt.astimezone(ist).strftime("%I:%M %p")

def send_discord_reminder(data, event_link, time_remaining):
    time_label = f"\u23F0 {time_remaining} minutes!! to " if time_remaining else "🚨 Event Started | "
    embed = {
        "image": {"url": data.get("banner")},
        "title": f"{time_label}{data.get('name', 'TruckersMP Event')}",
        "url": event_link,
        "color": 16776960,
        "fields": [
            {
                "name": "",
                "value": (
                    f"**\ud83d\udee0 VTC** : {data.get('vtc', {}).get('name', 'Unknown VTC')}\n\n"
                    f"**\ud83d\uddd5 Date** : {format_date(data['start_at'])}\n\n"
                    f"**\u23f0 Meetup Time** : {data['meetup_at'].split(' ')[1][:5]} UTC "
                    f"({utc_to_ist_ampm(data['meetup_at'])} IST)\n\n"
                    f"**\ud83d\ude80 Departure Time** : {data['start_at'].split(' ')[1][:5]} UTC "
                    f"({utc_to_ist_ampm(data['start_at'])} IST)\n\n"
                    f"**\ud83d\udda5 Server** : {data.get('server', {}).get('name', 'Unknown Server')}\n\n"
                    f"**\ud83d\ude8f Departure** : {data.get('departure', {}).get('city', 'Unknown')} "
                    f"({data.get('departure', {}).get('location', 'Unknown')})\n\n"
                    f"**\ud83c\udfaf Arrival** : {data.get('arrive', {}).get('city', 'Unknown')} "
                    f"({data.get('arrive', {}).get('location', 'Unknown')})\n\n"
                ),
                "inline": False
            }
        ],
        "footer": {"text": "by TNL | PRIYADARSHAN"},
    }

    payload = {
        "content": f"||<@&{ROLE_ID}>||",
        "embeds": [embed],
    }

    r = requests.post(os.environ['DISCORD_WEBHOOK_URL'], json=payload)
    if r.status_code == 204:
        print(f"✅ Reminder sent successfully to Discord.")
    else:
        print(f"❌ Failed to send to Discord: {r.status_code}, {r.text}")

for row in rows:
    event_link = row.get('TRUCKERSMP \nEVENT LINK ')
    date_str = row.get('DATE')

    if not event_link or not date_str:
        continue

    try:
        safe_date = parser.parse(date_str.replace('.', ':')).astimezone(ist).date()
        if safe_date.strftime('%Y-%m-%d') != today_str:
            continue
    except Exception as e:
        print(f"❌ Invalid date format: {date_str} | {e}")
        continue

    try:
        event_id = event_link.split("/")[-1].split("-")[0]
        data = requests.get(f"https://api.truckersmp.com/v2/events/{event_id}").json()['response']
        event_time = datetime.strptime(data['start_at'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=utc).astimezone(ist)
    except Exception as e:
        print(f"❌ Failed to fetch event details: {e}")
        continue

    for offset in [60, 30, 0]:
        reminder_time = event_time - timedelta(minutes=offset)
        window_start = reminder_time
        window_end = reminder_time + timedelta(minutes=29, seconds=59)

        if window_start <= now_ist <= window_end:
            print(f"✅ Matched reminder at T-{offset} minutes")
            time_remaining = int((event_time - now_ist).total_seconds() // 60)
            send_discord_reminder(data, event_link, time_remaining)
            break
    else:
        print("⏩ No reminder time matched.")
