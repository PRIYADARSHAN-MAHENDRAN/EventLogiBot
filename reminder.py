import os
import json
import gspread
import requests
from datetime import datetime, timedelta
from dateutil import parser
from oauth2client.service_account import ServiceAccountCredentials
import pytz

print("⏰ Starting Event Reminder Script...")

# Setup timezone
utc = pytz.utc
ist = pytz.timezone("Asia/Kolkata")
now_utc = datetime.utcnow().replace(tzinfo=utc)
now_ist = now_utc.astimezone(ist)
print(f"Current time (UTC): {now_utc}")
print(f"Current time (IST): {now_ist}")

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

# Get today's month and year
today = datetime.utcnow()
month_name = today.strftime("%b").upper()  # "APR", "MAY", etc.
year = today.strftime("%Y")

sheet_name = f"{month_name}-{year}"  # Result: "APR-2025"
print(f"🔍 Looking for sheet: {sheet_name}")

try:
    worksheet = sheet.worksheet(sheet_name)
    print(f"✅ Found worksheet: {sheet_name}")
except:
    print(f"❌ Worksheet {sheet_name} not found")
    exit(1)

rows = worksheet.get_all_records()
print(f"📄 Found {len(rows)} rows")

# Loop through events
today_str = now_ist.strftime('%Y-%m-%d')
print(f"📅 Filtering events for today: {today_str}")

for row in rows:
    event_link = row.get('TRUCKERSMP \nEVENT LINK ') 
    date_str = row.get('DATE')

    if not event_link or not date_str:
        print("⚠️ Skipping row due to missing event link or date.")
        continue

    try:
        safe_date_str = date_str.replace('.', ':')
        sheet_date = parser.parse(safe_date_str).astimezone(ist).date()
        if sheet_date.strftime('%Y-%m-%d') != today_str:
            continue
    except Exception as e:
        print(f"❌ Failed to parse sheet date: {date_str} | Error: {e}")
        continue

    try:
        event_id = event_link.split("/")[-1].split("-")[0]
        api_url = f"https://api.truckersmp.com/v2/events/{event_id}"
        res = requests.get(api_url)
        if res.status_code != 200:
            print(f"❌ Failed to fetch event API: {res.status_code}")
            continue
        data = res.json()['response']
        event_time = datetime.strptime(data['start_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=utc).astimezone(ist)
        # reminder_time = event_time - timedelta(hours=1)
        reminder_1h = event_time - timedelta(hours=7)
        reminder_30m = event_time - timedelta(minutes=30)

        print(f"🕐 Event: {data['name']} | Event time: {event_time.strftime('%Y-%m-%d %H:%M:%S')} IST | Reminder time for 1hr: {reminder_1h.strftime('%Y-%m-%d %H:%M:%S')} IST | Reminder time for 30min: {reminder_30m.strftime('%Y-%m-%d %H:%M:%S')} IST | Current time: {now_ist.strftime('%Y-%m-%d %H:%M:%S')} IST")
    except Exception as e:
        print(f"❌ Error fetching event timing from API: {e}")
        continue


    reminder_1h = event_time - timedelta(hours=7)
    reminder_30m = event_time - timedelta(minutes=30)

    time_diff_1h = abs((now_ist - reminder_1h).total_seconds())
    time_diff_30m = abs((now_ist - reminder_30m).total_seconds())

    if time_diff_1h <= 300:
        reminder_label = "⏰ Reminder: This event starts in **1 hour!**"
        print("✅ 1-Hour Reminder matched.")

        try:
            
            embed = {
                "content": "\u23f0 Reminder: This event starts in **1 hour!**",
                "embeds": [
                    {
                        "title": data['name'],
                        "url": event_link,
                        "description": data['description'].replace('\n', ' ')[:400],
                        "fields": [
                            {
                                "name": "\u23f0 Meetup",
                                "value": f"{data['meetup_at'][11:16]} UTC ({datetime.strptime(data['meetup_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=utc).astimezone(ist).strftime('%I:%M %p')} IST)"
                            },
                            {
                                "name": "\ud83d\ude80 Start",
                                "value": f"{data['start_at'][11:16]} UTC ({datetime.strptime(data['start_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=utc).astimezone(ist).strftime('%I:%M %p')} IST)"
                            },
                            {"name": "Game", "value": data['game'], "inline": True},
                            {"name": "Server", "value": data['server']['name'], "inline": True},
                            {"name": "From", "value": data['departure'], "inline": True},
                            {"name": "To", "value": data['arrival'], "inline": True},
                        ],
                        "image": {"url": data['banner']} if data.get('banner') else None
                    }
                ]
            }

            response = requests.post(os.environ['DISCORD_WEBHOOK_URL'], json=embed)
            if response.status_code == 204:
                print("✅ Reminder sent successfully to Discord.")
            else:
                print(f"❌ Failed to send to Discord: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"❌ Failed to send reminder: {e}")
    

    elif time_diff_30m <= 300:
        reminder_label = "⏰ Reminder: This event starts in **30 minutes!**"
        print("✅ 30-Minute Reminder matched.")

        try:
            
            embed = {
                "content": "\u23f0 Reminder: This event starts in **30 minutes!**",
                "embeds": [
                    {
                        "title": data['name'],
                        "url": event_link,
                        "description": data['description'].replace('\n', ' ')[:400],
                        "fields": [
                            {
                                "name": "\u23f0 Meetup",
                                "value": f"{data['meetup_at'][11:16]} UTC ({datetime.strptime(data['meetup_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=utc).astimezone(ist).strftime('%I:%M %p')} IST)"
                            },
                            {
                                "name": "\ud83d\ude80 Start",
                                "value": f"{data['start_at'][11:16]} UTC ({datetime.strptime(data['start_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=utc).astimezone(ist).strftime('%I:%M %p')} IST)"
                            },
                            {"name": "Game", "value": data['game'], "inline": True},
                            {"name": "Server", "value": data['server']['name'], "inline": True},
                            {"name": "From", "value": data['departure'], "inline": True},
                            {"name": "To", "value": data['arrival'], "inline": True},
                        ],
                        "image": {"url": data['banner']} if data.get('banner') else None
                    }
                ]
            }

            response = requests.post(os.environ['DISCORD_WEBHOOK_URL'], json=embed)
            if response.status_code == 204:
                print("✅ Reminder sent successfully to Discord.")
            else:
                print(f"❌ Failed to send to Discord: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"❌ Failed to send reminder: {e}")

    else:
        print("⏩ Not the time yet for reminder.")
        continue
