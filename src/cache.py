import json
import redis.asyncio as redis
from config import config
import structlog

log = structlog.get_logger()


class Cache:
    def __init__(self):
        self.client = redis.Redis(
            host=config.VALKEY_HOST,
            port=config.VALKEY_PORT,
            password=config.VALKEY_PASSWORD,
            decode_responses=True,
        )

    async def set_processed(self, upload_id: str, data: dict):
        await self.client.setex(f"upload:{upload_id}", 3600, json.dumps(data))
        log.info("cache.set", key=f"upload:{upload_id}")

    async def get_processed(self, upload_id: str) -> dict | None:
        raw = await self.client.get(f"upload:{upload_id}")
        return json.loads(raw) if raw else None
