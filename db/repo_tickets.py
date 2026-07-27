from db.pool import DB


class TicketsRepo:
    def __init__(self, db: DB):
        self.db = db

    async def create(self, user_tg_id: int, username: str | None, first_message: str) -> int:
        ticket_id = await self.db.fetchval(
            """INSERT INTO tickets (user_tg_id, username, last_message)
               VALUES ($1,$2,$3) RETURNING id""",
            user_tg_id, username, first_message,
        )
        await self.add_message(ticket_id, "user", first_message)
        return ticket_id

    async def get(self, ticket_id: int) -> dict | None:
        row = await self.db.fetchrow("SELECT * FROM tickets WHERE id=$1", ticket_id)
        return dict(row) if row else None

    async def get_open_by_user(self, user_tg_id: int) -> dict | None:
        row = await self.db.fetchrow(
            """SELECT * FROM tickets WHERE user_tg_id=$1 AND status != 'closed'
               ORDER BY created_at DESC LIMIT 1""",
            user_tg_id,
        )
        return dict(row) if row else None

    async def get_last_by_user(self, user_tg_id: int) -> dict | None:
        row = await self.db.fetchrow(
            "SELECT * FROM tickets WHERE user_tg_id=$1 ORDER BY created_at DESC LIMIT 1",
            user_tg_id,
        )
        return dict(row) if row else None

    async def update(self, ticket_id: int, **fields):
        if not fields:
            return
        keys = list(fields.keys())
        set_clause = ", ".join(f"{k}=${i+2}" for i, k in enumerate(keys))
        values = [fields[k] for k in keys]
        await self.db.execute(
            f"UPDATE tickets SET {set_clause} WHERE id=$1", ticket_id, *values,
        )

    async def add_message(self, ticket_id: int, sender: str, text: str):
        await self.db.execute(
            "INSERT INTO ticket_messages (ticket_id, sender, text) VALUES ($1,$2,$3)",
            ticket_id, sender, text,
        )

    async def get_messages(self, ticket_id: int) -> list[dict]:
        rows = await self.db.fetch(
            "SELECT * FROM ticket_messages WHERE ticket_id=$1 ORDER BY created_at ASC",
            ticket_id,
        )
        return [dict(r) for r in rows]

    async def open_list(self) -> list[dict]:
        rows = await self.db.fetch(
            "SELECT * FROM tickets WHERE status IN ('new','waiting') ORDER BY created_at ASC"
        )
        return [dict(r) for r in rows]

    async def admin_stats_today(self, admin_login: str) -> dict:
        taken = await self.db.fetchval(
            f"""SELECT COUNT(*) FROM tickets WHERE admin_login=$1
               AND {self.db.today_clause('taken_at')}""", admin_login,
        ) or 0
        closed = await self.db.fetchval(
            f"""SELECT COUNT(*) FROM tickets WHERE admin_login=$1 AND status='closed'
               AND {self.db.today_clause('closed_at')}""", admin_login,
        ) or 0
        waiting = await self.db.fetchval(
            "SELECT COUNT(*) FROM tickets WHERE admin_login=$1 AND status='waiting'",
            admin_login,
        ) or 0
        satisfied = await self.db.fetchval(
            f"""SELECT COUNT(*) FROM tickets WHERE admin_login=$1 AND rating=1
               AND {self.db.today_clause('closed_at')}""", admin_login,
        ) or 0
        unsatisfied = await self.db.fetchval(
            f"""SELECT COUNT(*) FROM tickets WHERE admin_login=$1 AND rating=0
               AND {self.db.today_clause('closed_at')}""", admin_login,
        ) or 0
        return {
            "taken": taken, "closed": closed, "waiting": waiting,
            "satisfied": satisfied, "unsatisfied": unsatisfied,
        }

    async def all_admin_stats_today(self, admin_logins: list[str]) -> list[dict]:
        result = []
        for login in admin_logins:
            s = await self.admin_stats_today(login)
            result.append({"login": login, **s})
        return result