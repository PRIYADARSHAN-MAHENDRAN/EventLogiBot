import os
import gspread
import requests
from datetime import datetime, timedelta
from dateutil import parser
from oauth2client.service_account import ServiceAccountCredentials
import pytz

# Setup timezone
utc = pytz.utc
ist = pytz.timezone("Asia/Kolkata")
now_utc = datetime.utcnow().replace(tzinfo=utc)

# Authenticate
creds_dict = eval(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(os.environ['GOOGLE_SHEET_ID'])

# Determine month sheet
month_name = now_utc.strftime('%B %Y')
try:
    worksheet = sheet.worksheet(month_name)
except:
    print(f"Worksheet {month_name} not found")
    exit()

rows = worksheet.get_all_records()

for row in rows:
    event_link = row.get('Event Link') or row.get('event link') or row.get('Link')
    date_str = row.get('Date') or row.get('date')
    if not event_link or not date_str:
        continue

    try:
        event_time = parser.parse(date_str)
        event_time = event_time.replace(tzinfo=ist)
        reminder_time = event_time - timedelta(hours=1)
    except:
        continue

    if now_utc.astimezone(ist).strftime('%Y-%m-%d %H:%M') == reminder_time.strftime('%Y-%m-%d %H:%M'):
        try:
            event_id = event_link.split("/")[-1].split("-")[0]
            api_url = f"https://api.truckersmp.com/v2/events/{event_id}"
            res = requests.get(api_url)
            if res.status_code != 200:
                continue
            data = res.json()['response']

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
            requests.post(os.environ['DISCORD_WEBHOOK_REMINDER1'], json=embed)
        except Exception as e:
            print(f"Failed to send reminder: {e}")
