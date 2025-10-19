import os
from dotenv import load_dotenv

try:
    load_dotenv()
except:
    pass  # Если .env нет, используем переменные окружения из Docker

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ALLOWED_USER_IDS = [int(x.strip()) for x in os.getenv('ALLOWED_USER_IDS', '').split(',') if x.strip()]
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0))