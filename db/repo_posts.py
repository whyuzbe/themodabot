from db.pool import DB


class PostsRepo:
    def __init__(self, db: DB):
        self.db = db

    async def create(self, brand_id: int, gender: str, category: str, title: str,
                      price: str, photo_file_id: str, tg_message_id: int | None,
                      admin_login: str, size: str | None = None, description: str | None = None) -> int:
        return await self.db.fetchval(
            """INSERT INTO channel_posts
               (brand_id, gender, category, title, price, size, description, photo_file_id, tg_message_id, admin_login)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id""",
            brand_id, gender, category, title, price, size, description, photo_file_id, tg_message_id, admin_login,
        )

    async def get(self, post_id: int) -> dict | None:
        row = await self.db.fetchrow("SELECT * FROM channel_posts WHERE id=$1", post_id)
        return dict(row) if row else None

    async def find_by_brand_title(self, brand_id: int, title: str) -> dict | None:
        """
        Сначала ищем точно в этом разделе (brand_id). Если не нашли — расширяем поиск
        до всей категории (на случай, если в базе есть дублирующиеся разделы с одинаковым
        названием, но разными id — товар может физически лежать под "соседним" разделом).
        Сравнение регистра делаем в Python — встроенный lower() в SQLite не умеет работать
        с кириллицей (только ASCII), что давало ложные "не найдено".
        """
        target = self._normalize(title)

        rows = await self.db.fetch(
            "SELECT * FROM channel_posts WHERE brand_id=$1 ORDER BY created_at DESC", brand_id
        )
        for r in rows:
            row = dict(r)
            if self._normalize(row["title"]) == target:
                return row

        brand = await self.db.fetchrow("SELECT gender, category FROM brands WHERE id=$1", brand_id)
        if not brand:
            return None

        rows2 = await self.db.fetch(
            "SELECT * FROM channel_posts WHERE gender=$1 AND category=$2 ORDER BY created_at DESC",
            brand["gender"], brand["category"],
        )
        for r in rows2:
            row = dict(r)
            if self._normalize(row["title"]) == target:
                return row
        return None

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.strip().casefold().split())

    async def create_virtual(self, brand_id: int, gender: str, category: str, title: str,
                              price: str, photo_file_id: str, admin_login: str) -> int:
        """
        "Виртуальный" пост — товара пока нет в реальном канале (tg_message_id=None),
        но нужна запись в БД, чтобы можно было собирать лист ожидания и потом
        уведомить клиентов, когда товар появится.
        """
        return await self.db.fetchval(
            """INSERT INTO channel_posts
               (brand_id, gender, category, title, price, photo_file_id, tg_message_id, admin_login, in_stock)
               VALUES ($1,$2,$3,$4,$5,$6,NULL,$7,FALSE) RETURNING id""",
            brand_id, gender, category, title, price, photo_file_id, admin_login,
        )

    async def find_virtual_duplicate(self, brand_id: int, title: str) -> dict | None:
        """
        Ищем виртуальную запись (создана складом, tg_message_id ещё нет) с таким же
        названием в этом разделе — чтобы при публикации админом реального поста
        не плодить дубль и перенести на него уже накопленный лист ожидания.
        """
        target = self._normalize(title)
        rows = await self.db.fetch(
            "SELECT * FROM channel_posts WHERE brand_id=$1 AND tg_message_id IS NULL ORDER BY created_at DESC",
            brand_id,
        )
        for r in rows:
            row = dict(r)
            if self._normalize(row["title"]) == target:
                return row
        return None

    async def merge_virtual_into_real(self, virtual_post_id: int, real_post_id: int):
        """Переносит лист ожидания с виртуальной записи на только что опубликованный
        реальный пост и удаляет виртуальную запись (дублировать её больше незачем)."""
        await self.db.execute(
            "UPDATE stock_interest SET post_id=$1 WHERE post_id=$2", real_post_id, virtual_post_id
        )
        await self.db.execute("DELETE FROM channel_posts WHERE id=$1", virtual_post_id)

    async def by_admin(self, admin_login: str, limit: int = 50) -> list[dict]:
        rows = await self.db.fetch(
            "SELECT * FROM channel_posts WHERE admin_login=$1 ORDER BY created_at DESC LIMIT $2",
            admin_login, limit,
        )
        return [dict(r) for r in rows]

    async def stats(self) -> dict:
        total = await self.db.fetchval("SELECT COUNT(*) FROM channel_posts") or 0
        today = await self.db.fetchval(
            f"SELECT COUNT(*) FROM channel_posts WHERE {self.db.today_clause('created_at')}"
        ) or 0
        week = await self.db.fetchval(
            f"SELECT COUNT(*) FROM channel_posts WHERE {self.db.days_clause('created_at', 7)}"
        ) or 0
        month = await self.db.fetchval(
            f"SELECT COUNT(*) FROM channel_posts WHERE {self.db.days_clause('created_at', 30)}"
        ) or 0
        return {"total": total, "today": today, "week": week, "month": month}

    # ── Наличие товара ───────────────────────────────────────────

    async def set_in_stock(self, post_id: int, in_stock: bool):
        await self.db.execute("UPDATE channel_posts SET in_stock=$1 WHERE id=$2", in_stock, post_id)

    async def by_brand(self, brand_id: int) -> list[dict]:
        rows = await self.db.fetch(
            "SELECT * FROM channel_posts WHERE brand_id=$1 ORDER BY created_at DESC", brand_id
        )
        return [dict(r) for r in rows]

    async def recent(self, limit: int = 20) -> list[dict]:
        rows = await self.db.fetch(
            "SELECT * FROM channel_posts ORDER BY created_at DESC LIMIT $1", limit
        )
        return [dict(r) for r in rows]

    # ── Лист ожидания "уведомить когда появится" ──────────────────

    async def add_interest(self, post_id: int, user_tg_id: int):
        """
        ИСПРАВЛЕНИЕ: раньше не было проверки на дубликат — если человек несколько
        раз нажимал "🔔 Notify me when it's back" на один и тот же товар (например,
        снова открыв карточку), в stock_interest копились повторные записи. На
        уведомления это не влияло (interested_users() и так делает DISTINCT), но
        искажало аналитику склада interest_today_summary(): COUNT(*) считал не
        уникальных людей, а количество кликов, завышая интерес к товару.
        """
        existing = await self.db.fetchval(
            "SELECT id FROM stock_interest WHERE post_id=$1 AND user_tg_id=$2",
            post_id, user_tg_id,
        )
        if existing:
            return
        await self.db.execute(
            "INSERT INTO stock_interest (post_id, user_tg_id) VALUES ($1,$2)", post_id, user_tg_id
        )

    async def interested_users(self, post_id: int) -> list[int]:
        rows = await self.db.fetch(
            "SELECT DISTINCT user_tg_id FROM stock_interest WHERE post_id=$1", post_id
        )
        return [r["user_tg_id"] for r in rows]

    async def clear_interest(self, post_id: int):
        await self.db.execute("DELETE FROM stock_interest WHERE post_id=$1", post_id)

    async def interest_today_summary(self) -> list[dict]:
        """
        Сводка за сегодня: по каждому посту — сколько раз кликнули "уведомить"
        и список (tg_id) тех, кто кликал. Используется складом для аналитики
        "что заказывать в первую очередь".
        """
        rows = await self.db.fetch(
            f"""SELECT si.post_id, cp.title, cp.price, COUNT(*) AS clicks
                FROM stock_interest si
                LEFT JOIN channel_posts cp ON cp.id = si.post_id
                WHERE {self.db.today_clause('si.created_at')}
                GROUP BY si.post_id, cp.title, cp.price
                ORDER BY clicks DESC"""
        )
        result = []
        for r in rows:
            row = dict(r)
            users = await self.db.fetch(
                f"""SELECT DISTINCT si.user_tg_id, u.username FROM stock_interest si
                    LEFT JOIN users u ON u.tg_id = si.user_tg_id
                    WHERE si.post_id=$1 AND {self.db.today_clause('si.created_at')}""",
                row["post_id"],
            )
            row["users"] = [dict(u) for u in users]
            result.append(row)
        return result

    async def deficit_summary(self) -> list[dict]:
        """
        Товары, которых сейчас нет в наличии (in_stock=FALSE), но которыми
        интересовались клиенты за всё время (не только сегодня) — то, что
        складу стоит закупить в первую очередь. Отсортировано по популярности.
        Используется кнопкой "🚨 Дефицит" в панели склада.
        """
        rows = await self.db.fetch(
            """SELECT cp.id, cp.title, cp.price, cp.gender, cp.category,
                      b.name AS brand_name, b.emoji AS brand_emoji,
                      COUNT(si.id) AS interest_count
               FROM channel_posts cp
               LEFT JOIN stock_interest si ON si.post_id = cp.id
               LEFT JOIN brands b ON b.id = cp.brand_id
               WHERE cp.in_stock = FALSE
               GROUP BY cp.id, cp.title, cp.price, cp.gender, cp.category, b.name, b.emoji
               HAVING COUNT(si.id) > 0
               ORDER BY interest_count DESC"""
        )
        return [dict(r) for r in rows]
