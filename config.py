import os
from dotenv import load_dotenv

# Загружаем переменные из .env для локальной разработки
load_dotenv()


class Config:
    # Здесь твои старые переменные (BOT_TOKEN, базы и т.д.)
    BOT_TOKEN: str = ...
    # ...
    
    # Добавь эту строку в любое место внутри класса:
    SESSION_HOURS: int = 8
    def __init__(self):
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
        self.REDIS_URL = os.getenv("REDIS_URL")
        self.DATABASE_URL = os.getenv("DATABASE_URL")
        self.DB_DRIVER = os.getenv("DB_DRIVER", "postgres")
        self.CATEGORIES = {
            "male": [
                "Одежда",
                "Обувь",
                "Аксессуары",
                "Сумки",
            ],
            "female": [
                "Одежда",
                "Обувь",
                "Аксессуары",
                "Сумки",
            ]
        }


# Объект конфигурации
config = Config()

# Отдельные переменные для импортов
BOT_TOKEN = config.BOT_TOKEN
REDIS_URL = config.REDIS_URL
DATABASE_URL = config.DATABASE_URL
DB_DRIVER = config.DB_DRIVER
CATEGORIES = config.CATEGORIES

# Проверка токена
if not BOT_TOKEN:
    raise ValueError("ОШИБКА: Переменная BOT_TOKEN не найдена в окружении!")
