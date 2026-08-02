import os
import sys
import pytz
from dotenv import load_dotenv

# Load the .env file automatically
load_dotenv()

# Timezone Configuration
IST = pytz.timezone('Asia/Kolkata')

# Environment Variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
SHEET_ID = os.getenv('SHEET_ID')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE', 'service_account.json')

# Validate required configurations
def validate_config():
    missing = []
    if not BOT_TOKEN:
        missing.append('BOT_TOKEN')
    if not SHEET_ID:
        missing.append('SHEET_ID')
    if not ADMIN_CHAT_ID:
        missing.append('ADMIN_CHAT_ID')
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        missing.append(f"Service account file not found at: {SERVICE_ACCOUNT_FILE}")

    if missing:
        print(f"CRITICAL ERROR: Missing configuration for: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

validate_config()