from db.pool import DB


class TranslationCacheRepo:
    def __init__(self, db: DB):
        self.db = db

    async def get(self, source_text: str, lang: str) -> str | None:
        return await self.db.fetchval(
            "SELECT translated FROM translation_cache WHERE source_text=$1 AND lang=$2",
            source_text, lang,
        )

    async def set(self, source_text: str, lang: str, translated: str):
        await self.db.execute(
            """INSERT INTO translation_cache (source_text, lang, translated)
               VALUES ($1,$2,$3)
               ON CONFLICT (source_text, lang) DO UPDATE SET translated=$3""",
            source_text, lang, translated,
        )