from redis.asyncio import Redis
from db.pool import DB

DEFAULT_TEXTS = {
    "text_welcome_ru": "👋 <b>TheModa</b> рада видеть вас!\n\nЗдесь — стильные вещи, приятные цены и забота о каждом заказе. Начнём? 🌐 Выберите язык:",
    "text_welcome_en": "👋 <b>TheModa</b> is happy to see you!\n\nStylish finds, great prices, and care with every order. Ready? 🌐 Choose your language:",
    "text_welcome_uk": "👋 <b>TheModa</b> рада вас бачити!\n\nТут — стильні речі, приємні ціни та турбота про кожне замовлення. Починаємо? 🌐 Виберіть мову:",
    "text_welcome_es": "👋 ¡<b>TheModa</b> se alegra de verte!\n\nPrendas con estilo, precios increíbles y cuidado en cada pedido. ¿Empezamos? 🌐 Elige tu idioma:",

    # Обновлённые продающие приветствия каталога
    "text_opening_ru": "⚡️ <b>THE MODA // SECRET DROP</b> ⚡️\n\n✨ <i>Твой гардероб заслуживает большего, чем просто базовая одежда.</i>\n\nМы собрали главный сок этого сезона: редкие релизы, топ-качество и позиции, за которыми охотятся стилисты.\n\n🏷 <b>Размеры разбирают за минуты.</b> Выбирай категорию и забирай своё 👇",
    "text_opening_en": "⚡️ <b>THE MODA // SECRET DROP</b> ⚡️\n\n✨ <i>Your wardrobe deserves way more than just basic outfits.</i>\n\nHandpicked pieces for this season: rare items, premium quality, and styles everyone is hunting for.\n\n🏷 <b>Sizes sell out in minutes.</b> Pick a category and secure yours now 👇",
    "text_opening_uk": "⚡️ <b>THE MODA // SECRET DROP</b> ⚡️\n\n✨ <i>Твій гардероб заслуговує на більше, ніж просто базовий одяг.</i>\n\nЗібрали головний сік цього сезону: рідкісні релізи, топ-якість та позиції, за якими полюють стилісти.\n\n🏷 <b>Розміри розлітаються за хвилини.</b> Обирай категорію та забирай своє 👇",
    "text_opening_es": "⚡️ <b>THE MODA // SECRET DROP</b> ⚡️\n\n✨ <i>Tu armario merece mucho más que ropa básica.</i>\n\nHemos reunido lo mejor de la temporada: piezas exclusivas, máxima calidad y los outfits más buscados.\n\n🏷 <b>Las tallas vuelan en minutos.</b> Elige tu categoría y asegura el tuyo 👇",

    "text_support_ru": "💬 <b>Поддержка TheModa</b>\n\nМы рядом и готовы помочь! Опишите ваш вопрос — ответим как можно скорее:",
    "text_support_en": "💬 <b>TheModa Support</b>\n\nWe're here to help! Describe your question and we'll get back to you shortly:",
    "text_support_uk": "💬 <b>Підтримка TheModa</b>\n\nМи поруч і готові допомогти! Опишіть ваше питання — відповімо якнайшвидше:",
    "text_support_es": "💬 <b>Soporte de TheModa</b>\n\n¡Estamos aquí para ayudarte! Cuéntanos tu duda y te responderemos enseguida:",
}

CACHE_TTL = 86400  # Время жизни кэша в Redis (24 часа)


class TextsRepo:
    def __init__(self, db: DB, redis: Redis | None = None):
        self.db = db
        self.redis = redis

    async def get(self, key: str) -> str:
        cache_key = f"bot_text:{key}"

        if self.redis:
            try:
                cached = await self.redis.get(cache_key)
                if cached is not None:
                    return cached.decode("utf-8") if isinstance(cached, bytes) else cached
            except Exception:
                pass

        val = await self.db.fetchval("SELECT value FROM bot_texts WHERE key=$1", key)
        result = val if val is not None else DEFAULT_TEXTS.get(key, key)

        if self.redis and result:
            try:
                await self.redis.set(cache_key, result, ex=CACHE_TTL)
            except Exception:
                pass

        return result

    async def set(self, key: str, value: str):
        await self.db.execute(
            """INSERT INTO bot_texts (key, value) VALUES ($1,$2)
               ON CONFLICT (key) DO UPDATE SET value=$2""",
            key, value,
        )
        if self.redis:
            try:
                await self.redis.set(f"bot_text:{key}", value, ex=CACHE_TTL)
            except Exception:
                pass

    async def reset(self, key: str):
        await self.db.execute("DELETE FROM bot_texts WHERE key=$1", key)
        if self.redis:
            try:
                await self.redis.delete(f"bot_text:{key}")
            except Exception:
                pass


class SettingsRepo:
    def __init__(self, db: DB, redis: Redis | None = None):
        self.db = db
        self.redis = redis

    async def get(self, key: str) -> str | None:
        cache_key = f"bot_setting:{key}"

        if self.redis:
            try:
                cached = await self.redis.get(cache_key)
                if cached is not None:
                    return cached.decode("utf-8") if isinstance(cached, bytes) else cached
            except Exception:
                pass

        val = await self.db.fetchval("SELECT value FROM bot_settings WHERE key=$1", key)

        if self.redis and val is not None:
            try:
                await self.redis.set(cache_key, val, ex=CACHE_TTL)
            except Exception:
                pass

        return val

    async def set(self, key: str, value: str):
        await self.db.execute(
            """INSERT INTO bot_settings (key, value) VALUES ($1,$2)
               ON CONFLICT (key) DO UPDATE SET value=$2""",
            key, value,
        )
        if self.redis:
            try:
                await self.redis.set(f"bot_setting:{key}", value, ex=CACHE_TTL)
            except Exception:
                pass
