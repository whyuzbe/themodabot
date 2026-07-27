from db.pool import DB


class WarehouseRepo:
    def __init__(self, db: DB):
        self.db = db

    async def save_report(self, warehouse_tg_id: int, order_id: int | None,
                           title: str, price: str, photo_file_id: str,
                           report_channel_msg_id: int | None = None) -> int:
        return await self.db.fetchval(
            """INSERT INTO warehouse_reports
               (warehouse_tg_id, order_id, title, price, photo_file_id, report_channel_msg_id)
               VALUES ($1,$2,$3,$4,$5,$6) RETURNING id""",
            warehouse_tg_id, order_id, title, price, photo_file_id, report_channel_msg_id,
        )

    async def list_recent(self, limit: int = 50) -> list[dict]:
        rows = await self.db.fetch(
            "SELECT * FROM warehouse_reports ORDER BY created_at DESC LIMIT $1", limit
        )
        return [dict(r) for r in rows]