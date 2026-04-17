# showcase-recipe-worker

Async image-processing worker companion to `showcase-recipe-app` — subscribes to NATS `pipeline.uploaded`, generates thumbnails and WebP resizes via Pillow, and persists results to PostgreSQL, Valkey, and S3.

## Zerops service facts

- HTTP port: none (background worker — no `ports:` block)
- Siblings:
  - `db` (PostgreSQL) — env: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS`, `DB_NAME`
  - `redis` (Valkey) — env: `REDIS_HOST`, `REDIS_PORT`
  - `queue` (NATS) — env: `NATS_URL` (connection string)
  - `storage` (S3-compatible) — env: `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET`
- Runtime base: `python@3.12`

## Zerops dev

`setup: dev` idles on `zsc noop --silent`; the agent starts the worker process.

- Dev command: `python src/main.py`

**All platform operations (start/stop/status/logs of the worker, deploy, env / scaling / storage) go through the Zerops development workflow via `zcp` MCP tools. Don't shell out to `zcli`.**

## Notes

- Background worker, not an HTTP service — no `ports:`, no `readinessCheck`, no `healthCheck`. The L7 balancer never routes traffic here; it is reachable only over SSH / internal NATS.
- Requirements install via `prepareCommands` (`pip install -r requirements.txt`) and are baked into the runtime image — not re-run on container restart.
- Companion to `showcase-recipe-app`: consumes `pipeline.uploaded`, publishes `pipeline.processed` or error events back to NATS. Pipeline is download original → thumbnail → resize → extract EXIF/color → upload WebP variants → update DB + Valkey → publish completion.
