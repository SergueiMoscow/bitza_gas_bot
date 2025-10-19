import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ALLOWED_USER_IDS = [int(x.strip()) for x in os.getenv('ALLOWED_USER_IDS', '').split(',') if x.strip()]
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0))