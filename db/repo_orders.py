from datetime import datetime
from db.pool import DB

STATUS_LABELS = {
    "pending":             "⏳ Ожидает подтверждения администратора",
    "confirmed":           "📦 Передан на склад",
    "warehouse_received":  "🧰 Склад собрал заказ",
    "shipping":            "🚚 Доставляется",
    "delivered":           "✅ Доставлен",
    "completed":           "✅ Доставлен",
    "cancelled":           "❌ Отменён",
}


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


class OrdersRepo:
    def __init__(self, db: DB):
        self.db = db

    async def create(self, user_tg_id: int, items: list[dict], size: str, comment: str) -> int:
        order_id = await self.db.fetchval(
            "INSERT INTO orders (user_tg_id, size, comment) VALUES ($1,$2,$3) RETURNING id",
            user_tg_id, size, comment,
        )
        for item in items:
            await self.db.execute(
                """INSERT INTO order_items (order_id, post_id, title, price, size, photo_file_id, brand_id)
                   VALUES ($1,$2,$3,$4,$5,$6,$7)""",
                order_id, item.get("post_id"), item.get("title"), item.get("price"), size,
                item.get("photo_file_id"), item.get("brand_id"),
            )
        return order_id

    async def get(self, order_id: int) -> dict | None:
        row = await self.db.fetchrow("SELECT * FROM orders WHERE id=$1", order_id)
        return dict(row) if row else None

    async def get_items(self, order_id: int) -> list[dict]:
        rows = await self.db.fetch("SELECT * FROM order_items WHERE order_id=$1", order_id)
        return [dict(r) for r in rows]

    async def update_status(self, order_id: int, status: str):
        # ИСПРАВЛЕНИЕ: раньше сюда передавалась строка (.isoformat(...)), а
        # confirmed_at/completed_at в Postgres — колонки TIMESTAMPTZ. asyncpg
        # строго типизирован и не принимает строку вместо настоящего datetime —
        # падал с DataError на каждое подтверждение/доставку заказа. Теперь
        # передаём сам объект datetime.now().
        extra_sql, extra_val = "", None
        if status == "confirmed":
            extra_sql, extra_val = ", confirmed_at=$2", datetime.now()
        elif status in ("completed", "delivered"):
            extra_sql, extra_val = ", completed_at=$2", datetime.now()

        if extra_val:
            await self.db.execute(
                f"UPDATE orders SET status=$1{extra_sql} WHERE id=$3" if extra_sql else "UPDATE orders SET status=$1 WHERE id=$2",
                status, extra_val, order_id,
            )
        else:
            await self.db.execute("UPDATE orders SET status=$1 WHERE id=$2", status, order_id)

    async def set_client_confirmed(self, order_id: int):
        # ИСПРАВЛЕНИЕ: та же проблема — client_confirmed_at тоже TIMESTAMPTZ,
        # нужен объект datetime, а не строка.
        await self.db.execute(
            "UPDATE orders SET client_confirmed_at=$1 WHERE id=$2",
            datetime.now(), order_id,
        )

    async def by_user(self, user_tg_id: int) -> list[dict]:
        rows = await self.db.fetch(
            "SELECT * FROM orders WHERE user_tg_id=$1 ORDER BY created_at DESC", user_tg_id
        )
        return [dict(r) for r in rows]

    async def active_for_user(self, user_tg_id: int) -> dict | None:
        """Текущий незавершённый заказ клиента (самый свежий)."""
        row = await self.db.fetchrow(
            """SELECT * FROM orders WHERE user_tg_id=$1 AND status NOT IN ('delivered','cancelled')
               ORDER BY created_at DESC LIMIT 1""",
            user_tg_id,
        )
        return dict(row) if row else None

    async def history_for_user(self, user_tg_id: int) -> list[dict]:
        """Заказы, подтверждённые администратором (pending и отменённые не показываем в истории)."""
        rows = await self.db.fetch(
            """SELECT * FROM orders WHERE user_tg_id=$1
               AND status IN ('confirmed','warehouse_received','shipping','delivered','completed')
               ORDER BY created_at DESC""",
            user_tg_id,
        )
        return [dict(r) for r in rows]

    async def pending(self) -> list[dict]:
        rows = await self.db.fetch(
            """SELECT o.*, u.username, u.phone FROM orders o
               LEFT JOIN users u ON u.tg_id = o.user_tg_id
               WHERE o.status='pending' ORDER BY o.created_at ASC"""
        )
        return [dict(r) for r in rows]

    async def confirmed(self) -> list[dict]:
        rows = await self.db.fetch(
            """SELECT o.*, u.username FROM orders o
               LEFT JOIN users u ON u.tg_id = o.user_tg_id
               WHERE o.status IN ('confirmed','warehouse_received')
               ORDER BY o.created_at ASC"""
        )
        return [dict(r) for r in rows]

    async def active_for_admin(self) -> list[dict]:
        """Все незавершённые заказы (для панели админа) — pending + всё, что уже в работе."""
        rows = await self.db.fetch(
            """SELECT o.*, u.username, u.phone FROM orders o
               LEFT JOIN users u ON u.tg_id = o.user_tg_id
               WHERE o.status NOT IN ('delivered','cancelled')
               ORDER BY o.created_at ASC"""
        )
        return [dict(r) for r in rows]

    async def update_details(self, order_id: int, size: str | None = None, comment: str | None = None):
        if size is not None:
            await self.db.execute("UPDATE orders SET size=$1 WHERE id=$2", size, order_id)
        if comment is not None:
            await self.db.execute("UPDATE orders SET comment=$1 WHERE id=$2", comment, order_id)

    async def set_client_verified(self, order_id: int, verified: bool):
        await self.db.execute(
            "UPDATE orders SET client_verified=$1 WHERE id=$2", verified, order_id
        )

    async def set_rating(self, order_id: int, rating: int):
        await self.db.execute("UPDATE orders SET rating=$1 WHERE id=$2", rating, order_id)

    async def stats(self) -> dict:
        total = await self.db.fetchval("SELECT COUNT(*) FROM orders") or 0
        today = await self.db.fetchval(
            f"SELECT COUNT(*) FROM orders WHERE {self.db.today_clause('created_at')}"
        ) or 0
        week = await self.db.fetchval(
            f"SELECT COUNT(*) FROM orders WHERE {self.db.days_clause('created_at', 7)}"
        ) or 0
        month = await self.db.fetchval(
            f"SELECT COUNT(*) FROM orders WHERE {self.db.days_clause('created_at', 30)}"
        ) or 0
        return {"total": total, "today": today, "week": week, "month": month}


class FinanceRepo:
    """Финансовая аналитика для менеджера."""

    def __init__(self, db: DB):
        self.db = db

    async def add_entry(self, order_id: int, revenue: float, cost: float):
        profit = revenue - cost
        await self.db.execute(
            "INSERT INTO finance_entries (order_id, revenue, cost, profit) VALUES ($1,$2,$3,$4)",
            order_id, revenue, cost, profit,
        )

    async def summary(self, days: int | None = None) -> dict:
        where = ""
        if days:
            where = f"WHERE {self.db.days_clause('created_at', days)}"
        row = await self.db.fetchrow(
            f"""SELECT
                    COALESCE(SUM(revenue),0) AS revenue,
                    COALESCE(SUM(cost),0)    AS cost,
                    COALESCE(SUM(profit),0)  AS profit,
                    COUNT(*) AS entries
                FROM finance_entries {where}"""
        )
        return dict(row) if row else {"revenue": 0, "cost": 0, "profit": 0, "entries": 0}
