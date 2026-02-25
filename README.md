# Showcase Recipe Worker

<!-- #ZEROPS_EXTRACT_START:intro# -->
Asynchronous image processing worker built with [Python](https://python.org) and [Pillow](https://python-pillow.org), listening for upload events via NATS message queue, generating thumbnails and resized WebP images, and persisting results to PostgreSQL, Valkey, and S3-compatible storage on [Zerops](https://zerops.io).
Used within [Showcase Recipe](https://app.zerops.io/recipes/showcase-recipe) for [Zerops](https://zerops.io) platform.
<!-- #ZEROPS_EXTRACT_END:intro# -->

⬇️ **Full recipe page and deploy with one-click**

[![Deploy on Zerops](https://github.com/zeropsio/recipe-shared-assets/blob/main/deploy-button/light/deploy-button.svg)](https://app.zerops.io/recipes/showcase-recipe?environment=small-production)

## Integration Guide

<!-- #ZEROPS_EXTRACT_START:integration-guide# -->

### 1. Adding `zerops.yaml`
The main application configuration file you place at the root of your repository, it tells Zerops how to build, deploy and run your application.

```yaml
zerops:
  # Production setup — deploy source and install dependencies at runtime.
  # Python is interpreted, so no compilation step is needed in buildCommands.
  - setup: prod
    build:
      # Deploy entire source tree — Python runs directly from source
      deploy: ./
      # Ensures requirements.txt is available during run.prepareCommands
      addToRunPrepare: requirements.txt

    run:
      base: python@3.12

      # Install Python packages into the runtime container image.
      # prepareCommands run once per container creation and are cached,
      # unlike initCommands which run on every restart.
      prepareCommands:
        - pip install -r requirements.txt

      envVariables:
        # Database — references auto-generated variables from the 'db' service hostname
        DB_HOST: ${db_hostname}
        DB_PORT: ${db_port}
        DB_USER: ${db_user}
        DB_PASS: ${db_password}
        DB_NAME: ${db_dbName}
        # Valkey cache — referenced by 'redis' service hostname
        REDIS_HOST: ${redis_hostname}
        REDIS_PORT: ${redis_port}
        # NATS connection string — single URI with embedded credentials
        NATS_URL: ${queue_connectionString}
        # S3-compatible object storage — referenced by 'storage' service hostname
        S3_ENDPOINT: ${storage_apiUrl}
        S3_ACCESS_KEY: ${storage_accessKeyId}
        S3_SECRET_KEY: ${storage_secretAccessKey}
        S3_BUCKET: ${storage_bucketName}

      start: python src/main.py

  # Development setup — deploy full source for live editing via SSH.
  # The developer SSHs in and starts the worker manually.
  - setup: dev
    build:
      deploy: ./
      addToRunPrepare: requirements.txt

    run:
      base: python@3.12
      prepareCommands:
        - pip install -r requirements.txt
      # Container stays idle — developer starts worker manually via SSH
      start: zsc noop --silent
```

<!-- #ZEROPS_EXTRACT_END:integration-guide# -->
