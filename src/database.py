import psycopg
from config import config
import structlog

log = structlog.get_logger()


class Database:
    def __init__(self, conn):
        self.conn = conn

    @classmethod
    async def create(cls):
        conn = await psycopg.AsyncConnection.connect(config.db_url, autocommit=True)
        log.info("db.connected")
        return cls(conn)

    async def update_processing(self, upload_id: str):
        await self.conn.execute(
            "UPDATE uploads SET status = 'processing', processing_started_at = NOW() WHERE id = %s",
            (upload_id,),
        )

    async def update_processed(self, upload_id: str, data: dict):
        await self.conn.execute(
            """
            UPDATE uploads SET
                status = 'processed',
                thumbnail_key = %(thumbnail_key)s,
                resized_key = %(resized_key)s,
                width = %(width)s,
                height = %(height)s,
                format = %(format)s,
                exif_data = %(exif_data)s,
                dominant_color = %(dominant_color)s,
                size_thumbnail = %(size_thumbnail)s,
                size_resized = %(size_resized)s,
                processing_duration_ms = %(processing_duration_ms)s,
                processed_at = NOW()
            WHERE id = %(id)s
            """,
            {**data, "id": upload_id, "exif_data": psycopg.types.json.Json(data.get("exif_data"))},
        )

    async def update_error(self, upload_id: str, error: str):
        await self.conn.execute(
            "UPDATE uploads SET status = 'error', error_message = %s WHERE id = %s",
            (error, upload_id),
        )
