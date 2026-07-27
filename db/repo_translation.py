from redis.asyncio import Redis
from db.pool import DB

CACHE_TTL = 604800  # 7 дней жизни кэша перевода в Redis


class TranslationCacheRepo:
    def __init__(self, db: DB, redis: Redis | None = None):
        self.db = db
        self.redis = redis

    async def get(self, source_text: str, lang: str) -> str | None:
        cache_key = f"tr:{lang}:{hash(source_text)}"

        # 1. Проверяем оперативку Redis
        if self.redis:
            try:
                cached = await self.redis.get(cache_key)
                if cached is not None:
                    return cached.decode("utf-8") if isinstance(cached, bytes) else cached
            except Exception:
                pass

        # 2. Если в Redis нет — ищем в БД
        val = await self.db.fetchval(
            "SELECT translated FROM translation_cache WHERE source_text=$1 AND lang=$2",
            source_text, lang,
        )

        # 3. Кэшируем результат в Redis
        if self.redis and val is not None:
            try:
                await self.redis.set(cache_key, val, ex=CACHE_TTL)
            except Exception:
                pass

        return val

    async def set(self, source_text: str, lang: str, translated: str):
        # Сохраняем в БД
        await self.db.execute(
            """INSERT INTO translation_cache (source_text, lang, translated)
               VALUES ($1,$2,$3)
               ON CONFLICT (source_text, lang) DO UPDATE SET translated=$3""",
            source_text, lang, translated,
        )

        # Сохраняем в Redis
        if self.redis:
            try:
                cache_key = f"tr:{lang}:{hash(source_text)}"
                await self.redis.set(cache_key, translated, ex=CACHE_TTL)
            except Exception:
                pass

    async def cleanup_old(self, limit: int = 5000):
        """Очистка старых записей перевода"""
        await self.db.execute(
            """DELETE FROM translation_cache 
               WHERE ctid IN (
                   SELECT ctid FROM translation_cache LIMIT $1
               )""",
            limit,
        )
