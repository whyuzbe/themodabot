from db.pool import DB


class UsersRepo:
    def __init__(self, db: DB):
        self.db = db

    async def get(self, tg_id: int) -> dict | None:
        row = await self.db.fetchrow("SELECT * FROM users WHERE tg_id=$1", tg_id)
        return dict(row) if row else None

    async def create(self, tg_id: int, username: str | None, language: str = "ru"):
        await self.db.execute(
            """INSERT INTO users (tg_id, username, language)
               VALUES ($1,$2,$3)
               ON CONFLICT (tg_id) DO NOTHING""",
            tg_id, username, language,
        )

    async def update(self, tg_id: int, **fields):
        if not fields:
            return
        keys = list(fields.keys())
        set_clause = ", ".join(f"{k}=${i+2}" for i, k in enumerate(keys))
        values = [fields[k] for k in keys]
        await self.db.execute(
            f"UPDATE users SET {set_clause} WHERE tg_id=$1",
            tg_id, *values,
        )

    async def is_blocked(self, tg_id: int) -> bool:
        val = await self.db.fetchval("SELECT is_blocked FROM users WHERE tg_id=$1", tg_id)
        return bool(val)

    async def delete_account(self, tg_id: int) -> bool:
        """Полное удаление аккаунта клиента по его собственному запросу (/dell_num)."""
        result = await self.db.execute("DELETE FROM users WHERE tg_id=$1", tg_id)
        await self.db.execute("DELETE FROM cart WHERE user_tg_id=$1", tg_id)
        await self.db.execute("DELETE FROM wishlist WHERE user_tg_id=$1", tg_id)
        await self.db.execute("DELETE FROM user_sizes WHERE user_tg_id=$1", tg_id)
        return result > 0

    async def all(self, gender: str | None = None) -> list[dict]:
        if gender:
            rows = await self.db.fetch("SELECT * FROM users WHERE gender=$1", gender)
        else:
            rows = await self.db.fetch("SELECT * FROM users")
        return [dict(r) for r in rows]

    async def stats(self) -> dict:
        total = await self.db.fetchval("SELECT COUNT(*) FROM users")
        males = await self.db.fetchval("SELECT COUNT(*) FROM users WHERE gender='male'")
        females = await self.db.fetchval("SELECT COUNT(*) FROM users WHERE gender='female'")
        today = await self.db.fetchval(
            f"SELECT COUNT(*) FROM users WHERE {self.db.today_clause('registered_at')}"
        )
        week = await self.db.fetchval(
            f"SELECT COUNT(*) FROM users WHERE {self.db.days_clause('registered_at', 7)}"
        )
        month = await self.db.fetchval(
            f"SELECT COUNT(*) FROM users WHERE {self.db.days_clause('registered_at', 30)}"
        )
        return {
            "total": total or 0, "males": males or 0, "females": females or 0,
            "today": today or 0, "week": week or 0, "month": month or 0,
        }

    # ── Сохранённые размеры (по категории) и адрес ───────────────

    async def get_size(self, tg_id: int, category: str) -> str | None:
        if not category:
            return None
        return await self.db.fetchval(
            "SELECT size FROM user_sizes WHERE user_tg_id=$1 AND category=$2", tg_id, category
        )

    async def set_size(self, tg_id: int, category: str, size: str):
        if not category or not size or size.strip() in ("", "—", "-"):
            return
        await self.db.execute(
            """INSERT INTO user_sizes (user_tg_id, category, size)
               VALUES ($1,$2,$3)
               ON CONFLICT (user_tg_id, category) DO UPDATE SET size=$3""",
            tg_id, category, size.strip(),
        )

    async def get_last_address(self, tg_id: int) -> str | None:
        return await self.db.fetchval("SELECT last_address FROM users WHERE tg_id=$1", tg_id)

    async def set_last_address(self, tg_id: int, address: str):
        if not address or address.strip() in ("", "—", "-"):
            return
        await self.db.execute(
            "UPDATE users SET last_address=$1 WHERE tg_id=$2", address.strip(), tg_id
        )