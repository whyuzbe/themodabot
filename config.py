import os
from dotenv import load_dotenv

# Загружаем переменные из .env для локальной разработки
load_dotenv()


class Config:
    def __init__(self):
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        self.REDIS_URL = os.getenv("REDIS_URL")
        self.DATABASE_URL = os.getenv("DATABASE_URL")
        self.DB_DRIVER = os.getenv("DB_DRIVER", "postgres")
        self.CATEGORIES = [
            "Одежда",
            "Обувь",
            "Аксессуары",
        ]


# Объект конфигурации (для от файла auth.py и других)
config = Config()

# Отдельные переменные (для импортов в main.py и admin.py)
BOT_TOKEN = config.BOT_TOKEN
REDIS_URL = config.REDIS_URL
DATABASE_URL = config.DATABASE_URL
DB_DRIVER = config.DB_DRIVER
CATEGORIES = config.CATEGORIES

# Проверка токена
if not BOT_TOKEN:
    raise ValueError("ОШИБКА: Переменная BOT_TOKEN не найдена в окружении!")
