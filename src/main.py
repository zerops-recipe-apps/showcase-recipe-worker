import asyncio
import json
import signal
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import nats
from nats.aio.client import Client as NATS
import structlog

from config import config
from processor import ImageProcessor
from storage import S3Storage
from database import Database
from cache import Cache
from events import EventPublisher

log = structlog.get_logger()


async def main():
    log.info("worker.starting", nats_url=config.NATS_URL.replace(config.DB_PASSWORD, "***") if config.DB_PASSWORD in config.NATS_URL else config.NATS_URL)

    # Initialize clients
    nc = await nats.connect(
        servers=[config.NATS_URL],
        name="pipeline-worker",
        reconnect_time_wait=2,
        max_reconnect_attempts=-1,
    )
    log.info("nats.connected")

    storage = S3Storage()
    db = await Database.create()
    cache = Cache()
    publisher = EventPublisher(nc)
    processor = ImageProcessor()

    log.info("services.connected")

    # Subscribe to uploaded events
    sub = await nc.subscribe("pipeline.uploaded")
    log.info("nats.subscribed", subject="pipeline.uploaded")

    async for msg in sub.messages:
        try:
            event = json.loads(msg.data.decode())
            upload_id = event["id"]
            log.info("job.received", id=upload_id, filename=event["filename"])

            await process_upload(
                event, nc, storage, db, cache, publisher, processor
            )

        except Exception as e:
            log.error("job.failed", error=str(e), exc_info=True)
            try:
                error_id = json.loads(msg.data.decode()).get("id", "unknown")
                await publisher.publish_error(error_id, str(e), "unknown")
                await db.update_error(error_id, str(e))
            except Exception:
                pass


async def process_upload(
    event: dict,
    nc: NATS,
    storage: S3Storage,
    db: Database,
    cache: Cache,
    publisher: EventPublisher,
    processor: ImageProcessor,
):
    upload_id = event["id"]
    start_time = asyncio.get_event_loop().time()
    pace = config.STEP_PACE_MS / 1000  # seconds between steps

    try:
        # Step 1: Mark as processing
        await db.update_processing(upload_id)

        # Step 2: Download original from Object Storage
        step_start = asyncio.get_event_loop().time()

        await publisher.publish_step(upload_id, "downloading", "Downloading original from Object Storage", 0,
            active_nodes=["worker", "storage"],
            active_edges=["nats-worker", "worker-storage"],
            edge_labels={"nats-worker": "pipeline.uploaded", "worker-storage": f"GET {event['originalKey']}"})

        original_bytes = await storage.download(event["originalKey"])
        dl_duration = int((asyncio.get_event_loop().time() - step_start) * 1000)

        await publisher.publish_step(upload_id, "downloading", f"Downloaded original ({len(original_bytes)} bytes)", dl_duration,
            active_nodes=["worker"],
            active_edges=["worker-storage"],
            edge_labels={"worker-storage": f"GET complete ({dl_duration}ms)"})

        log.info("step.download_complete", id=upload_id, size=len(original_bytes), duration_ms=dl_duration)
        await asyncio.sleep(pace)

        # Step 3: Generate thumbnail
        step_start = asyncio.get_event_loop().time()

        await publisher.publish_step(upload_id, "thumbnail", f"Generating {config.THUMBNAIL_SIZE}x{config.THUMBNAIL_SIZE} thumbnail", 0,
            active_nodes=["worker"],
            active_edges=[],
            edge_labels={})

        thumbnail_bytes, thumb_info = processor.create_thumbnail(original_bytes, config.THUMBNAIL_SIZE)
        thumb_duration = int((asyncio.get_event_loop().time() - step_start) * 1000)

        await publisher.publish_step(upload_id, "thumbnail", f"Thumbnail generated ({len(thumbnail_bytes)} bytes, {thumb_duration}ms)", thumb_duration,
            active_nodes=["worker"],
            active_edges=[],
            edge_labels={})

        log.info("step.thumbnail_complete", id=upload_id, size=len(thumbnail_bytes), duration_ms=thumb_duration)
        await asyncio.sleep(pace)

        # Step 4: Generate resized version
        step_start = asyncio.get_event_loop().time()

        await publisher.publish_step(upload_id, "resizing", f"Resizing to max {config.RESIZED_MAX_DIMENSION}px", 0,
            active_nodes=["worker"],
            active_edges=[],
            edge_labels={})

        resized_bytes, resize_info = processor.create_resized(original_bytes, config.RESIZED_MAX_DIMENSION)
        resize_duration = int((asyncio.get_event_loop().time() - step_start) * 1000)

        log.info("step.resize_complete", id=upload_id, size=len(resized_bytes), duration_ms=resize_duration)
        await asyncio.sleep(pace)

        # Step 5: Extract metadata
        step_start = asyncio.get_event_loop().time()

        await publisher.publish_step(upload_id, "metadata", "Extracting EXIF and color data", 0,
            active_nodes=["worker"],
            active_edges=[],
            edge_labels={})

        metadata = processor.extract_metadata(original_bytes)
        meta_duration = int((asyncio.get_event_loop().time() - step_start) * 1000)

        log.info("step.metadata_complete", id=upload_id, width=metadata["width"], height=metadata["height"], duration_ms=meta_duration)
        await asyncio.sleep(pace)

        # Step 6: Upload processed files to Object Storage
        step_start = asyncio.get_event_loop().time()
        thumbnail_key = f"thumbnails/{upload_id}.webp"
        resized_key = f"resized/{upload_id}.webp"

        await publisher.publish_step(upload_id, "storing", "Uploading thumbnail and resized to Object Storage", 0,
            active_nodes=["worker", "storage"],
            active_edges=["worker-storage"],
            edge_labels={"worker-storage": "PUT thumbnail + resized"})

        await storage.upload(thumbnail_key, thumbnail_bytes, "image/webp")
        await storage.upload(resized_key, resized_bytes, "image/webp")
        store_duration = int((asyncio.get_event_loop().time() - step_start) * 1000)

        log.info("step.store_complete", id=upload_id, duration_ms=store_duration)
        await asyncio.sleep(pace)

        # Step 7: Update Postgres + Valkey
        step_start = asyncio.get_event_loop().time()
        total_duration = int((asyncio.get_event_loop().time() - start_time) * 1000)

        await publisher.publish_step(upload_id, "finalizing", "Updating database and cache", 0,
            active_nodes=["worker", "db", "valkey"],
            active_edges=["worker-db", "worker-valkey"],
            edge_labels={"worker-db": "UPDATE processed", "worker-valkey": "SET cache"})

        await db.update_processed(upload_id, {
            "thumbnail_key": thumbnail_key,
            "resized_key": resized_key,
            "width": metadata["width"],
            "height": metadata["height"],
            "format": metadata["format"],
            "exif_data": metadata.get("exif"),
            "dominant_color": metadata["dominant_color"],
            "size_thumbnail": len(thumbnail_bytes),
            "size_resized": len(resized_bytes),
            "processing_duration_ms": total_duration,
        })

        # Cache the result in Valkey
        await cache.set_processed(upload_id, {
            "id": upload_id,
            "thumbnail_key": thumbnail_key,
            "resized_key": resized_key,
            "metadata": metadata,
            "processing_duration_ms": total_duration,
        })

        finalize_duration = int((asyncio.get_event_loop().time() - step_start) * 1000)

        # Step 8: Publish completion
        await publisher.publish_processed(upload_id, {
            "originalKey": event["originalKey"],
            "thumbnailKey": thumbnail_key,
            "resizedKey": resized_key,
            "metadata": {
                "width": metadata["width"],
                "height": metadata["height"],
                "format": metadata["format"],
                "exif": metadata.get("exif"),
                "dominantColor": metadata["dominant_color"],
                "sizeOriginal": event["sizeBytes"],
                "sizeThumbnail": len(thumbnail_bytes),
                "sizeResized": len(resized_bytes),
            },
            "totalDurationMs": total_duration,
        })

        log.info("job.complete", id=upload_id, total_duration_ms=total_duration)

    except Exception as e:
        log.error("job.error", id=upload_id, error=str(e), exc_info=True)
        await publisher.publish_error(upload_id, str(e), "processing")
        await db.update_error(upload_id, str(e))


if __name__ == "__main__":
    loop = asyncio.new_event_loop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: loop.stop())

    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
        log.info("worker.shutdown")
