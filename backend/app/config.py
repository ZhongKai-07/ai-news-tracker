from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./ai_news.db"
    crawl_concurrency: int = 5
    crawl_default_interval_minutes: int = 360
    failure_backoff_threshold: int = 3

    # LLM service
    llm_provider: str = "openai_compatible"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_tier1_model: str = "qwen-turbo"
    llm_tier2_model: str = "qwen-plus"
    llm_tier3_model: str = "qwen-max"
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2
    llm_batch_size: int = 20
    llm_circuit_breaker_threshold: int = 5
    llm_process_interval_minutes: int = 10

    class Config:
        env_file = ".env"

settings = Settings()
