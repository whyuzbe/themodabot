from db.pool import DB

# Заказы с этими статусами считаются "состоявшейся покупкой" для статистики партнёра.
# ИСПРАВЛЕНИЕ: добавлены "shipping" и "delivered" — склад переводит заказ в
# "shipping" при отправке (warehouse.py, cb_wh_confirm_ship), а клиент — в
# "delivered" при подтверждении получения (cart.py, cb_myorder_received).
# Без этих статусов заказы временно/навсегда выпадали из подсчёта комиссии.
QUALIFYING_STATUSES = ("confirmed", "warehouse_received", "shipping", "delivered", "completed")


class PartnersRepo:
    def __init__(self, db: DB):
        self.db = db

    async def register_referral(self, partner_login: str, user_tg_id: int) -> bool:
        """
        Привязывает клиента к партнёру. Первый переход по реф-ссылке — навсегда
        (UNIQUE на user_tg_id), повторные попытки молча игнорируются.
        """
        try:
            await self.db.execute(
                "INSERT INTO partner_referrals (partner_login, user_tg_id) VALUES ($1,$2)",
                partner_login, user_tg_id,
            )
            return True
        except Exception:
            return False

    async def get_referral(self, user_tg_id: int) -> dict | None:
        row = await self.db.fetchrow(
            "SELECT * FROM partner_referrals WHERE user_tg_id=$1", user_tg_id
        )
        return dict(row) if row else None

    async def referred_user_ids(self, partner_login: str) -> list[int]:
        rows = await self.db.fetch(
            "SELECT user_tg_id FROM partner_referrals WHERE partner_login=$1", partner_login
        )
        return [r["user_tg_id"] for r in rows]

    async def referral_count(self, partner_login: str) -> int:
        return await self.db.fetchval(
            "SELECT COUNT(*) FROM partner_referrals WHERE partner_login=$1", partner_login
        ) or 0

    async def orders_for_partner(self, partner_login: str) -> list[dict]:
        """Все заказы (с товарами) клиентов, пришедших по ссылке этого партнёра, прошедшие минимум подтверждение."""
        placeholders_status = ",".join(f"'{s}'" for s in QUALIFYING_STATUSES)
        rows = await self.db.fetch(
            f"""SELECT o.id AS order_id, o.user_tg_id, o.status, o.created_at,
                       u.username
                FROM partner_referrals pr
                JOIN orders o ON o.user_tg_id = pr.user_tg_id
                LEFT JOIN users u ON u.tg_id = o.user_tg_id
                WHERE pr.partner_login=$1 AND o.status IN ({placeholders_status})
                ORDER BY o.created_at DESC""",
            partner_login,
        )
        result = []
        for r in rows:
            row = dict(r)
            items = await self.db.fetch(
                "SELECT title, price FROM order_items WHERE order_id=$1", row["order_id"]
            )
            row["items"] = [dict(i) for i in items]
            result.append(row)
        return result

    @staticmethod
    def _parse_price(price: str) -> float:
        try:
            return float(str(price).replace("$", "").replace(",", ".").strip())
        except Exception:
            return 0.0

    async def stats(self, partner_login: str, commission_pct: float) -> dict:
        total_referrals = await self.referral_count(partner_login)
        orders = await self.orders_for_partner(partner_login)
        buyers = {o["user_tg_id"] for o in orders}
        total_revenue = 0.0
        for o in orders:
            for it in o["items"]:
                total_revenue += self._parse_price(it.get("price", ""))
        commission_earned = round(total_revenue * commission_pct / 100, 2)
        return {
            "total_referrals": total_referrals,
            "buyers_count": len(buyers),
            "orders_count": len(orders),
            "total_revenue": round(total_revenue, 2),
            "commission_earned": commission_earned,
        }
