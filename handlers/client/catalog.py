import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

# Экспортируем переменные напрямую для main.py
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "8707683137:AAHpCNdLbuGzNADSClM2y5J1QIzwArkAJlw")
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")


@dataclass
class Config:
    BOT_TOKEN: str = BOT_TOKEN
    REDIS_URL: str = REDIS_URL

    DB_DRIVER: str = os.getenv("DB_DRIVER", "sqlite")
    DB_PATH: str = os.getenv("DB_PATH", "themoda.db")          # для sqlite
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")          # для postgres

    BOOTSTRAP_MANAGER_LOGIN: str = os.getenv("BOOTSTRAP_MANAGER_LOGIN", "manager")
    BOOTSTRAP_MANAGER_PASSWORD: str = os.getenv("BOOTSTRAP_MANAGER_PASSWORD", "changeme")

    SESSION_HOURS: int = int(os.getenv("SESSION_HOURS", "8"))

    REPORT_CHANNEL_ID: str = os.getenv("REPORT_CHANNEL_ID", "")  # канал отчётов склада

    @property
    def db_dsn_or_path(self) -> str:
        return self.DATABASE_URL if self.DB_DRIVER == "postgres" else self.DB_PATH


config = Config()

CATEGORIES = {
    "male": {
        "clothes":     "👔 Мужская одежда",
        "shoes":       "👟 Мужская обувь",
        "accessories": "⌚️ Мужские аксессуары",
    },
    "female": {
        "clothes":     "👗 Женская одежда",
        "shoes":       "👠 Женская обувь",
        "accessories": "💍 Женские аксессуары",
        "bags":        "👜 Женские сумки",
    },
}
