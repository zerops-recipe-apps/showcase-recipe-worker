import psycopg
from psycopg_pool import AsyncConnectionPool
from config import config
import structlog

log = structlog.get_logger()


class Database:
    """PostgreSQL access through a small connection pool.

    A single long-lived connection is not safe against a PostgreSQL HA
    cluster: on failover (or when the primary container is replaced) the
    socket is closed server-side and every later query raises
    "the connection is closed". The pool checks each connection before
    handing it out, replaces dead ones, and reconnects in the background.
    """

    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool

    @classmethod
    async def create(cls):
        pool = AsyncConnectionPool(
            conninfo=config.db_url,
            min_size=1,
            max_size=4,
            kwargs={"autocommit": True},
            # Ping each connection before use; broken ones are discarded.
            check=AsyncConnectionPool.check_connection,
            # Recycle connections periodically so none outlive a topology change.
            max_lifetime=600,
            max_idle=120,
            open=False,
        )
        await pool.open(wait=True, timeout=30)
        log.info("db.connected", pool_max=pool.max_size)
        return cls(pool)

    async def close(self):
        await self.pool.close()

    async def _execute(self, query: str, params=None):
        # One retry covers a connection that dies between the check and the
        # query (e.g. mid-failover); the retry gets a fresh connection.
        for attempt in (1, 2):
            try:
                async with self.pool.connection() as conn:
                    await conn.execute(query, params)
                return
            except psycopg.OperationalError as e:
                if attempt == 2:
                    raise
                log.warning("db.retry", error=str(e))

    async def update_processing(self, upload_id: str):
        await self._execute(
            "UPDATE uploads SET status = 'processing', processing_started_at = NOW() WHERE id = %s",
            (upload_id,),
        )

    async def update_processed(self, upload_id: str, data: dict):
        await self._execute(
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
        await self._execute(
            "UPDATE uploads SET status = 'error', error_message = %s WHERE id = %s",
            (error, upload_id),
        )
