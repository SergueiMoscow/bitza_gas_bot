import os
from dotenv import load_dotenv

try:
    load_dotenv()
except:
    pass  # Если .env нет, используем переменные окружения из Docker

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ALLOWED_USER_IDS = [int(x.strip()) for x in os.getenv('ALLOWED_USER_IDS', '').split(',') if x.strip()]
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0))
WEB_APP_DOMAIN = os.getenv('WEB_APP_DOMAIN', 'https://localhost:5000')
DATABASE_URL = os.getenv('DATABASE_URL')

if ADMIN_USER_ID and ADMIN_USER_ID not in ALLOWED_USER_IDS:
    ALLOWED_USER_IDS.append(ADMIN_USER_ID)