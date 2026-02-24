import json
import time
from nats.aio.client import Client as NATS
import structlog

log = structlog.get_logger()


class EventPublisher:
    def __init__(self, nc: NATS):
        self.nc = nc

    async def publish_step(
        self,
        upload_id: str,
        step: str,
        detail: str,
        duration_ms: int,
        active_nodes: list[str] | None = None,
        active_edges: list[str] | None = None,
        edge_labels: dict[str, str] | None = None,
    ):
        payload = {
            "id": upload_id,
            "step": step,
            "detail": detail,
            "durationMs": duration_ms,
            "timestamp": int(time.time() * 1000),
            "activeNodes": active_nodes or [],
            "activeEdges": active_edges or [],
            "edgeLabels": edge_labels or {},
        }
        await self.nc.publish("pipeline.step", json.dumps(payload).encode())

    async def publish_processed(self, upload_id: str, data: dict):
        payload = {
            "id": upload_id,
            **data,
            "timestamp": int(time.time() * 1000),
        }
        await self.nc.publish("pipeline.processed", json.dumps(payload).encode())
        log.info("nats.published", subject="pipeline.processed", id=upload_id)

    async def publish_error(self, upload_id: str, error: str, step: str):
        payload = {
            "id": upload_id,
            "error": error,
            "step": step,
            "timestamp": int(time.time() * 1000),
        }
        await self.nc.publish("pipeline.error", json.dumps(payload).encode())
        log.info("nats.published", subject="pipeline.error", id=upload_id)
