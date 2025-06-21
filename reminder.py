import os
import json
import gspread
import requests
import pytz
from datetime import datetime, timedelta
from dateutil import parser
from oauth2client.service_account import ServiceAccountCredentials

print("⏰ Starting Event Reminder Script...")

utc = pytz.utc
ist = pytz.timezone("Asia/Kolkata")
now_utc = datetime.utcnow().replace(tzinfo=utc)
now_ist = datetime.now(ist)

print(f"Current time (UTC): {now_utc}")
print(f"Current time (IST): {now_ist}")

ROLE_ID = os.environ["ROLE_ID"]

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
    sheet = client.open_by_key(os.environ["GOOGLE_SHEET_ID"])
    print(f"✅ Connected to Google Sheet ID: {os.environ['GOOGLE_SHEET_ID']}")
except Exception as e:
    print(f"❌ Failed to open Google Sheet: {e}")
    exit(1)

today = datetime.utcnow()
month_name = today.strftime("%b").upper()
year = today.strftime("%Y")
sheet_name = f"{month_name}-{year}"
print(f"🔍 Looking for sheet: {sheet_name}")

try:
    worksheet = sheet.worksheet(sheet_name)
    print(f"✅ Found worksheet: {sheet_name}")
except:
    print(f"❌ Worksheet {sheet_name} not found")
    exit(1)

rows = worksheet.get_all_records()
print(f"📄 Found {len(rows)} rows")

today_str = now_ist.strftime('%Y-%m-%d')
print(f"📅 Filtering events for today: {today_str}")

def format_date(utc_date_str):
    dt = datetime.strptime(utc_date_str, "%Y-%m-%d %H:%M:%S")
    return dt.strftime("%A, %d %B %Y")

def utc_to_ist_ampm(utc_datetime_str):
    utc = pytz.utc
    ist = pytz.timezone("Asia/Kolkata")
    utc_time = utc.localize(datetime.strptime(utc_datetime_str, "%Y-%m-%d %H:%M:%S"))
    ist_time = utc_time.astimezone(ist)
    return ist_time.strftime("%I:%M %p")

for row in rows:
    event_link = row.get("TRUCKERSMP \nEVENT LINK ")
    date_str = row.get("DATE")

    if not event_link or not date_str:
        print("⚠️ Skipping row due to missing event link or date.")
        continue

    try:
        safe_date_str = date_str.replace(".", ":")
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
        data = res.json()["response"]
        event_time = datetime.strptime(data["start_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=utc).astimezone(ist)
    except Exception as e:
        print(f"❌ Error fetching event timing from API: {e}")
        continue

    for window_minutes in [60, 30, 0]:
        reminder_time = event_time - timedelta(minutes=window_minutes)
        if reminder_time <= now_ist <= reminder_time + timedelta(minutes=29, seconds=59):
            print(f"✅ Matched {window_minutes}-minute reminder window.")
            try:
                time_remaining_minutes = int((event_time - now_ist).total_seconds() // 60)
            except:
                time_remaining_minutes = None

            if window_minutes == 0:
                time_label = "🚨 Event Started: "
            else:
                time_label = f"⏰ {time_remaining_minutes} minutes!! to "

            thumbnail_url = data.get("banner")
            embed = {
                "image": {"url": thumbnail_url},
                "title": f"{time_label}{data.get('name', 'TruckersMP Event')}",
                "url": event_link,
                "color": 16776960,
                "fields": [
                    {
                        "name": "",
                        "value": (
                            f"**🛠 VTC** : {data.get('vtc', {}).get('name', 'Unknown VTC')}\n\n"
                            f"**📅 Date** : {format_date(data.get('start_at', ''))}\n\n"
                            f"**⏰ Meetup Time** : {data.get('meetup_at', '').split(' ')[1][:5]} UTC "
                            f"({utc_to_ist_ampm(data.get('meetup_at', ''))} IST)\n\n"
                            f"**🚀 Departure Time** : {data.get('start_at', '').split(' ')[1][:5]} UTC "
                            f"({utc_to_ist_ampm(data.get('start_at', ''))} IST)\n\n"
                            f"**🖥 Server** : {data.get('server', {}).get('name', 'Unknown Server')}\n\n"
                            f"**🚏 Departure** : {data.get('departure', {}).get('city', 'Unknown')} "
                            f"({data.get('departure', {}).get('location', 'Unknown')})\n\n"
                            f"**🎯 Arrival** : {data.get('arrive', {}).get('city', 'Unknown')} "
                            f"({data.get('arrive', {}).get('location', 'Unknown')})\n\n"
                            f"**💬 Thank You Message:**\n\n"
                            f"💛 Thank you, {event_data.get('vtc', {}).get('name', 'your VTC')}. "
                            f"For inviting us to your {event_data.get('name', 'event')}. "
                            f"We had a great time and enjoyed it a lot! - TAMILNADU LOGISTICS 💛"
                        ),
                        "inline": False,
                    }
                ],
                "footer": {"text": "by TNL | PRIYADARSHAN"},
            }

            payload = {
                "content": f"||<@&{ROLE_ID}>||",
                "embeds": [embed],
            }

            response = requests.post(os.environ["DISCORD_WEBHOOK_URL"], json=payload)
            if response.status_code == 204:
                print(f"✅ {window_minutes}-minute reminder sent successfully to Discord.")
            else:
                print(f"❌ Failed to send reminder: {response.status_code}, {response.text}")
            break
        else:
            print(f"⏩ Skipping {window_minutes}-minute window.")
