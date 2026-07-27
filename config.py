import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

    # Ссылка для быстрой FSM-памяти Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # DB_DRIVER: "sqlite" (по умолчанию, для лёгкого локального теста — просто файл)
    #            "postgres" (для продакшена, например Railway)
    DB_DRIVER: str = os.getenv("DB_DRIVER", "sqlite")
    DB_PATH: str = os.getenv("DB_PATH", "themoda.db")          # для sqlite
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")          # для postgres

    # Стартовый менеджер (создаётся при первом запуске, если таблица staff_accounts пуста)
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