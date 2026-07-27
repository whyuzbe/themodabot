from db.pool import DB


class CartRepo:
    def __init__(self, db: DB):
        self.db = db

    # ── корзина ──────────────────────────────────────────────

    async def add(self, user_tg_id: int, post_id: int) -> bool:
        try:
            await self.db.execute(
                "INSERT INTO cart (user_tg_id, post_id) VALUES ($1,$2)",
                user_tg_id, post_id,
            )
            return True
        except Exception:
            return False

    async def remove(self, cart_id: int, user_tg_id: int):
        await self.db.execute(
            "DELETE FROM cart WHERE id=$1 AND user_tg_id=$2", cart_id, user_tg_id
        )

    async def get(self, user_tg_id: int) -> list[dict]:
        rows = await self.db.fetch(
            """SELECT c.id AS cart_id, c.post_id, c.added_at,
                      p.title, p.price, p.photo_file_id, p.brand_id, p.gender, p.category, p.in_stock
               FROM cart c LEFT JOIN channel_posts p ON p.id = c.post_id
               WHERE c.user_tg_id=$1 ORDER BY c.added_at DESC""",
            user_tg_id,
        )
        return [dict(r) for r in rows]

    async def clear(self, user_tg_id: int):
        await self.db.execute("DELETE FROM cart WHERE user_tg_id=$1", user_tg_id)

    async def has(self, user_tg_id: int, post_id: int) -> bool:
        val = await self.db.fetchval(
            "SELECT 1 FROM cart WHERE user_tg_id=$1 AND post_id=$2", user_tg_id, post_id
        )
        return bool(val)

    # ── wishlist ─────────────────────────────────────────────

    async def wish_add(self, user_tg_id: int, post_id: int) -> bool:
        try:
            await self.db.execute(
                "INSERT INTO wishlist (user_tg_id, post_id) VALUES ($1,$2)",
                user_tg_id, post_id,
            )
            return True
        except Exception:
            return False

    async def wish_remove(self, wish_id: int, user_tg_id: int):
        await self.db.execute(
            "DELETE FROM wishlist WHERE id=$1 AND user_tg_id=$2", wish_id, user_tg_id
        )

    async def wish_get(self, user_tg_id: int) -> list[dict]:
        rows = await self.db.fetch(
            """SELECT w.id AS wish_id, w.post_id, w.added_at,
                      p.title, p.price, p.photo_file_id, p.brand_id, p.gender, p.category, p.in_stock
               FROM wishlist w LEFT JOIN channel_posts p ON p.id = w.post_id
               WHERE w.user_tg_id=$1 ORDER BY w.added_at DESC""",
            user_tg_id,
        )
        return [dict(r) for r in rows]

    async def wish_has(self, user_tg_id: int, post_id: int) -> bool:
        val = await self.db.fetchval(
            "SELECT 1 FROM wishlist WHERE user_tg_id=$1 AND post_id=$2", user_tg_id, post_id
        )
        return bool(val)