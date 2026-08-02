from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import config

class GoogleSheetsManager:
    def __init__(self):
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        self.client = None
        self.sheet = None
        self._authenticate()

    def _authenticate(self):
        try:
            creds = Credentials.from_service_account_file(
                config.SERVICE_ACCOUNT_FILE, scopes=self.scopes
            )
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_key(config.SHEET_ID)
        except Exception as e:
            print(f"Error authenticating with Google Sheets: {e}")
            raise

    def _get_worksheet(self, name: str):
        try:
            return self.sheet.worksheet(name)
        except gspread.exceptions.APIError:
            self._authenticate()
            return self.sheet.worksheet(name)

    # --- User Management ---
    def get_user(self, telegram_id: int):
        ws = self._get_worksheet("Users")
        rows = ws.get_all_values()
        for row in rows[1:]:
            if len(row) > 2 and str(row[0]).strip() == str(telegram_id).strip():
                return {"Telegram_ID": row[0], "Chat_ID": row[1], "Name": row[2]}
        return None

    def register_user(self, telegram_id: int, chat_id: int, name: str):
        ws = self._get_worksheet("Users")
        ws.append_row([str(telegram_id), str(chat_id), name])

    def get_all_chat_ids(self):
        ws = self._get_worksheet("Users")
        rows = ws.get_all_values()
        return [str(row[1]).strip() for row in rows[1:] if len(row) > 1 and str(row[1]).strip()]

    # --- Standardized Date Helper ---
    def _parse_date(self, date_val):
        if not date_val:
            return None
        clean_str = str(date_val).replace('[', '').replace(']', '').replace("'", "").replace('"', "").strip().split()[0]
        for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y"):
            try:
                return datetime.strptime(clean_str, fmt).date()
            except ValueError:
                continue
        return None

    # --- Anti-Cheat Daily Lockout Verification ---
    def has_logged_today(self, worksheet_name: str, telegram_id: int) -> bool:
        """Checks if the user has ALREADY logged ANY entry in this sheet today."""
        ws = self._get_worksheet(worksheet_name)
        rows = ws.get_all_values()
        today = datetime.now(config.IST).date()

        for row in rows[1:]:
            if len(row) > 2 and str(row[0]).strip() == str(telegram_id).strip():
                row_date = self._parse_date(row[2])
                if row_date == today:
                    return True
        return False

    def log_attendance(self, telegram_id: int, name: str, activity: str) -> tuple[bool, str]:
        now = datetime.now(config.IST)
        ws = self._get_worksheet("Attendance_Log")
        ws.append_row([str(telegram_id), name, now.strftime("%d-%m-%Y"), now.strftime("%H:%M:%S"), activity])
        return True, f"✅ **{activity}**: Successfully logged!"

    def log_riyaz(self, telegram_id: int, name: str, kalaam: str) -> tuple[bool, str]:
        now = datetime.now(config.IST)
        ws = self._get_worksheet("Riyaz_Log")
        ws.append_row([str(telegram_id), name, now.strftime("%d-%m-%Y"), now.strftime("%H:%M:%S"), kalaam])
        return True, f"🎙️ Successfully logged Riyaz: **{kalaam}**!"

    # --- Progress Analytics ---
    def get_progress_counts(self, telegram_id: int) -> tuple[int, int]:
        """Returns (riyaz_distinct_days, practice_total_sessions) for the last 7 days."""
        today = datetime.now(config.IST).date()
        seven_days_ago = today - timedelta(days=7)
        
        # Riyaz: Distinct Calendar Days (Goal: 6 morning sessions/week)
        riyaz_dates = set()
        ws_riyaz = self._get_worksheet("Riyaz_Log")
        for row in ws_riyaz.get_all_values()[1:]:
            if len(row) > 2 and str(row[0]).strip() == str(telegram_id).strip():
                r_date = self._parse_date(row[2])
                if r_date and seven_days_ago <= r_date <= today:
                    riyaz_dates.add(r_date)

        # Practice: Total Sessions (Goal: 3 practices/week, can do multiple in 1 day)
        practice_count = 0
        ws_att = self._get_worksheet("Attendance_Log")
        for row in ws_att.get_all_values()[1:]:
            if len(row) > 2 and str(row[0]).strip() == str(telegram_id).strip():
                p_date = self._parse_date(row[2])
                if p_date and seven_days_ago <= p_date <= today:
                    practice_count += 1

        return len(riyaz_dates), practice_count

db = GoogleSheetsManager()