from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./ai_news.db"
    crawl_concurrency: int = 5
    crawl_default_interval_minutes: int = 360
    failure_backoff_threshold: int = 3

    class Config:
        env_file = ".env"

settings = Settings()
