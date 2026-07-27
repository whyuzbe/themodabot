import os
from dotenv import load_dotenv

# Загружаем переменные из .env для локальной разработки
load_dotenv()

# Основные переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
REDIS_URL = os.getenv("REDIS_URL")
DATABASE_URL = os.getenv("DATABASE_URL")
DB_DRIVER = os.getenv("DB_DRIVER", "postgres")

# Категории товаров (значение по умолчанию, если не задано)
CATEGORIES = [
    "Одежда",
    "Обувь",
    "Аксессуары",
]

# Проверка токена
if not BOT_TOKEN:
    raise ValueError("ОШИБКА: Переменная BOT_TOKEN не найдена в окружении!")
