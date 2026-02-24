import os


class Config:
    # PostgreSQL — prefer explicit env vars from zerops.yml, fallback to auto-injected
    DB_HOST = os.environ.get("DB_HOST", os.environ.get("db_hostname", "localhost"))
    DB_PORT = int(os.environ.get("DB_PORT", os.environ.get("db_port", "5432")))
    DB_USER = os.environ.get("DB_USER", os.environ.get("db_user", "postgres"))
    DB_PASSWORD = os.environ.get("DB_PASS", os.environ.get("db_password", "postgres"))
    DB_DATABASE = os.environ.get("DB_NAME", os.environ.get("db_dbName", "db"))

    @property
    def db_url(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_DATABASE}"

    # Valkey
    VALKEY_HOST = os.environ.get("REDIS_HOST", os.environ.get("redis_hostname", "localhost"))
    VALKEY_PORT = int(os.environ.get("REDIS_PORT", os.environ.get("redis_port", "6379")))
    VALKEY_PASSWORD = os.environ.get("redis_password", None)

    # NATS — prefer NATS_URL from zerops.yml, fallback to auto-injected connection string
    NATS_URL = os.environ.get(
        "NATS_URL",
        os.environ.get(
            "queue_connectionString",
            f"nats://{os.environ.get('queue_user', '')}:{os.environ.get('queue_password', '')}@{os.environ.get('queue_hostname', 'localhost')}:{os.environ.get('queue_port', '4222')}"
        )
    )

    # Object Storage
    S3_ENDPOINT = os.environ.get("S3_ENDPOINT", os.environ.get("storage_apiUrl", "https://localhost"))
    S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", os.environ.get("storage_accessKeyId", ""))
    S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", os.environ.get("storage_secretAccessKey", ""))
    S3_BUCKET = os.environ.get("S3_BUCKET", os.environ.get("storage_bucketName", ""))

    # Processing
    THUMBNAIL_SIZE = int(os.environ.get("THUMBNAIL_SIZE", "400"))
    RESIZED_MAX_DIMENSION = int(os.environ.get("RESIZED_MAX_DIMENSION", "1600"))
    PROCESSING_QUALITY = int(os.environ.get("PROCESSING_QUALITY", "85"))


config = Config()
