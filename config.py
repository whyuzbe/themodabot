import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SESSION_HOURS: int = int(os.getenv("SESSION_HOURS", "8"))

    def __init__(self):
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")

        self.REDIS_URL = os.getenv("REDIS_URL")

        self.DATABASE_URL = os.getenv("DATABASE_URL")

        self.DB_DRIVER = os.getenv("DB_DRIVER", "postgres")

        # Bootstrap manager
        self.BOOTSTRAP_MANAGER_LOGIN = os.getenv(
            "BOOTSTRAP_MANAGER_LOGIN",
            "manager",
        )

        self.BOOTSTRAP_MANAGER_PASSWORD = os.getenv(
            "BOOTSTRAP_MANAGER_PASSWORD",
            "changeme123",
        )

        # Авторизация
        self.MAX_LOGIN_ATTEMPTS = int(
            os.getenv("MAX_LOGIN_ATTEMPTS", "5")
        )

        self.LOGIN_BLOCK_MINUTES = int(
            os.getenv("LOGIN_BLOCK_MINUTES", "15")
        )

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
            ],
        }


config = Config()

BOT_TOKEN = config.BOT_TOKEN
REDIS_URL = config.REDIS_URL
DATABASE_URL = config.DATABASE_URL
DB_DRIVER = config.DB_DRIVER
CATEGORIES = config.CATEGORIES

if not BOT_TOKEN:
    raise ValueError(
        "ОШИБКА: Переменная BOT_TOKEN не найдена в окружении!"
    )
