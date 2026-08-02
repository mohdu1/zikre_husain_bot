# Zikre Husain Tracking Bot 🌙

A production-ready Telegram bot built to automate daily check-ins, track ensemble practice consistency, and manage voice note submissions. Backed by a live Google Sheets database, the bot features a smart guided sequence, dual 7-day progress bars, and daily automated reminders.

## ✨ Key Features

* **Smart Check-In Sequence:** A frictionless, guided `/mark` flow that walks users through logging their morning Riyaz, specific Kalaam practice, and group attendance.
* **Dual Progress Tracking:** Calculates rolling 7-day activity directly from the database to track Riyaz (Goal: 6 sessions/week) and Group Practice (Goal: 3 sessions/week).
* **Anti-Cheat Lockout:** Prevents duplicate entries and stat-padding by blocking multiple check-ins on the same calendar day.
* **Voice Note Forwarding:** Allows members to seamlessly record and submit practice audio, instantly forwarding it to the Admin.
* **Automated Push Notifications:** Utilizes `APScheduler` to broadcast a daily 11:00 PM IST reminder with an embedded check-in command to all registered members.
* **Serverless Database:** Integrates directly with Google Sheets via the `gspread` API, eliminating the need for complex SQL hosting.

## 🛠️ Tech Stack

* **Language:** Python 3.10+
* **Telegram API:** `python-telegram-bot` (v20+ Async API)
* **Database Integration:** `gspread`, `google-auth`
* **Scheduling & Timezones:** `PTB JobQueue`, `pytz` (Strictly set to `Asia/Kolkata`)

## 📋 Database Schema

The bot relies on a Google Spreadsheet with exactly three worksheets (Row 1 headers must match exactly):

1. **`Users`**: `Telegram_ID` | `Chat_ID` | `Name`
2. **`Riyaz_Log`**: `ID` | `Name` | `Date` | `Time` | `Kalaam_Focused`
3. **`Attendance_Log`**: `ID` | `Name` | `Date` | `Time` | `Activity`

## 🚀 Setup & Installation

**1. Clone the repository and set up a virtual environment:**

```bash
python -m venv .venv
# On Windows:
.\.venv\Scripts\Activate.ps1
# On macOS/Linux:
source .venv/bin/activate

```

**2. Install dependencies:**

```bash
pip install -r requirements.txt

```

**3. Configure Environment Variables:**
Create a `.env` file in the root directory and add your credentials:

```env
BOT_TOKEN="your_telegram_bot_token"
SHEET_ID="your_google_sheet_id"
ADMIN_CHAT_ID="your_telegram_user_id"
SERVICE_ACCOUNT_FILE="service_account.json"

```

**4. Add Service Account Key:**
Place your Google Cloud `service_account.json` file in the root directory and ensure the client email is granted **Editor** access to your Google Sheet.

**5. Run the Bot:**

```bash
python bot.py

```

## 📱 Bot Commands

* `/start` - Registers a new user and adds their details to the database.
* `/mark` - Triggers the master daily check-in sequence.
* `/riyaz` - Alternative shortcut to trigger the master daily check-in sequence.
