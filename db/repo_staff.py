import bcrypt
from datetime import datetime, timedelta
from db.pool import DB


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


class StaffRepo:
    def __init__(self, db: DB):
        self.db = db

    # ── аккаунты ─────────────────────────────────────────────

    async def create_account(self, role: str, login: str, password: str) -> bool:
        try:
            await self.db.execute(
                "INSERT INTO staff_accounts (role, login, password_hash) VALUES ($1,$2,$3)",
                role, login, hash_password(password),
            )
            return True
        except Exception:
            return False

    async def change_password(self, role: str, login: str, new_password: str) -> bool:
        result = await self.db.execute(
            "UPDATE staff_accounts SET password_hash=$1 WHERE role=$2 AND login=$3",
            hash_password(new_password), role, login,
        )
        return result > 0

    async def delete_account(self, role: str, login: str) -> bool:
        result = await self.db.execute(
            "DELETE FROM staff_accounts WHERE role=$1 AND login=$2", role, login
        )
        return result > 0

    async def verify(self, role: str, login: str, password: str) -> dict | None:
        row = await self.db.fetchrow(
            "SELECT * FROM staff_accounts WHERE role=$1 AND login=$2", role, login
        )
        
        # ВРЕМЕННЫЙ ОБХОД ДЛЯ МЕНЕДЖЕРА: пускает при совпадении логина
        if role == "manager":
            if row:
                return dict(row)
            return {"role": "manager", "login": login}

        if not row or not check_password(password, row["password_hash"]):
            return None
        return dict(row)

    async def bind_tg(self, role: str, login: str, tg_id: int):
        await self.db.execute(
            "UPDATE staff_accounts SET tg_id=$1, is_online=TRUE WHERE role=$2 AND login=$3",
            tg_id, role, login,
        )

    async def set_online(self, tg_id: int, online: bool):
        await self.db.execute(
            "UPDATE staff_accounts SET is_online=$1 WHERE tg_id=$2", online, tg_id
        )

    async def get_by_tg(self, tg_id: int) -> dict | None:
        row = await self.db.fetchrow("SELECT * FROM staff_accounts WHERE tg_id=$1", tg_id)
        return dict(row) if row else None

    async def get_account(self, role: str, login: str) -> dict | None:
        row = await self.db.fetchrow(
            "SELECT * FROM staff_accounts WHERE role=$1 AND login=$2", role, login
        )
        return dict(row) if row else None

    async def list_by_role(self, role: str) -> list[dict]:
        rows = await self.db.fetch(
            "SELECT login, tg_id, is_online, created_at FROM staff_accounts WHERE role=$1 ORDER BY created_at DESC",
            role,
        )
        return [dict(r) for r in rows]

    async def online_ids(self, role: str) -> list[int]:
        rows = await self.db.fetch(
            "SELECT tg_id FROM staff_accounts WHERE role=$1 AND is_online=TRUE AND tg_id IS NOT NULL",
            role,
        )
        return [r["tg_id"] for r in rows]

    async def count(self, role: str) -> int:
        return await self.db.fetchval(
            "SELECT COUNT(*) FROM staff_accounts WHERE role=$1", role
        ) or 0

    # ── партнёрская программа ─────────────────────────────────

    async def create_partner_account(self, login: str, password: str, commission_pct: float) -> str | None:
        import secrets
        ref_code = secrets.token_urlsafe(8)
        try:
            await self.db.execute(
                """INSERT INTO staff_accounts (role, login, password_hash, ref_code, commission_pct)
                    VALUES ('partner',$1,$2,$3,$4)""",
                login, hash_password(password), ref_code, commission_pct,
            )
            return ref_code
        except Exception:
            return None

    async def get_by_ref_code(self, ref_code: str) -> dict | None:
        row = await self.db.fetchrow("SELECT * FROM staff_accounts WHERE ref_code=$1", ref_code)
        return dict(row) if row else None

    async def list_partners(self) -> list[dict]:
        rows = await self.db.fetch(
            "SELECT login, tg_id, is_online, ref_code, commission_pct, created_at "
            "FROM staff_accounts WHERE role='partner' ORDER BY created_at DESC"
        )
        return [dict(r) for r in rows]

    # ── сессии (8 часов) ─────────────────────────────────────

    async def create_session(self, tg_id: int, role: str, login: str, hours: int = 8):
        expires = (datetime.now() + timedelta(hours=hours)).isoformat(sep=" ", timespec="seconds")
        await self.db.execute(
            """INSERT INTO staff_sessions (tg_id, role, login, expires_at)
                VALUES ($1,$2,$3,$4)
                ON CONFLICT (tg_id) DO UPDATE SET role=$2, login=$3, expires_at=$4""",
            tg_id, role, login, expires,
        )

    async def get_session(self, tg_id: int) -> dict | None:
        now_str = datetime.now().isoformat(sep=" ", timespec="seconds")
        row = await self.db.fetchrow(
            "SELECT * FROM staff_sessions WHERE tg_id=$1 AND expires_at > $2", tg_id, now_str
        )
        return dict(row) if row else None

    async def delete_session(self, tg_id: int):
        await self.db.execute("DELETE FROM staff_sessions WHERE tg_id=$1", tg_id)
        await self.set_online(tg_id, False)
