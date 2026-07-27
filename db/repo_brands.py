from db.pool import DB


class BrandsRepo:
    def __init__(self, db: DB):
        self.db = db

    # ── каналы (7 шт: пол × категория) ────────────────────────

    async def set_channel(self, gender: str, category: str, chat_id: str, invite_url: str):
        await self.db.execute(
            """INSERT INTO gender_channels (gender, category, chat_id, invite_url)
               VALUES ($1,$2,$3,$4)
               ON CONFLICT (gender, category) DO UPDATE SET chat_id=$3, invite_url=$4""",
            gender, category, chat_id, invite_url,
        )

    async def get_channel(self, gender: str, category: str) -> dict | None:
        row = await self.db.fetchrow(
            "SELECT * FROM gender_channels WHERE gender=$1 AND category=$2", gender, category
        )
        return dict(row) if row else None

    async def list_channels(self) -> list[dict]:
        rows = await self.db.fetch("SELECT * FROM gender_channels ORDER BY gender, category")
        return [dict(r) for r in rows]

    async def list_all_brands(self) -> list[dict]:
        rows = await self.db.fetch("SELECT * FROM brands WHERE is_active=TRUE ORDER BY gender, category, name")
        return [dict(r) for r in rows]

    # ── бренды ───────────────────────────────────────────────

    async def create(self, name: str, emoji: str, gender: str, category: str, topic_id: int) -> int:
        return await self.db.fetchval(
            """INSERT INTO brands (name, emoji, gender, category, topic_id)
               VALUES ($1,$2,$3,$4,$5) RETURNING id""",
            name, emoji, gender, category, topic_id,
        )

    async def list(self, gender: str, category: str) -> list[dict]:
        rows = await self.db.fetch(
            """SELECT * FROM brands WHERE gender=$1 AND category=$2 AND is_active=TRUE
               ORDER BY name ASC""",
            gender, category,
        )
        return [dict(r) for r in rows]

    async def get(self, brand_id: int) -> dict | None:
        row = await self.db.fetchrow("SELECT * FROM brands WHERE id=$1", brand_id)
        return dict(row) if row else None

    async def deactivate(self, brand_id: int):
        await self.db.execute("UPDATE brands SET is_active=FALSE WHERE id=$1", brand_id)

    def topic_url(self, channel: dict, brand: dict) -> str:
        """
        Ссылка на топик внутри супергруппы/канала-форума.
        invite_url ожидается в формате https://t.me/c/<internal_id> ИЛИ https://t.me/<username>
        """
        base = channel["invite_url"].rstrip("/")
        return f"{base}/{brand['topic_id']}"

    def post_message_url(self, channel: dict, brand: dict, post: dict) -> str | None:
        """
        Прямая ссылка на конкретный пост (товар) в нужном топике — НЕ просто на канал.
        Формат t.me/c/<id>/<topic_id>/<message_id> — именно так Telegram сам генерирует
        "Copy Message Link" для сообщений внутри тем (топиков). Без topic_id в пути
        Telegram открывает чат в General, а не в нужной теме.
        """
        if not post.get("tg_message_id") or not brand.get("topic_id"):
            return None
        base = channel["invite_url"].rstrip("/")
        return f"{base}/{brand['topic_id']}/{post['tg_message_id']}"