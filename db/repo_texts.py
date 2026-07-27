from db.pool import DB

DEFAULT_TEXTS = {
    "text_welcome_ru": "👋 <b>TheModa</b> рада видеть вас!\n\nЗдесь — стильные вещи, приятные цены и забота о каждом заказе. Начнём? 🌐 Выберите язык:",
    "text_welcome_en": "👋 <b>TheModa</b> is happy to see you!\n\nStylish finds, great prices, and care with every order. Ready? 🌐 Choose your language:",
    "text_welcome_uk": "👋 <b>TheModa</b> рада вас бачити!\n\nТут — стильні речі, приємні ціни та турбота про кожне замовлення. Починаємо? 🌐 Виберіть мову:",
    "text_welcome_es": "👋 ¡<b>TheModa</b> se alegra de verte!\n\nPrendas con estilo, precios increíbles y cuidado en cada pedido. ¿Empezamos? 🌐 Elige tu idioma:",
    "text_opening_ru": "🟡 ═══════ Новинки уже здесь ═══════ 🟡\n   Листайте разделы и находите то, что влюбит с первого взгляда 👇",
    "text_opening_en": "🟡 ═══════ Fresh Arrivals ═══════ 🟡\n   Browse the sections and find something to fall in love with 👇",
    "text_opening_uk": "🟡 ═══════ Новинки вже тут ═══════ 🟡\n   Гортайте розділи та знаходьте те, що закохає з першого погляду 👇",
    "text_opening_es": "🟡 ═══════ Nuevas llegadas ═══════ 🟡\n   Explora las secciones y encuentra algo que te enamore 👇",
    "text_support_ru": "💬 <b>Поддержка TheModa</b>\n\nМы рядом и готовы помочь! Опишите ваш вопрос — ответим как можно скорее:",
    "text_support_en": "💬 <b>TheModa Support</b>\n\nWe're here to help! Describe your question and we'll get back to you shortly:",
    "text_support_uk": "💬 <b>Підтримка TheModa</b>\n\nМи поруч і готові допомогти! Опишіть ваше питання — відповімо якнайшвидше:",
    "text_support_es": "💬 <b>Soporte de TheModa</b>\n\n¡Estamos aquí para ayudarte! Cuéntanos tu duda y te responderemos enseguida:",
}


class TextsRepo:
    def __init__(self, db: DB):
        self.db = db

    async def get(self, key: str) -> str:
        val = await self.db.fetchval("SELECT value FROM bot_texts WHERE key=$1", key)
        return val if val is not None else DEFAULT_TEXTS.get(key, key)

    async def set(self, key: str, value: str):
        await self.db.execute(
            """INSERT INTO bot_texts (key, value) VALUES ($1,$2)
               ON CONFLICT (key) DO UPDATE SET value=$2""",
            key, value,
        )

    async def reset(self, key: str):
        await self.db.execute("DELETE FROM bot_texts WHERE key=$1", key)


class SettingsRepo:
    def __init__(self, db: DB):
        self.db = db

    async def get(self, key: str) -> str | None:
        return await self.db.fetchval("SELECT value FROM bot_settings WHERE key=$1", key)

    async def set(self, key: str, value: str):
        await self.db.execute(
            """INSERT INTO bot_settings (key, value) VALUES ($1,$2)
               ON CONFLICT (key) DO UPDATE SET value=$2""",
            key, value,
        )