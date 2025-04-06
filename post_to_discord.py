import requests
import os

# Config
VTC_ID = os.environ.get('VTC_ID')  # Set in GitHub Secrets
WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK')

# API request
url = f"https://api.truckersmp.com/v2/vtc/{VTC_ID}/events/attending"
response = requests.get(url)
data = response.json()

# Handle no events
if not data["response"]:
    message = {
        "content": f"No upcoming events found for VTC ID {VTC_ID}."
    }
    requests.post(WEBHOOK_URL, json=message)
    exit()

# Build message
for event in data["response"][:3]:  # Limit to 3
    embed = {
        "title": event["name"],
        "url": f"https://truckersmp.com/events/{event['id']}",
        "description": f"**Game:** {event['game']}\n**Server:** {event['server']}\n**Start:** {event['start_at']} UTC",
        "color": 7506394  # Blue-ish
    }

    payload = {
        "username": "TruckersMP Events Bot",
        "embeds": [embed]
    }

    requests.post(WEBHOOK_URL, json=payload)
