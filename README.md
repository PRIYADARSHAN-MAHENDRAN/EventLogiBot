
#  Daily Discord Notifier

This bot automatically fetches **TruckersMP event details** scheduled for the **current day** from a **Google Sheet**, retrieves event data from the **TruckersMP API**, and sends a rich embed message to a **Discord webhook**, tagging a specific role.

> 🛠 Built with Python + GSpread + TruckersMP API + Google Sheets API + Discord Webhook

---

## 📌 Features

- ✅ Reads today's date and checks all monthly-named sheets (e.g., "April 2025").
- ✅ Supports flexible date formats in the sheet.
- ✅ Extracts event link, slot number, and slot link from the sheet.
- ✅ Verifies the event is public using the TruckersMP API.
- ✅ Posts a styled embed to Discord with event info:
  - Event name, time (UTC/IST), date, VTC, server, departure, arrival, required DLCs, slot number, and event/map/slot links.
- ✅ Pings a role without tagging everyone.

---

## 📁 Google Sheet Structure

Each sheet (named as month and year, e.g., `April 2025`) should follow this format:



| A     | B         | ... | J           | K          | L                       |
|-------|-----------|-----|-------------|------------|--------------------------|
| Date  | ...       | ... | Slot Number | Slot Link  | TruckersMP Event Link    |

- **Column B:** Date (supports many formats, like `Wed, Apr 2, 2025 22.30`)
- **Column J:** Slot Number (optional)
- **Column K:** Slot Image/Link (optional)
- **Column L:** TruckersMP Event Link (required)

---

## ⚙️ Setup

### 1. Clone this repo

    git clone https://github.com/your-username/truckersmp-daily-discord-bot.git cd truckersmp-daily-discord-bot`


### 2. Install dependencies

    pip install -r requirements.txt

#### Required packages:
 - gspread
  - oauth2client
  - requests
  - pytz

### 3. Set up Google API credentials

 1. Go to Google Cloud Console
 2. Enable the Google Sheets API and Google Drive API
 3. Create a Service Account and download the JSON key
 4. Rename it to truckersmp-events-credentials.json (or match it in
    code)
   5. Share your Google Sheet with the service account email


### 4. Configure the bot

Edit these values in main.py:

    ROLE_ID = "YOUR_DISCORD_ROLE_ID"
    DISCORD_WEBHOOK = "YOUR_DISCORD_WEBHOOK_URL"
    SHEET_ID = "YOUR_GOOGLE_SHEET_ID"

## 🕒 Usage

Run the script manually:

    python main.py

Or automate it using GitHub Actions or cron jobs to run every day at midnight.

🧾 License
MIT License

