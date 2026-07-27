"""
DB — единая обёртка над БД с переключением драйвера через .env (DB_DRIVER=sqlite|postgres).

Репозитории везде пишут запросы в постгресовом стиле ($1, $2, ...) — для SQLite
эта обёртка сама переводит $N в ? на лету, поэтому менять repo_*.py при
переключении драйвера не нужно.
"""
import os
import re
import asyncio
import aiosqlite

PLACEHOLDER_RE = re.compile(r"\$\d+")


class DB:
    def __init__(self, driver: str, dsn_or_path: str):
        self.driver = driver  # "sqlite" | "postgres"
        self.dsn_or_path = dsn_or_path
        self.pool = None          # для postgres
        self._sqlite_lock = asyncio.Lock()  # sqlite не любит параллельные writes

    async def connect(self):
        if self.driver == "postgres":
            import asyncpg
            self.pool = await asyncpg.create_pool(dsn=self.dsn_or_path, min_size=1, max_size=10)
        else:
            # просто проверяем, что файл доступен для открытия
            async with aiosqlite.connect(self.dsn_or_path) as conn:
                await conn.execute("PRAGMA journal_mode=WAL;")

    async def init_schema(self):
        here = os.path.dirname(__file__)
        schema_file = "schema_postgres.sql" if self.driver == "postgres" else "schema_sqlite.sql"
        with open(os.path.join(here, schema_file), "r", encoding="utf-8") as f:
            sql = f.read()

        if self.driver == "postgres":
            async with self.pool.acquire() as conn:
                await conn.execute(sql)
        else:
            async with aiosqlite.connect(self.dsn_or_path) as conn:
                await conn.executescript(sql)
                await conn.commit()

        await self._migrate()

    async def _migrate(self):
        """
        Точечные миграции для случаев, когда CREATE TABLE IF NOT EXISTS не успевает
        изменить структуру уже существующей таблицы (например, добавление новой колонки).
        Безопасно вызывать многократно — каждая миграция проверяет, нужна ли она.
        """
        # gender_channels: переход с (gender PK) на (gender, category PK) — если в старой
        # базе таблица существует без колонки category, пересоздаём её с нуля (она хранит
        # только ссылки на каналы, эти данные дешевле перевнести через /manager, чем мигрировать).
        try:
            if self.driver == "postgres":
                async with self.pool.acquire() as conn:
                    cols = await conn.fetch(
                        "SELECT column_name, data_type FROM information_schema.columns WHERE table_name='gender_channels'"
                    )
                    col_map = {c["column_name"]: c["data_type"] for c in cols}
                    if "category" not in col_map:
                        await conn.execute("DROP TABLE IF EXISTS gender_channels")
                        await conn.execute(
                            """CREATE TABLE gender_channels (
                                gender TEXT NOT NULL, category TEXT NOT NULL,
                                chat_id TEXT NOT NULL, invite_url TEXT NOT NULL,
                                PRIMARY KEY (gender, category)
                            )"""
                        )
                    elif col_map.get("chat_id") in ("bigint", "integer"):
                        # старая версия хранила chat_id числом — расширяем под @username
                        await conn.execute("ALTER TABLE gender_channels ALTER COLUMN chat_id TYPE TEXT")
            else:
                async with aiosqlite.connect(self.dsn_or_path) as conn:
                    cur = await conn.execute("PRAGMA table_info(gender_channels)")
                    cols = await cur.fetchall()
                    col_names = {c[1] for c in cols}
                    if cols and "category" not in col_names:
                        await conn.execute("DROP TABLE IF EXISTS gender_channels")
                        await conn.execute(
                            """CREATE TABLE gender_channels (
                                gender TEXT NOT NULL, category TEXT NOT NULL,
                                chat_id INTEGER NOT NULL, invite_url TEXT NOT NULL,
                                PRIMARY KEY (gender, category)
                            )"""
                        )
                        await conn.commit()
        except Exception:
            # Миграция best-effort: если что-то пошло не так, не валим запуск бота из-за этого.
            pass

        # orders.client_verified — добавляем колонку, если её нет
        try:
            if self.driver == "postgres":
                async with self.pool.acquire() as conn:
                    cols = await conn.fetch(
                        "SELECT column_name FROM information_schema.columns WHERE table_name='orders'"
                    )
                    col_names = {c["column_name"] for c in cols}
                    if "client_verified" not in col_names:
                        await conn.execute("ALTER TABLE orders ADD COLUMN client_verified BOOLEAN DEFAULT FALSE")
            else:
                async with aiosqlite.connect(self.dsn_or_path) as conn:
                    cur = await conn.execute("PRAGMA table_info(orders)")
                    cols = await cur.fetchall()
                    col_names = {c[1] for c in cols}
                    if "client_verified" not in col_names:
                        await conn.execute("ALTER TABLE orders ADD COLUMN client_verified INTEGER DEFAULT 0")
                        await conn.commit()
        except Exception:
            pass
        try:
            if self.driver == "postgres":
                async with self.pool.acquire() as conn:
                    cols = await conn.fetch(
                        "SELECT column_name FROM information_schema.columns WHERE table_name='users'"
                    )
                    col_names = {c["column_name"] for c in cols}
                    if "last_address" not in col_names:
                        await conn.execute("ALTER TABLE users ADD COLUMN last_address TEXT")
            else:
                async with aiosqlite.connect(self.dsn_or_path) as conn:
                    cur = await conn.execute("PRAGMA table_info(users)")
                    cols = await cur.fetchall()
                    col_names = {c[1] for c in cols}
                    if "last_address" not in col_names:
                        await conn.execute("ALTER TABLE users ADD COLUMN last_address TEXT")
                        await conn.commit()
        except Exception:
            pass

        # staff_accounts.ref_code / commission_pct — для партнёрской программы
        try:
            if self.driver == "postgres":
                async with self.pool.acquire() as conn:
                    cols = await conn.fetch(
                        "SELECT column_name FROM information_schema.columns WHERE table_name='staff_accounts'"
                    )
                    col_names = {c["column_name"] for c in cols}
                    if "ref_code" not in col_names:
                        await conn.execute("ALTER TABLE staff_accounts ADD COLUMN ref_code TEXT UNIQUE")
                    if "commission_pct" not in col_names:
                        await conn.execute("ALTER TABLE staff_accounts ADD COLUMN commission_pct NUMERIC(5,2) DEFAULT 0")
            else:
                async with aiosqlite.connect(self.dsn_or_path) as conn:
                    cur = await conn.execute("PRAGMA table_info(staff_accounts)")
                    cols = await cur.fetchall()
                    col_names = {c[1] for c in cols}
                    if "ref_code" not in col_names:
                        await conn.execute("ALTER TABLE staff_accounts ADD COLUMN ref_code TEXT")
                        await conn.commit()
                    if "commission_pct" not in col_names:
                        await conn.execute("ALTER TABLE staff_accounts ADD COLUMN commission_pct REAL DEFAULT 0")
                        await conn.commit()
        except Exception:
            pass

        # orders.client_confirmed_at — добавляем колонку, если её нет
        try:
            if self.driver == "postgres":
                async with self.pool.acquire() as conn:
                    cols = await conn.fetch(
                        "SELECT column_name FROM information_schema.columns WHERE table_name='orders'"
                    )
                    col_names = {c["column_name"] for c in cols}
                    if "client_confirmed_at" not in col_names:
                        await conn.execute("ALTER TABLE orders ADD COLUMN client_confirmed_at TIMESTAMPTZ")
            else:
                async with aiosqlite.connect(self.dsn_or_path) as conn:
                    cur = await conn.execute("PRAGMA table_info(orders)")
                    cols = await cur.fetchall()
                    col_names = {c[1] for c in cols}
                    if "client_confirmed_at" not in col_names:
                        await conn.execute("ALTER TABLE orders ADD COLUMN client_confirmed_at TEXT")
                        await conn.commit()
        except Exception:
            pass

        # channel_posts.in_stock — добавляем колонку, если её нет
        try:
            if self.driver == "postgres":
                async with self.pool.acquire() as conn:
                    cols = await conn.fetch(
                        "SELECT column_name FROM information_schema.columns WHERE table_name='channel_posts'"
                    )
                    col_names = {c["column_name"] for c in cols}
                    if "in_stock" not in col_names:
                        await conn.execute("ALTER TABLE channel_posts ADD COLUMN in_stock BOOLEAN DEFAULT TRUE")
            else:
                async with aiosqlite.connect(self.dsn_or_path) as conn:
                    cur = await conn.execute("PRAGMA table_info(channel_posts)")
                    cols = await cur.fetchall()
                    col_names = {c[1] for c in cols}
                    if "in_stock" not in col_names:
                        await conn.execute("ALTER TABLE channel_posts ADD COLUMN in_stock INTEGER DEFAULT 1")
                        await conn.commit()
        except Exception:
            pass

        # channel_posts.size / channel_posts.description — поля шаблона поста (размер + мини-описание)
        try:
            if self.driver == "postgres":
                async with self.pool.acquire() as conn:
                    cols = await conn.fetch(
                        "SELECT column_name FROM information_schema.columns WHERE table_name='channel_posts'"
                    )
                    col_names = {c["column_name"] for c in cols}
                    if "size" not in col_names:
                        await conn.execute("ALTER TABLE channel_posts ADD COLUMN size TEXT")
                    if "description" not in col_names:
                        await conn.execute("ALTER TABLE channel_posts ADD COLUMN description TEXT")
            else:
                async with aiosqlite.connect(self.dsn_or_path) as conn:
                    cur = await conn.execute("PRAGMA table_info(channel_posts)")
                    cols = await cur.fetchall()
                    col_names = {c[1] for c in cols}
                    if "size" not in col_names:
                        await conn.execute("ALTER TABLE channel_posts ADD COLUMN size TEXT")
                        await conn.commit()
                    if "description" not in col_names:
                        await conn.execute("ALTER TABLE channel_posts ADD COLUMN description TEXT")
                        await conn.commit()
        except Exception:
            pass

        # orders.rating — оценка заказа клиентом после доставки (1 = доволен, 0 = нет)
        try:
            if self.driver == "postgres":
                async with self.pool.acquire() as conn:
                    cols = await conn.fetch(
                        "SELECT column_name FROM information_schema.columns WHERE table_name='orders'"
                    )
                    col_names = {c["column_name"] for c in cols}
                    if "rating" not in col_names:
                        await conn.execute("ALTER TABLE orders ADD COLUMN rating INTEGER")
            else:
                async with aiosqlite.connect(self.dsn_or_path) as conn:
                    cur = await conn.execute("PRAGMA table_info(orders)")
                    cols = await cur.fetchall()
                    col_names = {c[1] for c in cols}
                    if "rating" not in col_names:
                        await conn.execute("ALTER TABLE orders ADD COLUMN rating INTEGER")
                        await conn.commit()
        except Exception:
            pass

    async def close(self):
        if self.driver == "postgres" and self.pool:
            await self.pool.close()
        # sqlite соединения открываются/закрываются на каждый запрос — закрывать нечего

    # ── helpers ──────────────────────────────────────────────

    def _to_sqlite(self, query: str, args: tuple):
        """
        Переводит $1,$2,... в ? и выстраивает аргументы в порядке их появления,
        поддерживая повторное использование одного и того же $N несколько раз
        (например ON CONFLICT ... DO UPDATE SET col=$2, где $2 встречается и в INSERT, и в UPDATE).
        """
        new_args = []

        def repl(m):
            idx = int(m.group(0)[1:]) - 1
            new_args.append(args[idx])
            return "?"

        new_query = PLACEHOLDER_RE.sub(repl, query)
        return new_query, tuple(new_args)

    async def fetch(self, query: str, *args):
        if self.driver == "postgres":
            async with self.pool.acquire() as conn:
                return await conn.fetch(query, *args)
        sqlite_query, sqlite_args = self._to_sqlite(query, args)
        async with self._sqlite_lock:
            async with aiosqlite.connect(self.dsn_or_path) as conn:
                conn.row_factory = aiosqlite.Row
                cur = await conn.execute(sqlite_query, sqlite_args)
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    async def fetchrow(self, query: str, *args):
        if self.driver == "postgres":
            async with self.pool.acquire() as conn:
                return await conn.fetchrow(query, *args)
        sqlite_query, sqlite_args = self._to_sqlite(query, args)
        async with self._sqlite_lock:
            async with aiosqlite.connect(self.dsn_or_path) as conn:
                conn.row_factory = aiosqlite.Row
                cur = await conn.execute(sqlite_query, sqlite_args)
                row = await cur.fetchone()
                return dict(row) if row else None

    async def execute(self, query: str, *args) -> int:
        """
        Возвращает количество затронутых строк как int — одинаково для обоих драйверов.
        Postgres (asyncpg) сам отдаёт строку статуса вида "UPDATE 1" / "DELETE 0" —
        разбираем её, чтобы вызывающему коду не нужно было знать про разницу между драйверами.
        """
        if self.driver == "postgres":
            async with self.pool.acquire() as conn:
                status = await conn.execute(query, *args)
            try:
                return int(status.split()[-1])
            except (ValueError, IndexError):
                return 0
        sqlite_query, sqlite_args = self._to_sqlite(query, args)
        async with self._sqlite_lock:
            async with aiosqlite.connect(self.dsn_or_path) as conn:
                cur = await conn.execute(sqlite_query, sqlite_args)
                await conn.commit()
                return cur.rowcount

    async def fetchval(self, query: str, *args):
        if self.driver == "postgres":
            async with self.pool.acquire() as conn:
                return await conn.fetchval(query, *args)
        sqlite_query, sqlite_args = self._to_sqlite(query, args)
        async with self._sqlite_lock:
            async with aiosqlite.connect(self.dsn_or_path) as conn:
                cur = await conn.execute(sqlite_query, sqlite_args)
                row = await cur.fetchone()
                await conn.commit()
                if row is None:
                    return None
                return row[0]

    # ── переносимые date-хелперы (используются в repo_*.py для статистики) ──

    def today_clause(self, column: str) -> str:
        if self.driver == "postgres":
            return f"{column}::date = now()::date"
        return f"date({column}) = date('now')"

    def days_clause(self, column: str, days: int) -> str:
        if self.driver == "postgres":
            return f"{column} >= now() - interval '{int(days)} days'"
        return f"{column} >= datetime('now', '-{int(days)} days')"