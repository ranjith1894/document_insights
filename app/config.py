from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Document Insights API"
    MONGODB_URL: str = "mongodb://mongodb:27017"
    MONGODB_DB: str = "document_insights"
    REDIS_URL: str = "redis://redis:6379/0"
    QUEUE_NAME: str = "document_queue"
    CACHE_TTL_SECONDS: int = 3600
    ACTIVE_JOB_LIMIT: int = 3

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()