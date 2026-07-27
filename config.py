import os
from dotenv import load_dotenv

# Загружаем переменные из .env для локальной разработки
load_dotenv()

# Чтение переменных из окружения Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")
REDIS_URL = os.getenv("REDIS_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
DB_DRIVER = os.getenv("DB_DRIVER", "postgres")
