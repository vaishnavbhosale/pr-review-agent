from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    GITHUB_TOKEN: str
    GITHUB_WEBHOOK_SECRET: str
    GROQ_API_KEY: str
    GEMINI_API_KEY: str

    DATABASE_URL: str = "sqlite:///./reviews.db"
    LOG_LEVEL: str = "INFO"
    AGENTIC_MODE: bool = False
    MAX_DIFF_LINES_PER_FILE: int = 1000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()